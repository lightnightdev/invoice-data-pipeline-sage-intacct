import json
import logging

import numpy as np
import pandas as pd
from core.db import db_c_engine
from core.e_sage_lineitem_key import sage_lineitem_key
from sqlalchemy import text

logger = logging.getLogger(__name__)


def normalize_main_charge_fees_loggedexpense(
    main_charge_df: pd.DataFrame,
    fees_df: pd.DataFrame,
    loggedexpense_df: pd.DataFrame,
    teamid_teamtype: dict[str, str],
) -> pd.DataFrame:

    target_cols = ["TeamId", "Amount", "sage_lineitem_key", "additional_memo"]
    valid_dfs = [pd.DataFrame(columns=target_cols)]

    # 1. Process main_charge
    if not main_charge_df.empty and "main_chargeTotal" in main_charge_df.columns:
        normed_main_charge = main_charge_df.rename(columns={"main_chargeTotal": "Amount"}).copy()
        normed_main_charge["sage_lineitem_key"] = sage_lineitem_key.main_charge_PLATFORM_EXPORT.value
        normed_main_charge["additional_memo"] = normed_main_charge.apply(build_main_charge_memo, axis=1)
        # if set(target_cols).issubset(normed_main_charge.columns):
        valid_dfs.append(normed_main_charge[target_cols])

    # 2. Process Fees
    if not fees_df.empty:
        normed_fees = normalize_fee_df(fees_df=fees_df, teamid_teamtype=teamid_teamtype)
        # if set(target_cols).issubset(normed_fees.columns):
        valid_dfs.append(normed_fees[target_cols])

    # 3. Process loggedexpense
    if not loggedexpense_df.empty:
        loggedexpense_df["additional_memo"] = pd.NA
        if "LoggedExpenseName" in loggedexpense_df.columns:
            normed_loggedexpense = loggedexpense_df.rename(
                columns={"LoggedExpenseName": "sage_lineitem_key"}
            ).copy()
        else:
            normed_loggedexpense = loggedexpense_df.copy()
        # if set(target_cols).issubset(normed_loggedexpense.columns):
        valid_dfs.append(normed_loggedexpense[target_cols])

    return pd.concat(valid_dfs, ignore_index=True)

def build_main_charge_memo(row):
    Product = row["ProductContributions"]
    # pd.notna checks for both None, np.nan, and pd.NA
    if pd.notna(Product) and Product != 0:
        total = row["Amount"]
        employee = total - Product
        return f"Total: ${total:,.2f}\nEmployer Product Contributions: ${Product:,.2f}\nEmployee Withholdings: ${employee:,.2f}"
    return None

def normalize_fee_df(
    fees_df: pd.DataFrame, teamid_teamtype: dict[str, str]
) -> pd.DataFrame:

    # --- Process Subscription Fees ---
    fees_fee_df = fees_df[["TeamId", "Fee"]].copy()
    fees_fee_df = fees_fee_df[fees_fee_df["Fee"].notna()]

    teamtypeseries = (
        fees_fee_df["TeamId"].astype(str).map(teamid_teamtype).str[0].fillna("X")
    )
    teamtypeseries = teamtypeseries.where(teamtypeseries.isin(["I", "W"]), "Other")

    mapp = {
        "I": sage_lineitem_key.MONTHLYFEE_A.value,
        "W":sage_lineitem_key.MONTHLYFEE_B.value,
        "Other": sage_lineitem_key.MONTHLYFEE_OTHER.value
    }

    fees_fee_df["sage_lineitem_key"] = teamtypeseries.map(mapp)
    fees_fee_df.rename(columns={"Fee": "Amount"}, inplace=True)

    # --- Process Fee Credits ---
    fees_credit_df = fees_df[["TeamId", "FeeCredit"]].copy()

    # Map TeamId to TeamType and apply conditional logic
    mapped_teamtype = fees_credit_df["TeamId"].astype(str).map(teamid_teamtype)
    is_w_team = mapped_teamtype.astype(str).str.startswith("W", na=False)
    is_zero_credit = fees_credit_df["FeeCredit"] == 0

    # Keep non-null credits, dropping $0 credits ONLY if team type matches
    # Should move this to enum
    fees_credit_df = fees_credit_df[
        fees_credit_df["FeeCredit"].notna() & ~(is_w_team & is_zero_credit)
    ]

    fees_credit_df["sage_lineitem_key"] = "FeeCredit_platform_export"
    fees_credit_df.rename(columns={"FeeCredit": "Amount"}, inplace=True)
    fees_credit_df["Amount"] = -fees_credit_df["Amount"]

    fees_final_df = pd.concat([fees_fee_df, fees_credit_df], ignore_index=True)
    fees_final_df["additional_memo"] = pd.NA
    return fees_final_df


