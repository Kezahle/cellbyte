#!/bin/bash
# Setup script for the Chat with Your Data application

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Setting up the Chat with Your Data environment..."
echo ""

# --- 1. Check Python Version ---
echo "> Checking Python version (requires 3.9+)..."
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "Error: python3 command not found. Please install Python 3.9 or higher."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "  Found Python $PYTHON_VERSION"

# --- 2. Create Virtual Environment ---
echo "> Creating virtual environment in './venv'..."
if [ -d "venv" ]; then
    echo "  'venv' directory already exists, skipping creation."
else
    $PYTHON_CMD -m venv venv
    echo "  Virtual environment created."
fi

# --- 3. Activate Virtual Environment ---
echo "> Activating virtual environment..."
source venv/bin/activate
echo "  Virtual environment activated."

# --- 4. Install Dependencies ---
echo "> Installing dependencies from requirements.txt..."
pip install --upgrade pip --quiet
pip install -r requirements.txt
echo "  Dependencies installed successfully."

# --- 5. Create Directories ---
echo "> Ensuring required directories exist..."
mkdir -p sample_data outputs
echo "  'sample_data' and 'outputs' directories are ready."

# --- 6. Setup .env File ---
echo "> Setting up .env file..."
if [ -f ".env" ]; then
    echo "  '.env' file already exists. Skipping creation."
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "  '.env' file created from '.env.example'."
        echo "  IMPORTANT: Please edit the '.env' file and add your OPENAI_API_KEY."
    else
        cat > .env << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Execution Settings
USE_DOCKER_EXECUTION=False
CODE_EXECUTION_TIMEOUT=60

# Application Settings
HISTORY_LIMIT=5
MAX_CSV_SIZE_MB=100
EOF
        echo "  Created '.env' file with default settings."
        echo "  IMPORTANT: Edit the '.env' file and add your OPENAI_API_KEY."
    fi
fi

echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your OpenAI API key"
echo ""
echo "2. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Run the application:"
echo "   python main.py"
echo ""