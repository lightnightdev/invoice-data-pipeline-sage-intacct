import logging

import pandas as pd
from core.db import db_b_engine
from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)


def pull_fee_data(team_ids: list[str], year: int, month: int) -> pd.DataFrame:
    if not team_ids:
        logger.info("Did not receive team_ids; returning empty results.")
        return pd.DataFrame()

    fee_qry = text("""
SELECT
    pr.TeamId,
    es.Fee,
    es.FeeCredit,
    mft.Name FeeType
FROM
    dbo.C_PR pr
    LEFT JOIN dbo.ExpenseSummaries es on es.C_PRId = pr.Id
    LEFT JOIN dbo.MonthlyFeeTypes mft on mft.Id = es.FeeTypeId
WHERE
    pr.Year = :year
    and pr.Month = :month
    and pr.TeamId in :team_ids
    """).bindparams(bindparam("team_ids", expanding=True))

    logger.info(f"Querying live core engine for {len(team_ids)} teams' Fees")

    with db_b_engine.connect() as conn:
        fee_df = pd.read_sql(
            fee_qry,
            con=conn,
            params={
                "year": year,
                "month": month,
                "team_ids": team_ids,
            },  # type: ignore
        )

    return fee_df
