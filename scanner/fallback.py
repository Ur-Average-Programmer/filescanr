from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .models import ScanConfig, ScanResult

CHUNK_SIZE = 4 * 1024 * 1024   # 4 MB
OVERLAP = 256                   # bytes overlap between chunks
BINARY_CHECK_SIZE = 512


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_CHECK_SIZE)
        return b"\x00" in chunk
    except OSError:
        return False


def _search_file(
    file_path: str,
    patterns: list[str],
    case_sensitive: bool,
    match_mode: str,
    skip_binary: bool,
) -> list[tuple[str, int, list[str]]]:
    """Return list of (match_line, line_number, matched_strings)."""
    if skip_binary and _is_binary(file_path):
        return []

    if not case_sensitive:
        cmp_patterns = [p.lower() for p in patterns]
    else:
        cmp_patterns = patterns

    results = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            prev_tail = ""
            line_offset = 0

            while True:
                raw = f.read(CHUNK_SIZE)
                if not raw:
                    break

                block = prev_tail + raw
                lines = block.splitlines(keepends=True)

                # Keep the last partial line as overlap for next iteration
                if not raw.endswith(("\n", "\r")):
                    prev_tail = lines[-1] if lines else ""
                    lines = lines[:-1]
                else:
                    prev_tail = ""

                for i, line in enumerate(lines):
                    stripped = line.rstrip("\r\n")
                    cmp_line = stripped.lower() if not case_sensitive else stripped
                    matched = [
                        patterns[j]
                        for j, p in enumerate(cmp_patterns)
                        if p in cmp_line
                    ]
                    if match_mode == "all":
                        if len(matched) == len(patterns):
                            results.append((stripped, line_offset + i + 1, matched))
                    else:
                        if matched:
                            results.append((stripped, line_offset + i + 1, matched))

                line_offset += len(lines)

    except (PermissionError, OSError):
        pass

    return results


def python_search(
    root: str,
    config: ScanConfig,
    stop_event=None,
) -> Generator[ScanResult, None, None]:
    cs = config.filters.content_search
    perf = config.performance
    filters = config.filters

    import fnmatch
    pattern = filters.filename_pattern or "*"
    max_bytes = perf.max_file_size_mb * 1024 * 1024

    date_from_ts = filters.date_from.timestamp() if filters.date_from else None
    date_to_ts = filters.date_to.timestamp() if filters.date_to else None

    stack = [root]
    pending_futures = {}

    with ThreadPoolExecutor(max_workers=perf.max_threads) as pool:
        files_checked = 0

        while stack or pending_futures:
            # Drain the directory stack and submit file tasks
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as it:
                        for entry in it:
                            if stop_event and stop_event.is_set():
                                return
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                if not fnmatch.fnmatch(entry.name, pattern):
                                    continue
                                try:
                                    stat = entry.stat()
                                except OSError:
                                    continue
                                if stat.st_size > max_bytes:
                                    continue
                                mtime = stat.st_mtime
                                if date_from_ts and mtime < date_from_ts:
                                    continue
                                if date_to_ts and mtime > date_to_ts:
                                    continue

                                if cs.enabled and cs.strings:
                                    fut = pool.submit(
                                        _search_file,
                                        entry.path,
                                        cs.strings,
                                        cs.case_sensitive,
                                        cs.match_mode,
                                        perf.skip_binary,
                                    )
                                    pending_futures[fut] = (entry.path, entry.name, stat)
                                else:
                                    # filename/date match only
                                    modified = datetime.fromtimestamp(
                                        stat.st_mtime, tz=timezone.utc
                                    )
                                    yield ScanResult(
                                        path=entry.path,
                                        filename=entry.name,
                                        modified=modified,
                                        size_bytes=stat.st_size,
                                        source="file_share",
                                        match_strings=[],
                                    )

                                files_checked += 1
                except PermissionError:
                    pass
                except OSError:
                    pass

            # Yield completed futures
            done = [f for f in list(pending_futures) if f.done()]
            for fut in done:
                file_path, filename, stat = pending_futures.pop(fut)
                try:
                    hits = fut.result()
                except Exception:
                    hits = []

                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                for match_line, line_num, matched_strings in hits:
                    yield ScanResult(
                        path=file_path,
                        filename=filename,
                        modified=modified,
                        size_bytes=stat.st_size,
                        source="file_share",
                        match_line=match_line,
                        match_line_number=line_num,
                        match_strings=matched_strings,
                    )

            if not done and pending_futures:
                import time
                time.sleep(0.05)
