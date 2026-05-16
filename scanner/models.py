from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ContentSearchConfig(BaseModel):
    enabled: bool = False
    strings: list[str] = Field(default_factory=list)
    case_sensitive: bool = False
    match_mode: Literal["any", "all"] = "any"


class FilterConfig(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    filename_pattern: str = "*"
    content_search: ContentSearchConfig = Field(default_factory=ContentSearchConfig)


class SourceConfig(BaseModel):
    type: Literal["file_share", "system_log", "windows_event", "database"]
    path: Optional[str] = None
    enabled: bool = True
    platform: Optional[str] = None
    event_channels: Optional[list[str]] = None
    connection_string: Optional[str] = None
    log_table: Optional[str] = None
    timestamp_column: Optional[str] = None
    message_column: Optional[str] = None


class PerformanceConfig(BaseModel):
    max_threads: int = 16
    max_file_size_mb: int = 500
    skip_binary: bool = True


class ScanConfig(BaseModel):
    name: str
    sources: list[SourceConfig] = Field(default_factory=list)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)


class ScanResult(BaseModel):
    path: str
    filename: str
    modified: Optional[datetime] = None
    size_bytes: Optional[int] = None
    source: str
    match_line: Optional[str] = None
    match_line_number: Optional[int] = None
    match_strings: list[str] = Field(default_factory=list)
