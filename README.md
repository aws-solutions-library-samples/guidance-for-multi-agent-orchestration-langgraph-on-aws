# LangGraph Multi-Agent Deployment

A multi-agent customer support system using LangGraph and AWS Bedrock, deployed on AWS with ECS Fargate and Aurora Serverless v2.

## Features

- Supervisor agent for intent analysis and agent coordination
- Order management agent for handling order-related queries
- Product recommendation agent for product suggestions
- Troubleshooting agent for technical support
- Personalization agent for customer profile management

## AWS Deployment

### Quick Start
```bash
# Deploy to AWS
cd infra
npm install
npx cdk deploy --all

# Clean up
./destroy-stacks.sh
```

### Architecture
- **ECS Fargate**: Serverless containers for each agent
- **Aurora Serverless v2**: Auto-scaling PostgreSQL database
- **Application Load Balancer**: Traffic routing to agents
- **RDS Data API**: Connection-less database access
- **GuardDuty Integration**: Automatic security monitoring

### Important Notes
- GuardDuty automatically creates VPC endpoints for ECS Fargate monitoring
- Use the provided cleanup script if stack destruction fails
- See `AWS_DEPLOYMENT_PLAN.md` for detailed architecture information

## Local Development

### Installation

```bash
# Install in editable mode
pip install -e .

# Or using UV
uv pip install -e .
```

### Usage

```bash
# Run supervisor agent
python -m src.supervisor_agent.main

# Run order management agent
python -m src.order_agent.main
```

### Testing

```bash
# Run tests
pytest tests/

# Run specific test
python tests/test_simple_graph_agent.py
```

## Documentation

- `AWS_DEPLOYMENT_PLAN.md` - Comprehensive deployment guide
- `AGENT_IMPLEMENTATION_GUIDE.md` - Agent development guide
- `LANGGRAPH_SUPERVISOR_IMPLEMENTATION.md` - Supervisor agent details
