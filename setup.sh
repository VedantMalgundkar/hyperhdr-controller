#!/bin/bash

# Exit on error
set -e

# Colors
RED='\033[1;31m'
GREEN='\033[1;32m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function banner() {
    echo -e "\n${CYAN}========================================="
    echo -e "${YELLOW}$1"
    echo -e "${CYAN}=========================================${NC}\n"
}

banner "🚀 Starting Full Backend Setup on Raspberry Pi"

# 1. Install Git
banner "📦 Installing Git"
sudo apt update
sudo apt install -y git

# 2. Install VS Code (ARM64)
banner "💻 Installing VS Code"
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
sudo install -o root -g root -m 644 packages.microsoft.gpg /etc/apt/trusted.gpg.d/
sudo sh -c 'echo "deb [arch=arm64] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
sudo apt update
sudo apt install -y code

USER_NAME=$(whoami)

# 3. Clone your repository
REPO_URL="https://github.com/VedantMalgundkar/hyperhdr-controller.git"
CLONE_DIR="$HOME/myproject"

banner "📁 Cloning Repository"
git clone "$REPO_URL" "$CLONE_DIR"

# 4. Setup Python environment
banner "🐍 Setting Up Python Environment"
cd "$CLONE_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Paths
PROJECT_DIR="$CLONE_DIR"
PYTHON="$PROJECT_DIR/venv/bin/python3"

# 6. Create systemd services (BLE and WiFi only)
banner "🛠 Creating systemd Services"

# auto_pair_agent
sudo tee /etc/systemd/system/auto_pair_agent.service > /dev/null <<EOF
[Unit]
Description=BLE Auto Pair Agent
After=network.target

[Service]
ExecStart=$PYTHON $PROJECT_DIR/backend/ble/auto_pair_agent.py
Restart=always
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# wifi_utilities
sudo tee /etc/systemd/system/wifi_utilities.service > /dev/null <<EOF
[Unit]
Description=WiFi Utilities
After=network.target auto_pair_agent.service
Requires=auto_pair_agent.service

[Service]
ExecStart=$PYTHON $PROJECT_DIR/backend/wifi_module/wifi_utilities.py
Restart=always
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 7. Enable and start BLE + WiFi services
banner "🚦 Enabling & Starting BLE + WiFi Services"
sudo systemctl daemon-reload
sudo systemctl enable wifi_utilities.service
sudo systemctl enable auto_pair_agent.service

sudo systemctl start wifi_utilities.service
sudo systemctl start auto_pair_agent.service

# 8. Run Flask server manually
banner "🚀 Launching Flask Server (manual)"
cd "$PROJECT_DIR/backend"
source "$PROJECT_DIR/venv/bin/activate"
python run.py
