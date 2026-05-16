#!/bin/bash

# CCF Federated Learning Service Manager
# Usage: ./manage_services.sh [start|stop|status|restart|test]

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
CCF_PORT=8000
PROXY_PORT=5000
FRONTEND_PORT=8080
WORKSPACE_DIR="/workspaces/CCF_FL_Block"
FRONTEND_DIR="$WORKSPACE_DIR/frontend"

# PID files for tracking processes
CCF_PID_FILE="/tmp/ccf_backend.pid"
PROXY_PID_FILE="/tmp/ccf_proxy.pid"
FRONTEND_PID_FILE="/tmp/ccf_frontend.pid"

print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

get_pid() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        cat "$pid_file" 2>/dev/null
    else
        echo ""
    fi
}

save_pid() {
    local pid_file=$1
    local pid=$2
    echo $pid > "$pid_file"
}

kill_pid_file() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if [ ! -z "$pid" ] && kill -0 $pid 2>/dev/null; then
            print_status $YELLOW "Stopping $service_name (PID: $pid)..."
            kill -9 $pid 2>/dev/null
            rm -f "$pid_file"
            print_status $GREEN "✅ $service_name stopped"
        else
            print_status $YELLOW "$service_name not running"
            rm -f "$pid_file"
        fi
    else
        print_status $YELLOW "$service_name not running"
    fi
}

start_ccf_backend() {
    print_status $BLUE "🚀 Starting CCF backend..."
    
    if check_port $CCF_PORT; then
        print_status $GREEN "✅ CCF backend already running on port $CCF_PORT"
        return 0
    fi
    
    cd $WORKSPACE_DIR
    if [ ! -f "./build/app" ]; then
        print_status $RED "❌ CCF backend not built. Run 'make' first."
        return 1
    fi
    
    ./build/app &
    local pid=$!
    save_pid $CCF_PID_FILE $pid
    
    # Wait for backend to start
    local attempts=0
    while [ $attempts -lt 15 ]; do
        if check_port $CCF_PORT; then
            print_status $GREEN "✅ CCF backend started successfully (PID: $pid)"
            return 0
        fi
        sleep 2
        attempts=$((attempts + 1))
    done
    
    print_status $RED "❌ Failed to start CCF backend"
    kill $pid 2>/dev/null
    rm -f $CCF_PID_FILE
    return 1
}

start_proxy_server() {
    print_status $BLUE "🔄 Starting proxy server..."
    
    if check_port $PROXY_PORT; then
        print_status $GREEN "✅ Proxy server already running on port $PROXY_PORT"
        return 0
    fi
    
    cd $FRONTEND_DIR
    python3 proxy_server.py &
    local pid=$!
    save_pid $PROXY_PID_FILE $pid
    
    # Wait for proxy to start
    local attempts=0
    while [ $attempts -lt 10 ]; do
        if check_port $PROXY_PORT; then
            print_status $GREEN "✅ Proxy server started successfully (PID: $pid)"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    
    print_status $RED "❌ Failed to start proxy server"
    kill $pid 2>/dev/null
    rm -f $PROXY_PID_FILE
    return 1
}

start_frontend_server() {
    print_status $BLUE "🌐 Starting frontend server..."
    
    if check_port $FRONTEND_PORT; then
        print_status $GREEN "✅ Frontend server already running on port $FRONTEND_PORT"
        return 0
    fi
    
    cd $FRONTEND_DIR
    python3 -m http.server $FRONTEND_PORT &
    local pid=$!
    save_pid $FRONTEND_PID_FILE $pid
    
    # Wait for frontend to start
    local attempts=0
    while [ $attempts -lt 5 ]; do
        if check_port $FRONTEND_PORT; then
            print_status $GREEN "✅ Frontend server started successfully (PID: $pid)"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    
    print_status $RED "❌ Failed to start frontend server"
    kill $pid 2>/dev/null
    rm -f $FRONTEND_PID_FILE
    return 1
}

