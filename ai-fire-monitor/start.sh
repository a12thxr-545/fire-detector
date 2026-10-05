#!/bin/bash

echo "Starting AI Fire Monitor..."

osascript -e 'tell application "Terminal" to do script "echo \"MQTT - Mosquitto\"; mosquitto -c ~/mosquitto.conf -v"'

osascript -e 'tell application "Terminal" to do script "echo \"Flask Server\"; cd ~/fire-detector/ai-fire-monitor && source venv/bin/activate && python3 server.py"'

osascript -e 'tell application "Terminal" to do script "echo \"Cloudflare Quick Tunnel\"; cloudflared tunnel --url http://localhost:5001"'

echo "All services started!"
