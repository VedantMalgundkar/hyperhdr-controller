#!/bin/bash

echo "🔧 STEP 1: Uninstalling all Python packages (except pip, setuptools, wheel)..."
sudo pip3 freeze | grep -vE '^(pip|setuptools|wheel)==.*' | xargs sudo pip3 uninstall -y

echo "✅ All non-essential Python packages removed."

echo "🧹 STEP 2: Removing BLE/GATT-related system packages..."
sudo apt remove --purge -y \
  bluez \
  bluez-tools \
  libglib2.0-dev \
  python3-dbus \
  python3-gi

sudo apt autoremove -y
sudo apt clean

echo "✅ BLE-related system packages removed."

echo "📦 STEP 3: Reinstalling required system packages for BLE GATT server..."

sudo apt update
sudo apt install -y \
  bluez \
  bluez-tools \
  libglib2.0-dev \
  python3-dbus \
  python3-gi \
  python3-pip \
  python3-dev \
  python3-setuptools \
  build-essential \
  dbus-x11 \
  python3-bluez

echo "✅ System environment ready for GATT server."

