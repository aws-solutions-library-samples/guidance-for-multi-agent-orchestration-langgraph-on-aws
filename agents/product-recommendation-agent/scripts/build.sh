#!/bin/bash
# Build script for Product Recommendation Agent

set -e

echo "🔨 Building Product Recommendation Agent"
echo "======================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📁 Project directory: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Build Docker image
echo "🐳 Building Docker image..."
docker build -t product-recommendation-agent:latest .

echo "✅ Build complete!"
echo ""
echo "🚀 To run the agent:"
echo "   ./scripts/run.sh local   # Run locally with Python"
echo "   ./scripts/run.sh docker  # Run in Docker container"
echo ""
echo "🧪 To test the agent:"
echo "   curl http://localhost:8002/health"