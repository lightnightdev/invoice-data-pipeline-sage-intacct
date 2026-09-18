# Front-End UI Architecture

This section of the repository contains the JavaScript front-end components for the desktop invoice generation application. Built as a lightweight, vanilla JS web interface hosted by `pywebview`, it handles user interaction, state management, Tabulator grid rendering, and API communication with the Python back-end.

## Roadmap (front-end and back-end)

See `README_py.md`.

## Core Modules

| File | Primary Responsibility |
| :--- | :--- |
| `app_state.js` | Manages the global `ApplicationState` singleton (`window.AppState`). Holds current period, team mappings, and Logged Expense configurations. |
| `main.js` | Initialization script. Listens for `pywebviewready`, configures default dates, binds primary UI buttons, and manages manual Sage ID inputs. |
| `choose_sheets.js` | Interacts with the Python API to load and display available Google Sheet names. Manages caching and validates sheet name formats (e.g., "2026-Jan"). |
| `choose_teams.js` | Loads selected sheet data, populates the primary Tabulator grid (`customerTable`), and handles row selection logic (defaulting to rows where invoices are not yet sent). |
| `setup_teams.js` | Builds contextual UI controls (Refresh, Date Needed filtering, Generate button) once team data is loaded into the grid. |
| `select_loggedexpense.js` | Renders the Logged Expense (loggedexpense) selection Tabulator grid. Allows users to map Sage line-item fields (`ItemId`, `Memo`, `Location`, `SODECId`) before final generation. |
| `generate_invoices.js` | Orchestrates the primary business workflow: validates Sage IDs/Team Names via Python, prepares state, and triggers the Logged Expense selection or bypasses to preview. |
| `invoice_preview.js` | Requests the final formatted data from Python, renders the final Sage Import preview table, and binds the direct CSV download functionality. |
| `choice_tables.js` | Utility script for dynamically generating simple HTML tables for user selections (used primarily for the sheet selection menu). |
| `format_to_year_month.js` | Utility function to parse arbitrary sheet names (e.g., "Jan-2026") into a standard `YYYY-MM` format. |

## Application Workflow

1. **Initialization (`main.js` & `choose_sheets.js`)**:
   * App loads and fetches available sheets from the local cache or Google Sheets via `pywebview.api`.
   * User selects a target period (e.g., "2026-Jan").
2. **Team Selection (`choose_teams.js` & `setup_teams.js`)**:
   * The app fetches customer data from the selected sheet.
   * A Tabulator grid displays teams, Sage IDs, Type, and metadata (`dateneeded`, `invoicesent`).
   * Rows missing the "Invoice Sent" flag are auto-selected. Users can modify selections.
   * A dateneeded selector allows bulk selecting teams based on date needed.
3. **Back-End Data Validation & Setup (`generate_invoices.js`)**:
   * Selected rows are sent to the Python back-end to validate `SageId` to platform `TeamId` mappings.
   * `AppState` is updated with validated mappings.
4. **Logged Expense Mapping (`select_loggedexpense.js`)**:
   * The app fetches unique Logged Expenses for the selected teams.
   * An editable Tabulator grid allows users to accept default Sage mapping codes or input new ones (`ItemId`, `Location`, etc.).
5. **Custom Rows (`custom_rows.js`)**:
   * Each team's previous month's custom_rows are presented for confirmation that we are adding to the current month.
6. **Invoice Generation & Export (`invoice_preview.js`)**:
   * Final configurations are sent to Python to calculate Main Charge, Fees, and loggedexpense totals.
   * The formatted Sage  CSV preview is displayed in a final Tabulator grid.
   * User clicks "Download CSV", triggering `pywebview`'s native file save dialog.

## Dependencies

*   **Tabulator (JS):** Used extensively for interactive, selectable data grids with sorting, filtering, and inline editing.
*   **pywebview API:** All data fetching, caching, and heavy data processing are delegated to the Python backend via `window.pywebview.api.<method_name>()`.
