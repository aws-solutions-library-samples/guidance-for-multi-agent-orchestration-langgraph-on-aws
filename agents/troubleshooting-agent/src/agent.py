"""
Troubleshooting Agent using LangGraph StateGraph with correct pattern.
"""

import logging
import os
from typing import List, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from tools import (
    search_faq_for_product_info,
    search_troubleshooting_guides,
    search_product_specific_help,
    search_category_issues,
    get_warranty_information,
    search_comprehensive_help,
)
from models import (
    TroubleshootingRequest,
    TroubleshootingResponse,
    TroubleshootingSolution,
)
from prompts import TROUBLESHOOTING_SYSTEM_PROMPT
from dynamodb_session_saver import DynamoDBSaver

from config import config

logger = logging.getLogger(__name__)


class TroubleshootingState(TypedDict):
    """State for the Troubleshooting Agent."""

    messages: Annotated[list, add_messages]
    query: str
    product_name: str
    product_category: str
    session_id: str
    processing_time: float


class SolutionGeneration(BaseModel):
    """Structured solution generation."""

    solutions: List[TroubleshootingSolution] = Field(
        description="Troubleshooting solutions"
    )
    issue_analysis: str = Field(description="Analysis of the reported issue")
    confidence_score: float = Field(description="Confidence in solutions (0-1)")
    escalation_needed: bool = Field(description="Whether escalation is needed")


