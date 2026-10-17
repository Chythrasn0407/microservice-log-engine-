"""
Unit and Integration Tests for Microservice Log Parser and Analytics Engine.
Covers log parsing, regex extraction, error classification, and edge cases.
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

# Add src to sys.path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from parser import (
    parse_line,
    parse_logs,
    classify_error,
    compute_metrics,
    get_error_distribution,
    get_service_breakdown,
)


def test_parse_valid_distributed_line():
    line = "2026-10-17 08:30:01.120 [api-gateway] [INFO] [trace_id=tr-1001, span_id=sp-001] Received incoming POST /login"
    result = parse_line(line)
    assert result is not None
    assert result["timestamp"] == "2026-10-17 08:30:01.120"
    assert result["service"] == "api-gateway"
    assert result["level"] == "INFO"
    assert result["trace_id"] == "tr-1001"
    assert result["span_id"] == "sp-001"
    assert "Received incoming POST /login" in result["message"]
    assert result["error_category"] == "N/A (Normal Operation)"


def test_parse_error_line_with_db_connection():
    line = "2026-10-17 08:30:17.300 [order-service] [ERROR] [trace_id=tr-1007, span_id=sp-017] ConnectionRefusedError: Unable to connect to postgres-cluster:5432"
    result = parse_line(line)
    assert result is not None
    assert result["level"] == "ERROR"
    assert result["service"] == "order-service"
    assert result["error_category"] == "Database / Connection Error"


def test_error_classification_signatures():
    assert classify_error("PaymentGatewayTimeoutException: Stripe timed out", "ERROR") == "Payment Gateway Timeout"
    assert classify_error("CircuitBreakerOpenException: Circuit breaker is OPEN", "ERROR") == "Circuit Breaker Tripped"
    assert classify_error("OutOfMemoryError: Java heap space", "ERROR") == "Memory Exhaustion (OOM)"
    assert classify_error("NullPointerException: userContext is null", "ERROR") == "Null Pointer / Reference Error"
    assert classify_error("RateLimitExceeded: IP 192.168.1.1 exceeded threshold", "WARN") == "Rate Limiting / Throttling"
    assert classify_error("KafkaBrokerUnavailable: broker leader down", "ERROR") == "Message Broker / Kafka Error"
    assert classify_error("JWTValidationFailed: Token signature expired", "ERROR") == "Authentication / JWT Error"
    assert classify_error("502 Bad Gateway: Upstream pod unreachable", "ERROR") == "HTTP 5xx Gateway Error"
    assert classify_error("Some random unknown exception occurred", "ERROR") == "Unclassified Application Error"
    assert classify_error("User logged in successfully", "INFO") == "N/A (Normal Operation)"


def test_empty_string_input_handling():
    df, total = parse_logs("")
    assert df.empty
    assert total == 0
    metrics = compute_metrics(df, total)
    assert metrics["parsed_logs"] == 0
    assert metrics["error_count"] == 0
    assert metrics["info_count"] == 0
    assert metrics["warn_count"] == 0
    assert metrics["error_rate_pct"] == 0.0


def test_whitespace_and_comments():
    sample = "   \n\n# This is a comment\n   \n"
    df, total = parse_logs(sample)
    assert df.empty
    assert total == 4


def test_malformed_unstructured_line():
    line = "Random unformatted system crash text without timestamp or level"
    df, total = parse_logs(line)
    assert len(df) == 1
    assert total == 1
    assert df.iloc[0]["level"] == "UNSTRUCTURED"
    assert df.iloc[0]["error_category"] == "Unstructured Log"
    assert df.iloc[0]["raw_line"] == line


def test_level_counts_and_metrics():
    log_data = (
        "2026-10-17 08:30:01 [service-a] [INFO] Request started\n"
        "2026-10-17 08:30:02 [service-a] [INFO] Request completed\n"
        "2026-10-17 08:30:03 [service-b] [WARN] Cache miss\n"
        "2026-10-17 08:30:04 [service-c] [ERROR] ConnectionRefusedError: postgres down\n"
    )
    df, total = parse_logs(log_data)
    assert len(df) == 4
    metrics = compute_metrics(df, total)
    assert metrics["info_count"] == 2
    assert metrics["warn_count"] == 1
    assert metrics["error_count"] == 1
    assert metrics["error_rate_pct"] == 25.0
    assert metrics["top_affected_service"] == "service-c"


def test_service_breakdown():
    log_data = (
        "2026-10-17 08:30:01 [auth] [INFO] msg 1\n"
        "2026-10-17 08:30:02 [auth] [ERROR] OutOfMemoryError msg 2\n"
        "2026-10-17 08:30:03 [payment] [ERROR] PaymentGatewayTimeoutException msg 3\n"
    )
    df, _ = parse_logs(log_data)
    breakdown = get_service_breakdown(df)
    assert not breakdown.empty
    auth_errors = breakdown[(breakdown["service"] == "auth") & (breakdown["level"] == "ERROR")]["count"].iloc[0]
    assert auth_errors == 1


def test_sample_microservices_log_file():
    sample_file = Path(__file__).resolve().parent.parent / "data" / "sample_microservices.log"
    assert sample_file.exists()
    content = sample_file.read_text(encoding="utf-8")
    df, total = parse_logs(content)
    assert total > 20
    assert not df.empty
    metrics = compute_metrics(df, total)
    assert metrics["info_count"] > 0
    assert metrics["warn_count"] > 0
    assert metrics["error_count"] > 0
    # Ensure error categories are properly grouped
    err_dist = get_error_distribution(df)
    assert not err_dist.empty
    assert "Database / Connection Error" in err_dist["Error Category"].values
