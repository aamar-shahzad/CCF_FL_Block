#!/bin/bash

echo "🚀 Starting CCF Federated Learning Platform..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}Waiting for $service_name on port $port...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $port; then
            echo -e "${GREEN}✅ $service_name is ready on port $port${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start on port $port${NC}"
    return 1
}

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed. Please install Python3 first.${NC}"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 is not installed. Please install pip3 first.${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"
pip3 install -r requirements.txt

# Check if CCF backend is running
echo -e "${YELLOW}🔍 Checking CCF backend status...${NC}"
if check_port 8000; then
    echo -e "${GREEN}✅ CCF backend is already running on port 8000${NC}"
else
    echo -e "${RED}❌ CCF backend is not running on port 8000${NC}"
    echo -e "${YELLOW}Please start your CCF backend first:${NC}"
    echo "  cd .. && make && ./build/app"
    echo ""
    read -p "Press Enter when CCF backend is running, or Ctrl+C to cancel..."
fi

# Start proxy server in background
echo -e "${YELLOW}🔄 Starting proxy server...${NC}"
python3 proxy_server.py &
PROXY_PID=$!

# Wait for proxy server to be ready
if wait_for_service 5000 "Proxy server"; then
    echo -e "${GREEN}✅ Proxy server started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start proxy server${NC}"
    kill $PROXY_PID 2>/dev/null
    exit 1
fi

# Start frontend server in background
echo -e "${YELLOW}🌐 Starting frontend server...${NC}"
python3 -m http.server 8080 &
FRONTEND_PID=$!

# Wait for frontend server to be ready
if wait_for_service 8080 "Frontend server"; then
    echo -e "${GREEN}✅ Frontend server started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start frontend server${NC}"
    kill $PROXY_PID $FRONTEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 All servers are running!${NC}"
echo ""
echo -e "${YELLOW}📱 Access your application:${NC}"
echo -e "  Main App:     ${GREEN}http://localhost:8080${NC}"
echo -e "  Debug Test:   ${GREEN}http://localhost:8080/debug_test.html${NC}"
echo ""
echo -e "${YELLOW}🔧 Server Status:${NC}"
echo -e "  CCF Backend:  ${GREEN}http://localhost:8000${NC}"
echo -e "  Proxy Server: ${GREEN}http://localhost:5000${NC}"
echo -e "  Frontend:     ${GREEN}http://localhost:8080${NC}"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo -e "  - Use the debug test page to check API connectivity"
echo -e "  - Check the browser console for any JavaScript errors"
echo -e "  - Make sure certificates are properly configured in the Auth tab"
echo ""
echo -e "${YELLOW}🛑 To stop all servers, press Ctrl+C${NC}"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Stopping servers...${NC}"
    kill $PROXY_PID $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}✅ Servers stopped${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Keep the script running
while true; do
    sleep 1
done 