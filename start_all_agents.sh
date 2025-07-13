#!/bin/bash
# Start all agents for integration testing (updated for new structure)

set -e

echo "🚀 Starting Multi-Agent Customer Support System"
echo "=" * 50

# Function to start a service
start_service() {
    local service_name=$1
    local agent_dir=$2
    local port=$3
    local log_file=$4
    
    echo "🔧 Starting $service_name on port $port..."
    
    # Change to agent directory and run
    cd "$agent_dir"
    nohup ./scripts/run.sh local > "../$log_file" 2>&1 &
    local pid=$!
    echo "   PID: $pid (log: ../$log_file)"
    
    # Give service time to start
    sleep 3
    
    # Check if process is still running
    if kill -0 $pid 2>/dev/null; then
        echo "   ✅ $service_name started successfully"
    else
        echo "   ❌ $service_name failed to start"
        cat "../$log_file"
        return 1
    fi
    
    # Return to original directory
    cd ..
}

echo ""
echo "🔍 Starting services..."

# Start Order Management Agent
start_service "Order Agent" \
    "agents/order-management-agent" \
    "8001" \
    "order_agent.log"

# Start Supervisor Agent  
start_service "Supervisor Agent" \
    "agents/supervisor-agent" \
    "8000" \
    "supervisor_agent.log"

echo ""
echo "⏱️  Waiting for services to initialize..."
sleep 5

echo ""
echo "🧪 Testing service health..."

# Test Order Agent
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ Order Agent: Healthy"
else
    echo "❌ Order Agent: Not responding"
fi

# Test Supervisor Agent
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Supervisor Agent: Healthy"
else
    echo "❌ Supervisor Agent: Not responding"
fi

echo ""
echo "🎉 Multi-Agent System Ready!"
echo ""
echo "📋 Available Services:"
echo "   Order Agent:      http://localhost:8001"
echo "   Supervisor Agent: http://localhost:8000"
echo ""
echo "🧪 To test integration:"
echo "   python test_supervisor_integration.py"
echo ""
echo "📖 API Documentation:"
echo "   Order Agent:      http://localhost:8001/docs"
echo "   Supervisor Agent: http://localhost:8000/docs"
echo ""
echo "🔄 Services running in background. To stop:"
echo "   pkill -f 'order-management-agent'"
echo "   pkill -f 'supervisor-agent'"
echo "   # Or use: kill \$(ps aux | grep 'main.py' | grep -v grep | awk '{print \$2}')"
echo ""
echo "📜 View logs:"
echo "   tail -f order_agent.log"
echo "   tail -f supervisor_agent.log"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap 'echo ""; echo "🛑 Stopping all services..."; pkill -f "order-management-agent" || true; pkill -f "supervisor-agent" || true; echo "✅ All services stopped"; exit 0' INT

# Keep script running
while true; do
    sleep 1
done