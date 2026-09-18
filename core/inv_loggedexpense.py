import json
import logging

import pandas as pd
from sqlalchemy import bindparam, text

from core.cache_manager import CacheManager
from core.db import db_b_engine, db_c_engine

logger = logging.getLogger(__name__)


def pull_default_loggedexpense(
    custom_expense_names: list[str],
    cache_manager: CacheManager
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns two dataframes: One with all loggedexpense with defaults for the Logged Expense names given,
    the other will all sage information for populating as options for user entry.
    """
    
    # Delegate sync logic to CacheManager.
    cache_manager.sync_db_c_loggedexpense(
        remote_engine=db_c_engine
    )

    # Pull data from Sqlite 
    loggedexpenseOptionsQry = text("""
        SELECT Id, ItemId, Memo, SoDocumentEntryClassId, [Location]
        FROM SageInvoiceLineItemTypes
        ORDER BY ItemId 
    """)

    loggedexpenseDefaultsQry = text("""
        SELECT
            r.Id AS RelationshipId,
            r.LoggedExpenseName,
            t.ItemId,
            t.Memo,
            t.SoDocumentEntryClassId,
            t.[Location]
        FROM
            DefaultLoggedExpenseSageInvoiceLineItemTypeRelationships AS r
            JOIN SageInvoiceLineItemTypes AS t on r.SageInvoiceLineItemTypeId = t.Id
        WHERE
            r.IsActive = 1 AND r.LoggedExpenseName in :custom_expense_names
    """).bindparams(bindparam("custom_expense_names", expanding=True))

    with cache_manager.sqlite_engine.connect() as sqlite_conn:
        if custom_expense_names:
            loggedexpense_sage_defaults = pd.read_sql(
                loggedexpenseDefaultsQry,
                con=sqlite_conn,
                params={"custom_expense_names": custom_expense_names},  # type: ignore
            )
        else:
            loggedexpense_sage_defaults = pd.DataFrame(
                columns=[
                    "RelationshipId",
                    "LoggedExpenseName",
                    "ItemId",
                    "Memo",
                    "SoDocumentEntryClassId",
                    "Location",
                ]
            )
        loggedexpense_sage_options = pd.read_sql(loggedexpenseOptionsQry, con=sqlite_conn)

    return loggedexpense_sage_defaults, loggedexpense_sage_options


def pull_loggedexpense_options(
    team_ids: list[str],
    year: int,
    month: int,
    cache_manager: CacheManager
) -> tuple[list[dict], list[dict]]:
    """Returns loggedexpense for teams with defaults, and list of all """

    if not team_ids:
        logger.info("No team_ids provided; returning empty results.")
        return [], []

    loggedexpenseQry = text("""
        SELECT loggedexpense.Name AS LoggedExpenseName,
            COUNT(*) AS TotalCount,
            ROUND(SUM(loggedexpense.Amount),2) AS TotalAmt,
            LEFT(STRING_AGG(t.Name, ';'), 100) AS SampleTeamNames
        FROM dbo.C_PR AS pr
            JOIN dbo.Teams AS t ON pr.TeamId = t.TeamId
            JOIN dbo.ExSummaries AS es ON es.C_PRId = pr.Id
            JOIN dbo.ExSummaryLoggedExpenses AS loggedexpense ON es.Id = loggedexpense.ExSummaryId
        WHERE pr.Month = :month
            AND pr.Year = :year
            AND pr.TeamId IN :team_ids
        GROUP BY loggedexpense.Name;
    """).bindparams(bindparam("team_ids", expanding=True))

    logger.info(f"Querying core engine for {len(team_ids)} teams' loggedexpense")

    # Get list of loggedexpense from Core for teams /yearmonth
    with db_b_engine.connect() as conn:
        loggedexpense_options_df = pd.read_sql(
            loggedexpenseQry,
            con=conn,
            params={"year": year, "month": month, "team_ids": team_ids},  # type: ignore
        )

    # Check cache or db_cDB for the list of default loggedexpense for the chosen names
    ce_names = list(loggedexpense_options_df["LoggedExpenseName"].dropna().unique())

    loggedexpense_sage_defaults_df, loggedexpense_sage_options_df = pull_default_loggedexpense(
        ce_names, cache_manager=cache_manager
    )

    # Merge defaults based on the LoggedExpenseName
    ce_merge = pd.merge(
        loggedexpense_options_df, loggedexpense_sage_defaults_df, on="LoggedExpenseName", how="left"
    )

    # Replace pd.NA with None, so to_json will work for returning data to javascript
    ce_merge = ce_merge.replace({pd.NA: None}).where(pd.notnull(ce_merge), None)
    loggedexpense_sage_options_df = loggedexpense_sage_options_df.replace({pd.NA: None}).where(
        pd.notnull(loggedexpense_sage_options_df), None
    )

    loggedexpense_options_with_defaults = json.loads(ce_merge.to_json(orient="records"))
    loggedexpense_sage_options = json.loads(loggedexpense_sage_options_df.to_json(orient="records"))

    return loggedexpense_options_with_defaults, loggedexpense_sage_options


def pull_loggedexpense_filtered(
    loggedexpense_names: list[str],
    team_ids: list[str],
    year: int,
    month: int,
) -> pd.DataFrame:

    if not team_ids or not loggedexpense_names:
        logger.info(
            "Did not receive both team_ids and loggedexpense_names; returning empty results."
        )
        return pd.DataFrame()

    loggedexpenseQry = text("""
        SELECT pr.TeamId,
            loggedexpense.Name AS LoggedExpenseName,
            loggedexpense.Amount
        FROM dbo.C_PR AS pr
            JOIN dbo.ExSummaries AS es ON es.C_PRId = pr.Id
            JOIN dbo.ExSummaryLoggedExpenses AS loggedexpense ON es.Id = loggedexpense.ExSummaryId
        WHERE pr.Month = :month
            AND pr.Year = :year
            AND pr.TeamId IN :team_ids
            AND loggedexpense.Name in :loggedexpense_names
    """).bindparams(
        bindparam("team_ids", expanding=True), bindparam("loggedexpense_names", expanding=True)
    )

    logger.info(
        f"Querying core engine for {len(team_ids)} teams for loggedexpense with {len(loggedexpense_names)} loggedexpense names"
    )

    with db_b_engine.connect() as conn:
        loggedexpense_filtered_df = pd.read_sql(
            loggedexpenseQry,
            con=conn,
            params={
                "year": year,
                "month": month,
                "team_ids": team_ids,
                "loggedexpense_names": loggedexpense_names,
            },  # type: ignore
        )

    return loggedexpense_filtered_df
