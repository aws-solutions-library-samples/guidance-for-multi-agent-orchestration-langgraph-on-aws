# LangGraph Multi-Agent Deployment

A multi-agent customer support system using LangGraph and AWS Bedrock.

## Features

- Supervisor agent for intent analysis and agent coordination
- Order management agent for handling order-related queries
- Product recommendation agent for product suggestions
- Troubleshooting agent for technical support
- Personalization agent for customer profile management

## Installation

```bash
# Install in editable mode
pip install -e .

# Or using UV
uv pip install -e .
```

## Usage

```bash
# Run supervisor agent
python -m src.supervisor_agent.main

# Run order management agent
python -m src.order_agent.main
```

## Testing

```bash
# Run tests
pytest tests/

# Run specific test
python tests/test_simple_graph_agent.py
```