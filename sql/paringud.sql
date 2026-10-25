-- Elektrihinna analüüsi SQL-päringud (SQLite).
-- Tabel: hinnad(aeg TEXT, kuupaev TEXT, tund INTEGER, hind REAL)
--   aeg     = kohalik aeg 'YYYY-MM-DD HH:MM:SS'
--   hind    = Eesti börsihind, EUR/MWh
-- Iga päring algab reaga "-- ### nimi", Python-skript loeb need sealt.


-- ### kuu_kokkuvote
-- Kuu keskmine, miinimum, maksimum ja tundide arv (GROUP BY).
SELECT
    strftime('%Y-%m', aeg)      AS kuu,
    ROUND(AVG(hind), 2)         AS keskmine,
    ROUND(MIN(hind), 2)         AS miinimum,
    ROUND(MAX(hind), 2)         AS maksimum,
    COUNT(*)                    AS tunde
FROM hinnad
GROUP BY kuu
ORDER BY kuu;


-- ### kallimad_tunnid
-- Kümme kõige kallimat tundi kogu perioodil (ORDER BY + LIMIT).
SELECT aeg, ROUND(hind, 2) AS hind
FROM hinnad
ORDER BY hind DESC
LIMIT 10;


-- ### tunniprofiil
-- Keskmine hind kellaaja järgi: millal on elekter kõige kallim ja odavam.
SELECT
    tund,
    ROUND(AVG(hind), 2) AS keskmine_hind
FROM hinnad
GROUP BY tund
ORDER BY tund;


-- ### paeva_kikkumine
-- Päevad, kus hind kõikus kõige rohkem (CTE: esmalt päevaagregaat).
WITH paev AS (
    SELECT
        kuupaev,
        AVG(hind) AS keskmine,
        MIN(hind) AS miinimum,
        MAX(hind) AS maksimum
    FROM hinnad
    GROUP BY kuupaev
)
SELECT
    kuupaev,
    ROUND(keskmine, 2)            AS keskmine,
    ROUND(miinimum, 2)            AS miinimum,
    ROUND(maksimum, 2)            AS maksimum,
    ROUND(maksimum - miinimum, 2) AS kikkumine
FROM paev
ORDER BY kikkumine DESC
LIMIT 10;


-- ### liikuv_keskmine_7p
-- Päeva keskmine hind ja 7 päeva liikuv keskmine (akenfunktsioon).
WITH paev AS (
    SELECT kuupaev, AVG(hind) AS keskmine
    FROM hinnad
    GROUP BY kuupaev
)
SELECT
    kuupaev,
    ROUND(keskmine, 2) AS paeva_keskmine,
    ROUND(AVG(keskmine) OVER (
        ORDER BY kuupaev
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS liikuv_keskmine_7p
FROM paev
ORDER BY kuupaev;


-- ### kuu_muutus
-- Kuu keskmine ja muutus võrreldes eelmise kuuga protsentides (LAG).
WITH kuu AS (
    SELECT strftime('%Y-%m', aeg) AS kuu, AVG(hind) AS keskmine
    FROM hinnad
    GROUP BY kuu
)
SELECT
    kuu,
    ROUND(keskmine, 2) AS keskmine,
    ROUND(
        (keskmine - LAG(keskmine) OVER (ORDER BY kuu))
        / NULLIF(LAG(keskmine) OVER (ORDER BY kuu), 0) * 100,
        1
    ) AS muutus_eelmise_kuuga_protsenti
FROM kuu
ORDER BY kuu;

-- ### tunniprofiil_aastaaeg
-- Keskmine hind kellaaja järgi igal aastaajal (talv = dets–veebr, kevad = märts–mai,
-- suvi = juuni–aug, sügis = sept–nov). Kontrollib hüpoteesi päikeseenergia mõjust päevasele hinnale.
WITH tunnid AS (
    SELECT
        tund,
        CAST(strftime('%m', aeg) AS INTEGER) AS kuu,
        hind
    FROM hinnad
)
SELECT
    tund,
    ROUND(AVG(CASE WHEN kuu IN (12, 1, 2)  THEN hind END), 2) AS talv,
    ROUND(AVG(CASE WHEN kuu IN (3, 4, 5)   THEN hind END), 2) AS kevad,
    ROUND(AVG(CASE WHEN kuu IN (6, 7, 8)   THEN hind END), 2) AS suvi,
    ROUND(AVG(CASE WHEN kuu IN (9, 10, 11) THEN hind END), 2) AS sygis
FROM tunnid
GROUP BY tund
ORDER BY tund;