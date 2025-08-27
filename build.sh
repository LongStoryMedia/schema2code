#!/bin/bash

# Exit on error
set -e

# Function to get the user's shell config file
get_shell_config() {
    # Detect the current shell
    CURRENT_SHELL=$(basename "$SHELL")
    
    case "$CURRENT_SHELL" in
        "bash")
            if [ "$(uname)" == "Darwin" ]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
        ;;
        "zsh")
            echo "$HOME/.zshrc"
        ;;
        *)
            echo "$HOME/.profile"
        ;;
    esac
}

# Create and activate a virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment (works in both Unix and Windows/Git Bash)
if [ "$(uname)" == "Darwin" ] || [ "$(uname)" == "Linux" ]; then
    source .venv/bin/activate
else
    source .venv/Scripts/activate
fi

# Install the package in editable mode
echo "Installing package..."
pip install -e . --no-cache-dir --force-reinstall

# Get the absolute path to the virtual environment's bin/Scripts directory
if [ "$(uname)" == "Darwin" ] || [ "$(uname)" == "Linux" ]; then
    VENV_BIN="$(pwd)/.venv/bin"
else
    VENV_BIN="$(pwd)/.venv/Scripts"
fi

# Get the appropriate shell config file
SHELL_CONFIG=$(get_shell_config)

# Check if PATH already includes our bin directory
if ! grep -q "$VENV_BIN" "$SHELL_CONFIG" 2>/dev/null; then
    echo "Adding schema2code to PATH..."
    echo "export PATH=\"$VENV_BIN:\$PATH\"" >> "$SHELL_CONFIG"
    echo "Please run 'source $SHELL_CONFIG' to update your PATH, or restart your terminal"
else
    echo "schema2code is already in PATH"
fi

echo "Installation complete!"
echo "You can now use 'schema2code' from anywhere in your terminal"
echo "Run 'schema2code --help' to see available options"
