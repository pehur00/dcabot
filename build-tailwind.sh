#!/bin/bash
# Build Tailwind CSS for production

# Download Tailwind CLI if not present
if [ ! -f "./tailwindcss" ]; then
    echo "Downloading Tailwind CSS CLI..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux (for Render.com deployment)
        curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
        chmod +x tailwindcss-linux-x64
        mv tailwindcss-linux-x64 tailwindcss
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if [[ $(uname -m) == "arm64" ]]; then
            curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-macos-arm64
            chmod +x tailwindcss-macos-arm64
            mv tailwindcss-macos-arm64 tailwindcss
        else
            curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-macos-x64
            chmod +x tailwindcss-macos-x64
            mv tailwindcss-macos-x64 tailwindcss
        fi
    else
        echo "Unsupported OS: $OSTYPE"
        exit 1
    fi
fi

# Build CSS
echo "Building Tailwind CSS..."
./tailwindcss -i ./saas/static/css/tailwind.input.css -o ./saas/static/css/tailwind.output.css --minify

echo "Tailwind CSS build complete!"
