"""
Product Recommendation Agent using LangGraph StateGraph with correct pattern.
"""

import logging
import os
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from tools import (
    search_products_by_name,
    get_products_by_category,
    get_customer_purchase_history,
    get_products_by_price_range,
    get_top_rated_products,
    search_customer_feedback,
)
from models import (
    ProductRecommendationRequest,
    ProductRecommendationResponse,
    ProductRecommendation,
)
from prompts import PRODUCT_RECOMMENDATION_SYSTEM_PROMPT

from config import config

logger = logging.getLogger(__name__)


class ProductRecommendationState(TypedDict):
    """State for the Product Recommendation Agent."""

    messages: Annotated[list, add_messages]
    customer_id: str
    query: str
    processing_time: float


class ProductAnalysis(BaseModel):
    """Structured analysis of customer query and preferences."""

    intent: str = Field(description="Customer's primary intent")
    category_preferences: List[str] = Field(description="Preferred product categories")
    price_sensitivity: str = Field(description="Price sensitivity (low/medium/high)")
    specific_products: List[str] = Field(description="Specific products mentioned")
    features_mentioned: List[str] = Field(description="Product features mentioned")


class ProductRecommendationAgent:
    """Product Recommendation Agent using LangGraph with correct pattern."""

    def __init__(self):
        # Initialize LLM
        self.llm = self._initialize_llm()

        # Create tools and bind to LLM
        self.tools = self._create_recommendation_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Build graph using correct pattern
        self.graph = self._create_state_graph()

    def _initialize_llm(self) -> ChatBedrockConverse:
        """Initialize the AWS Bedrock LLM."""
        try:
            # llm = ChatBedrockConverse(
            #     model_id=config.bedrock_model_id,
            #     temperature=config.bedrock_temperature,
            #     region_name=config.aws_default_region,
            #     # credentials_profile_name=config.aws_credentials_profile
            # )
            use_profile = not os.getenv(
                "AWS_EXECUTION_ENV"
            )  # Not running in AWS Lambda/ECS

            llm_kwargs = {
                "model_id": config.bedrock_model_id,
                "temperature": config.bedrock_temperature,
                "max_tokens": config.bedrock_max_tokens,
                "region_name": config.aws_default_region,
            }

            # Add credential profile for local development
            if use_profile:
                llm_kwargs["credentials_profile_name"] = config.aws_credentials_profile
                logger.info(
                    f"Using AWS credential profile: {config.aws_credentials_profile}"
                )
            else:
                logger.info(
                    "Using default AWS credential chain (IAM roles, environment variables, etc.)"
                )

            llm = ChatBedrockConverse(**llm_kwargs)
            logger.info("Successfully initialized Bedrock LLM")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock LLM: {e}")
            raise

    def _create_recommendation_tools(self):
        """Create product recommendation tools using @tool decorator."""

        @tool
        async def search_products(product_name: str) -> str:
            """
            Search for products by name.

            Args:
                product_name: Product name to search for

            Returns:
                Formatted string with product information
            """
            try:
                results = await search_products_by_name(product_name)
                if results:
                    product_list = []
                    for product in results[:3]:  # Limit to top 3
                        product_list.append(
                            f"- {product['product_name']}: ${product['price']} (Rating: {product['rating']}/5)"
                        )
                    return f"Products matching '{product_name}':\n" + "\n".join(
                        product_list
                    )
                else:
                    return f"No products found matching '{product_name}'"
            except Exception as e:
                logger.error(f"Product search failed: {e}")
                return f"Error searching for products: {str(e)}"

        @tool
        async def get_category_products(category: str, limit: int = 5) -> str:
            """
            Get products in a specific category.

            Args:
                category: Product category
                limit: Maximum number of products to return

            Returns:
                Formatted string with category products
            """
            try:
                results = await get_products_by_category(category, limit)
                if results:
                    product_list = []
                    for product in results:
                        product_list.append(
                            f"- {product['product_name']}: ${product['price']} (Rating: {product['rating']}/5)"
                        )
                    return f"Top products in {category} category:\n" + "\n".join(
                        product_list
                    )
                else:
                    return f"No products found in {category} category"
            except Exception as e:
                logger.error(f"Category search failed: {e}")
                return f"Error getting category products: {str(e)}"

        @tool
        async def get_purchase_history(customer_id: str) -> str:
            """
            Get customer's purchase history.

            Args:
                customer_id: Customer identifier

            Returns:
                Formatted string with purchase history
            """
            try:
                results = await get_customer_purchase_history(customer_id)
                if results:
                    purchase_list = []
                    for purchase in results[:5]:  # Limit to 5 recent purchases
                        purchase_list.append(
                            f"- {purchase['product_name']} ({purchase['category']}) - ${purchase['purchase_amount']} on {purchase['purchase_date']}"
                        )
                    return (
                        f"Recent purchases for customer {customer_id}:\n"
                        + "\n".join(purchase_list)
                    )
                else:
                    return f"No purchase history found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Purchase history query failed: {e}")
                return f"Error retrieving purchase history: {str(e)}"

        @tool
        async def get_top_products(category: str = None, limit: int = 5) -> str:
            """
            Get top-rated products.

            Args:
                category: Optional category filter
                limit: Maximum number of products to return

            Returns:
                Formatted string with top products
            """
            try:
                results = await get_top_rated_products(category, limit)
                if results:
                    product_list = []
                    for product in results:
                        product_list.append(
                            f"- {product['product_name']}: ${product['price']} (Rating: {product['rating']}/5)"
                        )
                    filter_text = f" in {category}" if category else ""
                    return f"Top-rated products{filter_text}:\n" + "\n".join(
                        product_list
                    )
                else:
                    return f"No top products found"
            except Exception as e:
                logger.error(f"Top products query failed: {e}")
                return f"Error getting top products: {str(e)}"

        @tool
        async def search_feedback(query: str) -> str:
            """
            Search customer feedback for insights.

            Args:
                query: Search query for feedback

            Returns:
                Formatted string with feedback insights
            """
            try:
                results = await search_customer_feedback(query)
                if results:
                    feedback_list = []
                    for feedback in results[:3]:  # Limit to 3 feedback items
                        feedback_list.append(
                            f"- {feedback['product_name']}: {feedback['feedback'][:100]}..."
                        )
                    return f"Customer feedback for '{query}':\n" + "\n".join(
                        feedback_list
                    )
                else:
                    return f"No customer feedback found for '{query}'"
            except Exception as e:
                logger.error(f"Feedback search failed: {e}")
                return f"Error searching feedback: {str(e)}"

        return [
            search_products,
            get_category_products,
            get_purchase_history,
            get_top_products,
            search_feedback,
        ]

    def _create_state_graph(self):
        """Create the LangGraph StateGraph using the correct pattern."""

        # Create the tool node for executing tools
        tool_node = ToolNode(self.tools)

        def call_model(state):
            """Call the LLM with tools to analyze and provide product recommendations."""
            messages = state["messages"]
            customer_id = state.get("customer_id", "")
            query = state.get("query", "")

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", PRODUCT_RECOMMENDATION_SYSTEM_PROMPT),
                    ("placeholder", "{messages}"),
                ]
            )

            # Create the chain
            agent_chain = prompt | self.llm_with_tools

            # Call LLM with tools
            response = agent_chain.invoke(state)
            logger.info(f"LLM response: {response}")

            # Return updated state
            return {"messages": [response]}

        # Create the StateGraph
        workflow = StateGraph(ProductRecommendationState)

        # Add nodes
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)

        # Set entry point
        workflow.set_entry_point("agent")

        # Add conditional edges using tools_condition
        workflow.add_conditional_edges(
            "agent",
            tools_condition,
        )

        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")

        # Add edge to END when no more tools needed
        workflow.add_edge("agent", END)

        return workflow.compile()

    async def process_request(self, request: ProductRecommendationRequest):
        """Process a product recommendation request."""
        try:
            # Prepare the customer message
            customer_message = request.query
            if request.customer_id:
                customer_message += f" (Customer ID: {request.customer_id})"

            # Initialize state
            initial_state = {
                "messages": [HumanMessage(content=customer_message)],
                "customer_id": request.customer_id or "",
                "query": request.query,
                "processing_time": 0.0,
            }

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            logger.info(f"Final state: {final_state}")

            # Return the graph response as-is without parsing
            return final_state

        except Exception as e:
            logger.error(f"Error processing recommendation request: {e}")
            return {
                "recommendations": [],
                "customer_insights": f"Error processing request: {str(e)}",
                "query_analysis": "Failed to analyze query",
                "confidence_score": 0.0,
            }
