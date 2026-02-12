#!/bin/bash
set -e

echo "=== Edeon Desktop — Environment Setup ==="

# 1. Ensure cargo is in PATH
echo ""
echo "[1/5] Setting up Rust toolchain..."
if [ -f "$HOME/.cargo/env" ]; then
    . "$HOME/.cargo/env"
fi

if command -v rustup &> /dev/null; then
    echo "  rustup found, updating to latest stable..."
    rustup update stable
    rustup default stable
else
    echo "  Installing rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    . "$HOME/.cargo/env"
    rustup default stable
fi
echo "  Rust version: $(rustc --version)"

# 2. Install system dependencies for Tauri v2 on Ubuntu/Debian
# Note: libayatana-appindicator3-dev replaces the older libappindicator3-dev
# and they conflict with each other — only install one.
echo ""
echo "[2/5] Installing system dependencies for Tauri..."

# Remove conflicting package if present
if dpkg -l | grep -q 'libappindicator3-dev'; then
    echo "  Removing conflicting libappindicator3-dev..."
    sudo apt-get remove -y libappindicator3-dev libappindicator3-1 2>/dev/null || true
fi

sudo apt-get update
sudo apt-get install -y \
    libwebkit2gtk-4.1-dev \
    librsvg2-dev \
    patchelf \
    libssl-dev \
    libgtk-3-dev \
    libayatana-appindicator3-dev \
    libjavascriptcoregtk-4.1-dev \
    libsoup-3.0-dev \
    build-essential \
    curl \
    wget \
    file

# 3. Check Node.js
echo ""
echo "[3/5] Checking Node.js..."
echo "  Node version: $(node --version)"
echo "  npm version: $(npm --version)"

# 4. Install npm dependencies
echo ""
echo "[4/5] Installing npm dependencies..."
cd "$(dirname "$0")"
npm install

# 5. Verify everything
echo ""
echo "[5/5] Verifying setup..."
echo "  Rust: $(rustc --version)"
echo "  Cargo: $(cargo --version)"
echo "  Node: $(node --version)"
echo "  npm: $(npm --version)"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start the app, run:"
echo "  source \$HOME/.cargo/env"
echo "  npm run tauri dev"
