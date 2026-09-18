import logging

from core.cache_manager import CacheManager
from core.db import db_b_engine
from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)


def get_teamid_names_from_db(team_ids: list[str]) -> dict[str, str]:
    if not team_ids:
        return {}

    # Order SELECT as (Key, Value) so SQLAlchemy rows convert directly into a dict
    qry = text(
        "SELECT TeamId, Name AS TeamName FROM dbo.Teams WHERE TeamId IN :team_ids"
    ).bindparams(bindparam("team_ids", expanding=True))

    with db_b_engine.connect() as conn:
        result = conn.execute(qry, {"team_ids": tuple(team_ids)})
        return {str(row.TeamId): str(row.TeamName) for row in result}



def validate_teamnames_master(sageid_names_types: list[dict], sageids_teamids: dict, cached_map):

    # 1. Extract lookup payload
    teamid_names_to_check = extract_teamid_names(sageid_names_types, sageids_teamids)

    # 2. Partition into matches vs DB fetch queues
    matches, to_verify_db, mismatches_to_check, teamids_check_db = (
        partition_by_cache(teamid_names_to_check, cached_map)
    )

    logger.info(
        f"Name Validation Results — Matches: {len(matches)}, "
        f"Mismatches: {len(mismatches_to_check)}, Need DB Verification: {len(to_verify_db)}"
    )

    # 3. Fetch ground truth from DB
    db_teamid_names = {}
    if teamids_check_db:
        db_teamid_names = get_teamid_names_from_db(teamids_check_db)

    missing_db_tids = [tid for tid in teamids_check_db if tid not in db_teamid_names]
    summary = "ERROR_MISSING_TEAMID" if missing_db_tids else "ok"

    # 4. Reconcile differences and mutate cached_map
    mismatches_to_return, cache_updated = reconcile_db_results(
        to_verify_db, mismatches_to_check, db_teamid_names, cached_map
    )

    # 5. Persist updated cache if modified
    cache_return = { "updated": cache_updated, "cached_map": cached_map }

    # 6. Build final resolved map
    teamids_teamnames = {
        tid: db_teamid_names.get(tid) or cached_map.get(tid)
        for tid in teamid_names_to_check
    }

    return {
        "summary": summary,
        "teamids_teamnames": teamids_teamnames,
        "mismatches": mismatches_to_return,
    }, cache_return

def extract_teamid_names(
    sageid_names_types: list[dict], sageids_teamids: dict
) -> dict[str, str]:
    """Map incoming Sage ID input payloads to Team ID -> Name pairs."""
    teamid_names = {}
    for row in sageid_names_types:
        sageid = row.get("sageid")
        if sageid in sageids_teamids:
            tid = str(sageids_teamids[sageid])
            teamid_names[tid] = row.get("name")
    return teamid_names


def partition_by_cache(
    teamid_names_to_check: dict[str, str], cached_map: dict[str, str]
) -> tuple[dict[str, str], dict[str, str], dict[str, dict], list[str]]:
    """Partition incoming team names into cache matches, misses, and mismatches."""
    matches = {}
    to_verify_db = {}
    mismatches_to_check = {}
    teamids_check_db = []

    for tid, name in teamid_names_to_check.items():
        if tid not in cached_map:
            to_verify_db[tid] = name
            teamids_check_db.append(tid)
        elif cached_map[tid] != name:
            mismatches_to_check[tid] = {
                "input_name": name,
                "cached_name": cached_map[tid],
            }
            teamids_check_db.append(tid)
        else:
            matches[tid] = name

    return matches, to_verify_db, mismatches_to_check, teamids_check_db


def reconcile_db_results(
    to_verify_db: dict[str, str],
    mismatches_to_check: dict[str, dict],
    db_teamid_names: dict[str, str],
    cached_map: dict[str, str],
) -> tuple[dict[str, dict], bool]:
    """Compare input and cached names against DB ground truth and update cache dict."""
    mismatches_to_return = {}
    cache_updated = False

    # 1. Evaluate cache misses against DB ground truth
    for tid, input_name in to_verify_db.items():
        db_name = db_teamid_names.get(tid)
        if db_name is None:
            continue

        cached_map[tid] = db_name
        cache_updated = True

        if input_name != db_name:
            mismatches_to_return[tid] = {
                "input_name": input_name,
                "db_name": db_name,
            }

    # 2. Evaluate cache/input mismatches against DB ground truth
    for tid, info in mismatches_to_check.items():
        input_name = info["input_name"]
        cached_name = info["cached_name"]
        db_name = db_teamid_names.get(tid)
        if db_name is None:
            continue

        if input_name == db_name:
            cached_map[tid] = db_name
            cache_updated = True
        else:
            mismatches_to_return[tid] = {
                "input_name": input_name,
                "db_name": db_name,
                "cached_name": cached_name,
            }
            if cached_name != db_name:
                cached_map[tid] = db_name
                cache_updated = True

    return mismatches_to_return, cache_updated