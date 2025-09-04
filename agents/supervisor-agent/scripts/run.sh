#!/bin/bash
# Run script for Supervisor Agent

set -e

# Default configuration
PORT=${SUPERVISOR_PORT:-8000}

echo "🚀 Starting Supervisor Agent..."
echo "   Port: $PORT"

# Check if running in Docker or local
if [ "$1" = "docker" ]; then
    echo "🐳 Running with Docker..."
    
    # Build if image doesn't exist
    if ! docker image inspect supervisor-agent:latest >/dev/null 2>&1; then
        echo "📦 Image not found, building..."
        ./build.sh
    fi
    
    # Run Docker container
    docker run -it --rm \
        --name supervisor-agent \
        -p $PORT:8000 \
        -e SUPERVISOR_PORT=8000 \
        supervisor-agent:latest
        
elif [ "$1" = "local" ]; then
    echo "💻 Running locally..."
    
    # Get the agent root (one level up from scripts)
    AGENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$AGENT_ROOT"
    
    # Load environment variables from project root
    PROJECT_ROOT="$(cd "$AGENT_ROOT/../.." && pwd)"
    if [ -f "$PROJECT_ROOT/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    fi
    
    # Set port
    export SUPERVISOR_PORT=$PORT
    
    # Install dependencies if needed
    if [ ! -f ".venv/bin/activate" ]; then
        echo "📦 Installing dependencies..."
        python -m venv .venv
        source .venv/bin/activate
        pip install -e .
    else
        source .venv/bin/activate
    fi
    
    # Run the agent
    cd src && python main.py
    
else
    echo "Usage: $0 [docker|local]"
    echo ""
    echo "Examples:"
    echo "  $0 docker    # Run in Docker container"
    echo "  $0 local     # Run locally with Python"
    echo ""
    echo "Environment variables:"
    echo "  SUPERVISOR_PORT=8000     # Port to run on"
    echo ""
    echo "Integration with Order Agent:"
    echo "  Supervisor will connect to order agent at http://localhost:8001"
    echo "  Make sure order agent is running before starting supervisor"
    echo ""
    echo "AWS Configuration:"
    echo "  Requires AWS credentials for Bedrock LLM access"
    echo "  Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION"
    exit 1
fi