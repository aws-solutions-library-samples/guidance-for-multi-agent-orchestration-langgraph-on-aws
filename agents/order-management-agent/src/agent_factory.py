"""
Factory for creating different types of order management agents.
"""

import os
from typing import Union

from .agent import OrderManagementAgent
from .graph_agent import GraphOrderManagementAgent
from .simple_graph_agent import SimpleGraphOrderAgent


class OrderAgentFactory:
    """Factory for creating order management agents."""
    
    @staticmethod
    def create_agent(agent_type: str = "simple") -> Union[OrderManagementAgent, GraphOrderManagementAgent, SimpleGraphOrderAgent]:
        """
        Create an order management agent of the specified type.
        
        Args:
            agent_type: Type of agent to create ("enhanced", "graph", "simple")
                - "enhanced": Enhanced agent with LLM structured outputs
                - "graph": Complex graph-based agent using LangGraph StateGraph
                - "simple": Simplified graph agent with tool binding (recommended)
        
        Returns:
            Order management agent instance
        """
        agent_type = agent_type.lower()
        
        if agent_type == "enhanced":
            return OrderManagementAgent()
        elif agent_type == "graph":
            return GraphOrderManagementAgent()
        elif agent_type == "simple":
            return SimpleGraphOrderAgent()
        else:
            raise ValueError(f"Unknown agent type: {agent_type}. Use 'enhanced', 'graph', or 'simple'")
    
    @staticmethod
    def get_recommended_agent() -> Union[OrderManagementAgent, GraphOrderManagementAgent, SimpleGraphOrderAgent]:
        """
        Get the recommended agent type based on environment or configuration.
        
        Returns:
            Recommended order management agent instance
        """
        # Check environment variable for preference
        agent_preference = os.getenv("ORDER_AGENT_TYPE", "simple").lower()
        
        try:
            return OrderAgentFactory.create_agent(agent_preference)
        except ValueError:
            # Fallback to simple graph agent if invalid preference
            return OrderAgentFactory.create_agent("simple")