stop_all_services() {
    print_status $YELLOW "🛑 Stopping all CCF services..."
    
    kill_pid_file $FRONTEND_PID_FILE "Frontend server"
    kill_pid_file $PROXY_PID_FILE "Proxy server"
    kill_pid_file $CCF_PID_FILE "CCF backend"
    
    # Also kill any processes on our ports
    for port in $FRONTEND_PORT $PROXY_PORT $CCF_PORT; do
        local pids=$(lsof -ti:$port 2>/dev/null)
        if [ ! -z "$pids" ]; then
            print_status $YELLOW "Killing processes on port $port..."
            kill -9 $pids 2>/dev/null
        fi
    done
    
    print_status $GREEN "✅ All services stopped"
}

show_status() {
    print_status $CYAN "📊 CCF Federated Learning Service Status"
    print_status $CYAN "========================================="
    
    # CCF Backend
    local ccf_pid=$(get_pid $CCF_PID_FILE)
    if check_port $CCF_PORT; then
        print_status $GREEN "✅ CCF Backend: Running on port $CCF_PORT (PID: $ccf_pid)"
    else
        print_status $RED "❌ CCF Backend: Not running"
    fi
    
    # Proxy Server
    local proxy_pid=$(get_pid $PROXY_PID_FILE)
    if check_port $PROXY_PORT; then
        print_status $GREEN "✅ Proxy Server: Running on port $PROXY_PORT (PID: $proxy_pid)"
    else
        print_status $RED "❌ Proxy Server: Not running"
    fi
    
    # Frontend Server
    local frontend_pid=$(get_pid $FRONTEND_PID_FILE)
    if check_port $FRONTEND_PORT; then
        print_status $GREEN "✅ Frontend Server: Running on port $FRONTEND_PORT (PID: $frontend_pid)"
    else
        print_status $RED "❌ Frontend Server: Not running"
    fi
    
    echo ""
    print_status $CYAN "🔗 Access URLs:"
    print_status $GREEN "  Main App:     http://localhost:$FRONTEND_PORT"
    print_status $GREEN "  Debug Test:   http://localhost:$FRONTEND_PORT/debug_test.html"
    print_status $GREEN "  CCF Backend:  http://localhost:$CCF_PORT"
    print_status $GREEN "  Proxy Server: http://localhost:$PROXY_PORT"
}

test_services() {
    print_status $BLUE "🧪 Testing service connectivity..."
    
    # Test proxy server
    if curl -s http://localhost:$PROXY_PORT/api/health > /dev/null 2>&1; then
        print_status $GREEN "✅ Proxy server API test passed"
    else
        print_status $RED "❌ Proxy server API test failed"
    fi
    
    # Test CCF backend
    if curl -s http://localhost:$CCF_PORT/user/add > /dev/null 2>&1; then
        print_status $GREEN "✅ CCF backend API test passed"
    else
        print_status $RED "❌ CCF backend API test failed"
    fi
    
    # Test frontend
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        print_status $GREEN "✅ Frontend server test passed"
    else
        print_status $RED "❌ Frontend server test failed"
    fi
}

show_usage() {
    echo "CCF Federated Learning Service Manager"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     Start all services (CCF backend, proxy, frontend)"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  status    Show status of all services"
    echo "  test      Test connectivity of all services"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start    # Start all services"
    echo "  $0 status   # Check service status"
    echo "  $0 test     # Test API connectivity"
}

# Main script logic
case "${1:-help}" in
    start)
        print_status $BLUE "🚀 Starting all CCF services..."
        if start_ccf_backend && start_proxy_server && start_frontend_server; then
            print_status $GREEN "🎉 All services started successfully!"
            echo ""
            show_status
        else
            print_status $RED "❌ Failed to start all services"
            exit 1
        fi
        ;;
    stop)
        stop_all_services
        ;;
    restart)
        print_status $YELLOW "🔄 Restarting all services..."
        stop_all_services
        sleep 2
        if start_ccf_backend && start_proxy_server && start_frontend_server; then
            print_status $GREEN "🎉 All services restarted successfully!"
            echo ""
            show_status
        else
            print_status $RED "❌ Failed to restart all services"
            exit 1
        fi
        ;;
    status)
        show_status
        ;;
    test)
        test_services
        ;;
    help|*)
        show_usage
        ;;
esac 