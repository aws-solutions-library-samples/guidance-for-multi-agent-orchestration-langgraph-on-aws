#!/bin/bash
# Build script for Supervisor Agent

set -e

echo "🏗️  Building Supervisor Agent Docker image..."

# Get the agent root (one level up from this script)
AGENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AGENT_ROOT"

# Build the Docker image
echo "🐳 Building Docker image: supervisor-agent"
docker build \
    -t supervisor-agent:latest \
    .

echo "✅ Supervisor Agent Docker image built successfully!"
echo "🚀 To run: docker run -p 8000:8000 supervisor-agent"