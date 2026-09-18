import logging
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from core.db import db_c_engine
from core.e_sage_lineitem_key import sage_lineitem_key

logger = logging.getLogger(__name__)


def load_custom_rows(sage_ids: list[str], config: dict) -> list[dict]:
    """
    Gets custom_rows for sage_ids with a bit
    """

    if not sage_ids:
        return []

    qry = text("""
    SELECT
        cr.Id AS CustomRowId,
        cr.SageId,
        cr.Repeating,
        cr.UserNote,
        cr.DefaultAmount AS Amount,
        lit.Id AS SageInvoiceLineItemTypeId,
        lit.ItemId,
        lit.Memo,
        lit.SoDocumentEntryClassId,
        lit.Location
    FROM dbo.SageCustomRows AS cr
        JOIN dbo.SageInvoiceLineItemTypes AS lit on lit.Id = cr.SageInvoiceLineItemTypeId
    WHERE cr.SageId in :sage_ids
    """).bindparams(bindparam("sage_ids", expanding=True))

    with db_c_engine.connect() as conn:
        results = conn.execute(qry, parameters={"sage_ids": sage_ids}).fetchall()

    dict_results = []
    for row in results:
        row_dict = dict(row._mapping)
        # Convert Decimal to Float for json.dumps
        for key, val in row_dict.items():
            if isinstance(val, Decimal):
                row_dict[key] = float(
                    val
                )  # Use str(val) if exact string precision is needed in JS

        # Convert BIT column (1/0 or True/False) to a boolean 'selected' flag
        row_dict["selected"] = bool(row_dict.get("Repeating"))
        dict_results.append(row_dict)

    return dict_results


def add_custom_rows_to_df(
    normalized_core_data_df: pd.DataFrame,
    custom_rows: dict | list[dict],
    sageid_teamid: dict[str, str],
    teamid_teamname: dict[str, str],
    debug_print: bool = False,
) -> pd.DataFrame:
    if debug_print:
        print("***** [DEBUG] - Custom rows:")
        print(custom_rows)
        print("\n\n***** [DEBUG] - Normalized df:")
        print(normalized_core_data_df.head())

    if not custom_rows:
        logger.info("Added custom rows to df finished. Total rows added: 0\n")
        return normalized_core_data_df.copy()

    custom_rows_df = pd.DataFrame(custom_rows)

    if custom_rows_df.empty:
        logger.info("Added custom rows to df finished. Total rows added: 0\n")
        return normalized_core_data_df.copy()

    # Safely retrieve validation series even if columns are completely missing to flag dirty rows
    sage_ids = custom_rows_df.get("SageId", pd.Series([None] * len(custom_rows_df)))
    item_ids = custom_rows_df.get("ItemId", pd.Series([None] * len(custom_rows_df)))
    is_dirty = sage_ids.isna() | (sage_ids == "") | item_ids.isna() | (item_ids == "")
    # Split immediately: dirty_custom_rows_df retains ALL original/extra columns
    dirty_custom_rows_df = custom_rows_df[is_dirty].copy()
    clean_custom_rows_df = custom_rows_df[~is_dirty].copy()

    # Log dirty rows with full original column context
    if not dirty_custom_rows_df.empty:
        print(dirty_custom_rows_df)
        logger.error(
            f"Invalid custom rows detected (missing SageId or ItemId).\n"
            f"Columns: {list(dirty_custom_rows_df.columns)}\n"
            f"Rows:\n{dirty_custom_rows_df}"
        )

    # Clean columns from clean rows
    clean_custom_rows_df["sage_lineitem_key"] = sage_lineitem_key.CUSTOM_ROW_ERROR.value
    if not clean_custom_rows_df.empty:
        if "Amount" in clean_custom_rows_df.columns:
            clean_custom_rows_df["Amount"] = clean_custom_rows_df["Amount"].fillna(0)
        if "Repeating" in clean_custom_rows_df.columns:
            clean_custom_rows_df["sage_lineitem_key"] = np.where(
                clean_custom_rows_df["Repeating"], sage_lineitem_key.CUSTOM_ROW_REPEAT.value, sage_lineitem_key.CUSTOM_ROW_ONETIME.value
            )
            clean_custom_rows_df["Amount"] = clean_custom_rows_df["Amount"].fillna(0)
        else:
            clean_custom_rows_df["Amount"] = 0

        # Map TeamId from SageId, then TeamName from TeamId
        clean_custom_rows_df["TeamId"] = (
            clean_custom_rows_df["SageId"]
            .astype(str)
            .map(sageid_teamid)
            .fillna("Unknown")
        )
        clean_custom_rows_df["TeamName"] = (
            clean_custom_rows_df["TeamId"]
            .astype(str)
            .map(teamid_teamname)
            .fillna("Unknown")
        )

        # Reindex restricts columns to match normalized_core_data_df exactly
        # (drops extra columns and injects missing optional ones as NaN/None)
        clean_custom_rows_df = clean_custom_rows_df.reindex(
            columns=normalized_core_data_df.columns
        )
        df_to_return = pd.concat(
            [normalized_core_data_df, clean_custom_rows_df], ignore_index=True
        )
    else:
        df_to_return = normalized_core_data_df.copy()

    logger.info(
        f"Added custom rows to df finished. Total rows added: {len(clean_custom_rows_df)}"
    )

    return df_to_return
