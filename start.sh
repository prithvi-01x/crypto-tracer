#!/usr/bin/env bash
# ==============================================================================
# Crypto-Tracer — Unified Startup Script
# Starts PostgreSQL, Redis, FastAPI Backend, and Vite Frontend
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ANSI Color Codes
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_RED="\033[31m"
CLR_GREEN="\033[32m"
CLR_YELLOW="\033[33m"
CLR_BLUE="\033[34m"
CLR_CYAN="\033[36m"
CLR_GRAY="\033[90m"

log_info() {
    echo -e "${CLR_BLUE}[INFO]${CLR_RESET} $1"
}

log_ok() {
    echo -e "${CLR_GREEN}[OK]${CLR_RESET} $1"
}

log_warn() {
    echo -e "${CLR_YELLOW}[WARN]${CLR_RESET} $1"
}

log_err() {
    echo -e "${CLR_RED}[ERROR]${CLR_RESET} $1"
}

print_banner() {
    echo -e "${CLR_CYAN}${CLR_BOLD}"
    cat << "EOF"
  ____                  _             _____                          
 / ___|_ __ _   _ _ __ | |_ ___      |_   _| __ __ _  ___ ___ _ __ 
| |   | '__| | | | '_ \| __/ _ \ _____ | || '__/ _` |/ __/ _ \ '__|
| |___| |  | |_| | |_) | || (_) |_____|| || | | (_| | (_|  __/ |   
 \____|_|   \__, | .__/ \__\___/       |_||_|  \__,_|\___\___|_|   
            |___/|_|                                               
EOF
    echo -e "${CLR_RESET}"
    echo -e "${CLR_BOLD}Crypto-Tracer Forensics & Attribution Workstation${CLR_RESET}"
    echo -e "${CLR_GRAY}------------------------------------------------------------${CLR_RESET}"
}

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    log_info "Shutting down Crypto-Tracer services..."

    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
        log_ok "Vite frontend server stopped."
    fi

    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
        log_ok "FastAPI backend server stopped."
    fi

    # Kill any dangling processes on target ports if started by this user
    fuser -k 8000/tcp 2>/dev/null || true
    fuser -k 5173/tcp 2>/dev/null || true

    log_ok "Crypto-Tracer processes terminated cleanly. Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

print_banner

# ------------------------------------------------------------------------------
# 1. Environment Template (.env) Check
# ------------------------------------------------------------------------------
if [[ ! -f ".env" ]]; then
    if [[ -f ".env.example" ]]; then
        log_warn ".env file not found. Copying .env.example to .env..."
        cp .env.example .env
        log_ok "Created .env configuration file."
    else
        log_err "Neither .env nor .env.example found in repository root."
        exit 1
    fi
else
    log_ok "Configuration file (.env) found."
fi

# ------------------------------------------------------------------------------
# 2. Redis Cache Check & Auto-Start
# ------------------------------------------------------------------------------
log_info "Checking Redis status..."
if redis-cli ping &>/dev/null; then
    log_ok "Redis is active and accepting connections."
else
    log_warn "Redis is not running. Attempting to start redis-server in background..."
    if command -v redis-server &>/dev/null; then
        redis-server --daemonize yes || sudo systemctl start redis || true
        sleep 1
        if redis-cli ping &>/dev/null; then
            log_ok "Redis started successfully."
        else
            log_err "Failed to start Redis. Please start redis-server manually."
            exit 1
        fi
    else
        log_err "redis-server is not installed or not in PATH."
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# 3. PostgreSQL Database Check & Auto-Start
# ------------------------------------------------------------------------------
log_info "Checking PostgreSQL status on port 5432..."
if pg_isready -h localhost -p 5432 &>/dev/null; then
    log_ok "PostgreSQL is active and accepting connections."
else
    log_warn "PostgreSQL is not responding. Attempting to start PostgreSQL cluster..."
    STARTED_PG=false

    # Check for user-space pg_ctl cluster in ~/.postgres_data
    if [[ -d "$HOME/.postgres_data" ]] && command -v pg_ctl &>/dev/null; then
        pg_ctl -D "$HOME/.postgres_data" -l "$HOME/.postgres_data/server.log" -o "-p 5432" start || true
        STARTED_PG=true
    fi

    # Fallback to systemd service if pg_ctl was not applicable
    if [[ "$STARTED_PG" == false ]] && command -v systemctl &>/dev/null; then
        sudo systemctl start postgresql 2>/dev/null || true
    fi

    # Wait up to 10 seconds for PostgreSQL to accept connections
    RETRIES=10
    while ! pg_isready -h localhost -p 5432 &>/dev/null && [[ $RETRIES -gt 0 ]]; do
        sleep 1
        RETRIES=$((RETRIES - 1))
    done

    if pg_isready -h localhost -p 5432 &>/dev/null; then
        log_ok "PostgreSQL started successfully."
    else
        log_err "Unable to start PostgreSQL on port 5432. Please start PostgreSQL manually."
        exit 1
    fi
fi

# Ensure database 'crypto_tracer' exists
if command -v psql &>/dev/null; then
    if ! psql -U postgres -h localhost -p 5432 -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw crypto_tracer; then
        log_warn "Database 'crypto_tracer' not found. Creating database..."
        createdb -U postgres -h localhost -p 5432 crypto_tracer 2>/dev/null || true
        log_ok "Database 'crypto_tracer' created."
    else
        log_ok "Database 'crypto_tracer' verified."
    fi
fi

# ------------------------------------------------------------------------------
# 4. Backend Virtual Environment & Dependencies
# ------------------------------------------------------------------------------
if [[ ! -d "venv" ]]; then
    log_warn "Python virtual environment (venv) not found. Creating..."
    python3 -m venv venv
    log_info "Installing backend dependencies from backend/requirements.txt..."
    ./venv/bin/pip install --upgrade pip -q
    ./venv/bin/pip install -r backend/requirements.txt -q
    log_ok "Backend virtual environment prepared."
else
    log_ok "Python virtual environment found."
fi

# ------------------------------------------------------------------------------
# 5. Frontend Dependencies Check
# ------------------------------------------------------------------------------
if [[ ! -d "frontend/node_modules" ]]; then
    log_warn "Frontend node_modules not found. Running npm install..."
    (cd frontend && npm install)
    log_ok "Frontend dependencies installed."
else
    log_ok "Frontend dependencies found."
fi

# ------------------------------------------------------------------------------
# 6. Check Port Conflicts & Free Stale Listeners
# ------------------------------------------------------------------------------
for port in 8000 5173; do
    if lsof -i :"$port" &>/dev/null; then
        log_warn "Port $port is already in use by a stale process. Terminating..."
        fuser -k "$port/tcp" 2>/dev/null || true
        sleep 1
    fi
done

# ------------------------------------------------------------------------------
# 7. Launch Backend (FastAPI + Uvicorn)
# ------------------------------------------------------------------------------
log_info "Starting FastAPI backend server on http://localhost:8000..."
./venv/bin/python -m uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    &
BACKEND_PID=$!

# ------------------------------------------------------------------------------
# 8. Launch Frontend (Vite + React)
# ------------------------------------------------------------------------------
log_info "Starting Vite frontend dev server on http://localhost:5173..."
npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

# ------------------------------------------------------------------------------
# 9. Wait for Services to Become Healthy
# ------------------------------------------------------------------------------
log_info "Waiting for services to become responsive..."
WAIT_RETRIES=20
BACKEND_READY=false
FRONTEND_READY=false

while [[ $WAIT_RETRIES -gt 0 ]]; do
    if [[ "$BACKEND_READY" == false ]] && curl -sf http://localhost:8000/api/v1/health &>/dev/null; then
        BACKEND_READY=true
    fi

    if [[ "$FRONTEND_READY" == false ]] && curl -sfI http://localhost:5173 &>/dev/null; then
        FRONTEND_READY=true
    fi

    if [[ "$BACKEND_READY" == true && "$FRONTEND_READY" == true ]]; then
        break
    fi

    sleep 1
    WAIT_RETRIES=$((WAIT_RETRIES - 1))
done

# ------------------------------------------------------------------------------
# 10. Ready Dashboard
# ------------------------------------------------------------------------------
echo ""
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
echo -e "${CLR_GREEN}${CLR_BOLD}  🚀 Crypto-Tracer is LIVE and ready for investigations!    ${CLR_RESET}"
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
echo ""
echo -e "  ${CLR_BOLD}Workstation UI:${CLR_RESET}   ${CLR_CYAN}http://localhost:5173${CLR_RESET}"
echo -e "  ${CLR_BOLD}API Server:${CLR_RESET}       ${CLR_CYAN}http://localhost:8000${CLR_RESET}"
echo -e "  ${CLR_BOLD}Swagger Docs:${CLR_RESET}     ${CLR_CYAN}http://localhost:8000/docs${CLR_RESET}"
echo -e "  ${CLR_BOLD}Health Status:${CLR_RESET}    ${CLR_CYAN}http://localhost:8000/api/v1/health${CLR_RESET}"
echo ""
echo -e "  ${CLR_GRAY}To seed the canonical SIH demo scenario, run:${CLR_RESET}"
echo -e "  ${CLR_YELLOW}curl -X POST http://localhost:8000/api/v1/demo/seed${CLR_RESET}"
echo ""
echo -e "${CLR_GRAY}Press [Ctrl+C] anytime to stop all services cleanly.${CLR_RESET}"
echo -e "${CLR_GREEN}${CLR_BOLD}============================================================${CLR_RESET}"
echo ""

# Keep running and wait for background processes
wait "$BACKEND_PID" "$FRONTEND_PID"
