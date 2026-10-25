"""Samm 2: SQL-päringud ja Pythoni analüüs elektrihinna andmetel.

Käivitamine:  python src/02_analuus.py
Eeldus:       andmed on laetud (python src/01_lae_andmed.py)
"""
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # joonistab faili, ei vaja akent
import matplotlib.pyplot as plt
import pandas as pd

JUUR = Path(__file__).resolve().parent.parent
CSV = JUUR / "data" / "elektrihind_ee.csv"
SQL_FAIL = JUUR / "sql" / "paringud.sql"
TULEMUSED = JUUR / "results"


def salvesta_csv(df: pd.DataFrame, fail: Path, **kwargs) -> None:
    """Salvestab CSV. Kui fail on mõnes programmis (nt Excelis) avatud, annab selge teate ja jätkab."""
    try:
        df.to_csv(fail, **kwargs)
    except PermissionError:
        print(f"HOIATUS: faili {fail.name} ei saanud salvestada. Sulge see (nt Excelis) ja käivita uuesti.")


def salvesta_pilt(fig, fail: Path, **kwargs) -> None:
    """Salvestab graafiku. Kui fail on avatud, annab selge teate ja jätkab."""
    try:
        fig.savefig(fail, **kwargs)
    except (PermissionError, OSError):
        print(f"HOIATUS: pilti {fail.name} ei saanud salvestada. Sulge see (nt pildivaates) ja käivita uuesti.")


