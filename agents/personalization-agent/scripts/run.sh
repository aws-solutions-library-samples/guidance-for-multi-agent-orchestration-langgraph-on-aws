#!/bin/bash
# Run script for Personalization Agent

set -e

# Default mode
MODE=${1:-local}

echo "🚀 Starting Personalization Agent ($MODE mode)"
echo "============================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📁 Project directory: $PROJECT_DIR"
cd "$PROJECT_DIR"

case $MODE in
    "local")
        echo "🐍 Running locally with Python..."
        
        # Check if .venv exists, create if not
        if [ ! -d ".venv" ]; then
            echo "📦 Creating virtual environment..."
            python -m venv .venv
        fi
        
        # Activate virtual environment
        echo "⚡ Activating virtual environment..."
        source .venv/bin/activate
        
        # Install dependencies
        echo "📦 Installing dependencies..."
        pip install -e .
        
        # Set environment variables
        export PYTHONPATH="$PROJECT_DIR/src:$PYTHONPATH"
        export PORT=8004
        export HOST=0.0.0.0
        export ENVIRONMENT=development
        
        # Set Knowledge Base IDs (these would be real KB IDs in production)
        export BROWSING_HISTORY_KNOWLEDGE_BASE_ID="BROWSING_KB_12345"
        
        # Run application
        echo "🎯 Starting Personalization Agent on port 8004..."
        cd src
        python main.py
        ;;
        
    "docker")
        echo "🐳 Running in Docker container..."
        
        # Build if image doesn't exist
        if ! docker images | grep -q personalization-agent; then
            echo "🔨 Building Docker image first..."
            ./scripts/build.sh
        fi
        
        # Stop existing container
        echo "🛑 Stopping existing container..."
        docker stop personalization-agent 2>/dev/null || true
        docker rm personalization-agent 2>/dev/null || true
        
        # Run container
        echo "🚀 Starting Docker container..."
        docker run -d \
            --name personalization-agent \
            -p 8004:8004 \
            -e PORT=8004 \
            -e HOST=0.0.0.0 \
            -e BROWSING_HISTORY_KNOWLEDGE_BASE_ID=BROWSING_KB_12345 \
            personalization-agent:latest
        
        echo "✅ Container started successfully!"
        echo "📋 Container info:"
        docker ps | grep personalization-agent
        ;;
        
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage: $0 [local|docker]"
        exit 1
        ;;
esac

echo ""
echo "✅ Personalization Agent is running!"
echo ""
echo "🌐 Service URL: http://localhost:8004"
echo "📖 API Documentation: http://localhost:8004/docs"
echo "❤️  Health Check: http://localhost:8004/health"
echo ""
echo "🧪 Test the service:"
echo '   curl -X POST http://localhost:8004/personalize \'
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"customer_id": "cust001", "query": "What are my preferences?"}'"'"''