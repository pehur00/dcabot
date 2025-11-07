#!/bin/bash
# Build Tailwind CSS for production

set -e  # Exit on any error

# Download Tailwind CLI if not present
if [ ! -f "./tailwindcss" ]; then
    echo "Downloading Tailwind CSS CLI..."

    # Detect OS using uname (more reliable than OSTYPE)
    OS=$(uname -s)
    ARCH=$(uname -m)

    echo "Detected OS: $OS, Architecture: $ARCH"

    # Use Tailwind v3.4.17 (stable, v4 has content scanning issues)
    TAILWIND_VERSION="v3.4.17"

    if [[ "$OS" == "Linux" ]]; then
        # Linux (for Render.com deployment)
        echo "Downloading Tailwind CSS $TAILWIND_VERSION for Linux x64..."
        curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64
        chmod +x tailwindcss-linux-x64
        mv tailwindcss-linux-x64 tailwindcss
    elif [[ "$OS" == "Darwin" ]]; then
        # macOS
        if [[ "$ARCH" == "arm64" ]]; then
            echo "Downloading Tailwind CSS $TAILWIND_VERSION for macOS ARM64..."
            curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-macos-arm64
            chmod +x tailwindcss-macos-arm64
            mv tailwindcss-macos-arm64 tailwindcss
        else
            echo "Downloading Tailwind CSS $TAILWIND_VERSION for macOS x64..."
            curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-macos-x64
            chmod +x tailwindcss-macos-x64
            mv tailwindcss-macos-x64 tailwindcss
        fi
    else
        echo "ERROR: Unsupported OS: $OS"
        exit 1
    fi

    echo "Tailwind CLI downloaded successfully"
fi

# Verify tailwindcss binary exists and is executable
if [ ! -x "./tailwindcss" ]; then
    echo "ERROR: tailwindcss binary not found or not executable"
    exit 1
fi

# Build CSS
echo "Building Tailwind CSS..."
./tailwindcss -i ./saas/static/css/tailwind.input.css -o ./saas/static/css/tailwind.output.css --minify

# Verify output file was created
if [ ! -f "./saas/static/css/tailwind.output.css" ]; then
    echo "ERROR: Tailwind CSS output file was not generated"
    exit 1
fi

echo "Tailwind CSS build complete! ($(wc -c < ./saas/static/css/tailwind.output.css) bytes)"
