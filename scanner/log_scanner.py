from __future__ import annotations
import subprocess
import sys
from datetime import datetime, timezone
from typing import Generator

from .models import ScanConfig, ScanResult
from .file_scanner import scan_path


def scan_system_logs(
    log_dir: str,
    config: ScanConfig,
    stop_event=None,
) -> Generator[ScanResult, None, None]:
    """Scan plain text log files in a directory."""
    for result in scan_path(log_dir, config, stop_event=stop_event, source="system_log"):
        result.source = "system_log"
        yield result


def scan_windows_event_logs(
    channels: list[str],
    config: ScanConfig,
    stop_event=None,
) -> Generator[ScanResult, None, None]:
    """Scan Windows Event Log channels using pywin32."""
    if sys.platform != "win32":
        return

    try:
        import win32evtlog
        import win32con
        import pywintypes
    except ImportError:
        return

    cs = config.filters.content_search
    search_strings = cs.strings if cs.enabled else []

    for channel in channels:
        if stop_event and stop_event.is_set():
            break
        try:
            hand = win32evtlog.OpenEventLog(None, channel)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            try:
                while True:
                    if stop_event and stop_event.is_set():
                        break
                    events = win32evtlog.ReadEventLog(hand, flags, 0)
                    if not events:
                        break
                    for ev in events:
                        ts = None
                        try:
                            ts = datetime.fromtimestamp(
                                int(ev.TimeGenerated), tz=timezone.utc
                            )
                        except Exception:
                            pass

                        if config.filters.date_from and ts and ts < config.filters.date_from:
                            continue
                        if config.filters.date_to and ts and ts > config.filters.date_to:
                            continue

                        message = str(ev.StringInserts or "")

                        matched: list[str] = []
                        if search_strings:
                            cmp_msg = message.lower() if not cs.case_sensitive else message
                            for s in search_strings:
                                cmp_s = s.lower() if not cs.case_sensitive else s
                                if cmp_s in cmp_msg:
                                    matched.append(s)
                            if cs.match_mode == "all" and len(matched) < len(search_strings):
                                continue
                            if cs.match_mode == "any" and not matched:
                                continue

                        yield ScanResult(
                            path=f"EventLog://{channel}",
                            filename=channel,
                            modified=ts,
                            size_bytes=None,
                            source="windows_event",
                            match_line=message[:500],
                            match_line_number=ev.RecordNumber,
                            match_strings=matched,
                        )
            finally:
                win32evtlog.CloseEventLog(hand)
        except Exception:
            pass


def scan_journald(
    config: ScanConfig,
    stop_event=None,
) -> Generator[ScanResult, None, None]:
    """Scan systemd journal via journalctl."""
    import json as _json

    cmd = ["journalctl", "--output=json", "--no-pager"]

    if config.filters.date_from:
        cmd.extend(["--since", config.filters.date_from.strftime("%Y-%m-%d %H:%M:%S")])
    if config.filters.date_to:
        cmd.extend(["--until", config.filters.date_to.strftime("%Y-%m-%d %H:%M:%S")])

    cs = config.filters.content_search
    search_strings = cs.strings if cs.enabled else []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in proc.stdout:
            if stop_event and stop_event.is_set():
                proc.terminate()
                break
            line = line.strip()
            if not line:
                continue
            try:
                entry = _json.loads(line)
            except _json.JSONDecodeError:
                continue

            message = entry.get("MESSAGE", "")
            ts = None
            try:
                usec = int(entry.get("__REALTIME_TIMESTAMP", 0))
                ts = datetime.fromtimestamp(usec / 1e6, tz=timezone.utc)
            except Exception:
                pass

            matched: list[str] = []
            if search_strings:
                cmp_msg = message.lower() if not cs.case_sensitive else message
                for s in search_strings:
                    cmp_s = s.lower() if not cs.case_sensitive else s
                    if cmp_s in cmp_msg:
                        matched.append(s)
                if cs.match_mode == "all" and len(matched) < len(search_strings):
                    continue
                if cs.match_mode == "any" and not matched:
                    continue

            yield ScanResult(
                path="journald://system",
                filename="journal",
                modified=ts,
                size_bytes=None,
                source="system_log",
                match_line=message[:500],
                match_line_number=None,
                match_strings=matched,
            )
        proc.wait()
    except FileNotFoundError:
        pass
    except Exception:
        pass
