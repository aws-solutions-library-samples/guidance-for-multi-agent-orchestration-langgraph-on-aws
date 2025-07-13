#!/bin/bash
# Build script for Order Management Agent

set -e

echo "🏗️  Building Order Management Agent Docker image..."

# Get the agent root (one level up from this script)
AGENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AGENT_ROOT"

# Build the Docker image
echo "🐳 Building Docker image: order-management-agent"
docker build \
    -t order-management-agent:latest \
    .

echo "✅ Order Management Agent Docker image built successfully!"
echo "🚀 To run: docker run -p 8001:8001 order-management-agent"