import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path(__file__).resolve().parent / "programfiles"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = self.cache_dir / "DEPARTMENT_NAME_cache.db"
        self.sqlite_engine = create_engine(f"sqlite:///{self.sqlite_path}")
        logger.debug(f"CacheManager initialized at: {self.cache_dir}")

    def _sanitize_filename(self, name: str) -> str:
        return name.replace(" ", "_").replace("/", "_").replace("\\", "_")

    def get_cached_json(self, key: str) -> Any | None:
        safe_key = self._sanitize_filename(key)
        file_path = self.cache_dir / f"cached_{safe_key}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Cache HIT for key '{key}' at path: {file_path}")
                    return data
            except (json.JSONDecodeError, OSError) as e:
                logger.exception(
                    f"Cache read error for key '{key}' at path {file_path}. Error: {e}"
                )
                return None
        logger.info(f"Cache MISS for key '{key}' at path: {file_path}")
        return None

    def set_cached_json(self, key: str, data: Any) -> None:
        safe_key = self._sanitize_filename(key)
        file_path = self.cache_dir / f"cached_{safe_key}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(
                f"Successfully wrote cache for key '{key}' to path: {file_path}"
            )
        except Exception as e:
            logger.exception(
                f"Failed to write cache for key '{key}' at path: {file_path}. Error: {e}",
                exc_info=True,
            )

    def clear_cache_item(self, key: str) -> bool:
        """Removes a specific cached file by key. Returns True if deleted, False if not found."""
        safe_key = self._sanitize_filename(key)
        file_path = self.cache_dir / f"cached_{safe_key}.json"
        if file_path.exists():
            logger.info(f"Cleared cache item for key '{key}' (Path: {file_path})")
            file_path.unlink()
            return True
        return False

    def clear_all_cache(self) -> None:
        """Deletes all matching cached JSON files and SQLite databases without touching the directory itself."""
        # Close open connections in the pool so Windows allows file deletion
        if hasattr(self, "sqlite_engine") and self.sqlite_engine:
            self.sqlite_engine.dispose()

        # Collect JSON cache files and SQLite DB files (including WAL/journal sidecars)
        patterns = ("cached_*.json", "*.db", "*.db-wal", "*.db-shm")
        cached_files = [
            file_path
            for pattern in patterns
            for file_path in self.cache_dir.glob(pattern)
        ]

        count = 0
        for file_path in cached_files:
            if file_path.is_file():
                try:
                    file_path.unlink()
                    count += 1
                except OSError as e:
                    logger.warning(f"Failed to delete cache file '{file_path}': {e}")

        logger.info(f"Cleared all cache files. Total items deleted: {count}")

    # TODO: split this into its own class, SqliteCacheManager
    # --- SQLite Cache Methods ---
    def sync_DEPARTMENT_NAME_loggedexpense(self, remote_engine: Engine) -> None:

        # TODO: move keys to enum
        # if self._is_sync_fresh("last_default_loggedexpense_sync", max_age_hours=72):
        #     logger.info(
        #         "DEPARTMENT_NAME cache is fresh (synced within past 72 hours). Skipping sync."
        #     )
        #     return

        logger.info(
            "Syncing fresh DEPARTMENT_NAME tables from remote database to SQLite cache..."
        )

        types_sql = text("""
            SELECT Id, ItemId, Memo, SoDocumentEntryClassId, [Location]
            FROM dbo.SageInvoiceLineItemTypes
        """)

        rels_sql = text("""
            SELECT Id, LoggedExpenseName, SageInvoiceLineItemTypeId, IsActive
            FROM dbo.DefaultLoggedExpenseSageInvoiceLineItemTypeRelationships
        """)

        with remote_engine.connect() as conn:
            types_df = pd.read_sql(types_sql, con=conn)
            rels_df = pd.read_sql(rels_sql, con=conn)

        with self.sqlite_engine.begin() as sqlite_conn:
            types_df.to_sql(
                "SageInvoiceLineItemTypes",
                con=sqlite_conn,
                if_exists="replace",
                index=False,
            )
            rels_df.to_sql(
                "DefaultLoggedExpenseSageInvoiceLineItemTypeRelationships",
                con=sqlite_conn,
                if_exists="replace",
                index=False,
            )
            self._update_sync_timestamps(conn=sqlite_conn, keys=['last_default_loggedexpense_sync', 'last_sageinvoicelineitemtypes_sync'])

        logger.info("Successfully synced DEPARTMENT_NAME tables to SQLite cache.")

    def _is_sync_fresh(self, key, max_age_hours: int = 72) -> bool:
        """Returns True if the SQLite cache was updated within max_age_hours."""
        if not self.sqlite_path.exists():
            return False

        try:
            with self.sqlite_engine.connect() as conn:
                # Check if metadata table exists and read timestamp
                result = conn.execute(
                    text(f"SELECT value FROM _cache_metadata WHERE key = '{key}'")
                ).fetchone()

                if not result or not result[0]:
                    return False

                last_sync_time = datetime.fromisoformat(result[0])
                now = datetime.now(timezone.utc)

                return (now - last_sync_time) < timedelta(hours=max_age_hours)
        except Exception as e:
            logger.error(f"Cache freshness check skipped due to error: {e}")
            return False

    def _update_sync_timestamps(self, conn: Connection, keys: str | list[str]) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        key_list = [keys] if isinstance(keys, str) else keys

        upsert_sql = text("""
            INSERT INTO _cache_metadata (key, value) 
            VALUES (:key, :now_utc)
            ON CONFLICT(key) DO UPDATE SET 
                value = excluded.value;
        """)

        params = [{"key": k, "now_utc": now_utc} for k in key_list]

        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS _cache_metadata (key TEXT PRIMARY KEY, value TEXT);"
            )
        )
        conn.execute(upsert_sql, params)