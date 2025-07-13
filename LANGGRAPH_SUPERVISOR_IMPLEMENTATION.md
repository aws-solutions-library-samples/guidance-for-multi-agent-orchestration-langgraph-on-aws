# LangGraph Supervisor Implementation

This document explains how the supervisor agent has been updated to use LangGraph's StateGraph with handoffs while maintaining integration with remote specialized agents.

## Architecture Overview

The new implementation combines LangGraph's workflow management with remote agent delegation:

```
Customer Request → LangGraph Supervisor → Remote Agent Delegation → Response Synthesis → Customer Response
```

## Key Components

### 1. LangGraphSupervisorAgent Class

Located in `agents/supervisor-agent/src/langgraph_supervisor.py`

**Key Features:**
- Uses LangGraph StateGraph for workflow coordination
- Maintains existing remote agent integration
- Structured intent analysis and response synthesis
- Conversation memory with checkpointer
- Error handling and fallback mechanisms

### 2. SupervisorState

Extended state class that tracks:
- Messages (conversation history)
- Session and customer information
- Agent responses and confidence scores
- Intent analysis results
- Selected agents for delegation

### 3. Delegation Tools

Tools that interface with remote specialized agents:

- `delegate_to_order_agent`: Handles order-related tasks
- `delegate_to_product_agent`: Manages product recommendations
- `delegate_to_troubleshooting_agent`: Resolves technical issues
- `delegate_to_personalization_agent`: Manages customer profiles
- `analyze_customer_intent`: Performs intent analysis

### 4. StateGraph Workflow

Three main nodes:

1. **supervisor**: Analyzes requests and delegates to appropriate agents
2. **synthesize_response**: Combines multiple agent responses
3. **human_input**: Handles user interaction (supports interrupts)

## Implementation Details

### Remote Agent Integration

The supervisor maintains the existing remote agent architecture:

```python
@tool
async def delegate_to_order_agent(
    task_description: Annotated[str, "Specific task for the order management agent"],
    state: Annotated[SupervisorState, InjectedState],
) -> str:
    # Create agent request
    agent_request = AgentRequest(
        customer_message=task_description,
        session_id=state["session_id"],
        customer_id=state.get("customer_id"),
        # ... other parameters
    )
    
    # Call remote order agent
    response = await self.client.call_agent("order_management", agent_request)
    
    # Store response in state
    state["agent_responses"]["order_management"] = response
    return f"Order Agent Response: {response.response}"
```

### Workflow Coordination

The StateGraph coordinates the workflow:

```python
def _create_supervisor_graph(self):
    # Create supervisor agent with delegation tools
    supervisor_agent = create_react_agent(
        self.llm,
        delegation_tools,
        prompt="You are a customer service supervisor..."
    )
    
    # Build StateGraph
    builder = StateGraph(SupervisorState)
    builder.add_node("supervisor", call_supervisor)
    builder.add_node("synthesize_response", synthesize_response)
    builder.add_node("human_input", human_input_node)
    builder.add_edge(START, "supervisor")
    
    return builder.compile(checkpointer=self.checkpointer)
```

### Response Synthesis

Structured LLM-based synthesis of multiple agent responses:

```python
async def _synthesize_response(self, customer_message: str, agent_responses: Dict[str, Any]) -> str:
    # Format agent responses
    agent_responses_text = ""
    for agent_type, response in valid_responses.items():
        agent_responses_text += f"\n{agent_type.replace('_', ' ').title()}: {response.response}"
    
    # Use structured LLM synthesis
    synthesis_prompt = f"""
    You need to synthesize responses from multiple specialized agents...
    Customer's original message: "{customer_message}"
    Agent responses: {agent_responses_text}
    """
    
    synthesis_result = await self.response_synthesizer.ainvoke(synthesis_prompt)
    return synthesis_result.synthesized_response
```

## Benefits of This Approach

### 1. **Workflow Management**
- Clear, structured workflow using LangGraph
- Built-in state management and conversation memory
- Proper error handling at each step

### 2. **Remote Agent Integration**
- Maintains existing specialized agent architecture
- No need to rewrite existing agents
- Scalable - easy to add new remote agents

### 3. **Structured Processing**
- Intent analysis using structured LLM output
- Agent selection based on customer needs
- Response synthesis for coherent answers

### 4. **Conversation Context**
- Maintains conversation history
- Tracks agent responses across turns
- Supports multi-turn interactions

### 5. **Error Resilience**
- Fallback mechanisms at each step
- Graceful degradation when agents are unavailable
- Structured error responses to customers

## Usage Example

```python
from agents.supervisor_agent.src.langgraph_supervisor import LangGraphSupervisorAgent
from agents.order_management_agent.src.shared.models import SupervisorRequest

# Initialize supervisor
supervisor = LangGraphSupervisorAgent()

# Create request
request = SupervisorRequest(
    customer_message="What's the status of my order ORD-2024-001?",
    session_id="customer_session_123",
    customer_id="cust001"
)

# Process request
response = await supervisor.process_request(request)

print(f"Response: {response.response}")
print(f"Agents Called: {response.agents_called}")
print(f"Confidence: {response.confidence_score}")
```

## Testing

Run the test scripts to verify functionality:

```bash
# Test the LangGraph supervisor
python test_langgraph_supervisor.py

# Test multi-agent handoffs
python test_multi_agent_handoffs.py

# Simple example
python simple_multi_agent_example.py
```

## Key Differences from Original

### Original Supervisor
- Direct agent calls in sequence
- Manual response synthesis
- Limited workflow structure
- Basic error handling

### LangGraph Supervisor
- StateGraph workflow coordination
- Tool-based agent delegation
- Structured state management
- Built-in conversation memory
- Enhanced error handling
- Support for interrupts and human input

## Future Enhancements

1. **Human-in-the-Loop**: Use `interrupt()` for human escalation
2. **Parallel Agent Calls**: Implement concurrent agent delegation
3. **Dynamic Agent Selection**: ML-based agent routing
4. **Conversation Analytics**: Track conversation patterns and success metrics
5. **Agent Health Monitoring**: Real-time agent availability checking

## Conclusion

The LangGraph supervisor implementation provides a robust, scalable architecture that combines the benefits of structured workflow management with existing remote agent capabilities. It maintains backward compatibility while adding powerful new features for conversation management and agent coordination.