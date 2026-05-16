from __future__ import annotations
import fnmatch
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .models import ScanConfig, ScanResult

BINARY_CHECK_SIZE = 512


def _passes_date_filter(mtime: float, config: ScanConfig) -> bool:
    filters = config.filters
    if filters.date_from and mtime < filters.date_from.timestamp():
        return False
    if filters.date_to and mtime > filters.date_to.timestamp():
        return False
    return True


def scan_path(
    root: str,
    config: ScanConfig,
    stop_event=None,
    source: str = "file_share",
) -> Generator[ScanResult, None, None]:
    cs = config.filters.content_search
    perf = config.performance
    pattern = config.filters.filename_pattern or "*"
    max_bytes = perf.max_file_size_mb * 1024 * 1024

    use_rg = cs.enabled and cs.strings and shutil.which("rg") is not None

    if use_rg:
        from .ripgrep import rg_search
        yield from rg_search(root, config, stop_event=stop_event)
        return

    from .fallback import python_search
    yield from python_search(root, config, stop_event=stop_event)
