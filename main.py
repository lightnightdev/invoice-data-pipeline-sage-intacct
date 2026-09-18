import json
import logging
from pathlib import Path

import pandas as pd
import webview
from core.cache_manager import CacheManager
from core.gsheet import GSheetClient
from core.inv import create_lineitem_keys, format_for_sage, normalize_main_charge_fees_loggedexpense
from core.inv_custom_rows import add_custom_rows_to_df, load_custom_rows
from core.inv_loggedexpense import pull_loggedexpense_filtered, pull_loggedexpense_options
from core.inv_fees import pull_fee_data
from core.inv_persist_changes import persist_changes
from core.inv_main_charge import pull_main_charge
from core.logging_config import setup_logging
from core.sageid_to_teamid import sageid_to_teamid
from core.teamname_validation import validate_teamnames_master
from webview.window import Window

setup_logging(logging.INFO)

logger = logging.getLogger(__name__)


class API:
    """Methods in this class are automatically exposed to JavaScript."""

    def __init__(self):
        self.cache = CacheManager(
            cache_dir=Path(__file__).resolve().parent / "programfiles"
        )
        self.gsheet_client = GSheetClient()

    def get_cached_sheets(self):
        logger.info("Executing get_cached_sheets")

        data = self.cache.get_cached_json("sheets")
        if data is not None:
            logger.info(f"Loaded cached sheets data: {data}")
            return {"success": True, "sheets": data, "error": None}

        logger.info("Cache miss for sheets. Falling back to load_sheets()...")
        return self.load_sheets()

    def clear_cache(self):
        logger.warning("Clearing local cache")
        self.cache.clear_all_cache()

    def load_sheets(self):
        logger.info("Executing load_sheets (Fetching fresh sheets via API)")

        result = self.gsheet_client.get_sheets()

        if not result.get("success"):
            logger.error(f"Failed to load sheets: {result.get('error')}")
            return result

        sheet_names = result.get("sheets", [])
        logger.info(f"Fetched fresh sheet names: {sheet_names}")

        self.cache.set_cached_json("sheets", sheet_names)

        return result

    def get_cached_customer_data(self, sheetname):
        logger.info(f"Executing get_cached_customer_data('{sheetname}')")
        data = self.cache.get_cached_json(sheetname)
        if data is not None:
            preview = str(data)[:100]
            logger.info(f"Cache hit for '{sheetname}'. Data preview: {preview}...")
            return data

        logger.info(f"Cache miss for sheet '{sheetname}'.")
        return None

    def load_customer_data(self, sheetname):
        logger.info(f"Executing load_customer_data('{sheetname}')")
        gsheet_data = self.gsheet_client.get_customer_data(sheetname)

        self.cache.set_cached_json(sheetname, gsheet_data)

        customer_json_data = json.dumps(gsheet_data)
        logger.info(
            f"Customer JSON string prepared (preview): {customer_json_data[:100]}..."
        )
        return customer_json_data

    def validate_teamnames(self, sageid_names_types: list[dict], sageids_teamids: dict):
        if not sageid_names_types:
            logger.info("Validate Names. Received empty sageid_list.")
            return {"summary": "ok", "teamids_teamnames": {}, "mismatches": {}}

        logger.info(
            f"Validate Names. Received sageid_list: {len(sageid_names_types)}\n"
            f"First record: {json.dumps(sageid_names_types[0])}"
        )

        cached_map = self.cache.get_cached_json("teamids_teamnames") or {}

        output, cache_update = validate_teamnames_master(
            sageid_names_types, sageids_teamids, cached_map
        )

        if cache_update["updated"]:
            self.cache.set_cached_json("teamids_teamnames", cache_update["cached_map"])

        return output

    def validate_sageids(self, sageid_names_types: list[dict]):
        #   sageid_names_types = [{'name': x, 'sageid': y, 'type': z}]
        logger.info(
            f"Validate SageIds. Received sageid_list: {len(sageid_names_types)}\nFirst record: {json.dumps(sageid_names_types[0])}"
        )
        cached_map = self.cache.get_cached_json("sageid_teamids") or {}
        missing_items = [
            item
            for item in sageid_names_types
            if str(item.get("sageid")) not in cached_map
        ]
        # Full cache hit: return cached mappings immediately
        if not missing_items:
            logger.info("Cache hit: All requested Sage IDs found in cache.")
            return {
                "summary": "ok",
                "added_to_db_c": [],
                "sageids_teamids": {
                    item["sageid"]: cached_map[str(item["sageid"])]
                    for item in sageid_names_types
                    if str(item.get("sageid")) in cached_map
                },
                "teamids_teamtypes": {
                    cached_map[str(item["sageid"])]: item.get("type")
                    for item in sageid_names_types
                    if str(item.get("sageid")) in cached_map
                },
                "fuzzy_matched_names": [],
            }

        # 3. Refetch missing teams and write updated map back to cache
        logger.info(
            f"Cache (partial?) miss: Refetching {len(missing_items)} missing team(s)..."
        )
        output = sageid_to_teamid(missing_items)

        new_mappings = output.get("sageids_teamids", {})
        cached_map.update(new_mappings)
        self.cache.set_cached_json("sageid_teamids", cached_map)

        # Combine cached + newly refetched mappings for the full response
        output["sageids_teamids"] = {
            item["sageid"]: cached_map[str(item["sageid"])]
            for item in sageid_names_types
            if str(item.get("sageid")) in cached_map
        }
        output["teamids_teamtypes"] = {
            cached_map[str(item["sageid"])]: item.get("type")
            for item in sageid_names_types
            if str(item.get("sageid")) in cached_map
        }

        return output

    def generate_invoices_to_preview(
        self,
        sageid_teamid: dict[str, str],
        teamid_teamtype: dict[str, str],
        teamid_teamname: dict[str, str],
        loggedexpense_names: list[str],
        year: int,
        month: int,
        loggedexpense_keys: dict,
        loggedexpense_unselected: list[str] | str | None = None,
        custom_rows: dict | None = None,
        custom_rows_unselected: list[str] | str | None = None,
        debug_print: bool = False,
    ):

        # get list of TeamIds (for pulling from platform)
        team_ids: list[str] = list(sageid_teamid.values())
        teamid_sageid = {v: k for k, v in sageid_teamid.items()}

        # pull data from SQL
        main_charge_df = pull_main_charge(team_ids, year, month)

        # TeamId, Name, main_chargeTotal
        fees_df = pull_fee_data(team_ids, year, month)
        # TeamId, Fee, FeeCredit, FeeType
        loggedexpense_df = pull_loggedexpense_filtered(
            loggedexpense_names=loggedexpense_names, team_ids=team_ids, year=year, month=month
        )
        # TeamId, LoggedExpenseName, Amount

        logger.info("Grabbed all core data, normalizing")

        # normalize the data into pre-sage format:
        normalized_core_data_df = normalize_main_charge_fees_loggedexpense(
            main_charge_df, fees_df, loggedexpense_df, teamid_teamtype
        )
        # sage_id, amount, sage_lineitem_key

        lowercased_teamid_map = {str(k).lower(): v for k, v in teamid_teamtype.items()}
        normalized_core_data_df["teamtype"] = (
            normalized_core_data_df["TeamId"]
            .astype(str)
            .str.lower()
            .map(lowercased_teamid_map)
            .fillna("Unknown")
        )
        normalized_core_data_df["SageId"] = (
            normalized_core_data_df["TeamId"]
            .astype(str)
            .map(teamid_sageid)
            .fillna("Unknown")
        )
        normalized_core_data_df["TeamName"] = (
            normalized_core_data_df["TeamId"]
            .astype(str)
            .map(teamid_teamname)
            .fillna("Unknown")
        )

        # lineitem_key will give Sage columns ItemId, LocationId, SoDocumentEntryClassId, Memo
        loggedexpense_keys_df = pd.DataFrame(loggedexpense_keys)
        lineitem_keys_df = create_lineitem_keys(loggedexpense_keys_df)

        final_output_df = pd.merge(
            normalized_core_data_df,
            lineitem_keys_df,
            on="sage_lineitem_key",
            how="left",
        )
        mask = final_output_df["additional_memo"].notna() & (
            final_output_df["additional_memo"] != ""
        )
        final_output_df.loc[mask, "Memo"] = (
            final_output_df.loc[mask, "Memo"].fillna("").astype(str) + "\n"
            + final_output_df.loc[mask, "additional_memo"].astype(str)
        ).str.lstrip("\n")

        debug = False
        if debug:
            try:
                final_output_df.to_excel("debug_main.xlsx")
                logger.info("Writing to debug_main.xlsx")
            except:  # noqa: E722
                logger.error("Failed to write to debug_main.xlsx")

        if custom_rows:
            final_output_df = add_custom_rows_to_df(
                final_output_df,
                custom_rows,
                sageid_teamid,
                teamid_teamname,
                debug_print,
            )

        for col in ["SoDocumentEntryClassId", "Location"]:
            final_output_df[col] = pd.to_numeric(
                final_output_df[col], errors="coerce"
            ).astype("Int64")

        try:
            persist_changes(final_output_df, loggedexpense_unselected, custom_rows_unselected)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error persisting, error: {e}")

        final_output: list[dict] = format_for_sage(final_output_df, year, month)

        return final_output

    def get_loggedexpense_to_select(self, team_ids: list[str], year: int, month: int) -> dict:
        logger.info(f"Get Logged Expenses. Received {len(team_ids)} team ids.")

        if not year or not month:
            return {
                "summary": "error, no window state year month",
                "loggedexpense_options": None,
            }

        # defaults and loggedexpense options
        loggedexpense_options_with_defaults, loggedexpense_sage_options = pull_loggedexpense_options(
            team_ids=team_ids, year=year, month=month, cache_manager=self.cache
        )

        # LoggedExpenseName, TotalCount, TotalAmt, SampleTeamNames
        return {
            "summary": "ok",
            "loggedexpense_options": loggedexpense_options_with_defaults,
            "all_options": loggedexpense_sage_options,
        }

    def custom_rows_from_sageids(self, sageids: list[str]):
        result = load_custom_rows(sage_ids=sageids, config={})
        return result


if __name__ == "__main__":
    api = API()

    webview.settings["ALLOW_DOWNLOADS"] = True

    # Create the app window and point it to your web directory
    window: Window

    checkWindow = webview.create_window(
        title="Invoice Generation Py",
        url="web/index.html",  # Path to local HTML file or a local http:// URL
        js_api=api,  # Expose the API instance to JS
        width=1200,
        height=800,
        resizable=True,
    )

    if checkWindow == None:
        logger.error("Window failed to load")
    else:
        window = checkWindow

        # webview.start()
        webview.start(debug=True)
