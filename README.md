# SQL Server - Google Sheet - Sage Intacct - Invoice Generator

A full desktop app utilizing only Python libraries to generate invoices into Sage Intacct's proprietary CSV upload format, drawing from data from Google Sheets and SQL Server.

## Developer's Note

Thank you for checking out my repo. I had to extract and redact a lot of content throughout this project, so some things might be broken here or there. While AI was used for scaffolding and debugging, all the logic, design, and layout was my own. - Joseph Chang

## Back-End Engine & API Architecture

This repository contains a Python back-end engine in `\core` and a vanilla JS front-end in `web` for powering a desktop invoice generation application. Built on `pywebview`, SQL-Alchemy, and Pandas, it manages external Google Sheets integration, multi-database SQL querying (with the latest SQL Server version), fuzzy name matching, local caching, and Sage CSV export formatting.


## Core Modules

| File | Primary Responsibility |
| :--- | :--- |
| `main.py` | App entry point and `pywebview` initializer. Exposes the JS-to-Python bridge (`API` class) for UI interaction. |
| `cache_manager.py` | Manages local JSON file caches and local SQLite database sync (`db_c_cache.db`) for remote DB C tables. |
| `db.py` | Stores `SQLAlchemy` connections to core, payments, and db_cs. |
| `gsheet.py` | Requests client wrapper for Google Sheets Web API integration to pull data from Google Sheet with invoices with JSON payload validation. |
| `sageid_to_teamid.py` | Resolves `SageId` to platform `TeamId` via Database C, Database B exact matching, and T-SQL Jaro-Winkler fuzzy matching. |
| `teamname_validation.py` | Validates `TeamName` between Google Sheet with invoices and Database B. Requires SageId-TeamId from `sageid_to_teamid.py`|
| `inv_main_charge.py` | Executes chunked T-SQL queries extracting MAIN_CHARGE and REDACTED calculations. |
| `inv_fees.py` | Queries monthly fees and fee credits per team. |
| `inv_loggedexpense.py` | Extracts Expense Summary Logged Expenses (loggedexpense) and default Sage line-item mapping relationships. |
| `inv_custom_rows.py` | Extracts Custom Rows that carry over month-to-month not saved in the Core platform. |
| `inv.py` | Unifies and normalizes MAIN_CHARGE, fee, and loggedexpense datasets into Sage-compliant header/line item structures. |
| `logging_config.py` | Configures centralized console logging and rotating file logging (`logs/app.log`, 5MB max, 3 backups). |
| `README_js.md` | **Check this file for front-end architecture information.** |

## Data Pipeline & Workflow

1. **Customer & ID Mapping**:
   * Fetches customer data from Google Sheets via `GSheetClient`.
   * Maps client `SageId` to platform `TeamId` using local cache (`sageid_teamids`) if exists.
   * Missing ID relationships trigger Database C lookups followed by Core DB to extract exact name matches
   * Mismatches check Core DB with Jaro-Winkler fuzzy name matching to get top 3 possible ID matches based on name.
2. **Data Extraction**:
   * Executes SQL queries across `db_b_engine` (for MAIN_CHARGE, Fees, and loggedexpense data) and `db_c_engine` (for mapping default sage data).
   * Processes MAIN_CHARGE queries in chunks (200 teams per batch) to manage payload sizes.
         * May want to consider pushing consolidated MAIN_CHARGE into Database C after PRs are locked
3. **Normalization & Mapping**:
   * Standardizes datasets from Core into uniform DataFrames (`TeamId`, `Amount`, `sage_lineitem_key`).
   * Joins line item keys (`ItemId`, `Memo`, `Location`, `SoDocumentEntryClassId`) based on Logged Expense default relationships.
4. **Export Generation**:
   * Formats header rows (Invoice Date on the 5th, Due Date on the 15th, Net 10 terms) and line items.
   * Invokes native OS file dialog via `pywebview` to export structured CSVs for Sage  ingestion.

## Environment Variables & Setup

Required environment variables must be declared in a `.env` file in the project root. See `.env_template` for a sample.
The ODBC Driver 18 for SQL Server driver is used in this project, but can be updated in the `db.py` file to match the database needed. The project also depends on some stored procedures in the database. 
This project expects a Google Apps Script to expose a Google Sheet protected by a private key.

Stored procedures and Apps Scripts may be added to this repo at a future date.

# Licensing

**Copyright © 2026 Joseph Chang. All Rights Reserved.**

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

### What this means:
* **Allowed:** You may view, clone, study, and run this code for personal, educational, or non-commercial research purposes.
* **Prohibited:** You may not use this code or its algorithms for commercial purposes, sell it, or redistribute it as part of a commercial product without explicit permission.

For the full license terms, see the [LICENSE](LICENSE) file in this repository.