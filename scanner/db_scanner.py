from __future__ import annotations
from datetime import datetime, timezone
from typing import Generator

from .models import ScanConfig, ScanResult


def scan_database_logs(
    connection_string: str,
    log_table: str,
    timestamp_column: str,
    message_column: str,
    config: ScanConfig,
    stop_event=None,
) -> Generator[ScanResult, None, None]:
    try:
        import pyodbc
    except ImportError:
        return

    cs = config.filters.content_search
    filters = config.filters

    like_clauses = []
    params: list = []

    date_from = filters.date_from or datetime(2000, 1, 1, tzinfo=timezone.utc)
    date_to = filters.date_to or datetime(2100, 1, 1, tzinfo=timezone.utc)

    params.extend([date_from.isoformat(), date_to.isoformat()])

    if cs.enabled and cs.strings:
        like_clauses = [f"{message_column} LIKE ?" for _ in cs.strings]
        params.extend([f"%{s}%" for s in cs.strings])
        if cs.match_mode == "any":
            where_content = " OR ".join(like_clauses)
        else:
            where_content = " AND ".join(like_clauses)
        content_clause = f" AND ({where_content})"
    else:
        content_clause = ""

    query = (
        f"SELECT {timestamp_column}, {message_column} "
        f"FROM {log_table} "
        f"WHERE {timestamp_column} BETWEEN ? AND ?"
        f"{content_clause}"
    )

    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        cursor.execute(query, params)

        for row in cursor:
            if stop_event and stop_event.is_set():
                break

            ts_raw, message = row[0], str(row[1] or "")
            ts = None
            if ts_raw:
                try:
                    if isinstance(ts_raw, datetime):
                        ts = ts_raw.replace(tzinfo=timezone.utc)
                    else:
                        ts = datetime.fromisoformat(str(ts_raw)).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            matched: list[str] = []
            if cs.enabled and cs.strings:
                cmp_msg = message.lower() if not cs.case_sensitive else message
                for s in cs.strings:
                    cmp_s = s.lower() if not cs.case_sensitive else s
                    if cmp_s in cmp_msg:
                        matched.append(s)

            yield ScanResult(
                path=f"db://{log_table}",
                filename=log_table,
                modified=ts,
                size_bytes=None,
                source="database",
                match_line=message[:500],
                match_line_number=None,
                match_strings=matched,
            )

        cursor.close()
        conn.close()
    except Exception:
        pass
