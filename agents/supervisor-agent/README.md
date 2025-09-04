# Supervisor Agent

The central coordinator for the multi-agent customer support system. Analyzes customer intent, routes requests to specialized agents, and synthesizes responses using AWS Bedrock LLMs.

## Features

- **Intent Analysis**: Uses Claude 3 Sonnet for understanding customer queries
- **Agent Selection**: Routes requests to appropriate specialized agents
- **Response Synthesis**: Combines responses from multiple agents into coherent answers
- **LLM Structured Outputs**: Uses Pydantic models for consistent structured responses
- **Agent Health Monitoring**: Tracks status of all sub-agent services

## Architecture

- **LangChain with Structured Outputs**: Pydantic models for reliable parsing
- **AWS Bedrock**: Claude 3 Sonnet for intent analysis and response synthesis
- **FastAPI**: REST API for receiving customer requests
- **HTTP Client**: Communicates with specialized agent services
- **Async Processing**: Parallel agent calls for performance

## Quick Start

### Local Development

```bash
# Run locally (from supervisor agent directory)
./run.sh local

# Or manually
cd ../..  # Go to project root
python -m src.supervisor_agent.main
```

### Docker Deployment

```bash
# Build and run with Docker
./run.sh docker

# Or manually
./build.sh
docker run -p 8000:8000 supervisor-agent
```

## API Endpoints

### Process Customer Request
```bash
POST /process
Content-Type: application/json

{
    "customer_message": "What is the status of my order ORD-2024-001?",
    "session_id": "session-123",
    "customer_id": "cust001"
}
```

### Health Check
```bash
GET /health
```

### Agent Status
```bash
GET /agents/status
```

### Service Information
```bash
GET /
```

## Testing

### Test Integration with Order Agent

```bash
# From project root
python test_supervisor_integration.py
```

### Test Individual Components

```bash
# Test supervisor directly
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "customer_message": "Check my order status",
    "session_id": "test-123"
  }'

# Check agent health
curl http://localhost:8000/agents/status
```

## Agent Coordination

### Supported Agent Types

1. **Order Management** (port 8001)
   - Order status, inventory, shipping, returns
   - Route: `http://localhost:8001`

2. **Product Recommendation** (port 8002)
   - Product suggestions, reviews, purchase history
   - Route: `http://localhost:8002`

3. **Troubleshooting** (port 8003)
   - Technical issues, FAQ, warranty
   - Route: `http://localhost:8003`

4. **Personalization** (port 8004)
   - Customer profiles, preferences, browsing history
   - Route: `http://localhost:8004`

### Intent Analysis

The supervisor uses structured LLM outputs to analyze:

- **Primary Intent**: Main category (order, product, troubleshooting, etc.)
- **Multiple Intents**: Complex queries requiring multiple agents
- **Customer Context**: Customer ID mentions, urgency indicators
- **Confidence Scoring**: Reliability of intent classification

### Agent Selection Logic

```python
# Example intent → agent mapping
{
    "order": ["order_management"],
    "product": ["product_recommendation"], 
    "troubleshooting": ["troubleshooting"],
    "personalization": ["personalization"]
}

# Multiple agents for complex queries
if customer_id_mentioned:
    agents.insert(0, "personalization")  # Get context first
```

### Response Synthesis

- **Single Agent**: Direct response formatting
- **Multiple Agents**: LLM synthesis combining all responses
- **Error Handling**: Graceful degradation when agents fail
- **Confidence Calculation**: Weighted average of agent confidences

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
SUPERVISOR_PORT=8000
API_HOST=0.0.0.0

# Agent URLs (automatically configured)
ORDER_AGENT_URL=http://localhost:8001
PRODUCT_AGENT_URL=http://localhost:8002
TROUBLESHOOTING_AGENT_URL=http://localhost:8003
PERSONALIZATION_AGENT_URL=http://localhost:8004
```

## Integration Flow

```
1. Customer → Supervisor (/process)
2. Supervisor → Intent Analysis (LLM)
3. Supervisor → Agent Selection (LLM)
4. Supervisor → Parallel Agent Calls (HTTP)
5. Agents → Process & Return Results
6. Supervisor → Response Synthesis (LLM)
7. Supervisor → Customer (Final Response)
```

## Development

### File Structure

```
src/supervisor_agent/
├── Dockerfile              # Docker configuration
├── README.md               # This file
├── build.sh                # Build script
├── run.sh                  # Run script
├── main.py                 # FastAPI service
├── agent.py                # Main supervisor logic
├── client.py               # HTTP client for sub-agents
├── structured_models.py    # Pydantic models
├── prompts.py              # LLM prompts
└── config.py               # Configuration
```

### Adding New Agent Types

1. Add agent URL to `client.py`
2. Update intent analysis prompts
3. Add intent → agent mapping logic
4. Test routing with integration tests

### Monitoring

- Health endpoint: `GET /health`
- Agent status: `GET /agents/status`
- Structured logging with request tracing
- Processing time tracking
- Confidence score monitoring

## Error Handling

- **Agent Unavailable**: Graceful degradation, use available agents
- **LLM Failures**: Fallback to rule-based intent analysis
- **Timeout Handling**: 30s timeout with retry logic
- **Response Validation**: Pydantic model validation for all outputs