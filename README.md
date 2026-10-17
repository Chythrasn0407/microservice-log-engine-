<<<<<<< HEAD
# 🛡️ Microservice Distributed Log Anomaly & Error Triage Engine

> **DevOps Capstone Project • Use Case 9**  
> **Tech Stack:** Python 3.11 • Streamlit • pandas • Python regex (`re`) • Plotly • pytest • Docker • GitHub Actions CI/CD • Kubernetes

---

## 📌 Project Overview & Scope

The **Microservice Distributed Log Anomaly & Error Triage Engine** is designed to parse, aggregate, and triage complex distributed log dumps generated across multiple microservices. 

Distributed applications (e.g., API gateways, auth services, payment gateways, and databases) generate thousands of interconnected log lines with distinct formats, trace IDs, and nested exception stack traces. When incidents occur, site reliability engineers (SREs) and DevOps engineers require automated triage tools to quickly isolate root-cause anomalies, count log severities, cluster error types, and identify the faulting microservice.

> [!NOTE]  
> **Scope Disclaimer**: This engine performs **batch triage and anomaly root-cause clustering** on sample or uploaded log files. It does not provide real-time streaming monitoring.

---

## 🚀 Key Features

1. **Distributed Regex Parser**:
   - Parses multi-service log entries containing timestamps, service names, log levels (`INFO`, `WARN`, `ERROR`, `DEBUG`), trace IDs (`trace_id`), and span IDs (`span_id`).
   - Fallback pattern parsing for standard application logs.
   - Non-destructive handling of malformed or unstructured lines (tagged as `UNSTRUCTURED` for inspection without crashing).
2. **Error Signature Clustering**:
   - Automatically classifies errors into actionable DevOps categories:
     - 🗄️ *Database / Connection Error*
     - 💳 *Payment Gateway Timeout*
     - ⚡ *Circuit Breaker Tripped*
     - 🧠 *Memory Exhaustion (OOM / Heap)*
     - 🔍 *Null Pointer / Reference Error*
     - 🛑 *Rate Limiting / Throttling (HTTP 429)*
     - 📬 *Message Broker / Kafka Error*
     - 🔐 *Authentication / JWT Error*
     - 🌐 *HTTP 5xx Gateway Errors*
3. **Interactive Streamlit Web Dashboard**:
   - Real-time KPI summary cards (Total Logs, INFO, WARN, ERROR, Error Rate %).
   - Donut chart for log level distribution.
   - Microservice error and warning frequency breakdown.
   - Root-cause error category horizontal bar chart.
   - Time-series event activity & error spike timeline.
   - Multi-facet filters (by microservice, severity level, error category, or regex keyword search).
   - One-click CSV export of triaged incidents.
4. **Resilient Input Handling**:
   - Gracefully handles empty files, blank lines, and corrupted text without throwing unhandled exceptions.
5. **Production DevOps Delivery**:
   - Automated unit & integration tests with `pytest`.
   - Security-hardened Docker container with non-root user and health checks.
   - GitHub Actions CI/CD pipeline.
   - Production Kubernetes manifests with **ConfigMap**, **Deployment**, **Service**, and **Liveness & Readiness probes**.

---

## 📁 Repository Structure

```text
microservice-log-engine/
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI/CD pipeline
├── data/
│   └── sample_microservices.log # Realistic distributed microservice logs
├── k8s/
│   ├── configmap.yaml           # Runtime configuration
│   ├── deployment.yaml          # K8s Deployment with health probes & securityContext
│   ├── service.yaml             # ClusterIP and NodePort Services
│   └── kustomization.yaml       # Kustomize manifest for single-command deploy
├── src/
│   ├── __init__.py
│   ├── app.py                   # Streamlit web dashboard
│   └── parser.py                # Regex parsing & analytics engine (pure Python)
├── tests/
│   └── test_parser.py           # Pytest unit & integration test suite
├── .dockerignore                # Docker build exclusions
├── docker-compose.yml           # Local multi-container / single-command runner
├── Dockerfile                   # Python 3.11-slim production container
├── requirements.txt             # Project Python dependencies
└── README.md                    # Project documentation
```

---

## 🛠️ Step-by-Step Execution Guide

### 1. Local Setup (macOS / Linux)

Open your terminal and navigate to the project directory:

