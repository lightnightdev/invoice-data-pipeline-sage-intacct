import logging

import pandas as pd
from core.db import db_b_engine
from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)


def pull_main_charge(team_ids: list[str], year: int, month: int) -> pd.DataFrame:
    if not team_ids:
        logger.info("Did not receive team_ids; returning empty results.")
        return pd.DataFrame()

    main_charge_qry = text("""
WITH 
BaseTeams AS (
    SELECT DISTINCT 
        t.TeamId, 
        t.Name, 
        pr.[Month], 
        pr.[Year]
    FROM dbo.C_PRs pr
    JOIN dbo.Teams t ON pr.TeamId = t.TeamId
    WHERE pr.[Year] = :year
        AND pr.[Month] = :month
        AND pr.TeamId in :team_ids
),
RPAPs AS(
    select rp.Id,
        ROUND(SUM(
            isnull(pretp.AP, 0) + isnull(posttp.AP, 0)
        ),2) AS APSum
    from dbo.RPs AS rp
        LEFT JOIN dbo.C_PRUSPRTItems as pretp on rp.Id = pretp.RPId
        LEFT JOIN dbo.C_PRUSPSTItems AS posttp on rp.Id = posttp.RPId
    where rp.ItemType != 3
        AND ISNULL(rp.PayTypeId, 0) != 1
    GROUP BY rp.Id
),
RPs AS (
    SELECT
        pr.TeamId,
        ROUND(SUM(COALESCE(rp.ItemCST, 0)) + SUM(COALESCE(rp.Adjustment, 0)), 2) AS Amount,
        ROUND(SUM(rpar.APSum),2) AS APs
    FROM dbo.C_PRUSs AS main_charge
    JOIN dbo.C_PRs AS pr ON main_charge.C_PRId = pr.Id
    JOIN dbo.RPs AS rp ON main_charge.Id = rp.C_PRUSId
    JOIN RPAPs AS rpar on rp.Id = rpar.Id
    WHERE pr.[Year] = :year
        AND pr.[Month] = :month
        AND pr.TeamId in :team_ids
        AND main_charge.ProductReimbursement IS NOT NULL
        AND rp.ItemType != 3
        AND COALESCE(rp.PayTypeId, 0) != 1
    GROUP BY pr.TeamId
),
PSTItems AS (
    SELECT
        pr.TeamId,
        ROUND(SUM(COALESCE(ptp.CSTWithCredits, 0) - COALESCE(ptp.AP, 0)), 2) AS Amount
    FROM dbo.C_PRUSs main_charge
    JOIN dbo.C_PRs pr ON main_charge.C_PRId = pr.Id
    LEFT JOIN dbo.C_PRUSPSTItems ptp ON ptp.C_PRUSId = main_charge.Id
        AND ptp.ItemType NOT IN (0, 3, 10, 11, 13)
        AND NOT (ptp.ItemType = 9 AND ISNULL(ptp.HealthCareTypeId, 0) IN (1, 2))
    WHERE pr.[Year] = :year
        AND pr.[Month] = :month
        AND pr.TeamId in :team_ids
        AND main_charge.ProductReimbursement IS NOT NULL
    GROUP BY pr.TeamId
),
PSTREDACTEDs AS (
    SELECT
        pr.TeamId,
        ROUND(SUM(COALESCE(ptp.PSTREDACTEDTotal, 0)) + SUM(COALESCE(main_charge.PSTREDACTEDAdjustment, 0)), 2) AS Amount
    FROM dbo.C_PRUSs main_charge
    JOIN dbo.C_PRs pr ON main_charge.C_PRId = pr.Id
    LEFT JOIN (
        SELECT
            SUM(ISNULL(ptp.CSTWithCredits, 0) - ISNULL(ptp.AP, 0)) AS PSTREDACTEDTotal,
            ptp.C_PRUSId
        FROM dbo.C_PRUSPSTItems ptp
        GROUP BY ptp.C_PRUSId
    ) ptp ON ptp.C_PRUSId = main_charge.Id
    WHERE pr.[Year] = :year
        AND pr.[Month] = :month
        AND pr.TeamId in :team_ids
        AND main_charge.ProductReimbursement IS NULL
    GROUP BY pr.TeamId
)
SELECT
    b.TeamId,
    b.Name,
    COALESCE(rp.Amount, 0) + COALESCE(ptp.Amount, 0) + COALESCE(ptw.Amount, 0) AS MainChargeTotal,
    rp.APs AS ProductContributions
FROM BaseTeams b
LEFT JOIN RPs rp ON b.TeamId = rp.TeamId
LEFT JOIN PSTItems ptp ON b.TeamId = ptp.TeamId
LEFT JOIN PSTREDACTEDs ptw ON b.TeamId = ptw.TeamId
WHERE (rp.Amount IS NOT NULL OR ptp.Amount IS NOT NULL OR ptw.Amount IS NOT NULL)

    """).bindparams(bindparam("team_ids", expanding=True))

    logger.info(f"Querying REDACTED for {len(team_ids)} teams' MAIN_CHARGE")

    CHUNK_SIZE = 200

    if not team_ids:
        main_charge_df = pd.DataFrame()
    else:
        dfs = []
        with db_b_engine.connect() as conn:
            for i in range(0, len(team_ids), CHUNK_SIZE):
                team_ids_chunk = team_ids[i : i + CHUNK_SIZE]

                chunk_df = pd.read_sql(
                    main_charge_qry,
                    con=conn,
                    params={
                        "year": year,
                        "month": month,
                        "team_ids": team_ids_chunk,
                    },  # type: ignore
                )
                dfs.append(chunk_df)

        main_charge_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    return main_charge_df