import logging
import uuid

import pandas as pd
from sqlalchemy import bindparam, text

from core.db import db_c_engine
from core.e_sage_lineitem_key import sage_lineitem_key

logger = logging.getLogger(__name__)


def persist_changes(final_output_df: pd.DataFrame, loggedexpense_unselected: list[str] | str | None, custom_rows_unselected: list[str] | str | None):
    debug = False
    if debug:
        fn = "debug_fodf.xlsx"
        try:
            final_output_df.to_excel(fn)
            logger.info(f"Saved to {fn}")
        except Exception as e:  # noqa: BLE001
            logger.info(f"Not saving {fn}: {e}")

    df = final_output_df.copy()

    enum_values = [e.value for e in sage_lineitem_key]
    
    #custom_rows
    custom_rows = df[df["sage_lineitem_key"] == sage_lineitem_key.CUSTOM_ROW_REPEAT.value]
    persist_custom_rows(custom_rows, custom_rows_unselected)

    # loggedexpense rows
    loggedexpense_rows = df[~df["sage_lineitem_key"].isin(enum_values)]
    persist_loggedexpense(loggedexpense_rows, loggedexpense_unselected)

def persist_custom_rows(cr_df: pd.DataFrame, custom_rows_unselected: list[str] | str| None):
    if not cr_df.empty:
        # SageId, Repeating, UserNote, SageInvoiceLineItemType, DefaultAmount
        temptblname = f"#TempInput_{uuid.uuid4().hex[:8]}"
        df2 = cr_df[["SageId", "Amount", "ItemId", "Memo", "SoDocumentEntryClassId", "Location"]]

    if custom_rows_unselected:
        if isinstance(custom_rows_unselected, str):
            custom_rows_unselected = [custom_rows_unselected]
        hi = 1
        # just set Repeating = 0


def persist_loggedexpense(df: pd.DataFrame, loggedexpense_unselected: list[str] | str | None):
    df2 = df[["sage_lineitem_key", "ItemId", "Memo", "SoDocumentEntryClassId", "Location"]].copy()
    df2.rename(columns={"sage_lineitem_key": "LoggedExpenseName"}, inplace=True)
    df2.drop_duplicates(subset=['LoggedExpenseName'], keep='last', inplace=True)
    for col in ["SoDocumentEntryClassId", "Location"]:
        df2[col] = pd.to_numeric(df2[col], errors="coerce").astype("Int64")
    invalid_mask = (df2["ItemId"].isna()
        | (df2["ItemId"].astype(str).str.strip() == "")
        | (df2["ItemId"].astype(str).str.lower() == "none")
    )

    if invalid_mask.any():
        invalid_rows = df2[invalid_mask]
        logger.error(f"Dropping {len(invalid_rows)} row(s) due to missing/null ItemId: {invalid_rows[['LoggedExpenseName', 'ItemId']].to_dict(orient='records')}")
        df2 = df2[~invalid_mask].copy()

    debug = False
    if debug:
        try:
            df.to_excel("loggedexpense_persist2_test.xlsx")
            df2.to_excel("loggedexpense_persist_test.xlsx")
        except Exception as e:  # noqa: BLE001
            logger.info(f"skipping loggedexpense persist write: {e}")

    # 2. Normalize loggedexpense_unselected input into a clean list
    if isinstance(loggedexpense_unselected, str):
        unselected_list = [loggedexpense_unselected]
    elif isinstance(loggedexpense_unselected, list):
        unselected_list = [item for item in loggedexpense_unselected if item]
    else:
        unselected_list = []

    temptblname = f"#TempInput_{uuid.uuid4().hex[:8]}"
    with db_c_engine.begin() as fo_conn:

        # Deactivate unselected items
        # Not really a good methodology... may need to rethink this. Perhaps leave data as is and give it its own "console"/editor.
        # Currenlty no way to set IsActive = 1 other than manually
        if unselected_list:
            
            rem_script = text("""
                UPDATE dbo.DefaultLoggedExpenseSageInvoiceLineItemTypeRelationships 
                SET IsActive = 0
                WHERE LoggedExpenseName IN :custom_expense_names
            """).bindparams(bindparam("custom_expense_names", expanding=True))

            fo_conn.execute(rem_script, {"custom_expense_names": unselected_list})

        if not df2.empty:
            # 1. Write DataFrame to a local temp table
            df2.to_sql(temptblname, con=fo_conn, if_exists='replace', index=False)

            # 2. Populate TVP from #TempInput and call procedure
            sql_script = text(f"""
                DECLARE @TVP dbo.LoggedExpenseSageInvoiceLineItemTypeInputTableType;

                INSERT INTO @TVP (LoggedExpenseName, ItemId, Memo, SoDocumentEntryClassId, Location)
                SELECT LoggedExpenseName, ItemId, Memo, SoDocumentEntryClassId, Location
                FROM {temptblname};

                EXEC dbo.usp_AddDefaultLoggedExpenseSageInvoiceLineItemTypeRelationships @Input = @TVP;
            """)
            
            fo_conn.execute(sql_script)