def create_lineitem_keys(loggedexpense_options: pd.DataFrame) -> pd.DataFrame:
    qry = text("""
        WITH OrderedRows AS (
            SELECT 
                r.LoggedExpenseName AS sage_lineitem_key,
                x.ItemId,
                x.Memo,
                x.SoDocumentEntryClassId,
                x.[Location],
                ROW_NUMBER() OVER (
                    PARTITION BY r.LoggedExpenseName 
                    ORDER BY r.Id DESC
                ) AS RowNum
            FROM dbo.DefaultLoggedExpenseSageInvoiceLineItemTypeRelationships r
            JOIN SageInvoiceLineItemTypes x ON r.SageInvoiceLineItemTypeId = x.Id
        )
        SELECT sage_lineitem_key, ItemId, Memo, SoDocumentEntryClassId, [Location]
        FROM OrderedRows
        WHERE RowNum = 1
    """)

    defaults = pd.read_sql(qry, con=db_c_engine)
    cols = ["sage_lineitem_key", "ItemId", "Memo", "SoDocumentEntryClassId", "Location"]
    valid_dfs = pd.DataFrame(columns=cols)

    # Safely append user options if non-empty and schema matches
    if not loggedexpense_options.empty:
        renamed = loggedexpense_options.rename(columns={"LoggedExpenseName": "sage_lineitem_key"})
        if set(cols).issubset(renamed.columns):
            valid_dfs = renamed[cols]

    final_loggedexpense_keys = pd.concat(
        [valid_dfs, defaults], ignore_index=True
    ).drop_duplicates(subset=["sage_lineitem_key"], keep="first")
    return final_loggedexpense_keys


def format_for_sage(final: pd.DataFrame, year: int, month: int) -> list[dict]:
    sort_map = {
        sage_lineitem_key.main_charge_PLATFORM_EXPORT.value: 10,
        sage_lineitem_key.MONTHLYFEE_A.value: 20,
        sage_lineitem_key.MONTHLYFEE_B.value: 21,
        sage_lineitem_key.MONTHLYFEE_OTHER.value: 22,
        sage_lineitem_key.FEECREDIT_PLATFORM_EXPORT.value: 30,
        sage_lineitem_key.CUSTOM_ROW_ONETIME.value: 40,
        sage_lineitem_key.CUSTOM_ROW_REPEAT.value: 40,
    }
    final["sortindex"] = final["sage_lineitem_key"].map(sort_map).fillna(30).astype(int)

    final = final.sort_values(by=["SageId", "sortindex"]).reset_index(drop=True)

    final["row_num"] = final.groupby("TeamId").cumcount() + 1

    cols_in_order = [
        "TRANSACTIONTYPE",
        "DATE",
        "GLPOSTINGDATE",
        "CUSTOMER_ID",
        "TERM_NAME",
        "DATEDUE",
        "STATE",
        "LINE",
        "ITEMID",
        "QUANTITY",
        "UNIT",
        "PRICE",
        "LOCATIONID",
        "SODOCUMENTENTRY_CLASSID",
        "SODOCUMENTENTRY_CUSTOMERID",
        "MEMO",
        "TO_DELETE_TeamName",
        "TO_DELETE_TeamId",
    ]

    date_5th = f"{month:02d}/05/{year}"
    date_15th = f"{month:02d}/15/{year}"

    is_header = final["row_num"] == 1

    final["TRANSACTIONTYPE"] = np.where(is_header, "Sales invoice", "")
    final["DATE"] = np.where(is_header, date_5th, "")
    final["GLPOSTINGDATE"] = np.where(is_header, date_5th, "")
    final["CUSTOMER_ID"] = np.where(is_header, final.get("SageId", ""), "")
    final["TERM_NAME"] = np.where(is_header, "Net 10", "")
    final["DATEDUE"] = np.where(is_header, date_15th, "")
    final["STATE"] = np.where(is_header, "Pending", "")

    # Line item fields
    final["LINE"] = final["row_num"]
    final["ITEMID"] = final.get("ItemId", final.get("ITEMID", ""))
    final["QUANTITY"] = 1
    final["UNIT"] = "Each"
    final["PRICE"] = final.get("Amount", final.get("PRICE", 0))
    final["LOCATIONID"] = final.get("Location", final.get("LOCATIONID", ""))
    final["SODOCUMENTENTRY_CLASSID"] = final.get(
        "SoDocumentEntryClassId", final.get("SODOCUMENTENTRY_CLASSID", "")
    )
    final["SODOCUMENTENTRY_CUSTOMERID"] = np.where(
        is_header, final.get("SageId", ""), ""
    )
    final["MEMO"] = final.get("Memo", final.get("MEMO", ""))
    final["TO_DELETE_TeamName"] = final.get("TeamName", "")
    final["TO_DELETE_TeamId"] = final.get("TeamId", "")

    print(final.head(10))

    final.replace({np.nan: None}, inplace=True)

    output = final[cols_in_order].to_dict(orient="records")

    logger.info(
        f"Format for Sage finished. Total rows: {len(output)}\n"
        f"First 3 rows:\n{json.dumps(output[:3], indent=2)}"
    )

    return output
