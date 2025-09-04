"""
Simplified LangGraph StateGraph-based order management agent.

This module uses the proper LangGraph pattern with tool binding and
automatic tool execution.
"""

import logging
import os
import time

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from config import config
from db_init import DatabaseInitializationError, DatabaseInitializer
from dynamodb_session_saver import DynamoDBSaver
from postgresql_tools import PostgreSQLQueryExecutor
from shared.models import AgentRequest, AgentResponse, AgentType, ToolCall
from shared.utils import truncate_text

logger = logging.getLogger(__name__)


from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class OrderAgentState(TypedDict):
    """State for the order management agent graph."""

    messages: Annotated[list, add_messages]
    session_id: str
    customer_id: str
    processing_time: float


class SimpleGraphOrderAgent:
    """Simplified LangGraph StateGraph-based order management agent."""

    def __init__(self):
        """Initialize the simplified graph-based order management agent."""
        self.llm = self._initialize_llm()
        self.sql_executor = PostgreSQLQueryExecutor(config)
        self.db_initializer = DatabaseInitializer(config)
        self.agent_type = AgentType.ORDER_MANAGEMENT

        # Initialize session manager
        self.checkpointer = self._initialize_session_manager()

        # Create tools and bind to LLM
        self.tools = self._create_database_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Create the StateGraph
        self.graph = self._create_state_graph()

    async def startup(self):
        """Initialize the database connection pool and perform startup tasks."""
        logger.info("Starting up order management agent...")

        try:
            # Initialize database schema and test data
            logger.info("Initializing database schema and test data...")
            initialization_result = await self.db_initializer.initialize_database(
                include_test_data=True
            )

            if initialization_result["schema_created"]:
                logger.info("✅ Database schema created successfully")
            else:
                logger.info("ℹ️  Database schema already exists")

            if initialization_result["test_data_inserted"]:
                logger.info("✅ Test data inserted successfully")
            else:
                logger.info("ℹ️  Test data already exists")

            if initialization_result["verification_passed"]:
                logger.info("✅ Database schema verification passed")
            else:
                logger.warning("⚠️  Database schema verification failed")
                logger.warning(
                    f"Verification details: {initialization_result.get('verification_details', {})}"
                )

            # Initialize the SQL executor connection pool
            await self.sql_executor.initialize_pool()

            logger.info("🚀 Order management agent startup complete")

        except DatabaseInitializationError as e:
            logger.error(f"❌ Database initialization failed during startup: {e}")
            logger.error("   The agent will not be able to access the database")
            logger.error(
                "   Please check your DATABASE_CLUSTER_ARN and DATABASE_SECRET_ARN configuration"
            )
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during agent startup: {e}")
            raise

    async def shutdown(self):
        """Clean up resources during shutdown."""
        logger.info("Shutting down order management agent...")
        await self.sql_executor.close_pool()
        logger.info("Order management agent shutdown complete")

    def _initialize_llm(self) -> ChatBedrockConverse:
        """Initialize the AWS Bedrock LLM."""
        try:
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
                    "checkpoint_ns": "order-management",
                }
            }
        else:
            return {}

    def _create_database_tools(self):
        """Create pure database tools without LLM calls."""

        @tool
        async def query_order_by_id(order_id: str) -> str:
            """
            Get details for a specific order.

            Args:
                order_id: The order identifier (e.g., ORD-2024-001)

            Returns:
                Order details as a formatted string
            """
            try:
                result = await self.sql_executor.get_order_by_id(order_id)
                if result:
                    return f"Order {order_id}: {result['product_name']} - Status: {result['order_status']}, Shipping: {result['shipping_status']}"
                else:
                    return f"Order {order_id} not found"
            except Exception as e:
                logger.error(f"Order query failed: {e}")
                return f"Error retrieving order {order_id}: {str(e)}"

        @tool
        async def query_customer_orders(customer_id: str) -> str:
            """
            Get all orders for a specific customer.

            Args:
                customer_id: The customer identifier (e.g., cust001)

            Returns:
                List of customer orders as a formatted string
            """
            try:
                results = await self.sql_executor.get_customer_orders(customer_id)
                if results:
                    order_list = []
                    for order in results[:5]:  # Limit to 5 most recent
                        order_list.append(
                            f"- {order['order_id']}: {order['product_name']} ({order['order_status']})"
                        )
                    return (
                        f"Customer {customer_id} has {len(results)} orders:\n"
                        + "\n".join(order_list)
                    )
                else:
                    return f"No orders found for customer {customer_id}"
            except Exception as e:
                logger.error(f"Customer orders query failed: {e}")
                return f"Error retrieving orders for customer {customer_id}: {str(e)}"

        @tool
        async def check_product_inventory(
            product_name: str = None, category: str = None
        ) -> str:
            """
            Check product availability in inventory.

            Args:
                product_name: Specific product name to check (optional)
                category: Product category to filter by (optional)

            Returns:
                Inventory information as a formatted string
            """
            try:
                results = await self.sql_executor.check_product_availability(
                    product_name, category
                )
                if results:
                    inventory_list = []
                    for item in results[:5]:  # Limit to 5 items
                        inventory_list.append(
                            f"- {item['product_name']}: {item['quantity']} units available"
                        )
                    return "Inventory check results:\n" + "\n".join(inventory_list)
                else:
                    search_term = product_name or category or "products"
                    return f"No {search_term} found in inventory"
            except Exception as e:
                logger.error(f"Inventory query failed: {e}")
                return f"Error checking inventory: {str(e)}"

        @tool
        async def check_shipping_status(
            customer_id: str = None, order_id: str = None
        ) -> str:
            """
            Check shipping status for orders.

            Args:
                customer_id: Customer identifier (optional)
                order_id: Order identifier (optional)

            Returns:
                Shipping status information as a formatted string
            """
            try:
                results = await self.sql_executor.get_shipping_status(
                    customer_id, order_id
                )
                if results:
                    shipping_list = []
                    for shipment in results[:3]:  # Limit to 3 shipments
                        shipping_list.append(
                            f"- Order {shipment['order_id']}: {shipment['shipping_status']}"
                        )
                        if shipment.get("delivery_date"):
                            shipping_list.append(
                                f"  Expected delivery: {shipment['delivery_date']}"
                            )
                    return "Shipping status:\n" + "\n".join(shipping_list)
                else:
                    return "No shipping information found"
            except Exception as e:
                logger.error(f"Shipping status query failed: {e}")
                return f"Error checking shipping status: {str(e)}"

        @tool
        async def check_return_status(
            customer_id: str = None, order_id: str = None
        ) -> str:
            """
            Check return/exchange status for orders.

            Args:
                customer_id: Customer identifier (optional)
                order_id: Order identifier (optional)

            Returns:
                Return/exchange status information as a formatted string
            """
            try:
                results = await self.sql_executor.check_return_exchange_status(
                    customer_id, order_id
                )
                if results:
                    return_list = []
                    for return_item in results[:3]:  # Limit to 3 returns
                        return_list.append(
                            f"- {return_item['product_name']}: {return_item['return_exchange_status']}"
                        )
                    return "Return/exchange status:\n" + "\n".join(return_list)
                else:
                    return "No return/exchange information found"
            except Exception as e:
                logger.error(f"Return status query failed: {e}")
                return f"Error checking return status: {str(e)}"

        @tool
        async def get_order_summary() -> str:
            """
            Get general order status summary.

            Returns:
                Order status summary as a formatted string
            """
            try:
                results = await self.sql_executor.get_order_status_summary()
                if results:
                    summary_list = []
                    for status in results[:4]:  # Limit to 4 status types
                        summary_list.append(
                            f"- {status['order_status'].title()}: {status['total_orders']} orders"
                        )
                    return "Order status summary:\n" + "\n".join(summary_list)
                else:
                    return "No order summary available"
            except Exception as e:
                logger.error(f"Order summary query failed: {e}")
                return f"Error retrieving order summary: {str(e)}"

        return [
            query_order_by_id,
            query_customer_orders,
            check_product_inventory,
            check_shipping_status,
            check_return_status,
            get_order_summary,
        ]

    def _create_state_graph(self):
        """Create the LangGraph StateGraph using the proper pattern."""

        # Create the tool node for executing tools
        tool_node = ToolNode(self.tools)

        def call_model(state):
            """Call the LLM with tools to analyze and respond to the customer query."""
            messages = state["messages"]
            prompt = ChatPromptTemplate.from_messages(
                [
                    "system",
                    """You are an intelligent order management assistant that helps customers with their order-related inquiries.

                Your capabilities include:
                - Looking up specific order details by order ID
                - Finding customer order history by customer ID  
                - Checking product inventory and availability
                - Getting shipping status and delivery information
                - Checking return and exchange status
                - Providing general order statistics

                When a customer asks about orders, products, or shipping:
                1. Analyze their request to understand what they need
                2. Use the appropriate tools to get the information
                3. Provide a helpful, professional response based on the results

                Always be friendly and helpful. If you can't find specific information, suggest alternatives or next steps.""",
                    ("placeholder", "{messages}"),
                ]
            )

            agent_chain = prompt | self.llm_with_tools

            print("messages", messages)
            # Call LLM with tools
            response = agent_chain.invoke(state)

            # Return updated state
            return {"messages": [response]}

        # Create the StateGraph
        workflow = StateGraph(OrderAgentState)

        # Add nodes
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)

        # Set entry point
        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            tools_condition,
        )

        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")

        # Compile the graph with checkpointer if available
        if self.checkpointer:
            logger.info("Compiling graph with DynamoDB session persistence")
            return workflow.compile(checkpointer=self.checkpointer)
        else:
            logger.info("Compiling graph without session persistence")
            return workflow.compile()

    def _serialize_chunk_for_streaming(self, chunk):
        """
        Serialize LangGraph chunk to be JSON-compatible for streaming.

        Args:
            chunk: Raw LangGraph chunk data

        Returns:
            JSON-serializable dictionary
        """
        serialized = {}

        for node_name, node_data in chunk.items():
            if isinstance(node_data, dict):
                serialized_node = {}
                for key, value in node_data.items():
                    if key == "messages" and isinstance(value, list):
                        # Serialize message objects
                        serialized_messages = []
                        for msg in value:
                            if hasattr(msg, "content") and hasattr(msg, "type"):
                                # LangChain message object
                                msg_dict = {
                                    "type": getattr(msg, "type", "unknown"),
                                    "content": self._serialize_message_content(
                                        msg.content
                                    ),
                                    "id": getattr(msg, "id", None),
                                }
                                # Add tool calls if present
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    msg_dict["tool_calls"] = [
                                        {
                                            "name": tc.get("name", ""),
                                            "args": tc.get("args", {}),
                                            "id": tc.get("id", ""),
                                            "type": tc.get("type", "tool_call"),
                                        }
                                        for tc in msg.tool_calls
                                    ]
                                serialized_messages.append(msg_dict)
                            elif isinstance(msg, dict):
                                # Already a dictionary
                                serialized_messages.append(msg)
                            else:
                                # Convert to string representation
                                serialized_messages.append(
                                    {"type": "unknown", "content": str(msg)}
                                )
                        serialized_node[key] = serialized_messages
                    elif isinstance(value, (str, int, float, bool, type(None))):
                        # Basic types are already serializable
                        serialized_node[key] = value
                    elif isinstance(value, (list, dict)):
                        # Try to serialize as-is, fallback to string
                        try:
                            import json

                            json.dumps(value)  # Test if serializable
                            serialized_node[key] = value
                        except (TypeError, ValueError):
                            serialized_node[key] = str(value)
                    else:
                        # Convert complex objects to string
                        serialized_node[key] = str(value)
                serialized[node_name] = serialized_node
            else:
                # Non-dict node data, convert to string
                serialized[node_name] = str(node_data)

        return serialized

    def _serialize_message_content(self, content):
        """
        Serialize message content which can be string or list of content blocks.

        Args:
            content: Message content (string or list)

        Returns:
            Serializable content
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Handle content blocks (like tool use, text, etc.)
            serialized_content = []
            for block in content:
                if isinstance(block, dict):
                    # Already serializable
                    serialized_content.append(block)
                else:
                    # Convert to dict representation
                    if hasattr(block, "type") and hasattr(block, "text"):
                        serialized_content.append(
                            {"type": block.type, "text": block.text}
                        )
                    else:
                        serialized_content.append(str(block))
            return serialized_content
        else:
            return str(content)

    def _extract_final_response(self, final_state):
        """
        Extract the final response from the graph state.

        Args:
            final_state: Final state from graph execution

        Returns:
            String response content
        """
        if not final_state or "messages" not in final_state:
            return "No response generated"

        messages = final_state["messages"]
        if not messages:
            return "No messages in response"

        # Get the last message
        final_message = messages[-1]

        # Extract content from the message
        if hasattr(final_message, "content"):
            content = final_message.content
            # Handle different content formats
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Extract text from content blocks, ignoring tool_use blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        text_parts.append(block.text)
                return " ".join(text_parts) if text_parts else str(content)
            else:
                return str(content)
        elif isinstance(final_message, dict) and "content" in final_message:
            return str(final_message["content"])
        else:
            return str(final_message)

    async def process_request_stream(self, request: AgentRequest):
        """
        Process a customer order-related request with streaming support.

        Args:
            request: Customer request

        Yields:
            Streaming updates from the graph execution
        """
        try:
            logger.info(
                f"Processing streaming order management request for session {request.session_id}"
            )

            # Prepare the customer message
            customer_message = request.customer_message
            if request.customer_id:
                customer_message += f" (Customer ID: {request.customer_id})"

            # Create initial state
            initial_state = {
                "messages": [HumanMessage(content=customer_message)],
                "session_id": request.session_id,
                "customer_id": request.customer_id or "",
                "processing_time": 0.0,
            }

            # Get session configuration for persistence
            session_config = self._get_session_config(request.session_id)
            print(session_config)
            # Stream the graph execution with updates mode
            async for chunk in self.graph.astream(initial_state, config=session_config, stream_mode="updates"):
                # Serialize the chunk to be JSON-compatible
                serialized_chunk = self._serialize_chunk_for_streaming(chunk)
                yield {
                    "type": "progress",
                    "agent_type": self.agent_type.value,
                    "data": serialized_chunk,
                    "session_id": request.session_id,
                    "timestamp": time.time(),
                }

        except Exception as e:
            logger.error(f"Error in streaming order management request: {e}")
            yield {
                "type": "error",
                "agent_type": self.agent_type.value,
                "data": {"error": str(e)},
                "session_id": request.session_id,
                "timestamp": time.time(),
            }

    async def process_request_stream_tokens(self, request: AgentRequest):
        """
        Process a customer order-related request with LLM token streaming support.

        Args:
            request: Customer request

        Yields:
            Streaming LLM tokens and progress updates
        """
        try:
            logger.info(
                f"Processing token streaming order management request for session {request.session_id}"
            )

            # Prepare the customer message
            customer_message = request.customer_message
            if request.customer_id:
                customer_message += f" (Customer ID: {request.customer_id})"

            # Create initial state
            initial_state = {
                "messages": [HumanMessage(content=customer_message)],
                "session_id": request.session_id,
                "customer_id": request.customer_id or "",
                "processing_time": 0.0,
            }

            # Get session configuration for persistence
            session_config = self._get_session_config(request.session_id)

            # Stream with multiple modes: updates for progress, messages for LLM tokens
            async for stream_type, chunk in self.graph.astream(
                initial_state, config=session_config, stream_mode=["updates", "messages"]
            ):
                if stream_type == "updates":
                    # Serialize the chunk to be JSON-compatible
                    serialized_chunk = self._serialize_chunk_for_streaming(chunk)
                    yield {
                        "type": "progress",
                        "agent_type": self.agent_type.value,
                        "data": serialized_chunk,
                        "session_id": request.session_id,
                        "timestamp": time.time(),
                    }
                elif stream_type == "messages":
                    # Yield LLM token streams
                    message_chunk, metadata = chunk
                    if message_chunk.content:
                        yield {
                            "type": "token",
                            "agent_type": self.agent_type.value,
                            "data": {
                                "content": message_chunk.content,
                                "node": metadata.get("langgraph_node", "unknown"),
                                "metadata": metadata,  # LangGraph metadata is already serializable
                            },
                            "session_id": request.session_id,
                            "timestamp": time.time(),
                        }

        except Exception as e:
            logger.error(f"Error in token streaming order management request: {e}")
            yield {
                "type": "error",
                "agent_type": self.agent_type.value,
                "data": {"error": str(e)},
                "session_id": request.session_id,
                "timestamp": time.time(),
            }

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a customer order-related request using the StateGraph.

        Args:
            request: Customer request

        Returns:
            Agent response with order information
        """
        start_time = time.time()

        try:
            logger.info(
                f"Processing simple graph order management request for session {request.session_id}"
            )

            # Prepare the customer message
            customer_message = request.customer_message
            if request.customer_id:
                customer_message += f" (Customer ID: {request.customer_id})"

            # Create initial state
            initial_state = {
                "messages": [HumanMessage(content=customer_message)],
                "session_id": request.session_id,
                "customer_id": request.customer_id or "",
                "processing_time": 0.0,
            }

            # Get session configuration for persistence
            session_config = self._get_session_config(request.session_id)
            print(session_config)

            # Execute the graph and get final state
            final_state = None
            async for chunk in self.graph.astream(initial_state, config=session_config, stream_mode="values"):
                final_state = chunk

            # Extract the final response using our improved method
            response_text = self._extract_final_response(final_state)

            # Extract tool calls for response metadata
            # tool_calls = self._extract_tool_calls_from_messages(messages)

            # Calculate processing time
            processing_time = time.time() - start_time

            # Calculate confidence based on execution
            # confidence_score = self._calculate_confidence(tool_calls, response_text)

            return AgentResponse(
                response=truncate_text(response_text, 800),
                agent_type=self.agent_type,
                # confidence_score=confidence_score,
                # tool_calls=tool_calls,
                session_id=request.session_id,
                processing_time=processing_time,
            )

        except Exception as e:
            logger.error(f"Error processing simple graph order management request: {e}")
            processing_time = time.time() - start_time

            return AgentResponse(
                response="I'm experiencing technical difficulties accessing our order system. Please try again in a few minutes or contact our support team directly.",
                agent_type=self.agent_type,
                confidence_score=0.1,
                tool_calls=[],
                session_id=request.session_id,
                processing_time=processing_time,
            )

    def _extract_tool_calls_from_messages(self, messages) -> list[ToolCall]:
        """Extract tool call information from the conversation messages."""
        tool_calls = []

        for message in messages:
            # Check for tool calls in AI messages
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_calls.append(
                        ToolCall(
                            tool_name=tool_call["name"],
                            parameters=tool_call.get("args", {}),
                            result=None,  # Will be found in subsequent tool messages
                            execution_time=0.0,  # Not tracked in this simple pattern
                        )
                    )

            # Check for tool results in tool messages
            elif isinstance(message, ToolMessage):
                # Find the corresponding tool call and update its result
                for tool_call in reversed(tool_calls):
                    if tool_call.result is None:
                        tool_call.result = message.content
                        break

        return tool_calls

    def _calculate_confidence(
        self, tool_calls: list[ToolCall], response_text: str
    ) -> float:
        """Calculate confidence score based on tool execution and response quality."""
        confidence = 0.4  # Base confidence

        # Increase confidence for successful tool calls
        if tool_calls:
            successful_tools = sum(
                1 for tc in tool_calls if tc.result and "Error" not in tc.result
            )
            confidence += 0.1 * successful_tools

        # Increase confidence for substantial responses
        if len(response_text) > 50:
            confidence += 0.2

        # Decrease confidence for error indicators
        if "error" in response_text.lower() or "sorry" in response_text.lower():
            confidence -= 0.2

        return max(0.1, min(1.0, confidence))

    async def test_llm_connection(self) -> bool:
        """Test LLM connection."""
        try:
            test_message = "Hello, this is a test."
            response = await self.llm.ainvoke(
                [{"role": "user", "content": test_message}]
            )
            return bool(response and response.content)
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False

    async def test_database_connection(self) -> bool:
        """Test database connection."""
        try:
            result = await self.sql_executor.execute_query("SELECT 1 as test")
            return result.error is None
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    async def test_session_connection(self) -> bool:
        """Test session management connection."""
        if not self.checkpointer:
            return True  # Not enabled, so considered healthy

        try:
            # Test by trying to get a non-existent session
            test_config = self._get_session_config("health-check-test")
            await self.checkpointer.aget_tuple(test_config)
            return True
        except Exception as e:
            logger.warning(f"Session connection test failed: {e}")
            return False