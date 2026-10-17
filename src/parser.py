"""
Log Parser & Analytics Module for Microservice Distributed Log Triage.

Designed for batch triage of distributed system logs:
- Extracts timestamps, service names, log levels (INFO, WARN, ERROR), trace/span IDs, messages.
- Groups and classifies common microservice error types with regex.
- Aggregates metrics and time-series for dashboard visualization.
- Handles empty files, corrupt lines, and edge cases gracefully.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


# Primary regex for standard distributed microservice logs:
# Example: 2026-10-17 08:30:01.120 [api-gateway] [INFO] [trace_id=tr-1001, span_id=sp-001] Message
REGEX_DISTRIBUTED = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?:\[(?P<service>[a-zA-Z0-9_\-\.]+)\]\s+)?"
    r"\[(?P<level>INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|DEBUG)\]\s*"
    r"(?:\[trace_id=(?P<trace_id>[a-zA-Z0-9_\-]+)(?:,\s*span_id=(?P<span_id>[a-zA-Z0-9_\-]+))?\]\s*)?"
    r"(?P<message>.*)$",
    re.IGNORECASE,
)

# Secondary regex fallback for standard application logs (e.g. 2026-10-17 08:30:01 ERROR service: message)
REGEX_FALLBACK = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?:[-|:]\s*)?"
    r"(?:(?P<service>[a-zA-Z0-9_\-\.]+)\s+)?[-|:]?\s*"
    r"(?P<level>INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|DEBUG)\s+[-|:]?\s*"
    r"(?P<message>.*)$",
    re.IGNORECASE,
)

# Regex pattern catalogue for error classification
ERROR_SIGNATURES: List[Tuple[str, re.Pattern]] = [
    (
        "Database / Connection Error",
        re.compile(
            r"(ConnectionRefused|ConnectionTimedOut|DatabaseConnection|DBConnection|postgres|mysql|mongo|psycopg2|SqlException)",
            re.IGNORECASE,
        ),
    ),
    (
        "Payment Gateway Timeout",
        re.compile(
            r"(PaymentGatewayTimeout|Stripe upstream gateway timed out|Payment.*timeout)",
            re.IGNORECASE,
        ),
    ),
    (
        "Circuit Breaker Tripped",
        re.compile(
            r"(CircuitBreakerOpen|Circuit breaker.*is OPEN|Fast-failing request)",
            re.IGNORECASE,
        ),
    ),
    (
        "Memory Exhaustion (OOM)",
        re.compile(
            r"(OutOfMemory|OOM|heap space|high memory watermark|memory exhausted)",
            re.IGNORECASE,
        ),
    ),
    (
        "Null Pointer / Reference Error",
        re.compile(
            r"(NullPointer|NoneType.*has no attribute|null object reference|undefined is not an object)",
            re.IGNORECASE,
        ),
    ),
    (
        "Rate Limiting / Throttling",
        re.compile(
            r"(RateLimitExceeded|Too Many Requests|HTTP 429|exceeded threshold)",
            re.IGNORECASE,
        ),
    ),
    (
        "Message Broker / Kafka Error",
        re.compile(
            r"(KafkaBrokerUnavailable|Kafka|RabbitMQ|broker leader unavailable|topic.*unavailable)",
            re.IGNORECASE,
        ),
    ),
    (
        "Authentication / JWT Error",
        re.compile(
            r"(JWTValidationFailed|Token signature expired|Unauthorized|OAuth.*error|Auth.*failed)",
            re.IGNORECASE,
        ),
    ),
    (
        "HTTP 5xx Gateway Error",
        re.compile(
            r"(500 Internal Server Error|502 Bad Gateway|503 Service Unavailable|504 Gateway Timeout)",
            re.IGNORECASE,
        ),
    ),
    (
        "Generic Timeout",
        re.compile(r"(timed out|timeout|DeadlineExceeded)", re.IGNORECASE),
    ),
]


def classify_error(message: str, level: str) -> str:
    """
    Classify an error or warning message into a high-level root-cause category.
    Returns 'None' for non-error/warning entries.
    """
    normalized_level = level.upper()
    if normalized_level not in {"ERROR", "FATAL", "CRITICAL", "WARN", "WARNING"}:
        return "N/A (Normal Operation)"

    for category, pattern in ERROR_SIGNATURES:
        if pattern.search(message):
            return category

    if normalized_level in {"ERROR", "FATAL", "CRITICAL"}:
        return "Unclassified Application Error"
    return "General System Warning"


def normalize_level(raw_level: Optional[str]) -> str:
    """Normalize raw log level to standard INFO, WARN, ERROR, DEBUG, or UNKNOWN."""
    if not raw_level:
        return "UNKNOWN"
    lvl = raw_level.strip().upper()
    if lvl in {"WARN", "WARNING"}:
        return "WARN"
    if lvl in {"FATAL", "CRITICAL"}:
        return "ERROR"
    if lvl in {"INFO", "ERROR", "DEBUG"}:
        return lvl
    return "OTHER"


def parse_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single log line into structured fields.
    Returns None if line is blank or whitespace.
    """
    clean_line = line.strip()
    if not clean_line or clean_line.startswith("#"):
        return None

    match = REGEX_DISTRIBUTED.match(clean_line)
    if match:
        data = match.groupdict()
        level = normalize_level(data.get("level"))
        message = (data.get("message") or "").strip()
        service = (data.get("service") or "unspecified-service").strip()
        trace_id = data.get("trace_id") or "N/A"
        span_id = data.get("span_id") or "N/A"
        timestamp = data.get("timestamp")
        error_category = classify_error(message, level)

        return {
            "timestamp": timestamp,
            "service": service,
            "level": level,
            "trace_id": trace_id,
            "span_id": span_id,
            "message": message,
            "error_category": error_category,
            "raw_line": clean_line,
        }

    # Try fallback regex
    fallback_match = REGEX_FALLBACK.match(clean_line)
    if fallback_match:
        data = fallback_match.groupdict()
        level = normalize_level(data.get("level"))
        message = (data.get("message") or "").strip()
        service = (data.get("service") or "default-service").strip()
        timestamp = data.get("timestamp")
        error_category = classify_error(message, level)

        return {
            "timestamp": timestamp,
            "service": service,
            "level": level,
            "trace_id": "N/A",
            "span_id": "N/A",
            "message": message,
            "error_category": error_category,
            "raw_line": clean_line,
        }

    # Unstructured/Raw fallback so user data is never silently dropped
    return {
        "timestamp": None,
        "service": "unknown",
        "level": "UNSTRUCTURED",
        "trace_id": "N/A",
        "span_id": "N/A",
        "message": clean_line,
        "error_category": "Unstructured Log",
        "raw_line": clean_line,
    }


