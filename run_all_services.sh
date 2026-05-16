#!/bin/bash

echo "🚀 CCF Federated Learning Platform - All Services Startup"
echo "=========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
CCF_PORT=8000
# Use 8080 for UI in devcontainer (forwarded by default); override with PROXY_PORT=5000 if needed
PROXY_PORT="${PROXY_PORT:-8080}"
FRONTEND_PORT=8080
WORKSPACE_DIR="/workspaces/CCF_FL_Block"
FRONTEND_DIR="$WORKSPACE_DIR/frontend"

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if a port is accepting connections
check_port() {
    local port=$1
    if command -v lsof &>/dev/null && lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    fi
    if command -v ss &>/dev/null && ss -ltn "sport = :$port" 2>/dev/null | grep -q LISTEN; then
        return 0
    fi
    if (echo >/dev/tcp/127.0.0.1/$port) &>/dev/null; then
        return 0
    fi
    return 1
}

# Function to wait for a service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status $YELLOW "Waiting for $service_name on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $port; then
            print_status $GREEN "✅ $service_name is ready on port $port"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_status $RED "❌ $service_name failed to start on port $port"
    return 1
}

# Function to kill processes on specific ports
kill_port() {
    local port=$1
    if command -v fuser &>/dev/null; then
        fuser -k "${port}/tcp" 2>/dev/null || true
    fi
    if command -v lsof &>/dev/null; then
        local pids
        pids=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pids" ]; then
            print_status $YELLOW "Killing processes on port $port (pids: $pids)..."
            kill -9 $pids 2>/dev/null || true
        fi
    fi
    sleep 1
}

# Stop CCF sandbox and duplicate proxy instances from prior runs
stop_ccf_and_proxy() {
    print_status $YELLOW "Stopping old CCF sandbox and proxy processes..."
    pkill -f "start_network.py.*liblskv" 2>/dev/null || true
    pkill -f "/opt/ccf_virtual/bin/sandbox.sh" 2>/dev/null || true
    pkill -f "ccf_virtual/bin/cchost" 2>/dev/null || true
    pkill -f "proxy_server.py" 2>/dev/null || true
    pkill -f "redirect_8080.py" 2>/dev/null || true
    sleep 2
}

# Wipe workspace so CCF can recreate sandbox_0 and certs (fixes missing 0.pem)
reset_ccf_workspace() {
  local users="${SANDBOX_USERS:-5}"
  print_status $YELLOW "Resetting CCF workspace for ${users} users..."
  rm -rf "$WORKSPACE_DIR/workspace"
  mkdir -p "$WORKSPACE_DIR/workspace"
}

# Verify CCF HTTPS responds (not just an open port from a zombie)
check_ccf_healthy() {
    curl -sk --max-time 5 "https://127.0.0.1:${CCF_PORT}/" >/dev/null 2>&1
}

wait_for_ccf_healthy() {
    local attempt=1
    print_status $YELLOW "Waiting for CCF to become healthy..."
    while [ $attempt -le 45 ]; do
        if check_ccf_healthy; then
            if [ -f "$WORKSPACE_DIR/workspace/sandbox_common/user$((SANDBOX_USERS - 1))_cert.pem" ] || \
               [ -f "$WORKSPACE_DIR/workspace/sandbox_common/user4_cert.pem" ]; then
                print_status $GREEN "✅ CCF is healthy with user certificates"
                return 0
            fi
            # fewer users than 5
            if [ -f "$WORKSPACE_DIR/workspace/sandbox_common/user0_cert.pem" ]; then
                print_status $GREEN "✅ CCF is healthy"
                return 0
            fi
        fi
        if [ -f "$WORKSPACE_DIR/workspace/sandbox_0/err" ] && [ $attempt -gt 5 ]; then
            if grep -q "Error\|Traceback\|ValueError" "$WORKSPACE_DIR/workspace/sandbox_0/err" 2>/dev/null; then
                print_status $RED "❌ CCF node error — see workspace/sandbox_0/err"
                tail -20 "$WORKSPACE_DIR/workspace/sandbox_0/err" 2>/dev/null || true
                return 1
            fi
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    print_status $RED "❌ CCF did not become healthy in time"
    return 1
}

