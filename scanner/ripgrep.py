from __future__ import annotations
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .models import ScanConfig, ScanResult


def rg_available() -> bool:
    return shutil.which("rg") is not None


def rg_search(
    root: str,
    config: ScanConfig,
    stop_event=None,
) -> Generator[ScanResult, None, None]:
    cs = config.filters.content_search
    perf = config.performance

    cmd = [
        "rg",
        "--json",
        f"--threads={perf.max_threads}",
        "--after-context=0",
        "--before-context=0",
        f"--max-filesize={perf.max_file_size_mb}M",
    ]

    if not cs.case_sensitive:
        cmd.append("--ignore-case")

    pattern = config.filters.filename_pattern
    if pattern and pattern != "*":
        cmd.extend(["--iglob", pattern])

    # Skip common binary extensions
    cmd.extend(["-g", "!*.{exe,dll,bin,so,dylib,zip,gz,tar,7z,rar,jpg,jpeg,png,gif,bmp,mp4,mp3,avi,pdf,docx,xlsx}"])

    if cs.match_mode == "all" and len(cs.strings) > 1:
        # rg doesn't natively AND patterns; chain calls or use lookahead
        # Use the first pattern and post-filter for "all" mode
        cmd.extend(["-e", cs.strings[0]])
    else:
        for s in cs.strings:
            cmd.extend(["-e", s])

    cmd.append(root)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        for raw_line in proc.stdout:
            if stop_event and stop_event.is_set():
                proc.terminate()
                break

            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")
            if msg_type == "match":
                data = obj.get("data", {})
                file_path = data.get("path", {}).get("text", "")
                lines_obj = data.get("lines", {})
                line_text = lines_obj.get("text", "").rstrip("\n")
                line_num = data.get("line_number")

                p = Path(file_path)
                try:
                    stat = p.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    size_bytes = stat.st_size
                except OSError:
                    modified = None
                    size_bytes = None

                # For "all" mode post-filter
                if cs.match_mode == "all" and len(cs.strings) > 1:
                    lower_line = line_text.lower() if not cs.case_sensitive else line_text
                    matched = [
                        s for s in cs.strings
                        if (s.lower() if not cs.case_sensitive else s) in lower_line
                    ]
                    if len(matched) < len(cs.strings):
                        continue
                else:
                    matched = cs.strings

                yield ScanResult(
                    path=file_path,
                    filename=p.name,
                    modified=modified,
                    size_bytes=size_bytes,
                    source="file_share",
                    match_line=line_text,
                    match_line_number=line_num,
                    match_strings=matched,
                )

            elif msg_type == "error":
                pass  # caller handles logging

        proc.wait()

    except FileNotFoundError:
        raise RuntimeError("ripgrep (rg) not found on PATH")
    except Exception as exc:
        raise RuntimeError(f"ripgrep error: {exc}") from exc
