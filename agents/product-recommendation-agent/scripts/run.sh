#!/bin/bash
# Run script for Product Recommendation Agent

set -e

# Default mode
MODE=${1:-local}

echo "🚀 Starting Product Recommendation Agent ($MODE mode)"
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
        export PORT=8002
        export HOST=0.0.0.0
        export ENVIRONMENT=development
        
        # Run application
        echo "🎯 Starting Product Recommendation Agent on port 8002..."
        cd src
        python main.py
        ;;
        
    "docker")
        echo "🐳 Running in Docker container..."
        
        # Build if image doesn't exist
        if ! docker images | grep -q product-recommendation-agent; then
            echo "🔨 Building Docker image first..."
            ./scripts/build.sh
        fi
        
        # Stop existing container
        echo "🛑 Stopping existing container..."
        docker stop product-recommendation-agent 2>/dev/null || true
        docker rm product-recommendation-agent 2>/dev/null || true
        
        # Run container
        echo "🚀 Starting Docker container..."
        docker run -d \
            --name product-recommendation-agent \
            -p 8002:8002 \
            -e PORT=8002 \
            -e HOST=0.0.0.0 \
            product-recommendation-agent:latest
        
        echo "✅ Container started successfully!"
        echo "📋 Container info:"
        docker ps | grep product-recommendation-agent
        ;;
        
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage: $0 [local|docker]"
        exit 1
        ;;
esac

echo ""
echo "✅ Product Recommendation Agent is running!"
echo ""
echo "🌐 Service URL: http://localhost:8002"
echo "📖 API Documentation: http://localhost:8002/docs"
echo "❤️  Health Check: http://localhost:8002/health"
echo ""
echo "🧪 Test the service:"
echo '   curl -X POST http://localhost:8002/recommend \'
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"query": "I need headphones for music", "customer_id": "cust001"}'"'"''