# Function to cleanup on exit
cleanup() {
    print_status $YELLOW "\n🛑 Shutting down all services..."
    jobs -p | xargs -r kill -9 2>/dev/null || true
    stop_ccf_and_proxy
    kill_port $CCF_PORT
    kill_port $PROXY_PORT
    kill_port $FRONTEND_PORT
    print_status $GREEN "✅ All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if we're in the right directory
if [ ! -f "Makefile" ]; then
    print_status $RED "❌ Error: Makefile not found. Please run this script from the CCF_FL_Block directory."
    exit 1
fi

print_status $BLUE "📋 Checking prerequisites..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    print_status $RED "❌ Python3 is not installed. Please install Python3 first."
    exit 1
fi

# Prefer project venv for Python/pip (created by make build-virtual)
VENV_DIR="$WORKSPACE_DIR/.venv"
if [ -x "$VENV_DIR/bin/python3" ]; then
    PYTHON_CMD="$VENV_DIR/bin/python3"
    PIP_CMD="$VENV_DIR/bin/pip"
elif command -v pip3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
elif python3 -m pip --version &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="python3 -m pip"
else
    print_status $RED "❌ pip is not available. Run 'make build-virtual' first to create .venv."
    exit 1
fi

# Check if make is available
if ! command -v make &> /dev/null; then
    print_status $RED "❌ make is not installed. Please install build tools first."
    exit 1
fi

print_status $GREEN "✅ Prerequisites check passed"

# Kill any existing processes on our ports
print_status $YELLOW "🧹 Cleaning up existing processes..."
stop_ccf_and_proxy
kill_port $CCF_PORT
kill_port $PROXY_PORT
kill_port $FRONTEND_PORT

SANDBOX_USERS="${SANDBOX_USERS:-5}"
if [ "${RESET_WORKSPACE:-1}" = "1" ]; then
    reset_ccf_workspace
fi

# Install Python dependencies (frontend + experiments)
print_status $BLUE "📦 Installing Python dependencies..."
cd $WORKSPACE_DIR
if $PIP_CMD install -r frontend/requirements.txt && $PIP_CMD install -r requirements.txt; then
    print_status $GREEN "✅ Python dependencies installed"
else
    print_status $RED "❌ Failed to install Python dependencies"
    exit 1
fi

CCF_ENCLAVE="$WORKSPACE_DIR/build/liblskv.virtual.so"
# Build CCF backend only if enclave is missing
if [ ! -f "$CCF_ENCLAVE" ]; then
    print_status $BLUE "🔨 Building CCF backend..."
    cd $WORKSPACE_DIR
    if make build-virtual; then
        print_status $GREEN "✅ CCF backend built successfully"
    else
        print_status $RED "❌ Failed to build CCF backend"
        exit 1
    fi
else
    print_status $GREEN "✅ Using existing CCF enclave (skip build)"
    cd $WORKSPACE_DIR
fi

if [ ! -f "$CCF_ENCLAVE" ]; then
    print_status $RED "❌ Enclave not found at $CCF_ENCLAVE"
    exit 1
fi

# Start CCF backend (fresh workspace — no concurrent old sandbox)
print_status $BLUE "🚀 Starting CCF backend (${SANDBOX_USERS} users)..."
cd $WORKSPACE_DIR
if check_port $CCF_PORT; then
    print_status $RED "❌ Port $CCF_PORT still in use after cleanup. Run: bash scripts/stop_all_services.sh"
    exit 1
fi

VENV_DIR=.venv /opt/ccf_virtual/bin/sandbox.sh -p "$CCF_ENCLAVE" -e virtual -t virtual \
  --initial-member-count 3 --initial-user-count "$SANDBOX_USERS" --max-http-body-size 104857600 &
CCF_PID=$!

if ! wait_for_ccf_healthy; then
    print_status $RED "❌ Failed to start CCF backend"
    kill $CCF_PID 2>/dev/null || true
    stop_ccf_and_proxy
    exit 1
fi

# Start UI + API (Flask serves static files and all /api routes on PROXY_PORT)
print_status $BLUE "🔄 Starting UI and API server..."
if check_port $PROXY_PORT; then
    print_status $YELLOW "Port $PROXY_PORT still in use — freeing..."
    kill_port $PROXY_PORT
    sleep 1
fi
cd $FRONTEND_DIR
FLASK_DEBUG=0 PROXY_PORT=$PROXY_PORT $PYTHON_CMD proxy_server.py &
PROXY_PID=$!

if wait_for_service $PROXY_PORT "UI/API Server"; then
    if curl -s --max-time 3 "http://127.0.0.1:$PROXY_PORT/api/health" | grep -q healthy; then
        print_status $GREEN "✅ UI and API server started on port $PROXY_PORT"
    else
        print_status $RED "❌ Port $PROXY_PORT open but API not healthy (old process?)"
        exit 1
    fi
else
    print_status $RED "❌ Failed to start UI/API server"
    kill $CCF_PID $PROXY_PID 2>/dev/null
    exit 1
fi
FRONTEND_PID=$PROXY_PID

# If UI is not on 8080, offer redirect from 8080 → PROXY_PORT for devcontainer users
if [ "$PROXY_PORT" != "8080" ]; then
    if check_port 8080; then
        kill_port 8080
        sleep 1
    fi
    cd $FRONTEND_DIR
    PUBLIC_UI_URL="http://localhost:${PROXY_PORT}" $PYTHON_CMD redirect_8080.py &
fi

# Test API connectivity
print_status $BLUE "🧪 Testing API connectivity..."
sleep 3

# Test proxy server
if curl -s http://localhost:$PROXY_PORT/api/health > /dev/null; then
    print_status $GREEN "✅ Proxy server API test passed"
else
    print_status $RED "❌ Proxy server API test failed"
fi

# Test CCF backend (HTTPS; GET returns 405/verb error when node is up)
if curl -sk --max-time 5 "https://127.0.0.1:$CCF_PORT/user/add" > /dev/null 2>&1; then
    print_status $GREEN "✅ CCF backend API test passed"
else
    print_status $RED "❌ CCF backend API test failed"
fi

# Display success message
echo ""
print_status $GREEN "🎉 All services are running successfully!"
echo ""
print_status $CYAN "📱 Access your application:"
print_status $GREEN "  Main App:     http://localhost:$PROXY_PORT"
print_status $GREEN "  Debug Test:   http://localhost:$PROXY_PORT/debug_test.html"
print_status $YELLOW "  (UI + API on port $PROXY_PORT — use Experiments / System tabs)"
echo ""
print_status $CYAN "🔧 Server Status:"
print_status $GREEN "  CCF Backend:  http://localhost:$CCF_PORT"
print_status $GREEN "  Proxy Server: http://localhost:$PROXY_PORT"
print_status $YELLOW "  (Use port $PROXY_PORT only — UI and API are combined)"
echo ""
print_status $CYAN "🧪 Test Commands:"
print_status $YELLOW "  API Test:     cd $FRONTEND_DIR && python3 test_api.py"
print_status $YELLOW "  Manual Test:  curl -sk https://127.0.0.1:$CCF_PORT/user/add"
echo ""
print_status $CYAN "💡 Usage Tips:"
print_status $YELLOW "  - Use the debug test page to check API connectivity"
print_status $YELLOW "  - Configure certificates in the Auth tab for authenticated operations"
print_status $YELLOW "  - Check browser console for any JavaScript errors"
print_status $YELLOW "  - All API calls should now work without 'pending' status"
echo ""
print_status $PURPLE "🛑 To stop all services, press Ctrl+C"
print_status $PURPLE "📊 To view logs, check the terminal output above"

# Keep the script running and show status
echo ""
print_status $BLUE "📊 Service Status Monitor (Press Ctrl+C to stop)"
print_status $BLUE "================================================"

while true; do
    echo -n "."
    sleep 10
    
    # Check if all services are still running
    if ! check_port $CCF_PORT; then
        print_status $RED "\n❌ CCF backend stopped unexpectedly"
    fi
    
    if ! check_port $PROXY_PORT; then
        print_status $RED "\n❌ Proxy server stopped unexpectedly"
    fi
    
    if ! check_port $PROXY_PORT; then
        print_status $RED "\n❌ UI/API server stopped unexpectedly"
    fi
    
    # Show status every 30 seconds
    if (( $(date +%s) % 30 == 0 )); then
        echo ""
        print_status $CYAN "Status: CCF($(check_port $CCF_PORT && echo '✅' || echo '❌')) UI/API($(check_port $PROXY_PORT && echo '✅' || echo '❌'))"
    fi
done 