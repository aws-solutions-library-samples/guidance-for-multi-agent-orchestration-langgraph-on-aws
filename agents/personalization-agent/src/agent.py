"""
Personalization Agent using LangGraph StateGraph with correct pattern.
"""

import logging
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
    get_customer_profile,
    get_customer_preferences,
    analyze_customer_demographics,
    get_customer_browsing_behavior,
    analyze_browsing_patterns,
    get_similar_customer_insights,
    search_personalization_opportunities,
)
from models import (
    PersonalizationRequest,
    PersonalizationResponse,
    CustomerProfile,
    BrowsingInsight,
)
from prompts import PERSONALIZATION_SYSTEM_PROMPT

from config import config

logger = logging.getLogger(__name__)


class PersonalizationState(TypedDict):
    """State for the Personalization Agent."""

    messages: Annotated[list, add_messages]
    customer_id: str
    query: str
    processing_time: float


class PersonalizationGeneration(BaseModel):
    """Structured personalization generation."""

    customer_profile: CustomerProfile = Field(
        description="Customer profile information"
    )
    browsing_insights: List[BrowsingInsight] = Field(
        description="Browsing behavior insights"
    )
    personalization_summary: str = Field(
        description="Summary of customer personalization"
    )
    recommendations: List[str] = Field(description="Personalized recommendations")
    confidence_score: float = Field(description="Confidence in personalization (0-1)")


