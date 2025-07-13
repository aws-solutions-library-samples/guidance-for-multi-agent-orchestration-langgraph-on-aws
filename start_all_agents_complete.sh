#!/bin/bash
# Start all agents for complete multi-agent system testing

set -e

echo "🚀 Starting Complete Multi-Agent Customer Support System"
echo "========================================================="

# Function to start a service
start_service() {
    local service_name=$1
    local agent_dir=$2
    local port=$3
    local log_file=$4
    
    echo "🔧 Starting $service_name on port $port..."
    
    # Check if port is already in use
    if lsof -i :$port > /dev/null 2>&1; then
        echo "   ⚠️  Port $port is already in use, skipping $service_name"
        return 0
    fi
    
    # Change to agent directory and run
    cd "$agent_dir"
    if [[ ! -f "scripts/run.sh" ]]; then
        echo "   ❌ run.sh script not found in $agent_dir"
        cd ..
        return 1
    fi
    
    nohup ./scripts/run.sh local > "../../$log_file" 2>&1 &
    local pid=$!
    echo "   PID: $pid (log: $log_file)"
    
    # Give service time to start
    sleep 5
    
    # Check if process is still running
    if kill -0 $pid 2>/dev/null; then
        echo "   ✅ $service_name started successfully"
    else
        echo "   ❌ $service_name failed to start"
        echo "   📋 Log output:"
        tail -20 "../../$log_file" | sed 's/^/      /'
        cd ..
        return 1
    fi
    
    # Return to original directory
    cd ../..
}

echo ""
echo "🔍 Starting all services..."

# Start all agents in dependency order
echo ""
echo "📦 Starting foundational services..."

# Start Order Management Agent (required by supervisor)
start_service "Order Management Agent" \
    "agents/order-management-agent" \
    "8001" \
    "order_agent.log"

# Start Product Recommendation Agent
start_service "Product Recommendation Agent" \
    "agents/product-recommendation-agent" \
    "8002" \
    "product_recommendation_agent.log"

# Start Troubleshooting Agent
start_service "Troubleshooting Agent" \
    "agents/troubleshooting-agent" \
    "8003" \
    "troubleshooting_agent.log"

# Start Personalization Agent
start_service "Personalization Agent" \
    "agents/personalization-agent" \
    "8004" \
    "personalization_agent.log"

echo ""
echo "🎯 Starting supervisor service..."

# Start Supervisor Agent (depends on other agents)
start_service "Supervisor Agent" \
    "agents/supervisor-agent" \
    "8000" \
    "supervisor_agent.log"

echo ""
echo "⏱️  Waiting for all services to fully initialize..."
sleep 10

echo ""
echo "🧪 Testing service health..."

# Test all agents
services=(
    "8001:Order Management"
    "8002:Product Recommendation" 
    "8003:Troubleshooting"
    "8004:Personalization"
    "8000:Supervisor"
)

all_healthy=true

for service in "${services[@]}"; do
    port=$(echo $service | cut -d: -f1)
    name=$(echo $service | cut -d: -f2)
    
    if curl -s "http://localhost:$port/health" > /dev/null; then
        echo "✅ $name Agent (port $port): Healthy"
    else
        echo "❌ $name Agent (port $port): Not responding"
        all_healthy=false
    fi
done

echo ""
if [ "$all_healthy" = true ]; then
    echo "🎉 Complete Multi-Agent System is Ready!"
    echo ""
    echo "📋 Available Services:"
    echo "   Supervisor Agent:             http://localhost:8000"
    echo "   Order Management Agent:       http://localhost:8001"
    echo "   Product Recommendation Agent: http://localhost:8002"
    echo "   Troubleshooting Agent:        http://localhost:8003"
    echo "   Personalization Agent:        http://localhost:8004"
    echo ""
    echo "🧪 Test the complete system:"
    echo "   python quick_test_agents.py          # Quick validation"
    echo "   python test_all_agents_supervisor.py # Comprehensive test"
    echo ""
    echo "📖 API Documentation:"
    echo "   Supervisor:             http://localhost:8000/docs"
    echo "   Order Management:       http://localhost:8001/docs"
    echo "   Product Recommendation: http://localhost:8002/docs"
    echo "   Troubleshooting:        http://localhost:8003/docs"
    echo "   Personalization:        http://localhost:8004/docs"
else
    echo "⚠️  Some services are not healthy. Check the logs."
fi

echo ""
echo "🔄 All services running in background. To stop all:"
echo "   pkill -f 'order-management-agent' || true"
echo "   pkill -f 'product-recommendation-agent' || true"
echo "   pkill -f 'troubleshooting-agent' || true"
echo "   pkill -f 'personalization-agent' || true"
echo "   pkill -f 'supervisor-agent' || true"
echo ""
echo "📜 View logs:"
echo "   tail -f order_agent.log"
echo "   tail -f product_recommendation_agent.log"
echo "   tail -f troubleshooting_agent.log"
echo "   tail -f personalization_agent.log"
echo "   tail -f supervisor_agent.log"
echo ""
echo "Press Ctrl+C to stop all services"

# Create a function to stop all services
stop_all_services() {
    echo ""
    echo "🛑 Stopping all services..."
    
    # Kill all agent processes
    pkill -f "order-management-agent" || true
    pkill -f "product-recommendation-agent" || true  
    pkill -f "troubleshooting-agent" || true
    pkill -f "personalization-agent" || true
    pkill -f "supervisor-agent" || true
    
    # Wait a moment for graceful shutdown
    sleep 2
    
    # Force kill if needed
    services_ports=(8000 8001 8002 8003 8004)
    for port in "${services_ports[@]}"; do
        pid=$(lsof -ti :$port 2>/dev/null || true)
        if [[ -n "$pid" ]]; then
            echo "   Force stopping process on port $port (PID: $pid)"
            kill -9 $pid 2>/dev/null || true
        fi
    done
    
    echo "✅ All services stopped"
    exit 0
}

# Set up interrupt handler
trap stop_all_services INT

# Keep script running
echo "💡 Tip: Use 'python quick_test_agents.py' in another terminal to test the system"
echo ""

while true; do
    sleep 1
done