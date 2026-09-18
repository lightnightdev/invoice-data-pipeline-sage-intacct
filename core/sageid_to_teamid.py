import logging
import uuid

import pandas as pd
from core.db import db_b_engine, db_c_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)


def sageid_to_teamid(sageids_data: list[dict]) -> dict:
    """
    Processes a list of sageid/name mappings.
    Expected format: [{'sageid': 'S12345', 'name': 'Joe Team'}, ...]
    """
    print(sageids_data[:5])

    sageids = [item["sageid"] for item in sageids_data]

    sageids_teamids, missing_indices = check_db_cdb_for(sageids)

    # if there are ids not in db_c, search core based on the team names
    fuzzy_matched_names = {}
    db_b_exact_matches = {}

    if missing_indices:
        missing_items = [sageids_data[i] for i in missing_indices]
        print(sageids_data[:5])
        print(missing_items[:5])
        db_b_exact_matches, fuzzy_matched_names = check_coreid_for(missing_items)
        if db_b_exact_matches:
            update_db_cdb_sageidteamis(db_b_exact_matches)
            sageids_teamids.update(db_b_exact_matches)

    output_data = {
        "summary": "ok",
        "added_to_db_c": db_b_exact_matches,
        "sageids_teamids": sageids_teamids,
        "fuzzy_matched_names": fuzzy_matched_names,
    }

    return output_data


def check_db_cdb_for(sageids: list[str]) -> tuple[dict, list[int]]:
    """
    Checks which SageIDs already exist in the DB-C database.
    Returns a dict of SageId: TeamId for existing and a list[int] if missing indices
    """

    sageids_teamids = {}

    if not sageids:
        return sageids_teamids, []

    df = pd.DataFrame({"SageId": sageids})
    temp_table = f"#temp_db_c_check_{uuid.uuid4().hex[:8]}"

    logger.info(f"Checking DB-C DB for {len(sageids)} records in TeamSageIds")

    with db_c_engine.begin() as conn:
        # Write search list to a temp table
        df.to_sql(
            temp_table, con=conn, index=False, if_exists="replace", method="multi"
        )

        query = text(f"""
            SELECT t.SageId, t.TeamId 
            FROM dbo.TeamSageIds AS t
            INNER JOIN {temp_table} AS s ON t.SageId = s.SageId
        """)

        result = conn.execute(query).fetchall()
        for row in result:
            sageids_teamids[row.SageId] = row.TeamId

    # Determine which original indices were NOT found
    missing_indices = [
        i for i, item in enumerate(sageids) if item not in sageids_teamids
    ]

    logger.info(
        f"Found {len(sageids_teamids)} matching records in TeamSageIds, missing {len(missing_indices)}"
    )
    return sageids_teamids, missing_indices


def check_coreid_for(missing_items: list[dict]) -> tuple[dict, dict]:
    """
    Checks Core DB for exact name matches.
    For unmatched names, performs a T-SQL Jaro-Winkler similarity search for top 3 candidates.
    """
    exact_matches = {}
    fuzzy_matched_names = {}

    if not missing_items:
        return exact_matches, fuzzy_matched_names

    df = pd.DataFrame(missing_items)  # Contains 'sageid' and 'name'

    required_cols = {"sageid", "name"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        error_msg = f"Missing required columns in source data: {missing}\nOnly found {', '.join(df.columns)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    temp_table = f"#temp_db_c_search_{uuid.uuid4().hex[:8]}"

    logger.info(
        f"Finding {len(missing_items)} team ids in core based on name with temp table {temp_table}"
    )

    with db_b_engine.begin() as conn:
        df.to_sql(
            temp_table, con=conn, index=False, if_exists="replace", method="multi"
        )

        exact_result = conn.execute(
            text(f"""
            SELECT s.sageid, t.TeamId 
            FROM {temp_table} AS s
            INNER JOIN dbo.Teams AS t ON s.name = t.Name
        """)
        ).fetchall()

        matched_sageids = set()

        for row in exact_result:
            exact_matches[row.sageid] = row.TeamId
            matched_sageids.add(row.sageid)

        # 2. For items with NO exact match, run fuzzy matching (Top 3)
        unmatched_items = [
            item for item in missing_items if item["sageid"] not in matched_sageids
        ]

        if unmatched_items:
            logger.info(
                f"Found {len(unmatched_items)} unmatched items. Running fuzzy match."
            )
            fuzzy_df = pd.DataFrame(unmatched_items)
            fuzzy_temp_table = f"#temp_fuzzy_search_{uuid.uuid4().hex[:8]}"
            fuzzy_df.to_sql(
                fuzzy_temp_table,
                con=conn,
                index=False,
                if_exists="append",
                method="multi",
            )

            fuzzy_query = text(f"""
                SELECT 
                    f.name AS SearchName,
                    t.Name AS MatchedTeamName,
                    t.TeamId,
                    JARO_WINKLER_SIMILARITY(
                        CAST(f.name AS NVARCHAR(100)) COLLATE Latin1_General_100_CI_AS, 
                        t.Name 
                    ) AS Score
                FROM {fuzzy_temp_table} f
                CROSS APPLY (
                    SELECT TOP 3 TeamId, Name
                    FROM dbo.Teams 
                    ORDER BY JARO_WINKLER_SIMILARITY(
                        CAST(f.name AS NVARCHAR(100)) COLLATE Latin1_General_100_CI_AS, 
                        dbo.Teams.Name
                    ) DESC
                ) t
                ORDER BY f.name, Score DESC
            """)

            fuzzy_result = conn.execute(fuzzy_query).fetchall()
            logger.info(
                f"Fuzzy match query finished. Returning {len(fuzzy_result)} records."
            )

            # Group results into {"search_name": {"1": (team_name, team_id), ...}}
            for row in fuzzy_result:
                if row.SearchName not in fuzzy_matched_names:
                    fuzzy_matched_names[row.SearchName] = {}

                rank = str(len(fuzzy_matched_names[row.SearchName]) + 1)
                fuzzy_matched_names[row.SearchName][rank] = (
                    row.MatchedTeamName,
                    row.TeamId,
                )

    return exact_matches, fuzzy_matched_names


def update_db_cdb_sageidteamis(db_b_teamids: dict):
    """Inserts newly discovered SageId-TeamId pairs into DB-C DB."""

    if not db_b_teamids:
        return

    # Convert dictionary to list of dicts for bulk insert
    data_to_insert = [{"SageId": k, "TeamId": v} for k, v in db_b_teamids.items()]
    df = pd.DataFrame(data_to_insert)

    with db_c_engine.begin() as conn:
        # Assuming your DB-C table is dbo.TeamSageIds
        df.to_sql(
            "TeamSageIds", con=conn, if_exists="append", index=False, method="multi"
        )

    logger.info(f"Successfully inserted {len(db_b_teamids)} new records into DB-CDB.")