class PersonalizationAgent:
    """Personalization Agent using LangGraph with correct pattern."""

    def __init__(self):
        # Initialize LLM
        self.llm = self._initialize_llm()

        # Create tools and bind to LLM
        self.tools = self._create_personalization_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Create structured output LLM for final response generation
        self.personalization_llm = self.llm.with_structured_output(
            PersonalizationGeneration
        )

        # Build graph using correct pattern
        self.graph = self._create_state_graph()

    def _initialize_llm(self) -> ChatBedrockConverse:
        """Initialize the AWS Bedrock LLM."""
        try:
            llm = ChatBedrockConverse(
                model_id=config.bedrock_model_id,
                temperature=config.bedrock_temperature,
                region_name=config.aws_default_region,
                # credentials_profile_name=config.aws_credentials_profile
            )
            logger.info("Successfully initialized Bedrock LLM")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock LLM: {e}")
            raise

    def _create_personalization_tools(self):
        """Create personalization tools using @tool decorator."""

        @tool
        async def get_profile(customer_id: str) -> str:
            """
            Get customer profile information.

            Args:
                customer_id: Customer identifier

            Returns:
                Formatted string with customer profile
            """
            try:
                result = await get_customer_profile(customer_id)
                if result:
                    profile_info = []
                    profile_info.append(f"- Name: {result.get('name', 'N/A')}")
                    profile_info.append(f"- Age: {result.get('age', 'N/A')}")
                    profile_info.append(f"- Location: {result.get('location', 'N/A')}")
                    profile_info.append(
                        f"- Join Date: {result.get('join_date', 'N/A')}"
                    )
                    return f"Customer profile for {customer_id}:\n" + "\n".join(
                        profile_info
                    )
                else:
                    return f"No profile found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Profile lookup failed: {e}")
                return f"Error retrieving profile: {str(e)}"

        @tool
        async def get_preferences(customer_id: str) -> str:
            """
            Get customer preferences and settings.

            Args:
                customer_id: Customer identifier

            Returns:
                Formatted string with customer preferences
            """
            try:
                result = await get_customer_preferences(customer_id)
                if result:
                    pref_list = []
                    for pref in result:
                        pref_list.append(
                            f"- {pref.get('category', 'Category')}: {pref.get('preference', 'N/A')}"
                        )
                    return f"Customer preferences for {customer_id}:\n" + "\n".join(
                        pref_list
                    )
                else:
                    return f"No preferences found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Preferences lookup failed: {e}")
                return f"Error retrieving preferences: {str(e)}"

        @tool
        async def analyze_demographics(customer_id: str) -> str:
            """
            Analyze customer demographics for personalization.

            Args:
                customer_id: Customer identifier

            Returns:
                Formatted string with demographic analysis
            """
            try:
                result = await analyze_customer_demographics(customer_id)
                if result:
                    demo_info = []
                    demo_info.append(f"- Age Group: {result.get('age_group', 'N/A')}")
                    demo_info.append(
                        f"- Income Bracket: {result.get('income_bracket', 'N/A')}"
                    )
                    demo_info.append(
                        f"- Geographic Region: {result.get('geographic_region', 'N/A')}"
                    )
                    demo_info.append(
                        f"- Lifestyle Segment: {result.get('lifestyle_segment', 'N/A')}"
                    )
                    return f"Demographic analysis for {customer_id}:\n" + "\n".join(
                        demo_info
                    )
                else:
                    return f"No demographic data found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Demographics analysis failed: {e}")
                return f"Error analyzing demographics: {str(e)}"

        @tool
        async def get_browsing_behavior(customer_id: str, limit: int = 10) -> str:
            """
            Get customer browsing behavior from Knowledge Base.

            Args:
                customer_id: Customer identifier
                limit: Maximum number of browsing records

            Returns:
                Formatted string with browsing behavior
            """
            try:
                result = await get_customer_browsing_behavior(customer_id, limit)
                if result:
                    browsing_list = []
                    for item in result:
                        browsing_list.append(
                            f"- {item.get('page_category', 'Page')}: {item.get('time_spent', 0)}s on {item.get('visit_date', 'Unknown date')}"
                        )
                    return f"Recent browsing behavior for {customer_id}:\n" + "\n".join(
                        browsing_list
                    )
                else:
                    return f"No browsing data found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Browsing behavior lookup failed: {e}")
                return f"Error retrieving browsing data: {str(e)}"

        @tool
        async def analyze_patterns(
            customer_id: str, behavior_type: str = "general"
        ) -> str:
            """
            Analyze customer browsing patterns.

            Args:
                customer_id: Customer identifier
                behavior_type: Type of behavior analysis to perform

            Returns:
                Formatted string with pattern analysis
            """
            try:
                result = await analyze_browsing_patterns(customer_id, behavior_type)
                if result:
                    pattern_list = []
                    for pattern in result:
                        pattern_list.append(
                            f"- {pattern.get('pattern_type', 'Pattern')}: {pattern.get('description', 'N/A')}"
                        )
                    return (
                        f"Browsing patterns for {customer_id} ({behavior_type}):\n"
                        + "\n".join(pattern_list)
                    )
                else:
                    return f"No browsing patterns found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Pattern analysis failed: {e}")
                return f"Error analyzing patterns: {str(e)}"

        @tool
        async def get_similar_insights(customer_id: str) -> str:
            """
            Get insights from similar customers.

            Args:
                customer_id: Customer identifier

            Returns:
                Formatted string with similar customer insights
            """
            try:
                result = await get_similar_customer_insights(customer_id)
                if result:
                    insight_list = []
                    for insight in result:
                        insight_list.append(
                            f"- Similar Customer {insight.get('similar_customer_id', 'ID')}: {insight.get('insight', 'N/A')}"
                        )
                    return (
                        f"Similar customer insights for {customer_id}:\n"
                        + "\n".join(insight_list)
                    )
                else:
                    return f"No similar customer insights found for {customer_id}"
            except Exception as e:
                logger.error(f"Similar customer analysis failed: {e}")
                return f"Error getting similar insights: {str(e)}"

        @tool
        async def search_opportunities(customer_id: str, context: str) -> str:
            """
            Search for personalization opportunities.

            Args:
                customer_id: Customer identifier
                context: Context for personalization search

            Returns:
                Formatted string with personalization opportunities
            """
            try:
                result = await search_personalization_opportunities(
                    customer_id, context
                )
                if result:
                    opp_list = []
                    for opp in result:
                        opp_list.append(
                            f"- {opp.get('opportunity_type', 'Opportunity')}: {opp.get('description', 'N/A')}"
                        )
                    return (
                        f"Personalization opportunities for {customer_id}:\n"
                        + "\n".join(opp_list)
                    )
                else:
                    return f"No personalization opportunities found for {customer_id}"
            except Exception as e:
                logger.error(f"Opportunity search failed: {e}")
                return f"Error searching opportunities: {str(e)}"

        return [
            get_profile,
            get_preferences,
            analyze_demographics,
            get_browsing_behavior,
            analyze_patterns,
            get_similar_insights,
            search_opportunities,
        ]

    def _create_state_graph(self):
        """Create the LangGraph StateGraph using the correct pattern."""

        # Create the tool node for executing tools
        tool_node = ToolNode(self.tools)

        def call_model(state):
            """Call the LLM with tools to analyze and provide personalization insights."""
            messages = state["messages"]
            customer_id = state.get("customer_id", "")
            query = state.get("query", "")

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", PERSONALIZATION_SYSTEM_PROMPT),
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

            # Generate structured personalization
            structured_prompt = f"""
            Based on the conversation and tool results, generate structured personalization insights:
            
            Conversation Summary:
            {conversation_summary}
            
            Generate comprehensive customer personalization including profile, browsing insights, 
            recommendations, and confidence score.
            """

            try:
                structured_response = self.personalization_llm.invoke(
                    [HumanMessage(content=structured_prompt)]
                )
                return {"structured_output": structured_response}
            except Exception as e:
                logger.error(f"Error generating structured response: {e}")
                return {"structured_output": None}

        # Create the StateGraph
        workflow = StateGraph(PersonalizationState)

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

        return workflow.compile()

    async def process_request(
        self, request: PersonalizationRequest
    ) -> PersonalizationResponse:
        """Process a personalization request."""
        try:
            # Prepare the customer message
            customer_message = (
                request.query
                or f"Get personalization insights for customer {request.customer_id}"
            )
            if request.customer_id:
                customer_message += f" (Customer ID: {request.customer_id})"

            # Initialize state
            initial_state = {
                "messages": [HumanMessage(content=customer_message)],
                "customer_id": request.customer_id or "",
                "query": request.query or "",
                "processing_time": 0.0,
            }

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)

            # Extract structured output if available
            structured_output = final_state.get("structured_output")

            if structured_output and hasattr(structured_output, "customer_profile"):
                # Use structured output
                customer_profile = structured_output.customer_profile
                browsing_insights = structured_output.browsing_insights
                personalization_summary = structured_output.personalization_summary
                recommendations = structured_output.recommendations
                confidence_score = structured_output.confidence_score
            else:
                # Fallback to parsing the final message
                messages = final_state["messages"]
                final_message = messages[-1] if messages else None
                response_text = (
                    final_message.content
                    if final_message
                    else "No personalization data available"
                )

                # Create a simple fallback response
                customer_profile = None
                browsing_insights = []
                personalization_summary = response_text[:500]  # Truncate for summary
                recommendations = []
                confidence_score = 0.5

            return {
                "customer_profile": customer_profile,
                "browsing_insights": browsing_insights,
                "personalization_summary": personalization_summary,
                "recommendations": recommendations,
                "confidence_score": confidence_score,
            }

        except Exception as e:
            logger.error(f"Error processing personalization request: {e}")
            return PersonalizationResponse(
                customer_profile=None,
                browsing_insights=[],
                personalization_summary=f"Error processing request: {str(e)}",
                recommendations=[],
                confidence_score=0.0,
            )