def parse_logs(log_content: str) -> Tuple[pd.DataFrame, int]:
    """
    Parse raw string log content into a pandas DataFrame.
    Returns (DataFrame, total_raw_lines).
    Handles empty content and invalid inputs gracefully.
    """
    empty_columns = [
        "timestamp",
        "service",
        "level",
        "trace_id",
        "span_id",
        "message",
        "error_category",
        "raw_line",
    ]

    if not log_content or not isinstance(log_content, str) or not log_content.strip():
        return pd.DataFrame(columns=empty_columns), 0

    lines = log_content.splitlines()
    total_raw_lines = len(lines)
    parsed_records: List[Dict[str, Any]] = []

    for line in lines:
        parsed = parse_line(line)
        if parsed:
            parsed_records.append(parsed)

    if not parsed_records:
        return pd.DataFrame(columns=empty_columns), total_raw_lines

    df = pd.DataFrame(parsed_records)

    # Convert timestamps to datetime where possible
    if "timestamp" in df.columns and not df["timestamp"].isnull().all():
        df["parsed_timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        df["parsed_timestamp"] = pd.NaT

    return df, total_raw_lines


def compute_metrics(df: pd.DataFrame, total_raw_lines: int = 0) -> Dict[str, Any]:
    """
    Calculate summary metrics including counts of INFO, WARN, ERROR, and error rate.
    Safely handles empty DataFrames.
    """
    if df.empty:
        return {
            "total_lines": total_raw_lines,
            "parsed_logs": 0,
            "info_count": 0,
            "warn_count": 0,
            "error_count": 0,
            "debug_count": 0,
            "unstructured_count": 0,
            "error_rate_pct": 0.0,
            "top_affected_service": "N/A",
            "top_error_category": "N/A",
        }

    level_counts = df["level"].value_counts().to_dict()
    info_count = level_counts.get("INFO", 0)
    warn_count = level_counts.get("WARN", 0)
    error_count = level_counts.get("ERROR", 0)
    debug_count = level_counts.get("DEBUG", 0)
    unstructured_count = level_counts.get("UNSTRUCTURED", 0)

    total_parsed = len(df)
    error_rate = (error_count / total_parsed * 100.0) if total_parsed > 0 else 0.0

    # Top affected service for errors
    errors_df = df[df["level"] == "ERROR"]
    if not errors_df.empty:
        top_service = errors_df["service"].mode().iloc[0]
        # Most frequent error category (excluding N/A)
        err_cats = errors_df[errors_df["error_category"] != "N/A (Normal Operation)"]
        top_error_category = (
            err_cats["error_category"].mode().iloc[0]
            if not err_cats.empty
            else "Unclassified"
        )
    else:
        top_service = "None"
        top_error_category = "None"

    return {
        "total_lines": total_raw_lines or total_parsed,
        "parsed_logs": total_parsed,
        "info_count": info_count,
        "warn_count": warn_count,
        "error_count": error_count,
        "debug_count": debug_count,
        "unstructured_count": unstructured_count,
        "error_rate_pct": round(error_rate, 2),
        "top_affected_service": top_service,
        "top_error_category": top_error_category,
    }


def get_error_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns DataFrame of error categories and their occurrence counts.
    """
    if df.empty:
        return pd.DataFrame(columns=["Error Category", "Count"])

    errors_df = df[df["level"].isin(["ERROR", "WARN"])]
    if errors_df.empty:
        return pd.DataFrame(columns=["Error Category", "Count"])

    counts = (
        errors_df["error_category"]
        .value_counts()
        .reset_index()
    )
    counts.columns = ["Error Category", "Count"]
    return counts


def get_service_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns counts of logs by service and level.
    """
    if df.empty:
        return pd.DataFrame(columns=["service", "level", "count"])

    grouped = (
        df.groupby(["service", "level"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    return grouped
