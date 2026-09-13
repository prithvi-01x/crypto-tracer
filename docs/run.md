# Crypto-Tracer — Local Setup & Execution Guide

This guide walks a new user through setting up and running **Crypto-Tracer** locally on their machine without Docker.

---

## 🏗️ Architecture & Default Ports

| Component | Technology | Default URL / Port | Description |
|---|---|---|---|
| **Frontend** | React 19 + TypeScript + Vite | `http://localhost:5173` | Interactive forensic workstation & graph canvas |
| **Backend** | FastAPI + Uvicorn + Python | `http://localhost:8000` | REST API engine & attribution pipeline |
| **API Docs** | Swagger UI (FastAPI) | `http://localhost:8000/docs` | Interactive API documentation |
| **Database** | PostgreSQL | `localhost:5432` | Case records, traces, evidence items, reports |
| **Cache** | Redis | `localhost:6379` | Blockchain RPC caching & rate limiting |

---

## 📋 System Prerequisites

Ensure the following tools are installed on your host system:

* **Python:** `3.12` or higher (with `venv` support)
* **Node.js:** `20.x` LTS or higher (`npm` 10+)
* **PostgreSQL:** `15` or higher (`psql`, `initdb`, `pg_ctl`, or system service)
* **Redis:** `7` or higher (`redis-server`, `redis-cli`)

---

## ⚡ One-Command Startup (Recommended)

You can launch the entire platform with a single command:

```bash
./start.sh
```

`start.sh` automatically:
1. Verifies/starts **Redis** (`6379`) and **PostgreSQL** (`5432`).
2. Verifies the `crypto_tracer` database and initializes tables.
3. Sets up Python virtualenv and installs dependencies if needed.
4. Launches the **FastAPI backend** (`http://localhost:8000`).
5. Launches the **Vite React frontend** (`http://localhost:5173`).
6. Runs health probes and presents an interactive CLI status dashboard.
7. Gracefully stops all processes on `Ctrl+C`.

---

## 🚀 Manual Step-by-Step Setup

### Step 1: Configure Environment Variables

Copy the provided template to create your local `.env` configuration:

```bash
cp .env.example .env
```

The default values in `.env` are pre-configured for local execution with live TRON mainnet ingestion:
* `DEFAULT_EXECUTION_MODE=LIVE`
* `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_tracer`
* `REDIS_URL=redis://localhost:6379/0`
* `API_V1_STR=/api/v1`
* `TRON_API_BASE_URL=https://api.trongrid.io`
* `TRON_FALLBACK_API_URLS=` (comma-separated secondary RPC endpoints, optional)
* `TRON_API_KEY=` (optional TronGrid API key for higher rate limits)
* `TRON_HTTP_TIMEOUT_SECONDS=10.0`
* `TRON_MAX_RETRIES=3`

---

### Step 2: Start Redis

Ensure Redis is running on port `6379`:

```bash
# Start Redis daemon
redis-server --daemonize yes

# Verify connectivity (should return "PONG")
redis-cli ping
```

---

### Step 3: Start PostgreSQL & Create Database

Ensure PostgreSQL is running on port `5432`:

```bash
# If using system service (Linux/systemd):
sudo systemctl start postgresql

# OR if using user-space pg_ctl:
pg_ctl -D ~/.postgres_data -l ~/.postgres_data/server.log -o "-p 5432" start
```

Create the `crypto_tracer` database (if it doesn't already exist):

```bash
createdb -U postgres -h localhost -p 5432 crypto_tracer
```

> **Note:** You do not need to run manual SQL migration scripts. The FastAPI application automatically discovers and initializes all required database schemas and tables on startup via SQLAlchemy.

---

### Step 4: Setup and Start Backend (FastAPI)

In the repository root:

```bash
# 1. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install backend dependencies
pip install -r backend/requirements.txt

# 3. Start the FastAPI development server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify backend health in a separate terminal:
```bash
curl http://localhost:8000/api/v1/health
```
Expected response:
```json
{
  "status": "HEALTHY",
  "app": "Crypto-Tracer",
  "services": {
    "database": {"status": "HEALTHY"},
    "redis": {"status": "HEALTHY"}
  }
}
```

---

### Step 5: Setup and Start Frontend (React / Vite)

In a new terminal window:

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Start the Vite development server
npm run dev
```

The frontend will be live at:
👉 **[http://localhost:5173](http://localhost:5173)**

---

## 🎯 Demo Replay Walkthrough (Canonical SIH Case)

Once both the backend and frontend are running, you can seed and inspect the canonical demonstration case with a single command:

```bash
curl -X POST http://localhost:8000/api/v1/demo/seed
```

This deterministically initializes the official evaluation scenario:
* **FIR Number:** `FIR-2026-DEL-CY-0812`
* **Victim:** `Ramesh Kumar` (Telegram task-based investment fraud)
* **Reported Loss:** `₹50,00,000` (`60,000` USDT)
* **Suspect Root Wallet:** `TSuspectScamRootWallet111111111111`
* **Attributed VASP:** `Binance` (81.65% Confidence, `HIGH` Band)
* **Candidate Exchange Deposit:** `TBinanceUserDepositCandidate333333`
* **Evidence Items:** 59 items generated with RFC-8785 canonical hashes
* **Forensic Findings:** 7 automated risk signals (rapid sweeps, mule consolidation)

### How to verify in the browser:
1. Open **[http://localhost:5173](http://localhost:5173)**.
2. Click on case **`FIR-2026-DEL-CY-0812`**.
3. Explore the workspace tabs:
   * **Trace Graph:** Interactive Cytoscape graph canvas with path glow, pruning drawer, and node/edge inspection.
   * **VASP Attribution:** Multi-factor attribution cards and confidence scoring breakdown.
   * **Forensic Findings:** Categorized risk alerts and automated investigator observations.
   * **Evidence Vault:** Section 63 BSA cryptographic audit chain with SHA-256 integrity seals.
   * **Reports & Legal Draft:** Section 63 BSA Evidence Dossier and Section 94 BNSS Order generation & PDF download.
4. Test theme switching using the sun/moon icon in the top navigation bar.

---

## 🧪 Testing & Verification

Run the test suites to ensure everything is working correctly:

### Backend Tests (100 Pytest Suites)
```bash
source venv/bin/activate
PYTHONPATH=. pytest backend/tests -v
```

### Frontend Lint & Build
```bash
cd frontend
npm run lint    # Oxlint static analysis
npm run build   # Production Vite bundle compilation
```

### End-to-End Playwright Tests (35 Tests)
```bash
./venv-playwright/bin/pytest tests/e2e/tier1_feature_coverage
```

---

## 🛠️ Troubleshooting

### 1. Port Already in Use
If port `5173` or `8000` is already in use:
* Check running processes: `lsof -i :5173` or `lsof -i :8000`
* Terminate conflicting processes or change the port via CLI flags (e.g. `uvicorn ... --port 8001`, `npm run dev -- --port 5174`).

### 2. Database Connection Error (`ConnectionRefusedError`)
* Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
* Verify the database exists: `psql -U postgres -h localhost -p 5432 -l | grep crypto_tracer`
* If password authentication fails, ensure `.env` matches your local PostgreSQL credentials.

### 3. Redis Connection Error
* Check if Redis server is running: `redis-cli ping`
* If inactive, start it with `redis-server` or `sudo systemctl start redis`.
