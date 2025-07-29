# LangGraph Multi-Agent Deployment

A multi-agent customer support system using LangGraph and AWS Bedrock, deployed on AWS with ECS Fargate and Aurora Serverless v2.

## Features

- Supervisor agent for intent analysis and agent coordination
- Order management agent for handling order-related queries
- Product recommendation agent for product suggestions
- Troubleshooting agent for technical support
- Personalization agent for customer profile management

## AWS Deployment

### Prerequisites
Before deploying, ensure you have:
- AWS CLI installed and configured with appropriate permissions
- AWS CDK installed (`npm install -g aws-cdk`)
- Node.js (version 18 or later)
- jq (for JSON processing)

### Claude 3.7 Sonnet Cross-Region Inference Profile Setup

This project is configured to use **Claude 3.7 Sonnet cross-region inference profiles** for optimal performance and to avoid throttling issues. The system automatically selects the appropriate inference profile based on your deployment region:

**EU Regions (eu-west-1, eu-central-1, eu-west-3, eu-north-1):**
- Uses: `eu.anthropic.claude-3-7-sonnet-20250219-v1:0`
- Routes across multiple EU regions for better availability

**US Regions (us-east-1, us-east-2, us-west-2):**
- Uses: `us.anthropic.claude-3-7-sonnet-20250219-v1:0`
- Routes across multiple US regions for better availability

**Benefits:**
- Higher request limits compared to standard single-region models
- Eliminates throttling issues in multi-agent workflows
- Cross-region routing for improved availability and performance
- Optimized for concurrent multi-agent operations

**Override Configuration (Optional):**
If you need to use a specific model, set the environment variable:
```bash
export BEDROCK_MODEL_ID="eu.anthropic.claude-3-7-sonnet-20250219-v1:0"
```

### Quick Start - Automated Deployment
```bash
# One-command deployment (recommended)
./deploy.sh
```

The `deploy.sh` script will:
1. Deploy all AWS infrastructure (CDK stacks)
2. Extract configuration from deployed resources
3. Update frontend environment variables automatically
4. Install frontend dependencies
5. Display deployment summary

### Manual Deployment (Advanced)
```bash
# Deploy infrastructure only
cd infra
npm install
npx cdk deploy --all

# Update frontend configuration manually
cd ../frontend/scripts
node setup-config.js

# Install frontend dependencies
cd ..
npm install
```

### When to Use deploy.sh

**Use `./deploy.sh` when:**
- First-time deployment of the entire system
- You've made changes to CDK infrastructure code
- Frontend configuration is out of sync with deployed resources
- You want to ensure frontend and backend are properly connected

**The script automatically handles:**
- CDK infrastructure deployment
- Frontend environment variable configuration
- Dependency installation
- Configuration validation

**After deployment:**
- Frontend will be configured with correct API endpoints
- All AWS resources will be deployed and connected
- You can start the frontend with `cd frontend && npm run dev`

### Clean up
```bash
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