def lae_andmed() -> pd.DataFrame:
    if not CSV.exists():
        raise SystemExit(f"Faili {CSV} ei ole. Käivita kõigepealt: python src/01_lae_andmed.py")
    df = pd.read_csv(CSV, parse_dates=["aeg"])
    df["kuupaev"] = df["aeg"].dt.strftime("%Y-%m-%d")
    df["tund"] = df["aeg"].dt.hour
    df["aeg"] = df["aeg"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df.rename(columns={"hind_eur_mwh": "hind"})[["aeg", "kuupaev", "tund", "hind"]]


def loe_paringud(fail: Path) -> dict[str, str]:
    """Tükeldab SQL-faili päringuteks reamärgendi '-- ### nimi' järgi."""
    paringud: dict[str, str] = {}
    nimi, read = None, []
    for rida in fail.read_text(encoding="utf-8").splitlines():
        if rida.startswith("-- ### "):
            if nimi:
                paringud[nimi] = "\n".join(read).strip()
            nimi, read = rida[7:].strip(), []
        elif nimi:
            read.append(rida)
    if nimi:
        paringud[nimi] = "\n".join(read).strip()
    return paringud


def joonista(tulemused: dict[str, pd.DataFrame]) -> None:
    # 1) Kuu keskmine ja min–max vahemik
    k = tulemused["kuu_kokkuvote"]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(k["kuu"], k["miinimum"], k["maksimum"], alpha=0.2, label="Min–max")
    ax.plot(k["kuu"], k["keskmine"], marker="o", label="Kuu keskmine")
    ax.set_title("Eesti elektri börsihind kuude lõikes")
    ax.set_ylabel("EUR/MWh")
    ax.tick_params(axis="x", rotation=60)
    ax.legend()
    fig.text(0.01, 0.01, "Allikas: Elering / Nord Pool", fontsize=8)
    fig.tight_layout()
    salvesta_pilt(fig, TULEMUSED / "kuu_keskmine.png", dpi=150)
    plt.close(fig)

    # 2) Tunniprofiil
    t = tulemused["tunniprofiil"]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(t["tund"], t["keskmine_hind"])
    ax.set_title("Keskmine hind kellaaja järgi")
    ax.set_xlabel("Tund (kohalik aeg)")
    ax.set_ylabel("EUR/MWh")
    ax.set_xticks(range(0, 24))
    fig.text(0.01, 0.01, "Allikas: Elering / Nord Pool", fontsize=8)
    fig.tight_layout()
    salvesta_pilt(fig, TULEMUSED / "tunniprofiil.png", dpi=150)
    plt.close(fig)

    # 3) Päeva keskmine ja 7 päeva liikuv keskmine
    p = tulemused["liikuv_keskmine_7p"].copy()
    p["kuupaev"] = pd.to_datetime(p["kuupaev"])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(p["kuupaev"], p["paeva_keskmine"], alpha=0.35, label="Päeva keskmine")
    ax.plot(p["kuupaev"], p["liikuv_keskmine_7p"], label="7 päeva liikuv keskmine")
    ax.set_title("Päevahind ja 7 päeva liikuv keskmine")
    ax.set_ylabel("EUR/MWh")
    ax.legend()
    fig.text(0.01, 0.01, "Allikas: Elering / Nord Pool", fontsize=8)
    fig.tight_layout()
    salvesta_pilt(fig, TULEMUSED / "liikuv_keskmine.png", dpi=150)
    plt.close(fig)

    # 4) Tunniprofiil aastaaegade kaupa
    if "tunniprofiil_aastaaeg" in tulemused:
        a = tulemused["tunniprofiil_aastaaeg"]
        fig, ax = plt.subplots(figsize=(10, 5))
        for veerg, silt in [("talv", "Talv"), ("kevad", "Kevad"), ("suvi", "Suvi"), ("sygis", "Sügis")]:
            ax.plot(a["tund"], a[veerg], marker="o", markersize=3, label=silt)
        ax.set_title("Keskmine hind kellaaja järgi aastaaegade kaupa")
        ax.set_xlabel("Tund (kohalik aeg)")
        ax.set_ylabel("EUR/MWh")
        ax.set_xticks(range(0, 24))
        ax.legend()
        fig.text(0.01, 0.01, "Allikas: Elering / Nord Pool", fontsize=8)
        fig.tight_layout()
        salvesta_pilt(fig, TULEMUSED / "tunniprofiil_aastaaeg.png", dpi=150)
        plt.close(fig)


def riskinaitajad(df: pd.DataFrame) -> pd.DataFrame:
    """Kuu kaupa: keskmine, standardhälve (volatiilsus) ja 95. protsentiil."""
    kuu = df["aeg"].str[:7].rename("kuu")
    g = df.groupby(kuu)["hind"]
    tulemus = pd.DataFrame(
        {
            "keskmine": g.mean(),
            "standardhalve": g.std(),
            "p95": g.quantile(0.95),
            "negatiivseid_tunde": df["hind"].lt(0).groupby(kuu).sum(),
        }
    ).round(2)
    tulemus["variatsioonikordaja"] = (tulemus["standardhalve"] / tulemus["keskmine"]).round(2)
    return tulemus


def main() -> None:
    TULEMUSED.mkdir(exist_ok=True)
    df = lae_andmed()
    print(f"Andmeid: {len(df):,} tundi, {df['kuupaev'].min()} … {df['kuupaev'].max()}")

    # --- SQL ---
    with sqlite3.connect(":memory:") as con:
        df.to_sql("hinnad", con, index=False)
        tulemused = {}
        for nimi, paring in loe_paringud(SQL_FAIL).items():
            tulemused[nimi] = pd.read_sql_query(paring, con)
            salvesta_csv(tulemused[nimi], TULEMUSED / f"sql_{nimi}.csv", index=False)
            print(f"\n== {nimi} ==")
            print(tulemused[nimi].head(10).to_string(index=False))

    # --- Python/pandas ---
    risk = riskinaitajad(df)
    salvesta_csv(risk, TULEMUSED / "kuu_riskinaitajad.csv")
    print("\n== kuu_riskinaitajad ==")
    print(risk.to_string())

    joonista(tulemused)
    print(f"\nGraafikud ja tabelid salvestatud kausta {TULEMUSED}")


if __name__ == "__main__":
    main()
