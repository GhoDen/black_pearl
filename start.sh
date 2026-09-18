#!/bin/sh

# =======================================================================
# Tor Hidden Service Stack Startup
# 
# IMPORTANT: This script assumes the following file structure for security:
# - backend/main.py
# - backend/web_proxy.py
# - www/index.html (renamed from netcat_terminal.html)
# 
# =======================================================================

# --- Configuration (for reference) ---
# HiddenServicePort 80   127.0.0.1:8080
# HiddenServicePort 9000 127.0.0.1:9000
# -------------------------------------

echo "Starting Tor Service..."
# Restart Tor. (Ensures new configuration is loaded if torrc was changed)
sudo systemctl restart tor.service

# --- Function to gracefully terminate background jobs ---
cleanup() {
    echo ""
    echo "--- Shutting down services ---"
    # Kill the processes by their stored PIDs
    # 2>/dev/null suppresses "No such process" errors if a service failed to start
    kill "$NETCAT_PID" "$PROXY_PID" "$WEB_PID" 2>/dev/null
    echo "Cleanup complete."
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM (system signal) to run the cleanup function
trap cleanup INT TERM

# --- 1. Start Netcat/Telnet service (The backend) ---
# Run from the backend directory
echo "Starting Netcat/Telnet service (backend/main.py)..."
python backend/main.py > netcat.log 2>&1 &
NETCAT_PID=$!
echo "Netcat PID: $NETCAT_PID"

# --- 2. Start WebSocket -> TCP Proxy (The middleman) ---
# Run from the backend directory
echo "Starting WebSocket Proxy (backend/web_proxy.py)..."
python backend/web_proxy.py > proxy.log 2>&1 &
PROXY_PID=$!
echo "Proxy PID: $PROXY_PID"

# --- 3. Host Web Service (The HTML frontend) ---
# Use a subshell (cd ... && command) to run the server from the 'www' directory.
# This ensures ONLY files inside 'www' (i.e., index.html) are accessible.
echo "Starting Web Server on :8080 (serving www/)..."
(cd www && python -m http.server 8080 2> /dev/null) &
WEB_PID=$!
echo "Web Server PID: $WEB_PID"

echo "------------------------------------------------------------------"
echo "All services are running. Press Ctrl+C to stop the entire stack."
echo "------------------------------------------------------------------"

# Wait for a signal (like Ctrl+C). This keeps the main script alive
# so the background processes don't become disowned or close immediately.
wait
