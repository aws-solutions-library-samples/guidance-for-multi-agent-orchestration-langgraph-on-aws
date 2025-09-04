#!/bin/bash
# Run script for Troubleshooting Agent

set -e

# Default mode
MODE=${1:-local}

echo "🚀 Starting Troubleshooting Agent ($MODE mode)"
echo "=========================================="

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
        export PORT=8003
        export HOST=0.0.0.0
        export ENVIRONMENT=development
        
        # Set Knowledge Base IDs (these would be real KB IDs in production)
        export FAQ_KNOWLEDGE_BASE_ID="FAQ_KB_12345"
        export TROUBLESHOOTING_KNOWLEDGE_BASE_ID="TROUBLESHOOTING_KB_67890"
        
        # Run application
        echo "🎯 Starting Troubleshooting Agent on port 8003..."
        cd src
        python main.py
        ;;
        
    "docker")
        echo "🐳 Running in Docker container..."
        
        # Build if image doesn't exist
        if ! docker images | grep -q troubleshooting-agent; then
            echo "🔨 Building Docker image first..."
            ./scripts/build.sh
        fi
        
        # Stop existing container
        echo "🛑 Stopping existing container..."
        docker stop troubleshooting-agent 2>/dev/null || true
        docker rm troubleshooting-agent 2>/dev/null || true
        
        # Run container
        echo "🚀 Starting Docker container..."
        docker run -d \
            --name troubleshooting-agent \
            -p 8003:8003 \
            -e PORT=8003 \
            -e HOST=0.0.0.0 \
            -e FAQ_KNOWLEDGE_BASE_ID=FAQ_KB_12345 \
            -e TROUBLESHOOTING_KNOWLEDGE_BASE_ID=TROUBLESHOOTING_KB_67890 \
            troubleshooting-agent:latest
        
        echo "✅ Container started successfully!"
        echo "📋 Container info:"
        docker ps | grep troubleshooting-agent
        ;;
        
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage: $0 [local|docker]"
        exit 1
        ;;
esac

echo ""
echo "✅ Troubleshooting Agent is running!"
echo ""
echo "🌐 Service URL: http://localhost:8003"
echo "📖 API Documentation: http://localhost:8003/docs"
echo "❤️  Health Check: http://localhost:8003/health"
echo ""
echo "🧪 Test the service:"
echo '   curl -X POST http://localhost:8003/troubleshoot \'
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"query": "My headphones won't connect to Bluetooth"}'"'"''