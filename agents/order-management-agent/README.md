# Order Management Agent

LangGraph-based intelligent agent for handling customer order-related inquiries using AWS Bedrock and SQLite database.

## Features

- **Order Status Lookup**: Get detailed information about specific orders
- **Customer Order History**: Retrieve all orders for a customer
- **Inventory Checking**: Check product availability and stock levels
- **Shipping Status**: Track shipment progress and delivery dates
- **Return/Exchange Status**: Handle return and exchange inquiries
- **Order Summaries**: Provide general order statistics

## Architecture

- **LangGraph StateGraph**: Modern workflow orchestration with tool binding
- **AWS Bedrock**: Claude 3 Sonnet for natural language understanding
- **SQLite Database**: Local database with realistic test data
- **FastAPI**: REST API for integration with supervisor agent

## Quick Start

### Local Development

```bash
# Run locally (from order agent directory)
./run.sh local

# Or manually
cd ../..  # Go to project root
python -m src.order_agent.main
```

### Docker Deployment

```bash
# Build and run with Docker
./run.sh docker

# Or manually
./build.sh
docker run -p 8001:8001 order-management-agent
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Process Order Request
```bash
POST /process
Content-Type: application/json

{
    "customer_message": "What is the status of order ORD-2024-001?",
    "session_id": "session-123",
    "customer_id": "cust001"
}
```

### Service Information
```bash
GET /info
```

## Testing

### Test with SQLite Data

```bash
# From project root
python test_order_api.py
```

### Test Individual Queries

```bash
curl -X POST http://localhost:8001/process \
  -H "Content-Type: application/json" \
  -d '{
    "customer_message": "Check if ZenSound headphones are available",
    "session_id": "test-123"
  }'
```

## Database

The agent uses a SQLite database with realistic test data:

- **5 customers** (cust001-cust005)
- **10 products** in inventory (headphones, watches, speakers, etc.)
- **12 orders** with various statuses (processing, shipped, delivered, etc.)

### Sample Data

```sql
-- Orders
ORD-2024-001: ZenSound Wireless Headphones (processing)
ORD-2024-002: VitaFit Smartwatch (shipped) 
ORD-2024-003: QuickCharge Wireless Charger (delivered)

-- Inventory
ZenSound Wireless Headphones: 25 units available
AudioMax Pro Headphones: 18 units available
VitaFit Smartwatch: 15 units available
```

## Environment Variables

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
AWS_CREDENTIALS_PROFILE=your_profile

# Bedrock Configuration
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_TEMPERATURE=0.7

# Service Configuration
ORDER_AGENT_PORT=8001
API_HOST=0.0.0.0
```

## Tools Available

1. **query_order_by_id**: Look up specific order details
2. **query_customer_orders**: Get customer's order history
3. **check_product_inventory**: Check product availability
4. **check_shipping_status**: Get shipping information
5. **check_return_status**: Check return/exchange status
6. **get_order_summary**: Get general order statistics

## Integration

This agent is designed to work with the supervisor agent:

1. Supervisor receives customer query
2. Analyzes intent and routes order-related queries here
3. Order agent processes using LangGraph and database tools
4. Returns structured response to supervisor
5. Supervisor synthesizes final response to customer

## Development

### File Structure

```
src/order_agent/
├── Dockerfile              # Docker configuration
├── README.md               # This file
├── build.sh                # Build script
├── run.sh                  # Run script
├── main.py                 # FastAPI service
├── simple_graph_agent.py   # LangGraph agent implementation
├── sqlite_tools.py         # Database tools
└── config.py               # Configuration
```

### Adding New Tools

1. Add tool function in `sqlite_tools.py`
2. Create LangChain tool wrapper in `simple_graph_agent.py`
3. Add to tools list in `_create_database_tools()`
4. Test with new queries

### Monitoring

- Health endpoint: `GET /health`
- Logs: Structured logging with request tracing
- Metrics: Processing time, confidence scores, tool usage