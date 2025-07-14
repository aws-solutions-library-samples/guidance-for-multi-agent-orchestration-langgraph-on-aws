"""
Supervisor agent implementation using LangGraph multi-agent pattern.

This module contains the core logic for the supervisor agent, including
intent analysis, agent delegation, and response synthesis using LangGraph.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any, Annotated, TypedDict, Literal
from enum import Enum

from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langgraph.prebuilt import ToolNode

from shared.models import (
    SupervisorRequest,
    SupervisorResponse,
    AgentRequest,
    AgentResponse,
    AgentType,
)
from shared.utils import truncate_text
import client
import prompts as supervisor_prompts
import config as supervisor_config
from structured_models import (
    IntentAnalysis,
    AgentSelection,
    ResponseSynthesis,
    ErrorResponse,
    CustomerNeedAssessment,
)

config = supervisor_config.config
logger = logging.getLogger(__name__)


# Define the graph state
class GraphState(TypedDict):
    """State that gets passed between agents in the graph."""

    # Core request information
    customer_message: str
    session_id: str
    customer_id: Optional[str]
    conversation_history: Optional[List[Dict[str, str]]]
    context: Optional[Dict[str, Any]]

    # Intent analysis results
    intent_info: Optional[Dict[str, Any]]

    # Agent selection
    selected_agents: List[str]
    agents_to_call: List[str]  # Remaining agents to call

    # Agent responses
    agent_responses: Dict[str, Any]

    # Final synthesis
    synthesized_response: Optional[str]
    confidence_score: Optional[float]

    # Processing metadata
    processing_time: Optional[float]
    start_time: float

    # Messages for agent communication
    messages: Annotated[list, add_messages]


class AgentNode(str, Enum):
    """Enum for agent node names in the graph."""

    SUPERVISOR = "supervisor"
    ORDER_MANAGEMENT = "order_management"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    TROUBLESHOOTING = "troubleshooting"
    PERSONALIZATION = "personalization"
    SYNTHESIZER = "synthesizer"


class SupervisorAgent:
    """Main supervisor agent for coordinating customer support interactions using LangGraph."""

    def __init__(self):
        """Initialize the supervisor agent."""
        self.llm = self._initialize_llm()
        self.client = client.SubAgentClient()
        self.max_response_words = 100

        # Create structured output models
        self.intent_analyzer = self.llm.with_structured_output(IntentAnalysis)
        self.agent_selector = self.llm.with_structured_output(AgentSelection)
        self.response_synthesizer = self.llm.with_structured_output(ResponseSynthesis)
        self.error_handler = self.llm.with_structured_output(ErrorResponse)
        self.need_assessor = self.llm.with_structured_output(CustomerNeedAssessment)

        # Build the multi-agent graph
        self.graph = self._build_graph()

    def _initialize_llm(self) -> ChatBedrock:
        """Initialize the AWS Bedrock LLM."""
        try:
            llm = ChatBedrock(
                model_id=config.bedrock_model_id,
                model_kwargs={
                    "temperature": config.bedrock_temperature,
                    "max_tokens": config.bedrock_max_tokens,
                },
                region_name=config.aws_default_region,
                # credentials_profile_name=config.aws_credentials_profile
            )
            logger.info("Successfully initialized Bedrock LLM")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock LLM: {e}")
            raise

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph multi-agent graph."""
        # Create the graph
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node(AgentNode.SUPERVISOR, self._supervisor_node)
        workflow.add_node(AgentNode.ORDER_MANAGEMENT, self._order_management_node)
        workflow.add_node(
            AgentNode.PRODUCT_RECOMMENDATION, self._product_recommendation_node
        )
        workflow.add_node(AgentNode.TROUBLESHOOTING, self._troubleshooting_node)
        workflow.add_node(AgentNode.PERSONALIZATION, self._personalization_node)
        workflow.add_node(AgentNode.SYNTHESIZER, self._synthesizer_node)

        # Add edges
        # Start with supervisor
        workflow.set_entry_point(AgentNode.SUPERVISOR)

        # Supervisor can route to any agent or synthesizer
        workflow.add_conditional_edges(
            AgentNode.SUPERVISOR,
            self._supervisor_router,
            {
                AgentNode.ORDER_MANAGEMENT: AgentNode.ORDER_MANAGEMENT,
                AgentNode.PRODUCT_RECOMMENDATION: AgentNode.PRODUCT_RECOMMENDATION,
                AgentNode.TROUBLESHOOTING: AgentNode.TROUBLESHOOTING,
                AgentNode.PERSONALIZATION: AgentNode.PERSONALIZATION,
                AgentNode.SYNTHESIZER: AgentNode.SYNTHESIZER,
            },
        )

        # Each agent can route to next agent or synthesizer
        for agent in [
            AgentNode.ORDER_MANAGEMENT,
            AgentNode.PRODUCT_RECOMMENDATION,
            AgentNode.TROUBLESHOOTING,
            AgentNode.PERSONALIZATION,
        ]:
            workflow.add_conditional_edges(
                agent,
                self._agent_router,
                {
                    AgentNode.ORDER_MANAGEMENT: AgentNode.ORDER_MANAGEMENT,
                    AgentNode.PRODUCT_RECOMMENDATION: AgentNode.PRODUCT_RECOMMENDATION,
                    AgentNode.TROUBLESHOOTING: AgentNode.TROUBLESHOOTING,
                    AgentNode.PERSONALIZATION: AgentNode.PERSONALIZATION,
                    AgentNode.SYNTHESIZER: AgentNode.SYNTHESIZER,
                },
            )

        # Synthesizer goes to END
        workflow.add_edge(AgentNode.SYNTHESIZER, END)

        # Compile the graph
        return workflow.compile()

    async def _supervisor_node(self, state: GraphState) -> Command:
        """
        Supervisor node that analyzes intent and selects agents.

        Returns Command to route to appropriate agent.
        """
        logger.info(f"Supervisor processing request for session {state['session_id']}")

        # Record start time
        start_time = time.time()

        # Step 1: Analyze customer intent
        intent_info = await self._analyze_intent(state["customer_message"])
        logger.info(f"Detected intent: {intent_info}")

        # Step 2: Select appropriate agents
        selected_agents = await self._select_agents(
            state["customer_message"], intent_info
        )
        logger.info(f"Selected agents: {selected_agents}")

        # Update state with analysis results
        update_state = {
            "intent_info": intent_info,
            "selected_agents": selected_agents,
            "agents_to_call": selected_agents.copy(),
            "agent_responses": {},
            "start_time": start_time,
            "messages": [
                {
                    "role": "system",
                    "content": f"Intent analyzed: {intent_info['primary_intent']}",
                }
            ],
        }

        # Route to first agent or synthesizer if no agents selected
        if selected_agents:
            next_agent = selected_agents[0]
            return Command(goto=next_agent, update=update_state)
        else:
            return Command(goto=AgentNode.SYNTHESIZER, update=update_state)

    async def _order_management_node(self, state: GraphState) -> Command:
        """Order management agent node."""
        return await self._generic_agent_node(state, "order_management")

    async def _product_recommendation_node(self, state: GraphState) -> Command:
        """Product recommendation agent node."""
        return await self._generic_agent_node(state, "product_recommendation")

    async def _troubleshooting_node(self, state: GraphState) -> Command:
        """Troubleshooting agent node."""
        return await self._generic_agent_node(state, "troubleshooting")

    async def _personalization_node(self, state: GraphState) -> Command:
        """Personalization agent node."""
        return await self._generic_agent_node(state, "personalization")

    async def _generic_agent_node(self, state: GraphState, agent_type: str) -> Command:
        """
        Generic agent node that calls HTTP sub-agent.

        Args:
            state: Current graph state
            agent_type: Type of agent to call

        Returns:
            Command to route to next agent or synthesizer
        """
        logger.info(f"Calling {agent_type} agent")

        # Prepare agent request
        agent_request = AgentRequest(
            customer_message=state["customer_message"],
            session_id=state["session_id"],
            customer_id=state.get("customer_id"),
            conversation_history=state.get("conversation_history"),
            context=state.get("context"),
            max_response_length=self.max_response_words,
        )

        # Call agent via HTTP
        try:
            response = await self.client.call_agent(agent_type, agent_request)
            logger.info(f"Received response from {agent_type}: {response}")

            # Update agent responses
            agent_responses = state.get("agent_responses", {})
            agent_responses[agent_type] = response

            # Remove this agent from agents_to_call
            agents_to_call = state.get("agents_to_call", [])
            if agent_type in agents_to_call:
                agents_to_call.remove(agent_type)

            # Add message about agent completion
            messages = [
                {"role": "assistant", "content": f"{agent_type} completed processing"}
            ]

            return Command(
                goto=self._get_next_agent(agents_to_call),
                update={
                    "agent_responses": agent_responses,
                    "agents_to_call": agents_to_call,
                    "messages": messages,
                },
            )

        except Exception as e:
            logger.error(f"Failed to call {agent_type} agent: {e}")

            # Continue to next agent or synthesizer on error
            agents_to_call = state.get("agents_to_call", [])
            if agent_type in agents_to_call:
                agents_to_call.remove(agent_type)

            return Command(
                goto=self._get_next_agent(agents_to_call),
                update={
                    "agents_to_call": agents_to_call,
                    "messages": [
                        {
                            "role": "error",
                            "content": f"Failed to call {agent_type}: {str(e)}",
                        }
                    ],
                },
            )

    async def _synthesizer_node(self, state: GraphState) -> Dict[str, Any]:
        """
        Synthesizer node that combines all agent responses.

        Returns final state update with synthesized response.
        """
        logger.info("Synthesizing agent responses")

        # Synthesize response
        synthesized_response = await self._synthesize_response(
            state["customer_message"], state.get("agent_responses", {})
        )

        # Set default confidence score (removed dependency on agent confidence scores)
        confidence_score = 0.8 if state.get("agent_responses") else 0.1

        # Calculate processing time
        processing_time = time.time() - state.get("start_time", time.time())

        return {
            "synthesized_response": synthesized_response,
            "confidence_score": confidence_score,
            "processing_time": processing_time,
            "messages": [{"role": "assistant", "content": synthesized_response}],
        }

    def _supervisor_router(self, state: GraphState) -> str:
        """Route from supervisor to first agent or synthesizer."""
        agents_to_call = state.get("agents_to_call", [])
        if agents_to_call:
            return agents_to_call[0]
        return AgentNode.SYNTHESIZER

    def _agent_router(self, state: GraphState) -> str:
        """Route from agent to next agent or synthesizer."""
        agents_to_call = state.get("agents_to_call", [])
        return self._get_next_agent(agents_to_call)

    def _get_next_agent(self, agents_to_call: List[str]) -> str:
        """Get next agent to call or synthesizer if none left."""
        if agents_to_call:
            return agents_to_call[0]
        return AgentNode.SYNTHESIZER

    async def process_request(self, request: SupervisorRequest) -> Dict[str, Any]:
        """
        Process a customer support request using the LangGraph.

        Args:
            request: Customer support request

        Returns:
            Response data in JSON format
        """
        try:
            # Prepare initial state
            initial_state = {
                "customer_message": request.customer_message,
                "session_id": request.session_id,
                "customer_id": request.customer_id,
                "conversation_history": request.conversation_history,
                "context": request.context,
                "messages": [],
            }

            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)

            # Helper function to format agent responses for validation
            def format_agent_response(
                agent_type: str, response_data: Any
            ) -> Dict[str, Any]:
                """Format agent response to match expected structure."""
                # Extract text from response
                if isinstance(response_data, dict) and "messages" in response_data:
                    messages = response_data["messages"]
                    if messages:
                        # Find the last AI message (not tool or human)
                        for message in reversed(messages):
                            if (
                                isinstance(message, dict)
                                and message.get("type") == "ai"
                            ):
                                content = message.get("content", "")

                                # Handle different content formats
                                if isinstance(content, str):
                                    response_text = content
                                    break
                                elif isinstance(content, list):
                                    # Extract text from content array, ignoring tool_use items
                                    text_parts = []
                                    for item in content:
                                        if (
                                            isinstance(item, dict)
                                            and item.get("type") == "text"
                                        ):
                                            text_parts.append(item.get("text", ""))
                                    response_text = " ".join(text_parts)
                                    break
                                else:
                                    response_text = str(content)
                                    break
                        else:
                            response_text = "No AI response found"
                    else:
                        response_text = "No messages available"
                else:
                    response_text = str(response_data)

                return {
                    "response": response_text,
                    "agent_type": agent_type,
                    "session_id": request.session_id,
                    "requires_followup": False,
                }

            # Format agent responses
            formatted_agent_responses = []
            for agent_type, response_data in final_state.get(
                "agent_responses", {}
            ).items():
                if response_data is not None:
                    formatted_response = format_agent_response(
                        agent_type, response_data
                    )
                    formatted_agent_responses.append(formatted_response)

            # Prepare response data
            response_data = {
                "response": final_state.get(
                    "synthesized_response", "Unable to process request"
                ),
                "agents_called": final_state.get("selected_agents", []),
                "agent_responses": formatted_agent_responses,
                "confidence_score": final_state.get("confidence_score", 0.1),
                "session_id": request.session_id,
                "processing_time": final_state.get("processing_time", 0.0),
                "follow_up_needed": final_state.get("confidence_score", 0.1) < 0.7,
            }

            return response_data

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return await self._handle_error(request, str(e))

    async def _analyze_intent(self, message: str) -> Dict[str, Any]:
        """
        Analyze customer intent using structured LLM output.

        Args:
            message: Customer message

        Returns:
            Intent analysis results
        """
        try:
            # Use structured LLM analysis
            intent_prompt = f"""
            Analyze this customer support message and determine their intent:
            
            Customer message: "{message}"
            
            Consider these intent categories:
            - order: Order status, tracking, shipping, returns, exchanges
            - product: Product recommendations, product information, purchasing
            - troubleshooting: Technical issues, problems, FAQ, warranty
            - personalization: Account info, preferences, customer profile
            - general: General inquiries that don't fit other categories
            
            Pay attention to:
            - Customer IDs mentioned (like cust001, customer-123)
            - Order IDs (like ORD-2024-001)
            - Product names or categories
            - Problem descriptions
            - Multiple requests in one message
            """

            intent_analysis = await self.intent_analyzer.ainvoke(intent_prompt)

            # Convert to dict format expected by rest of code
            return {
                "primary_intent": intent_analysis.primary_intent,
                "all_intents": intent_analysis.all_intents,
                "confidence": intent_analysis.confidence,
                "requires_multiple_agents": intent_analysis.requires_multiple_agents,
                "customer_id_mentioned": intent_analysis.customer_id_mentioned,
                "reasoning": intent_analysis.reasoning,
            }

        except Exception as e:
            logger.warning(f"Structured intent analysis failed, using fallback: {e}")
            return {
                "primary_intent": "general",
                "all_intents": ["general"],
                "confidence": 0.5,
                "requires_multiple_agents": False,
                "customer_id_mentioned": "cust" in message.lower(),
                "reasoning": "Fallback analysis due to error",
            }

    async def _select_agents(
        self, message: str, intent_info: Dict[str, Any]
    ) -> List[str]:
        """
        Select appropriate agents using structured LLM output.

        Args:
            message: Customer message
            intent_info: Intent analysis results

        Returns:
            List of agent types to call
        """
        try:
            agent_selection_prompt = f"""
            Based on this customer message and intent analysis, select which specialized agents should handle the request:
            
            Customer message: "{message}"
            Primary intent: {intent_info.get('primary_intent', 'general')}
            All intents: {intent_info.get('all_intents', [])}
            Multiple agents needed: {intent_info.get('requires_multiple_agents', False)}
            Customer ID mentioned: {intent_info.get('customer_id_mentioned', False)}
            
            Available agents:
            - order_management: Handles orders, inventory, shipping, returns, exchanges
            - product_recommendation: Provides product suggestions, reviews purchase history
            - troubleshooting: Resolves technical issues, FAQ, warranty information
            - personalization: Manages customer profiles, preferences, browsing history
            
            Rules:
            - If customer ID is mentioned, include personalization agent
            - For complex requests, you may select multiple agents
            - Consider execution order (personalization first if customer context needed)
            - Maximum 3 agents for performance
            - Prefer parallel execution when agents don't depend on each other
            """

            agent_selection = await self.agent_selector.ainvoke(agent_selection_prompt)

            logger.info(f"Agent selection reasoning: {agent_selection.reasoning}")

            # Validate and limit agents
            valid_agents = [
                "order_management",
                "product_recommendation",
                "troubleshooting",
                "personalization",
            ]
            selected = [
                agent
                for agent in agent_selection.selected_agents
                if agent in valid_agents
            ]

            # Limit to 3 agents maximum
            return selected[:3] if selected else ["order_management"]

        except Exception as e:
            logger.warning(f"Structured agent selection failed, using fallback: {e}")
            # Fallback to simple rule-based selection
            primary_intent = intent_info.get("primary_intent", "general")
            intent_to_agents = {
                "order": ["order_management"],
                "product": ["product_recommendation"],
                "troubleshooting": ["troubleshooting"],
                "personalization": ["personalization"],
                "general": ["order_management"],
            }

            selected = intent_to_agents.get(primary_intent, ["order_management"])

            # Add personalization if customer ID mentioned
            if (
                intent_info.get("customer_id_mentioned", False)
                and "personalization" not in selected
            ):
                selected.insert(0, "personalization")

            return selected[:3]

    async def _synthesize_response(
        self, customer_message: str, agent_responses: Dict[str, Any]
    ) -> str:
        """
        Synthesize responses from multiple agents into a coherent answer using structured LLM output.

        Args:
            customer_message: Original customer message
            agent_responses: Responses from called agents

        Returns:
            Synthesized response text
        """
        try:
            # Filter out None responses
            valid_responses = {
                agent: resp
                for agent, resp in agent_responses.items()
                if resp is not None
            }

            if not valid_responses:
                return "I apologize, but I'm having trouble accessing our systems right now. Please try again in a moment."

            # Extract text from agent responses (handling new graph state format)
            def extract_response_text(response_data):
                """Extract readable text from agent response data."""
                if isinstance(response_data, dict):
                    # Check for messages in graph state
                    if "messages" in response_data:
                        messages = response_data["messages"]
                        if messages:
                            last_message = messages[-1]
                            if (
                                isinstance(last_message, dict)
                                and "content" in last_message
                            ):
                                return last_message["content"]
                            elif hasattr(last_message, "content"):
                                return last_message.content

                    # Check for direct response field
                    if "response" in response_data:
                        return response_data["response"]

                    # Fallback to string representation
                    return str(response_data)
                else:
                    return str(response_data)

            # If only one response, use it directly (with some formatting)
            if len(valid_responses) == 1:
                response = list(valid_responses.values())[0]
                response_text = extract_response_text(response)
                return f"Based on my analysis: {response_text}"

            # Format agent responses for synthesis
            agent_responses_text = ""
            for agent_type, response in valid_responses.items():
                response_text = extract_response_text(response)
                agent_responses_text += (
                    f"\n{agent_type.replace('_', ' ').title()}: {response_text}"
                )

            # Use structured LLM synthesis
            synthesis_prompt = f"""
            You need to synthesize responses from multiple specialized agents into a single, coherent customer response.
            
            Customer's original message: "{customer_message}"
            
            Agent responses:
            {agent_responses_text}
            
            Create a professional, helpful response that:
            1. Addresses the customer's request completely
            2. Integrates information from all relevant agents
            3. Maintains a consistent, friendly tone
            4. Is concise but comprehensive
            5. Includes specific details when available
            6. Suggests next steps if appropriate
            
            Avoid:
            - Repeating the same information multiple times
            - Mentioning which specific agent provided information
            - Using overly technical language
            - Making the response too long or verbose
            """

            synthesis_result = await self.response_synthesizer.ainvoke(synthesis_prompt)

            logger.info(
                f"Synthesis confidence: {synthesis_result.confidence_assessment:.2f}"
            )
            logger.info(
                f"Key information used: {synthesis_result.key_information_used}"
            )

            return truncate_text(
                synthesis_result.synthesized_response, self.max_response_words * 6
            )

        except Exception as e:
            logger.warning(f"Structured synthesis failed, using fallback: {e}")
            return "I'm having trouble processing your request. Please try again."

    async def _handle_error(
        self, request: SupervisorRequest, error_details: str
    ) -> Dict[str, Any]:
        """
        Handle errors and provide fallback response.

        Args:
            request: Original request
            error_details: Error information

        Returns:
            Error response data
        """
        try:
            # Try to provide helpful error response using structured LLM
            error_prompt = f"""
            A customer support request has encountered an error. Provide a professional, helpful response to the customer.
            
            Customer's original message: "{request.customer_message}"
            Error details: {error_details}
            
            Guidelines:
            1. Acknowledge the issue professionally without technical jargon
            2. Apologize for the inconvenience
            3. Provide actionable alternatives when possible
            4. Suggest escalation paths if needed
            5. Maintain a helpful, empathetic tone
            6. Keep the response concise but complete
            
            Consider what the customer was trying to accomplish and suggest alternative ways they might get help.
            """

            error_result = await self.error_handler.ainvoke(error_prompt)

            logger.info(f"Error escalation needed: {error_result.escalation_needed}")
            logger.info(f"Suggested actions: {error_result.suggested_actions}")

            error_response = error_result.customer_response

        except Exception as e:
            logger.error(f"Structured error handling failed: {e}")
            # Final fallback
            error_response = "I'm experiencing technical difficulties and cannot process your request right now. Please try again in a few minutes or contact our support team directly."

        return {
            "response": error_response,
            "agents_called": [],
            "agent_responses": [],
            "confidence_score": 0.1,
            "session_id": request.session_id,
            "processing_time": 0.0,
            "follow_up_needed": True,
        }

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of supervisor and all sub-agents.

        Returns:
            Health status information
        """
        try:
            # Check sub-agents
            agent_health = await self.client.check_all_agents_health()

            # Test LLM connection
            llm_healthy = await self._test_llm_connection()

            overall_status = "healthy"
            if not llm_healthy:
                overall_status = "degraded"
            elif not all(agent_health.values()):
                overall_status = "degraded"

            return {
                "status": overall_status,
                "llm_connection": llm_healthy,
                "sub_agents": agent_health,
                "available_agents": self.client.get_available_agents(),
                "graph_nodes": list(self.graph.nodes.keys()),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def _test_llm_connection(self) -> bool:
        """Test LLM connection with a simple query."""
        try:
            messages = [{"role": "user", "content": "Hello"}]
            response = await self.llm.ainvoke(messages)
            return bool(response and response.content)
        except Exception as e:
            logger.warning(f"LLM connection test failed: {e}")
            return False

    def visualize_graph(self) -> str:
        """
        Generate a visual representation of the graph.

        Returns:
            Mermaid diagram string
        """
        try:
            # LangGraph's built-in visualization
            return self.graph.get_graph().draw_mermaid()
        except Exception as e:
            logger.error(f"Failed to visualize graph: {e}")
            return "Unable to generate graph visualization"
