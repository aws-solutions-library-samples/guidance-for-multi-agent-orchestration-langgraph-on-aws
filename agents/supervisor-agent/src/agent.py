"""
Supervisor agent implementation using LangGraph multi-agent pattern.

This module contains the core logic for the supervisor agent, including
intent analysis, agent delegation, and response synthesis using LangGraph.
"""

import logging
import os
import time
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

import client
import config as supervisor_config
from dynamodb_session_saver import DynamoDBSaver
from shared.models import (
    AgentRequest,
    SupervisorRequest,
)
from shared.utils import truncate_text
from structured_models import (
    AgentSelection,
    CustomerNeedAssessment,
    ErrorResponse,
    IntentAnalysis,
    ResponseSynthesis,
    SupervisorDecision,
)

config = supervisor_config.config
logger = logging.getLogger(__name__)


# Define the graph state
class GraphState(TypedDict):
    """State that gets passed between agents in the graph."""

    # Core request information
    customer_message: str
    session_id: str
    customer_id: str | None
    conversation_history: list[dict[str, str]] | None
    context: dict[str, Any] | None

    # Intent analysis results
    intent_info: dict[str, Any] | None

    # Direct response capability
    can_respond_directly: bool | None
    direct_response: str | None

    # Agent selection
    selected_agents: list[str]
    agents_to_call: list[str]  # Remaining agents to call

    # Agent responses
    agent_responses: dict[str, Any]

    # Final synthesis
    synthesized_response: str | None
    confidence_score: float | None

    # Processing metadata
    processing_time: float | None
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

    def __init__(self, websocket_client=None):
        """Initialize the supervisor agent."""
        self.llm = self._initialize_llm()
        self.client = client.SubAgentClient()
        self.max_response_words = 100
        self.websocket_client = websocket_client

        # Create structured output models
        self.response_synthesizer = self.llm.with_structured_output(ResponseSynthesis)
        self.error_handler = self.llm.with_structured_output(ErrorResponse)
        self.supervisor_decision = self.llm.with_structured_output(SupervisorDecision)

        # Initialize session management
        self.checkpointer = self._initialize_session_manager()

        # Build the multi-agent graph
        self.graph = self._build_graph()

    def _initialize_llm(self) -> ChatBedrockConverse:
        """Initialize the AWS Bedrock LLM."""
        try:
            # Determine if we should use credential profile (for local development)
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

        # Compile the graph with checkpointer if available
        if self.checkpointer:
            logger.info("Compiling graph with DynamoDB session persistence")
            return workflow.compile(checkpointer=self.checkpointer)
        else:
            logger.info("Compiling graph without session persistence")
            return workflow.compile()

    async def _supervisor_node(self, state: GraphState) -> Command:
        """
        Supervisor node that analyzes intent, selects agents, and can provide direct responses.

        Returns Command to route to appropriate agent or synthesizer.
        """
        logger.info(f"Supervisor processing request for session {state['session_id']}")

        # Record start time
        start_time = time.time()

        # Combined intent analysis and agent selection with direct response capability
        supervisor_decision = await self._make_supervisor_decision(state)
        logger.info(f"Supervisor decision: {supervisor_decision}")

        # Convert to legacy format for compatibility
        intent_info = {
            "primary_intent": supervisor_decision.primary_intent,
            "all_intents": supervisor_decision.all_intents,
            "confidence": supervisor_decision.intent_confidence,
            "requires_multiple_agents": len(supervisor_decision.selected_agents) > 1,
            "customer_id_mentioned": supervisor_decision.customer_id_mentioned,
            "reasoning": supervisor_decision.reasoning,
        }

        # Update state with analysis results
        update_state = {
            "intent_info": intent_info,
            "can_respond_directly": supervisor_decision.can_respond_directly,
            "direct_response": supervisor_decision.direct_response,
            "selected_agents": supervisor_decision.selected_agents,
            "agents_to_call": supervisor_decision.selected_agents.copy(),
            "agent_responses": {},
            "start_time": start_time,
            "messages": [
                {
                    "role": "system",
                    "content": f"Intent analyzed: {supervisor_decision.primary_intent}",
                }
            ],
        }

        # Route based on decision
        if supervisor_decision.can_respond_directly:
            # Go directly to synthesizer with the direct response
            logger.info("Supervisor providing direct response")
            return Command(goto=AgentNode.SYNTHESIZER, update=update_state)
        elif supervisor_decision.selected_agents:
            # Route to first agent
            next_agent = supervisor_decision.selected_agents[0]
            logger.info(f"Routing to first agent: {next_agent}")
            return Command(goto=next_agent, update=update_state)
        else:
            # Fallback to synthesizer
            logger.info("No agents selected, going to synthesizer")
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

    async def _generic_agent_node_stream(self, state: GraphState, agent_type: str):
        """
        Generic agent node that streams from HTTP sub-agent.

        Args:
            state: Current graph state
            agent_type: Type of agent to call

        Yields:
            Streaming updates from the sub-agent
        """
        logger.info(f"Streaming from {agent_type} agent")

        # Prepare agent request
        agent_request = AgentRequest(
            customer_message=state["customer_message"],
            session_id=state["session_id"],
            customer_id=state.get("customer_id"),
            conversation_history=state.get("conversation_history"),
            context=state.get("context"),
            max_response_length=self.max_response_words,
        )

        # Stream from agent via HTTP
        try:
            final_response = None
            async for update in self.client.call_agent_stream(
                agent_type, agent_request
            ):
                # Forward sub-agent updates with supervisor context
                yield {
                    "type": "sub_agent_update",
                    "agent_type": agent_type,
                    "data": update,
                    "session_id": state["session_id"],
                    "timestamp": time.time(),
                }

                # Capture final response for state update
                if update.get("type") == "complete":
                    # Get the final response from the completed stream
                    final_response = update.get("data", {})

            # Update state with final response
            agent_responses = state.get("agent_responses", {})
            agent_responses[agent_type] = final_response or {
                "response": f"{agent_type} completed"
            }

            # Remove this agent from agents_to_call
            agents_to_call = state.get("agents_to_call", [])
            if agent_type in agents_to_call:
                agents_to_call.remove(agent_type)

            # Yield final state update
            yield {
                "type": "agent_completed",
                "agent_type": agent_type,
                "data": {
                    "agent_responses": agent_responses,
                    "agents_to_call": agents_to_call,
                    "next_agent": self._get_next_agent(agents_to_call),
                },
                "session_id": state["session_id"],
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Failed to stream from {agent_type} agent: {e}")

            # Continue to next agent or synthesizer on error
            agents_to_call = state.get("agents_to_call", [])
            if agent_type in agents_to_call:
                agents_to_call.remove(agent_type)

            # Yield error update
            yield {
                "type": "agent_error",
                "agent_type": agent_type,
                "data": {
                    "error": str(e),
                    "agents_to_call": agents_to_call,
                    "next_agent": self._get_next_agent(agents_to_call),
                },
                "session_id": state["session_id"],
                "timestamp": time.time(),
            }

    async def _synthesizer_node(self, state: GraphState) -> dict[str, Any]:
        """
        Synthesizer node that combines all agent responses or uses direct supervisor response.

        Returns final state update with synthesized response.
        """
        logger.info("Synthesizing response")

        # Check if supervisor provided direct response
        if state.get("can_respond_directly") and state.get("direct_response"):
            logger.info("Using direct supervisor response")
            synthesized_response = state["direct_response"]
            confidence_score = 0.9  # High confidence for direct responses
        else:
            # Synthesize from agent responses
            logger.info("Synthesizing from agent responses")
            synthesized_response = await self._synthesize_response(
                state["customer_message"], state.get("agent_responses", {})
            )
            # Set confidence score based on agent responses
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

    def _get_next_agent(self, agents_to_call: list[str]) -> str:
        """Get next agent to call or synthesizer if none left."""
        if agents_to_call:
            return agents_to_call[0]
        return AgentNode.SYNTHESIZER

    def _get_graph_config(self, session_id: str) -> dict[str, Any]:
        """
        Get graph configuration for session management.

        Args:
            session_id: Session identifier

        Returns:
            Graph configuration dictionary
        """
        if self.checkpointer:
            return {
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": "supervisor",
                }
            }
        else:
            return {}

    def _publish_websocket_update(self, session_id: str, update: dict[str, Any]) -> None:
        """
        Publish update to WebSocket channel for the session.

        Args:
            session_id: Session identifier
            update: Update data to publish
        """
        if not self.websocket_client or not self.websocket_client.connected:
            return

        try:
            # Publish to response channel for this session
            response_channel = f"/supervisor/{session_id}/response"
            self.websocket_client.publish_events(response_channel, [update])
            logger.debug(f"Published WebSocket update to {response_channel}: {update.get('type', 'unknown')}")
        except Exception as e:
            logger.warning(f"Failed to publish WebSocket update: {e}")

    async def process_request_stream(self, request: SupervisorRequest):
        """
        Process a customer support request using the LangGraph with streaming support.

        Args:
            request: Customer support request

        Yields:
            Streaming updates from the graph execution
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

            # Prepare configuration for session management
            graph_config = self._get_graph_config(request.session_id)

            # Publish start event
            start_update = {
                "type": "processing_started",
                "data": {
                    "session_id": request.session_id,
                    "customer_message": request.customer_message
                },
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, start_update)
            yield start_update
            
            last_chunk=None
            # Stream the graph execution with updates mode
            async for chunk in self.graph.astream(
                initial_state, config=graph_config, stream_mode="updates"
            ):
                # Create progress update
                progress_update = {
                    "type": "progress",
                    "data": chunk,
                    "session_id": request.session_id,
                    "timestamp": time.time(),
                }
                
                # Publish to WebSocket
                self._publish_websocket_update(request.session_id, progress_update)
                last_chunk=chunk
                # Yield progress updates
                yield progress_update

            # Publish completion event
            completion_update = {
                "type": "processing_complete",
                "session_id": request.session_id,
                "data": last_chunk,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, completion_update)
            yield completion_update

        except Exception as e:
            logger.error(f"Error in streaming request: {e}")
            error_update = {
                "type": "error",
                "data": {"error": str(e)},
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, error_update)
            yield error_update

    async def process_request_stream_tokens(self, request: SupervisorRequest):
        """
        Process a customer support request with LLM token streaming support.

        Args:
            request: Customer support request

        Yields:
            Streaming LLM tokens and progress updates
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

            # Prepare configuration for session management
            graph_config = self._get_graph_config(request.session_id)

            # Publish start event
            start_update = {
                "type": "token_streaming_started",
                "data": {
                    "session_id": request.session_id,
                    "customer_message": request.customer_message
                },
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, start_update)
            yield start_update

            # Stream with multiple modes: updates for progress, messages for LLM tokens
            async for stream_type, chunk in self.graph.astream(
                initial_state, config=graph_config, stream_mode=["updates", "messages"]
            ):
                if stream_type == "updates":
                    # Create progress update
                    progress_update = {
                        "type": "progress",
                        "data": chunk,
                        "session_id": request.session_id,
                        "timestamp": time.time(),
                    }
                    
                    # Publish to WebSocket
                    self._publish_websocket_update(request.session_id, progress_update)
                    
                    # Yield progress updates
                    yield progress_update
                    
                elif stream_type == "messages":
                    # Yield LLM token streams
                    message_chunk, metadata = chunk
                    if message_chunk.content:
                        token_update = {
                            "type": "token",
                            "data": {
                                "content": message_chunk.content,
                                "node": metadata.get("langgraph_node", "unknown"),
                                "metadata": metadata,
                            },
                            "session_id": request.session_id,
                            "timestamp": time.time(),
                        }
                        
                        # Publish to WebSocket
                        self._publish_websocket_update(request.session_id, token_update)
                        
                        yield token_update

            # Publish completion event
            completion_update = {
                "type": "token_streaming_complete",
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, completion_update)
            yield completion_update

        except Exception as e:
            logger.error(f"Error in token streaming request: {e}")
            error_update = {
                "type": "error",
                "data": {"error": str(e)},
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, error_update)
            yield error_update

    async def process_request(self, request: SupervisorRequest) -> dict[str, Any]:
        """
        Process a customer support request using the LangGraph.

        Args:
            request: Customer support request

        Returns:
            Response data in JSON format
        """
        try:
            # Publish start event
            start_update = {
                "type": "request_processing_started",
                "data": {
                    "session_id": request.session_id,
                    "customer_message": request.customer_message
                },
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, start_update)

            # Prepare initial state
            initial_state = {
                "customer_message": request.customer_message,
                "session_id": request.session_id,
                "customer_id": request.customer_id,
                "conversation_history": request.conversation_history,
                "context": request.context,
                "messages": [
                    {"role": "user", "content": request.customer_message},
                ],
            }

            # Prepare configuration for session management
            graph_config = self._get_graph_config(request.session_id)

            # Run the graph and get final state
            final_state = None
            async for chunk in self.graph.astream(
                initial_state, config=graph_config, stream_mode="values"
            ):
                final_state = chunk
                
                # Publish intermediate state updates
                state_update = {
                    "type": "state_update",
                    "data": {
                        "current_node": chunk.get("current_node", "unknown"),
                        "agents_called": chunk.get("selected_agents", []),
                        "processing_stage": "in_progress"
                    },
                    "session_id": request.session_id,
                    "timestamp": time.time(),
                }
                self._publish_websocket_update(request.session_id, state_update)

            # Helper function to format agent responses for validation
            def format_agent_response(
                agent_type: str, response_data: Any
            ) -> dict[str, Any]:
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

            # Publish completion event
            completion_update = {
                "type": "request_processing_complete",
                "data": {
                    "response": response_data["response"],
                    "agents_called": response_data["agents_called"],
                    "confidence_score": response_data["confidence_score"],
                    "processing_time": response_data["processing_time"]
                },
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, completion_update)

            return response_data

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            
            # Publish error event
            error_update = {
                "type": "request_processing_error",
                "data": {"error": str(e)},
                "session_id": request.session_id,
                "timestamp": time.time(),
            }
            self._publish_websocket_update(request.session_id, error_update)
            
            return await self._handle_error(request, str(e))

    async def _make_supervisor_decision(self, state: GraphState) -> SupervisorDecision:
        """
        Make combined supervisor decision including intent analysis, agent selection, and direct response capability.
        Uses complete state context including conversation history.

        Args:
            state: Complete graph state with all context

        Returns:
            SupervisorDecision with intent, agents, and potential direct response
        """
        try:
            # Create comprehensive prompt for supervisor decision using the complete state
            supervisor_prompt = f"""
            You are a customer support supervisor AI. Analyze the complete context and make a decision about how to handle this customer request.

            CURRENT STATE:
            Customer Message: "{state['customer_message']}"
            Session ID: {state['session_id']}
            Customer ID: {state.get('customer_id', 'Not provided')}
            Conversation History: {state.get('conversation_history', [])}
            Additional Context: {state.get('context', {})}
            Messages: {state.get('messages', [])}

            DECISION CRITERIA:

            1. DIRECT RESPONSE - You can respond directly (without calling sub-agents) for:
               - Simple greetings, thank you messages, or pleasantries
               - General company information questions (hours, policies, contact info)
               - Basic FAQ that doesn't require specific data lookup
               - Requests that are too vague to route to specific agents
               - Follow-up acknowledgments or clarifications

            2. SUB-AGENT ROUTING - Route to specialized agents for:
               - order_management: Order status, tracking, shipping, returns, exchanges, inventory
               - product_recommendation: Product suggestions, reviews, purchase history, recommendations
               - troubleshooting: Technical issues, problems, FAQ, warranty, how-to questions
               - personalization: Account info, preferences, customer profile, browsing history

            INTENT CATEGORIES:
            - order: Order-related requests
            - product: Product information and recommendations
            - troubleshooting: Technical support and problem resolution
            - personalization: Account and preference management
            - general: Greetings, company info, vague requests

            RULES:
            - You may select multiple agents (max 2) ONLY for COMPLEX QUERIES. DO NOT USE MULTIPLE AGENTS FOR SIMPLE QUERIES LIKE ORDER STATUS
            - Prefer direct response for simple, generic questions
            - Use conversation history and messages to understand context and intent
            - Be decisive - either respond directly OR route to agents, not both

            Analyze the complete state and provide your decision.
            """

            decision = await self.supervisor_decision.ainvoke(supervisor_prompt)

            logger.info(f"Supervisor decision reasoning: {decision.reasoning}")
            logger.info(f"Can respond directly: {decision.can_respond_directly}")
            if decision.can_respond_directly:
                logger.info(f"Direct response: {decision.direct_response}")
            else:
                logger.info(f"Selected agents: {decision.selected_agents}")

            # Validate and clean up the decision
            if decision.can_respond_directly and not decision.direct_response:
                # If marked as direct response but no response provided, fallback to agent routing
                decision.can_respond_directly = False
                decision.selected_agents = ["order_management"]  # Safe fallback

            # Validate selected agents
            valid_agents = [
                "order_management",
                "product_recommendation",
                "troubleshooting",
                "personalization",
            ]
            decision.selected_agents = [
                agent for agent in decision.selected_agents if agent in valid_agents
            ][
                :3
            ]  # Limit to 3 agents max

            # Ensure execution order matches selected agents
            decision.execution_order = decision.selected_agents.copy()

            return decision

        except Exception as e:
            logger.warning(f"Supervisor decision failed, using fallback: {e}")
            # Fallback decision
            return SupervisorDecision(
                primary_intent="general",
                all_intents=["general"],
                intent_confidence=0.5,
                can_respond_directly=False,
                selected_agents=["order_management"],
                execution_order=["order_management"],
                parallel_execution=True,
                customer_id_mentioned="cust" in state["customer_message"].lower(),
                key_entities=[],
                urgency_level="medium",
                reasoning="Fallback decision due to error in analysis",
            )

    async def _synthesize_response(
        self, customer_message: str, agent_responses: dict[str, Any]
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
    ) -> dict[str, Any]:
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

    async def get_health_status(self) -> dict[str, Any]:
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

            # Test session management
            session_healthy = await self._test_session_connection()

            # Check WebSocket status
            websocket_status = {
                "enabled": self.websocket_client is not None,
                "connected": self.websocket_client.connected if self.websocket_client else False,
                "status": self.websocket_client.show_status() if self.websocket_client else None
            }

            overall_status = "healthy"
            if not llm_healthy:
                overall_status = "degraded"
            elif not all(agent_health.values()):
                overall_status = "degraded"
            elif config.enable_session_persistence and not session_healthy:
                overall_status = "degraded"
            elif self.websocket_client and not self.websocket_client.connected:
                overall_status = "degraded"

            return {
                "status": overall_status,
                "llm_connection": llm_healthy,
                "websocket": websocket_status,
                "session_persistence": {
                    "enabled": config.enable_session_persistence,
                    "healthy": session_healthy,
                    "table_name": (
                        config.dynamodb_table_name
                        if config.enable_session_persistence
                        else None
                    ),
                },
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

    async def _test_session_connection(self) -> bool:
        """Test session management connection."""
        if not self.checkpointer:
            return True  # Not enabled, so considered healthy

        try:
            # Test by trying to get a non-existent session
            test_config = self._get_graph_config("health-check-test")
            await self.checkpointer.aget_tuple(test_config)
            return True
        except Exception as e:
            logger.warning(f"Session connection test failed: {e}")
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

    async def get_session_history(
        self, session_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of checkpoints to retrieve

        Returns:
            List of conversation checkpoints
        """
        if not self.checkpointer:
            logger.warning("Session persistence not enabled")
            return []

        try:
            config = self._get_graph_config(session_id)
            checkpoints = []

            async for checkpoint_tuple in self.checkpointer.alist(config, limit=limit):
                checkpoint_data = {
                    "checkpoint_id": checkpoint_tuple.checkpoint["id"],
                    "timestamp": checkpoint_tuple.checkpoint["ts"],
                    "metadata": checkpoint_tuple.metadata,
                    "messages": checkpoint_tuple.checkpoint.get(
                        "channel_values", {}
                    ).get("messages", []),
                }
                checkpoints.append(checkpoint_data)

            return checkpoints

        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    async def clear_session_history(self, session_id: str) -> bool:
        """
        Clear conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if successful, False otherwise
        """
        if not self.checkpointer:
            logger.warning("Session persistence not enabled")
            return False

        try:
            # Note: DynamoDB checkpointer doesn't have a direct clear method
            # In a production system, you might want to implement this by
            # querying and deleting all checkpoints for the session
            logger.warning("Session clearing not implemented for DynamoDB checkpointer")
            return False

        except Exception as e:
            logger.error(f"Failed to clear session history: {e}")
            return False

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """
        Get the current state of a session.

        Args:
            session_id: Session identifier

        Returns:
            Current session state or None if not found
        """
        if not self.checkpointer:
            logger.warning("Session persistence not enabled")
            return None

        try:
            config = self._get_graph_config(session_id)
            checkpoint_tuple = await self.checkpointer.aget_tuple(config)

            if checkpoint_tuple:
                return {
                    "session_id": session_id,
                    "checkpoint_id": checkpoint_tuple.checkpoint["id"],
                    "timestamp": checkpoint_tuple.checkpoint["ts"],
                    "state": checkpoint_tuple.checkpoint.get("channel_values", {}),
                    "metadata": checkpoint_tuple.metadata,
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get session state: {e}")
            return None