```bash
cd /Users/chythra407_shyam/.gemini/antigravity/scratch/microservice-log-engine
```

Create a virtual environment and activate it:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 2. Run Automated Pytest Tests

To run the automated test suite:

```bash
pytest -v tests/
```

Expected output:
```text
tests/test_parser.py::test_parse_valid_distributed_line PASSED           [ 11%]
tests/test_parser.py::test_parse_error_line_with_db_connection PASSED    [ 22%]
tests/test_parser.py::test_error_classification_signatures PASSED        [ 33%]
tests/test_parser.py::test_empty_string_input_handling PASSED            [ 44%]
tests/test_parser.py::test_whitespace_and_comments PASSED                [ 55%]
tests/test_parser.py::test_malformed_unstructured_line PASSED            [ 66%]
tests/test_parser.py::test_level_counts_and_metrics PASSED               [ 77%]
tests/test_parser.py::test_service_breakdown PASSED                      [ 88%]
tests/test_parser.py::test_sample_microservices_log_file PASSED          [100%]
============================== 9 passed in 0.42s ===============================
```

---

### 3. Launch the Streamlit Dashboard

Run the Streamlit application:

```bash
streamlit run src/app.py
```

Once started, open your web browser at:
👉 **`http://localhost:8501`**

Inside the dashboard:
- Use **"Use Built-in Sample Logs"** to analyze preloaded distributed logs.
- Switch to **"Upload Custom Log File"** to drag-and-drop your own `.log` or `.txt` file.
- Use the sidebar filters to isolate specific microservices or inspect only `ERROR` and `WARN` lines.
- Export the triage results by clicking **"Export Triage Report as CSV"**.

---

### 4. Run with Docker

1. Ensure Docker Desktop is running:
   ```bash
   open -a Docker
   ```

2. Build the Docker image:
   ```bash
   docker build -t microservice-log-engine:v1.0.0 .
   ```

3. Run the container:
   ```bash
   docker run -d --name log-engine -p 8501:8501 microservice-log-engine:v1.0.0
   ```

4. Verify container health:
   ```bash
   docker ps
   curl -s http://localhost:8501/_stcore/health
   ```
   Output: `ok`

5. Alternatively, run with Docker Compose:
   ```bash
   docker compose up -d --build
   ```

To stop the container:
```bash
docker compose down
```

---

### 5. Deploy to Kubernetes

The `k8s/` directory contains production-ready manifests configured according to DevOps best practices:
- **`configmap.yaml`**: Injects environment variables without rebuilding images.
- **`deployment.yaml`**: Runs 2 replicas with resource limits, non-root security context (`runAsUser: 10001`), and health probes.
- **`service.yaml`**: Exposes the app internally via `ClusterIP` and externally via `NodePort` on port `30501`.

#### Health Probes Explained:
- **Liveness Probe** (`httpGet: /_stcore/health`, port `8501`): Kubernetes continuously checks if the Streamlit server process is alive. If the process hangs or enters an unrecoverable state, Kubernetes automatically restarts the container.
- **Readiness Probe** (`httpGet: /_stcore/health`, port `8501`): Kubernetes ensures the pod is ready to accept user traffic before routing incoming requests to it from the Service.

#### Deploy Commands:

```bash
# 1. Apply all manifests using Kustomize
kubectl apply -k k8s/

# 2. Check deployment rollout status
kubectl rollout status deployment/microservice-log-engine-deployment

# 3. View running pods and services
kubectl get pods -l app=microservice-log-engine
kubectl get svc -l app=microservice-log-engine

# 4. Access via port-forwarding (if using Minikube or local cluster)
kubectl port-forward svc/microservice-log-engine-service 8501:80
```

Now access `http://localhost:8501` in your browser.

To clean up Kubernetes resources:
```bash
kubectl delete -k k8s/
```

---

### 6. Continuous Integration (CI/CD)

The GitHub Actions pipeline defined in [`.github/workflows/ci.yml`](file:///.github/workflows/ci.yml) triggers on every `push` and `pull_request` to `main`:
1. **Pytest Job**: Sets up Python 3.11, installs dependencies, and runs all unit tests.
2. **Docker Build Job**: Sets up Docker Buildx and validates that the container image builds without syntax or dependency errors.
=======
# microservice-log-engine-
>>>>>>> f8d80e0c1aa21849db9642e6069b0250f81ccaf9
