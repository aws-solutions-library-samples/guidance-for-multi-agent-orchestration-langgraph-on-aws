"""
Simple multi-agent example using LangGraph handoffs.

This demonstrates the core handoff pattern from the LangGraph documentation
applied to a customer support scenario.
"""

import asyncio
import logging
from typing import Annotated, Literal
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent, InjectedState
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiAgentState(MessagesState):
    """Extended state for multi-agent system."""
    last_active_agent: str = "supervisor"


def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """Create a handoff tool for transferring control to another agent."""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transfer to {agent_name}"

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MultiAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={"messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )
    return handoff_tool


def create_simple_multi_agent_system():
    """Create a simple multi-agent system with handoffs."""
    
    # Mock LLM for demonstration (replace with actual LLM)
    class MockLLM:
        def __init__(self, model_name):
            self.model_name = model_name
        
        async def ainvoke(self, messages):
            # Simple mock response
            class MockResponse:
                def __init__(self, content):
                    self.content = content
            return MockResponse(f"Mock response from {self.model_name}")
    
    mock_llm = MockLLM("claude-3-5-sonnet")
    
    # Create handoff tools
    transfer_to_order_agent = create_handoff_tool(
        agent_name="order_agent",
        description="Transfer to order management specialist"
    )
    transfer_to_product_agent = create_handoff_tool(
        agent_name="product_agent", 
        description="Transfer to product recommendation specialist"
    )
    transfer_to_supervisor = create_handoff_tool(
        agent_name="supervisor",
        description="Transfer back to supervisor"
    )
    
    # Create simple tools for each agent
    @tool
    async def check_order_status(order_id: str) -> str:
        """Check the status of an order."""
        return f"Order {order_id} is currently being processed and will ship tomorrow."
    
    @tool
    async def get_product_recommendations(category: str) -> str:
        """Get product recommendations for a category."""
        return f"For {category}, I recommend: Premium Headphones, Smart Watch, Wireless Speaker."
    
    # Create agents with handoffs
    order_agent = create_react_agent(
        mock_llm,
        [check_order_status, transfer_to_product_agent, transfer_to_supervisor],
        prompt="You are an order management specialist. Help with order status, shipping, and returns.",
        name="order_agent"
    )
    
    product_agent = create_react_agent(
        mock_llm,
        [get_product_recommendations, transfer_to_order_agent, transfer_to_supervisor],
        prompt="You are a product recommendation specialist. Help customers find the right products.",
        name="product_agent"
    )
    
    supervisor = create_react_agent(
        mock_llm,
        [transfer_to_order_agent, transfer_to_product_agent],
        prompt="You are a supervisor. Analyze requests and delegate to the right specialist.",
        name="supervisor"
    )
    
    # Create agent wrapper functions
    def call_order_agent(state: MultiAgentState) -> Command[Literal["supervisor", "product_agent"]]:
        """Call the order management agent."""
        response = order_agent.invoke(state)
        update = {**response, "last_active_agent": "order_agent"}
        return Command(update=update, goto="supervisor")
    
    def call_product_agent(state: MultiAgentState) -> Command[Literal["supervisor", "order_agent"]]:
        """Call the product recommendation agent."""
        response = product_agent.invoke(state)
        update = {**response, "last_active_agent": "product_agent"}
        return Command(update=update, goto="supervisor")
    
    def call_supervisor(state: MultiAgentState) -> Command[Literal["order_agent", "product_agent"]]:
        """Call the supervisor agent."""
        response = supervisor.invoke(state)
        update = {**response, "last_active_agent": "supervisor"}
        return Command(update=update)
    
    # Create the multi-agent graph
    builder = StateGraph(MultiAgentState)
    builder.add_node("supervisor", call_supervisor)
    builder.add_node("order_agent", call_order_agent)
    builder.add_node("product_agent", call_product_agent)
    builder.add_edge(START, "supervisor")
    
    # Compile with memory
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


async def test_simple_handoffs():
    """Test the simple multi-agent system."""
    
    print("Creating simple multi-agent system...")
    graph = create_simple_multi_agent_system()
    
    # Test cases
    test_messages = [
        "What's the status of order ORD-123?",
        "Can you recommend some good headphones?",
        "I need help with both my order and finding new products"
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- Test {i} ---")
        print(f"Customer: {message}")
        
        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "last_active_agent": "supervisor"
        }
        
        # Create thread config
        thread_config = {"configurable": {"thread_id": f"test_{i}"}}
        
        try:
            # Execute the graph
            final_state = await graph.ainvoke(initial_state, config=thread_config)
            
            # Extract response
            messages = final_state["messages"]
            if messages:
                last_message = messages[-1]
                print(f"Assistant: {getattr(last_message, 'content', 'No response')}")
                print(f"Last Active Agent: {final_state.get('last_active_agent', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Test {i} failed: {e}")
            logger.error(f"Test {i} error: {e}", exc_info=True)
    
    print("\nSimple handoff testing completed!")


def demonstrate_handoff_concepts():
    """Demonstrate the key handoff concepts from LangGraph documentation."""
    
    print("\n" + "="*60)
    print("LANGGRAPH HANDOFF CONCEPTS DEMONSTRATION")
    print("="*60)
    
    print("""
Key Concepts from LangGraph Documentation:

1. HANDOFFS - A pattern where one agent hands off control to another
   - Specify which agent to transfer to
   - Include payload/context for the next agent
   - Use Command objects for state updates and transitions

2. COMMAND OBJECTS - Enable handoffs by specifying:
   - goto: Which agent/node to transfer to
   - update: State updates to make during transfer
   - graph: Which graph level to operate on (Command.PARENT)

3. MULTI-AGENT PATTERNS:
   - Supervisor: Central coordinator delegates to specialists
   - Swarm: Agents communicate peer-to-peer via handoffs
   - Hierarchical: Nested agent structures

4. IMPLEMENTATION STEPS:
   a) Create handoff tools using @tool decorator
   b) Use InjectedState to access current agent state
   c) Return Command objects to trigger handoffs
   d) Build StateGraph with agent nodes
   e) Use create_react_agent for tool-enabled agents

5. BENEFITS:
   - Seamless agent-to-agent communication
   - Maintains conversation context
   - Enables specialization and modularity
   - Supports complex multi-turn interactions
    """)


if __name__ == "__main__":
    print("🚀 Simple Multi-Agent Handoff Example")
    
    # Demonstrate concepts
    demonstrate_handoff_concepts()
    
    # Run simple test
    asyncio.run(test_simple_handoffs())
    
    print("✅ Example completed!")