class TroubleshootingAgent:
    """Troubleshooting Agent using LangGraph with correct pattern."""

    def __init__(self):
        # Initialize LLM
        self.llm = self._initialize_llm()

        # Initialize session manager
        self.checkpointer = self._initialize_session_manager()

        # Create tools and bind to LLM
        self.tools = self._create_troubleshooting_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Create structured output LLM for final response generation
        self.solution_llm = self.llm.with_structured_output(SolutionGeneration)

        # Build graph using correct pattern
        self.graph = self._create_state_graph()

    def _initialize_llm(self) -> ChatBedrockConverse:
        """Initialize the AWS Bedrock LLM."""
        print(config.aws_credentials_profile)
        try:
            # llm = ChatBedrockConverse(
            #     model_id=config.bedrock_model_id,
            #     temperature=config.bedrock_temperature,
            #     region_name=config.aws_default_region,
            #     credentials_profile_name=config.aws_credentials_profile
            # )
            use_profile = not os.getenv(
                "AWS_EXECUTION_ENV"
            )  # Not running in AWS Lambda/ECS

            llm_kwargs = {
                "model_id": config.bedrock_model_id,
                "temperature": config.bedrock_temperature,
                "max_tokens": config.bedrock_max_tokens,
                "region_name": config.aws_default_region,
                # "performance_config": {"latency": "optimized"},
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

    def _initialize_session_manager(self) -> DynamoDBSaver | None:
        """Initialize the DynamoDB session manager."""
        try:
            if not config.enable_session_persistence:
                logger.info("Session persistence disabled")
                return None

            # Initialize the checkpointer
            checkpointer = DynamoDBSaver(
                table_name=config.dynamodb_table_name,
                region_name=config.aws_default_region,
                endpoint_url=config.dynamodb_endpoint_url,
            )

            logger.info(
                f"Successfully initialized DynamoDB session manager with table: {config.dynamodb_table_name}"
            )
            return checkpointer

        except Exception as e:
            logger.error(f"Failed to initialize session manager: {e}")
            logger.warning("Continuing without session persistence")
            return None

    def _get_session_config(self, session_id: str) -> dict:
        """
        Get session configuration for graph execution.

        Args:
            session_id: Session identifier

        Returns:
            Graph configuration dictionary
        """
        if self.checkpointer:
            return {
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": "troubleshooting",
                }
            }
        else:
            return {}

    def _create_troubleshooting_tools(self):
        """Create troubleshooting tools using @tool decorator."""

        @tool
        async def search_faq(query: str, limit: int = 3) -> str:
            """
            Search FAQ knowledge base for product information.

            Args:
                query: Search query for FAQ
                limit: Maximum number of results

            Returns:
                Formatted string with FAQ information
            """
            try:
                results = await search_faq_for_product_info(query, limit)
                if results:
                    faq_list = []
                    for item in results:
                        faq_list.append(
                            f"- Q: {item.get('question', 'N/A')} A: {item.get('answer', 'N/A')}"
                        )
                    return f"FAQ results for '{query}':\n" + "\n".join(faq_list)
                else:
                    return f"No FAQ results found for '{query}'"
            except Exception as e:
                logger.error(f"FAQ search failed: {e}")
                return f"Error searching FAQ: {str(e)}"

        @tool
        async def search_guides(query: str, limit: int = 3) -> str:
            """
            Search troubleshooting guides.

            Args:
                query: Search query for guides
                limit: Maximum number of results

            Returns:
                Formatted string with guide information
            """
            try:
                results = await search_troubleshooting_guides(query, limit)
                if results:
                    guide_list = []
                    for guide in results:
                        guide_list.append(
                            f"- {guide.get('title', 'Guide')}: {guide.get('content', '')[:100]}..."
                        )
                    return f"Troubleshooting guides for '{query}':\n" + "\n".join(
                        guide_list
                    )
                else:
                    return f"No troubleshooting guides found for '{query}'"
            except Exception as e:
                logger.error(f"Guide search failed: {e}")
                return f"Error searching guides: {str(e)}"

        @tool
        async def search_product_help(product_name: str, category: str = None) -> str:
            """
            Search product-specific help information.

            Args:
                product_name: Product name to search for
                category: Optional product category

            Returns:
                Formatted string with product help information
            """
            try:
                results = await search_product_specific_help(product_name, category)
                if results:
                    help_list = []
                    for item in results:
                        help_list.append(
                            f"- {item.get('topic', 'Help')}: {item.get('content', '')[:100]}..."
                        )
                    return f"Product help for '{product_name}':\n" + "\n".join(
                        help_list
                    )
                else:
                    return f"No product help found for '{product_name}'"
            except Exception as e:
                logger.error(f"Product help search failed: {e}")
                return f"Error searching product help: {str(e)}"

        @tool
        async def search_category_help(category: str, issue_keywords: List[str]) -> str:
            """
            Search category-specific issue information.

            Args:
                category: Product category
                issue_keywords: Keywords related to the issue

            Returns:
                Formatted string with category help information
            """
            try:
                results = await search_category_issues(category, issue_keywords)
                if results:
                    issue_list = []
                    for issue in results:
                        issue_list.append(
                            f"- {issue.get('issue_type', 'Issue')}: {issue.get('solution', '')[:100]}..."
                        )
                    return f"Category issues for '{category}':\n" + "\n".join(
                        issue_list
                    )
                else:
                    return f"No category issues found for '{category}'"
            except Exception as e:
                logger.error(f"Category search failed: {e}")
                return f"Error searching category issues: {str(e)}"

        @tool
        async def get_warranty_info(
            product_name: str = None, category: str = None
        ) -> str:
            """
            Get warranty information for products.

            Args:
                product_name: Optional product name
                category: Optional product category

            Returns:
                Formatted string with warranty information
            """
            try:
                results = await get_warranty_information(product_name, category)
                if results:
                    warranty_list = []
                    for warranty in results:
                        warranty_list.append(
                            f"- {warranty.get('product', 'Product')}: {warranty.get('warranty_period', 'N/A')} warranty"
                        )
                    return "Warranty information:\n" + "\n".join(warranty_list)
                else:
                    return "No warranty information found"
            except Exception as e:
                logger.error(f"Warranty search failed: {e}")
                return f"Error getting warranty info: {str(e)}"

        @tool
        async def search_comprehensive(query: str) -> str:
            """
            Comprehensive search across all troubleshooting resources.

            Args:
                query: Search query

            Returns:
                Formatted string with comprehensive search results
            """
            try:
                results = await search_comprehensive_help(query)
                if results:
                    help_list = []
                    for item in results[:5]:  # Limit to 5 results
                        help_list.append(
                            f"- {item.get('title', 'Result')}: {item.get('content', '')[:100]}..."
                        )
                    return f"Comprehensive search for '{query}':\n" + "\n".join(
                        help_list
                    )
                else:
                    return f"No comprehensive results found for '{query}'"
            except Exception as e:
                logger.error(f"Comprehensive search failed: {e}")
                return f"Error in comprehensive search: {str(e)}"

        return [
            search_faq,
            search_guides,
            search_product_help,
            search_category_help,
            get_warranty_info,
            search_comprehensive,
        ]

    def _create_state_graph(self):
        """Create the LangGraph StateGraph using the correct pattern."""

        # Create the tool node for executing tools
        tool_node = ToolNode(self.tools)

        def call_model(state):
            """Call the LLM with tools to analyze and provide troubleshooting solutions."""
            messages = state["messages"]
            query = state.get("query", "")
            product_name = state.get("product_name", "")
            product_category = state.get("product_category", "")

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", TROUBLESHOOTING_SYSTEM_PROMPT),
                    ("placeholder", "{messages}"),
                ]
            )

            # Create the chain
            agent_chain = prompt | self.llm_with_tools

            # Call LLM with tools
            response = agent_chain.invoke(state)

            # Return updated state
            return {"messages": [response]}

        def generate_structured_response(state):
            """Generate structured response using structured output."""
            messages = state["messages"]

            # Collect tool results and conversations
            conversation_summary = ""
            for message in messages:
                if hasattr(message, "content"):
                    conversation_summary += f"{message.content}\n"

            # Generate structured solutions
            structured_prompt = f"""
            Based on the conversation and tool results, generate structured troubleshooting solutions:
            
            Conversation Summary:
            {conversation_summary}
            
            Generate comprehensive troubleshooting solutions with analysis and confidence score.
            Include escalation recommendation if needed.
            """

            try:
                structured_response = self.solution_llm.invoke(
                    [HumanMessage(content=structured_prompt)]
                )
                return {"structured_output": structured_response}
            except Exception as e:
                logger.error(f"Error generating structured response: {e}")
                return {"structured_output": None}

        # Create the StateGraph
        workflow = StateGraph(TroubleshootingState)

        # Add nodes
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_node("generate_response", generate_structured_response)

        # Set entry point
        workflow.set_entry_point("agent")

        # Add conditional edges using tools_condition
        workflow.add_conditional_edges(
            "agent",
            tools_condition,
        )

        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")

        # Add edge to final response generation when no more tools needed
        workflow.add_edge("agent", "generate_response")
        workflow.add_edge("generate_response", END)

        # Compile the graph with checkpointer if available
        if self.checkpointer:
            logger.info("Compiling graph with DynamoDB session persistence")
            return workflow.compile(checkpointer=self.checkpointer)
        else:
            logger.info("Compiling graph without session persistence")
            return workflow.compile()

    async def process_request(
        self, request: TroubleshootingRequest
    ) -> TroubleshootingResponse:
        """Process a troubleshooting request."""
        try:
            # Prepare the customer message
            customer_message = request.query
            if request.product_name:
                customer_message += f" (Product: {request.product_name})"
            if request.product_category:
                customer_message += f" (Category: {request.product_category})"

            # Initialize state
            initial_state = {
                "messages": [HumanMessage(content=customer_message)],
                "query": request.query,
                "product_name": request.product_name or "",
                "product_category": request.product_category or "",
                "session_id": getattr(request, 'session_id', 'default-session'),
                "processing_time": 0.0,
            }

            # Get session configuration for persistence
            session_config = self._get_session_config(getattr(request, 'session_id', 'default-session'))

            # Run the graph with session persistence
            final_state = await self.graph.ainvoke(initial_state, config=session_config)

            # Extract structured output if available
            structured_output = final_state.get("structured_output")

            if structured_output and hasattr(structured_output, "solutions"):
                # Use structured output
                solutions = structured_output.solutions
                issue_analysis = structured_output.issue_analysis
                confidence_score = structured_output.confidence_score
                escalation_needed = structured_output.escalation_needed
            else:
                # Fallback to parsing the final message
                messages = final_state["messages"]
                final_message = messages[-1] if messages else None
                response_text = (
                    final_message.content if final_message else "No solutions available"
                )

                # Create a simple fallback response
                solutions = []
                issue_analysis = response_text[:500]  # Truncate for analysis
                confidence_score = 0.5
                escalation_needed = True

            return TroubleshootingResponse(
                solutions=solutions,
                issue_analysis=issue_analysis,
                confidence_score=confidence_score,
                escalation_needed=escalation_needed,
            )

        except Exception as e:
            logger.error(f"Error processing troubleshooting request: {e}")
            return TroubleshootingResponse(
                solutions=[],
                issue_analysis=f"Error processing request: {str(e)}",
                confidence_score=0.0,
                escalation_needed=True,
            )
