#!/bin/bash

# Exit immediately if a command fails
set -e

# 1. Install Git
echo "Installing Git..."
sudo apt update
sudo apt install -y git

# 2. Install VS Code (ARM64)
echo "Installing VS Code..."
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg
sudo install -o root -g root -m 644 packages.microsoft.gpg /etc/apt/trusted.gpg.d/
sudo sh -c 'echo "deb [arch=arm64] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
sudo apt update
sudo apt install -y code

# 3. Clone your repository
REPO_URL="https://github.com/VedantMalgundkar/hyperhdr-controller.git"  # change this
CLONE_DIR="$HOME/myproject"

echo "Cloning repository..."
git clone "$REPO_URL" "$CLONE_DIR"

# 4. Install Python requirements
echo "Installing Python dependencies..."
cd "$CLONE_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Run the backend
echo "Running backend..."
cd backend
python run.py
