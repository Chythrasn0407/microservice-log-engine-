"""
Microservice Distributed Log Anomaly & Error Triage Engine
Streamlit Web Dashboard
"""

import os
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from parser import (
    parse_logs,
    compute_metrics,
    get_error_distribution,
    get_service_breakdown,
)

# Page configuration
st.set_page_config(
    page_title="Microservice Log Anomaly & Error Triage Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Default sample log path
SAMPLE_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_microservices.log"


def load_file_content(uploaded_file) -> str:
    """Safely decode uploaded file content."""
    try:
        bytes_data = uploaded_file.read()
        return bytes_data.decode("utf-8", errors="replace")
    except Exception as exc:
        st.error(f"Failed to read file: {exc}")
        return ""


def main():
    # Header Banner
    st.title("🛡️ Microservice Distributed Log Anomaly & Error Triage Engine")
    st.caption("DevOps Capstone Project • Use Case 9 • Python 3.11 + Streamlit + pandas + Plotly")

    # Scope & Disclaimer Alert
    st.info(
        "ℹ️ **Project Scope Note**: This application is a **batch log anomaly and triage engine** "
        "designed to inspect, categorize, and triage distributed microservice log files. "
        "It uses sample and uploaded log dumps; it does **not** provide live streaming real-time monitoring.",
        icon="ℹ️",
    )

    # Sidebar: Data Source Selection
    st.sidebar.header("📁 Data Source Selection")
    data_source = st.sidebar.radio(
        "Choose Log Input Source:",
        ("Use Built-in Sample Logs", "Upload Custom Log File"),
        index=0,
    )

    raw_log_content = ""
    source_description = ""

    if data_source == "Use Built-in Sample Logs":
        if SAMPLE_LOG_PATH.exists():
            with open(SAMPLE_LOG_PATH, "r", encoding="utf-8") as f:
                raw_log_content = f.read()
            source_description = f"Built-in Sample Logs (`{SAMPLE_LOG_PATH.name}`)"
        else:
            st.error(f"Sample log file not found at: `{SAMPLE_LOG_PATH}`")
    else:
        uploaded_file = st.sidebar.file_uploader(
            "Upload Log File (.log or .txt)",
            type=["log", "txt"],
            help="Select a distributed microservice log file to analyze.",
        )
        if uploaded_file is not None:
            raw_log_content = load_file_content(uploaded_file)
            source_description = f"Uploaded File (`{uploaded_file.name}`)"
        else:
            st.sidebar.info("Awaiting file upload. Select a file or switch to 'Use Built-in Sample Logs'.")

    # Graceful handling for empty or missing input
    if not raw_log_content.strip():
        if data_source == "Upload Custom Log File":
            st.warning("⚠️ No log content loaded. Please upload a `.log` or `.txt` file via the sidebar to begin triage.")
        return

    # Parse logs
    with st.spinner("Parsing logs and clustering error anomalies..."):
        df, total_raw_lines = parse_logs(raw_log_content)

    if df.empty:
        st.warning("⚠️ The provided file was empty or contained no readable lines. Please upload a valid log file.")
        return

    # Compute high-level metrics
    metrics = compute_metrics(df, total_raw_lines)

    st.subheader(f"📊 Triage Summary — {source_description}")

    # Top KPI Metrics Cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    with kpi_col1:
        st.metric("Total Logs", f"{metrics['parsed_logs']:,}")
    with kpi_col2:
        st.metric("INFO Messages", f"{metrics['info_count']:,}")
    with kpi_col3:
        st.metric("WARN Messages", f"{metrics['warn_count']:,}")
    with kpi_col4:
        st.metric("ERROR Messages", f"{metrics['error_count']:,}", delta=f"{metrics['error_rate_pct']}% error rate", delta_color="inverse")
    with kpi_col5:
        st.metric("Top Faulting Service", metrics["top_affected_service"])

    # Sidebar Filters
    st.sidebar.header("🔍 Filter Log Data")
    all_services = sorted(df["service"].dropna().unique().tolist())
    selected_services = st.sidebar.multiselect(
        "Filter by Microservice:",
        options=all_services,
        default=all_services,
    )

    all_levels = sorted(df["level"].dropna().unique().tolist())
    selected_levels = st.sidebar.multiselect(
        "Filter by Log Level:",
        options=all_levels,
        default=all_levels,
    )

    search_query = st.sidebar.text_input("Search Log Message / Trace ID:", "")

    # Apply filters
    filtered_df = df[
        (df["service"].isin(selected_services)) &
        (df["level"].isin(selected_levels))
    ]

    if search_query.strip():
        query = search_query.strip()
        filtered_df = filtered_df[
            filtered_df["message"].str.contains(query, case=False, na=False) |
            filtered_df["trace_id"].str.contains(query, case=False, na=False)
        ]

    st.markdown("---")

    # Visualizations Row 1
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("### 🎯 Log Level Distribution")
        level_counts = df["level"].value_counts().reset_index()
        level_counts.columns = ["Level", "Count"]

        color_map = {
            "INFO": "#2ca02c",
            "WARN": "#ff7f0e",
            "ERROR": "#d62728",
            "DEBUG": "#1f77b4",
            "UNSTRUCTURED": "#7f7f7f",
        }

        fig_donut = px.pie(
            level_counts,
            values="Count",
            names="Level",
            hole=0.45,
            color="Level",
            color_discrete_map=color_map,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=320)
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_chart2:
        st.markdown("### 🏢 Error & Warning Count by Microservice")
        err_warn_df = df[df["level"].isin(["ERROR", "WARN"])]
        if not err_warn_df.empty:
            service_err = (
                err_warn_df.groupby(["service", "level"])
                .size()
                .reset_index(name="Count")
            )
            fig_service = px.bar(
                service_err,
                x="service",
                y="Count",
                color="level",
                color_discrete_map={"ERROR": "#d62728", "WARN": "#ff7f0e"},
                barmode="stack",
                labels={"service": "Microservice", "Count": "Issues Detected"},
            )
            fig_service.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=320)
            st.plotly_chart(fig_service, use_container_width=True)
        else:
            st.success("🎉 No ERROR or WARN messages found across microservices!")

    # Visualizations Row 2
    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        st.markdown("### 🧩 Common Error Signatures & Root Causes")
        err_dist = get_error_distribution(df)
        if not err_dist.empty:
            fig_err_cat = px.bar(
                err_dist,
                x="Count",
                y="Error Category",
                orientation="h",
                color="Count",
                color_continuous_scale="Reds",
                labels={"Count": "Frequency", "Error Category": "Root Cause Signature"},
            )
            fig_err_cat.update_layout(yaxis=dict(autorange="reversed"), margin=dict(t=20, b=20, l=20, r=20), height=340)
            st.plotly_chart(fig_err_cat, use_container_width=True)
        else:
            st.info("No error categories detected.")

    with col_chart4:
        st.markdown("### ⏱️ Timeline of Log Events & Errors")
        timeline_df = df.dropna(subset=["parsed_timestamp"]).copy()
        if not timeline_df.empty:
            # Resample by 10 seconds or minute for timeline visualization
            timeline_df["time_bucket"] = timeline_df["parsed_timestamp"].dt.floor("10s")
            time_counts = (
                timeline_df.groupby(["time_bucket", "level"])
                .size()
                .reset_index(name="Events")
            )
            fig_time = px.bar(
                time_counts,
                x="time_bucket",
                y="Events",
                color="level",
                color_discrete_map=color_map,
                barmode="stack",
                labels={"time_bucket": "Time", "Events": "Event Count"},
            )
            fig_time.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=340)
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.info("Timestamp information unavailable for timeline chart.")

    st.markdown("---")

    # Error Triage Table
    st.subheader(f"🚨 Triage Worklist ({len(filtered_df)} records matching filters)")

    # Color badge for level column
    display_cols = ["timestamp", "service", "level", "trace_id", "error_category", "message"]
    available_cols = [c for c in display_cols if c in filtered_df.columns]

    st.dataframe(
        filtered_df[available_cols],
        use_container_width=True,
        hide_index=True,
    )

    # CSV Download button for reporting
    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Triage Report as CSV",
        data=csv_data,
        file_name="microservice_log_triage_report.csv",
        mime="text/csv",
    )

    # Diagnostic unparsed lines expander
    unstructured_df = df[df["level"] == "UNSTRUCTURED"]
    if not unstructured_df.empty:
        with st.expander(f"⚠️ Unstructured / Malformed Lines Detected ({len(unstructured_df)})"):
            st.write("These lines did not conform to the expected format but were preserved for inspection:")
            st.dataframe(unstructured_df[["raw_line"]], use_container_width=True)


if __name__ == "__main__":
    main()
