"""Samm 1: laeb Eesti elektri börsihinna Eleringi avalikust API-st ja salvestab CSV-na.

Andmeallikas: Elering Dashboard (Nord Pooli Eesti piirkonna hind, EUR/MWh).
Käivitamine:  python src/01_lae_andmed.py
"""
from pathlib import Path

import pandas as pd
import requests

API = "https://dashboard.elering.ee/api/nps/price"
PIIRKOND = "ee"
ALGUS = "2024-01-01"      # esimene päev (kaasa arvatud)
LOPP = "2025-12-31"       # viimane päev (kaasa arvatud)

VÄLJUND = Path(__file__).resolve().parent.parent / "data" / "elektrihind_ee.csv"


def kuu_vahemikud(algus: str, lopp: str):
    """Jagab perioodi kuudeks, et päringud oleksid väiksed."""
    algus_ts = pd.Timestamp(algus, tz="Europe/Tallinn")
    lopp_ts = pd.Timestamp(lopp, tz="Europe/Tallinn") + pd.Timedelta(days=1)  # välistav ots
    kuu_algused = pd.date_range(algus_ts, lopp_ts, freq="MS", inclusive="left")
    if len(kuu_algused) == 0 or kuu_algused[0] != algus_ts:
        kuu_algused = kuu_algused.insert(0, algus_ts)
    for i, s in enumerate(kuu_algused):
        e = kuu_algused[i + 1] if i + 1 < len(kuu_algused) else lopp_ts
        if s < lopp_ts:
            yield s, min(e, lopp_ts)


def lae_vahemik(s: pd.Timestamp, e: pd.Timestamp) -> list[dict]:
    vorming = "%Y-%m-%dT%H:%M:%S.000Z"
    s_utc, e_utc = s.tz_convert("UTC"), e.tz_convert("UTC")
    vastus = requests.get(
        API,
        params={"start": s_utc.strftime(vorming), "end": e_utc.strftime(vorming)},
        timeout=30,
    )
    vastus.raise_for_status()
    sisu = vastus.json()
    if not sisu.get("success"):
        raise RuntimeError(f"API ei andnud edukat vastust: {sisu}")
    return sisu["data"].get(PIIRKOND, [])


def main() -> None:
    read = []
    for s, e in kuu_vahemikud(ALGUS, LOPP):
        print(f"Laen {s:%Y-%m-%d} … {e:%Y-%m-%d}")
        read.extend(lae_vahemik(s, e))

    if not read:
        raise SystemExit("Andmeid ei tulnud. Kontrolli ajavahemikku ja internetiühendust.")

    df = pd.DataFrame(read).drop_duplicates("timestamp").sort_values("timestamp")
    df["aeg"] = (
        pd.to_datetime(df["timestamp"], unit="s", utc=True)
        .dt.tz_convert("Europe/Tallinn")
    )

    # Alates 2025. aasta oktoobrist on päev-ette hind 15-minutiline, varem tunnine.
    # Viime kõik ühtlaseks tunnihinnaks (tunni keskmine).
    tunnid = (
        df.set_index("aeg")["price"]
        .resample("h")
        .mean()
        .dropna()
        .rename("hind_eur_mwh")
        .reset_index()
    )
    tunnid["aeg"] = tunnid["aeg"].dt.tz_localize(None)  # kohalik aeg, ilma ajavööndita

    # API vahemiku ots on kaasatud, lõika üleliigne ära: jäta alles ainult ALGUS … LOPP
    tunnid = tunnid[
        (tunnid["aeg"] >= pd.Timestamp(ALGUS))
        & (tunnid["aeg"] < pd.Timestamp(LOPP) + pd.Timedelta(days=1))
    ]

    VÄLJUND.parent.mkdir(parents=True, exist_ok=True)
    tunnid.to_csv(VÄLJUND, index=False)
    print(f"Salvestatud {len(tunnid):,} tunnihinda faili {VÄLJUND}")


if __name__ == "__main__":
    main()
