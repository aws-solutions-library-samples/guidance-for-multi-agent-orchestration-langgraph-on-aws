#!/bin/bash
# Run script for Order Management Agent

set -e

# Default configuration
PORT=${ORDER_AGENT_PORT:-8001}

echo "🚀 Starting Order Management Agent..."
echo "   Port: $PORT"

# Check if running in Docker or local
if [ "$1" = "docker" ]; then
    echo "🐳 Running with Docker..."
    
    # Build if image doesn't exist
    if ! docker image inspect order-management-agent:latest >/dev/null 2>&1; then
        echo "📦 Image not found, building..."
        ./build.sh
    fi
    
    # Run Docker container
    docker run -it --rm \
        --name order-management-agent \
        -p $PORT:8001 \
        -e ORDER_AGENT_PORT=8001 \
        order-management-agent:latest
        
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
    export ORDER_AGENT_PORT=$PORT
    
    # Ensure database exists
    if [ ! -f "order_management.db" ]; then
        echo "📁 Database not found. Creating SQLite database..."
        if [ -f "$PROJECT_ROOT/setup_sqlite_db.py" ]; then
            cd "$PROJECT_ROOT" && python setup_sqlite_db.py
            cp order_management.db "$AGENT_ROOT/"
            cd "$AGENT_ROOT"
        else
            echo "⚠️  Warning: No database setup script found"
        fi
    fi
    
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
    echo "  ORDER_AGENT_PORT=8001    # Port to run on"
    echo ""
    echo "Database:"
    echo "  SQLite database will be created automatically if not found"
    echo "  Database location: order_management.db"
    exit 1
fi