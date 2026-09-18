import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GSheetClient:
    """Client for interacting with the Google Sheets Web App API."""

    def __init__(self):
        url = os.getenv("GS_WEB_APP_URL")
        key = os.getenv("GS_WEB_APP_SK")
        if not url or not key:
            logger.error("Failed to initialize GSheetClient: Missing environment variables GS_WEB_APP_URL or GS_WEB_APP_SK.")
            raise ValueError("GS_WEB_APP_URL and GS_WEB_APP_SK must be set in environment variables.")

        self.web_app_url: str = url
        self.secret_key: str = key

        # Shared session for connection pooling
        self.session = requests.Session()
        logger.debug("GSheetClient initialized with configured web app credentials.")

    def _request(self, action: str, **extra_params) -> dict:
        """Helper to manage API requests and return parsed JSON."""
        params = {"key": self.secret_key, "action": action, **extra_params}
        logger.debug(f"Sending Google Sheets API request for action '{action}' with params: {extra_params}")

        try:
            response = self.session.get(self.web_app_url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Google Sheets API response received for action '{action}' [Status: {response.status_code}]")
            return data
        except requests.exceptions.JSONDecodeError as e:
            logger.exception(f"Failed to decode Google Sheets API JSON response for action '{action}': {e}", exc_info=True)
            raise
        except requests.exceptions.RequestException as e:
            logger.exception(f"Google Sheets HTTP API request failed for action '{action}': {e}", exc_info=True)
            raise

    def get_sheets(self) -> dict:
        """Returns a list of all sheet names in the workbook."""
        logger.info("Fetching list of sheet names from Google Sheets API.")

        try:
            data = self._request("list_sheets")

            if data.get("status") != "success":
                error_msg = data.get("error", "Unknown API error")
                logger.error(f"Google Sheets API returned non-success status for 'list_sheets': {error_msg}")
                return {
                        "success": False,
                        "error": f"API request failed: {error_msg}",
                        "sheets": [],
                    }

            sheets = data.get("sheets")
            if not isinstance(sheets, list):
                logger.error("Response payload for 'list_sheets' missing 'sheets' list key.")
                return {
                    "success": False,
                    "error": "Response payload missing 'sheets' list.",
                    "sheets": [],
                }

            logger.info(f"Successfully retrieved {len(sheets)} sheet names.")
            return {"success": True, "sheets": sheets, "error": None}
        except Exception as e:
            logger.exception("Unexpected error fetching sheet names.")
            return {
                "success": False,
                "error": f"Network or execution failure: {e!s}",
                "sheets": [],
            }

    def get_customer_data(self, sheet_name: str) -> dict:
        """Fetch and validate customer data from a sheet."""
        logger.info(f"Fetching customer data for sheet: '{sheet_name}'")
        extra_params = {"sheet": sheet_name} if sheet_name else {}
        gs_data = self._request("get_customer_data", **extra_params)

        self.validate_gsheet_data(gs_data)
        logger.info(f"Successfully fetched and validated customer data for sheet: '{sheet_name}'")
        return gs_data

    @staticmethod
    def validate_gsheet_data(gsheet_data: dict) -> bool:
        """Validates required structure in Google Sheet payload."""
        if not isinstance(gsheet_data, dict):
            logger.error(f"Validation failed: expected dict, received {type(gsheet_data).__name__}")
            raise TypeError(f"Expected dict, got {type(gsheet_data).__name__}")

        columns = gsheet_data.get("columns")
        if not isinstance(columns, dict):
            logger.error("Validation failed: 'columns' dictionary is missing or invalid.")
            raise KeyError("Missing or invalid 'columns' dictionary.")

        required_keys = ["customers", "sageid", "dateneeded"]
        for key in required_keys:
            if key not in columns:
                logger.error(f"Validation failed: missing required column key '{key}' in dataset.")
                raise KeyError(f"Missing required key '{key}' in columns dictionary.")

        logger.debug("Google Sheet data payload validation passed.")
        return True