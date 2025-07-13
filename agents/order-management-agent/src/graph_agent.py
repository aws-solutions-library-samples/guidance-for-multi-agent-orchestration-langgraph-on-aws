"""
LangGraph StateGraph-based order management agent.

This module provides an intelligent order management agent that uses
LangGraph StateGraph with separate nodes for analysis and tool execution.
"""

import logging
import time
from typing import Dict, List, Any, Annotated
import sys
import os

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_aws import ChatBedrock
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from shared.models import (
    AgentRequest,
    AgentResponse,
    AgentType,
    ToolCall
)
from shared.utils import truncate_text
from .tools import SQLQueryExecutor
from .config import config
from .structured_models import (
    InquiryAnalysis,
    EntityExtraction,
    QueryDecision,
    ResponseSynthesis,
    ErrorAnalysis
)

logger = logging.getLogger(__name__)


class OrderState(dict):
    """State for the order management agent graph."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize required fields
        self.setdefault("customer_message", "")
        self.setdefault("session_id", "")
        self.setdefault("customer_id", None)
        self.setdefault("inquiry_analysis", {})
        self.setdefault("extracted_entities", {})
        self.setdefault("query_plan", {})
        self.setdefault("query_results", {})
        self.setdefault("response", "")
        self.setdefault("confidence", 0.0)
        self.setdefault("tool_calls", [])
        self.setdefault("error", None)
        self.setdefault("processing_time", 0.0)


class GraphOrderManagementAgent:
    """LangGraph StateGraph-based order management agent."""
    
    def __init__(self):
        """Initialize the graph-based order management agent."""
        self.llm = self._initialize_llm()
        self.sql_executor = SQLQueryExecutor()
        self.agent_type = AgentType.ORDER_MANAGEMENT
        
        # Create structured output models
        self.inquiry_analyzer = self.llm.with_structured_output(InquiryAnalysis)
        self.entity_extractor = self.llm.with_structured_output(EntityExtraction)
        self.query_planner = self.llm.with_structured_output(QueryDecision)
        self.response_synthesizer = self.llm.with_structured_output(ResponseSynthesis)
        self.error_analyzer = self.llm.with_structured_output(ErrorAnalysis)
        
        # Create the StateGraph
        self.graph = self._create_state_graph()
        
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
                credentials_profile_name=config.aws_credentials_profile
            )
            logger.info("Successfully initialized Bedrock LLM")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock LLM: {e}")
            raise
    
    def _create_database_tools(self):
        """Create pure database tools without LLM calls."""
        
        @tool
        async def query_order_by_id(order_id: str) -> Dict[str, Any]:
            """
            Get details for a specific order.
            
            Args:
                order_id: The order identifier
                
            Returns:
                Order details or error message
            """
            try:
                async with self.sql_executor:
                    result = await self.sql_executor.get_order_by_id(order_id)
                    return {"success": True, "data": result, "message": f"Found order {order_id}"}
            except Exception as e:
                logger.error(f"Order query failed: {e}")
                return {"success": False, "data": None, "error": str(e)}
        
        @tool
        async def query_customer_orders(customer_id: str) -> Dict[str, Any]:
            """
            Get all orders for a specific customer.
            
            Args:
                customer_id: The customer identifier
                
            Returns:
                List of customer orders or error message
            """
            try:
                async with self.sql_executor:
                    results = await self.sql_executor.get_customer_orders(customer_id)
                    return {
                        "success": True, 
                        "data": results, 
                        "message": f"Found {len(results)} orders for customer {customer_id}"
                    }
            except Exception as e:
                logger.error(f"Customer orders query failed: {e}")
                return {"success": False, "data": [], "error": str(e)}
        
        @tool
        async def check_product_inventory(product_name: str = None, category: str = None) -> Dict[str, Any]:
            """
            Check product availability in inventory.
            
            Args:
                product_name: Specific product name to check
                category: Product category to filter by
                
            Returns:
                Inventory information or error message
            """
            try:
                async with self.sql_executor:
                    results = await self.sql_executor.check_product_availability(product_name, category)
                    return {
                        "success": True,
                        "data": results,
                        "message": f"Found {len(results)} products in inventory"
                    }
            except Exception as e:
                logger.error(f"Inventory query failed: {e}")
                return {"success": False, "data": [], "error": str(e)}
        
        @tool
        async def check_shipping_status(customer_id: str = None, order_id: str = None) -> Dict[str, Any]:
            """
            Check shipping status for orders.
            
            Args:
                customer_id: Customer identifier
                order_id: Order identifier
                
            Returns:
                Shipping status information or error message
            """
            try:
                async with self.sql_executor:
                    results = await self.sql_executor.get_shipping_status(customer_id, order_id)
                    return {
                        "success": True,
                        "data": results,
                        "message": f"Found shipping info for {len(results)} orders"
                    }
            except Exception as e:
                logger.error(f"Shipping status query failed: {e}")
                return {"success": False, "data": [], "error": str(e)}
        
        @tool
        async def check_return_status(customer_id: str = None, order_id: str = None) -> Dict[str, Any]:
            """
            Check return/exchange status for orders.
            
            Args:
                customer_id: Customer identifier
                order_id: Order identifier
                
            Returns:
                Return/exchange status information or error message
            """
            try:
                async with self.sql_executor:
                    results = await self.sql_executor.check_return_exchange_status(customer_id, order_id)
                    return {
                        "success": True,
                        "data": results,
                        "message": f"Found return info for {len(results)} orders"
                    }
            except Exception as e:
                logger.error(f"Return status query failed: {e}")
                return {"success": False, "data": [], "error": str(e)}
        
        @tool
        async def get_order_summary() -> Dict[str, Any]:
            """
            Get general order status summary.
            
            Returns:
                Order status summary or error message
            """
            try:
                async with self.sql_executor:
                    results = await self.sql_executor.get_order_status_summary()
                    return {
                        "success": True,
                        "data": results,
                        "message": f"Retrieved order summary with {len(results)} status types"
                    }
            except Exception as e:
                logger.error(f"Order summary query failed: {e}")
                return {"success": False, "data": [], "error": str(e)}
        
        return [
            query_order_by_id,
            query_customer_orders,
            check_product_inventory,
            check_shipping_status,
            check_return_status,
            get_order_summary
        ]
    
    def _create_state_graph(self):
        """Create the LangGraph StateGraph for order management."""
        
        # Create tools
        tools = self._create_database_tools()
        tools_by_name = {tool.name: tool for tool in tools}
        
        async def analyze_customer_query(state: OrderState) -> OrderState:
            """Analyze the customer query to understand intent and extract entities."""
            try:
                customer_message = state["customer_message"]
                
                # Analyze inquiry type
                analysis_prompt = f"""
                Analyze this customer inquiry about orders, shipping, inventory, or returns:
                
                Customer message: "{customer_message}"
                
                Determine:
                1. What type of inquiry this is (order_status, inventory, shipping, returns, general)
                2. Extract any specific entities mentioned (order IDs, customer IDs, product names)
                3. Assess the urgency and specific request
                4. Rate your confidence in this analysis
                
                Consider these patterns:
                - Order IDs: ORD-2024-001, order-123, #12345
                - Customer IDs: cust001, customer-123
                - Product categories: headphones, watch, speaker, computer
                - Status terms: shipped, delivered, processing, cancelled, returned
                - Inventory terms: available, in stock, quantity, buy, purchase
                - Return terms: return, exchange, refund, cancel
                - Shipping terms: delivery, ship, tracking, transit
                """
                
                analysis = await self.inquiry_analyzer.ainvoke(analysis_prompt)
                
                # Extract entities
                extraction_prompt = f"""
                Extract all relevant entities from this customer message:
                
                Customer message: "{customer_message}"
                
                Look for and extract:
                - Order IDs (patterns like ORD-2024-001, order-123, #12345)
                - Customer IDs (patterns like cust001, customer-123, id-456)
                - Product names (specific product names mentioned)
                - Product categories (headphones, watch, speaker, computer, phone)
                - Status references (shipped, delivered, processing, cancelled, returned)
                - Temporal references (today, yesterday, last week, etc.)
                - Quantity references (numbers, amounts)
                """
                
                entities = await self.entity_extractor.ainvoke(extraction_prompt)
                
                state["inquiry_analysis"] = {
                    "inquiry_type": analysis.inquiry_type,
                    "confidence": analysis.confidence,
                    "specific_request": analysis.specific_request,
                    "urgency": analysis.urgency_level,
                    "reasoning": analysis.reasoning
                }
                
                state["extracted_entities"] = {
                    "order_ids": entities.order_ids,
                    "customer_ids": entities.customer_ids,
                    "product_names": entities.product_names,
                    "product_categories": entities.product_categories,
                    "status_references": entities.status_references,
                    "temporal_references": entities.temporal_references,
                    "quantity_references": entities.quantity_references
                }
                
                logger.info(f"Analyzed inquiry: {analysis.inquiry_type} (confidence: {analysis.confidence:.2f})")
                
            except Exception as e:
                logger.error(f"Query analysis failed: {e}")
                state["error"] = f"Query analysis failed: {e}"
            
            return state
        
        async def plan_database_queries(state: OrderState) -> OrderState:
            """Plan which database queries to execute based on the analysis."""
            try:
                inquiry_analysis = state["inquiry_analysis"]
                entities = state["extracted_entities"]
                
                decision_prompt = f"""
                Based on this inquiry analysis, decide which database queries to execute:
                
                Inquiry type: {inquiry_analysis.get('inquiry_type')}
                Extracted entities: {entities}
                Specific request: {inquiry_analysis.get('specific_request')}
                
                Available query types:
                - query_order_by_id: Get specific order details (use when order ID is mentioned)
                - query_customer_orders: Get all orders for a customer (use when customer ID is mentioned)
                - check_product_inventory: Check product availability (use for inventory questions)
                - check_shipping_status: Get shipping information (use for shipping questions)
                - check_return_status: Get return/exchange information (use for return questions)
                - get_order_summary: Get general order statistics (use for general inquiries)
                
                Consider:
                - If order IDs are mentioned, use query_order_by_id
                - If customer IDs are mentioned, use query_customer_orders
                - If product names/categories are mentioned, check inventory
                - Plan the most efficient query strategy
                """
                
                decision = await self.query_planner.ainvoke(decision_prompt)
                
                state["query_plan"] = {
                    "primary_query": decision.primary_query_type,
                    "query_orders": decision.should_query_orders,
                    "query_inventory": decision.should_query_inventory,
                    "query_shipping": decision.should_query_shipping,
                    "query_returns": decision.should_query_returns,
                    "scope": decision.query_scope,
                    "priority": decision.priority_order
                }
                
                logger.info(f"Query plan: {decision.primary_query_type}")
                
            except Exception as e:
                logger.error(f"Query planning failed: {e}")
                state["error"] = f"Query planning failed: {e}"
            
            return state
        
        async def execute_database_queries(state: OrderState) -> OrderState:
            """Execute the planned database queries using tools."""
            try:
                query_plan = state["query_plan"]
                entities = state["extracted_entities"]
                results = {}
                tool_calls = []
                
                # Execute queries based on plan
                if query_plan.get("query_orders", False):
                    # Check if we have specific order ID
                    order_ids = entities.get("order_ids", [])
                    customer_ids = entities.get("customer_ids", [])
                    
                    if order_ids:
                        # Query specific order
                        order_id = order_ids[0]
                        start_time = time.time()
                        result = await tools_by_name["query_order_by_id"].ainvoke({"order_id": order_id})
                        execution_time = time.time() - start_time
                        
                        results["specific_order"] = result
                        tool_calls.append(ToolCall(
                            tool_name="query_order_by_id",
                            parameters={"order_id": order_id},
                            result=result,
                            execution_time=execution_time,
                            error=result.get("error")
                        ))
                        
                    elif customer_ids or state.get("customer_id"):
                        # Query customer orders
                        customer_id = customer_ids[0] if customer_ids else state.get("customer_id")
                        start_time = time.time()
                        result = await tools_by_name["query_customer_orders"].ainvoke({"customer_id": customer_id})
                        execution_time = time.time() - start_time
                        
                        results["customer_orders"] = result
                        tool_calls.append(ToolCall(
                            tool_name="query_customer_orders",
                            parameters={"customer_id": customer_id},
                            result=result,
                            execution_time=execution_time,
                            error=result.get("error")
                        ))
                
                if query_plan.get("query_inventory", False):
                    # Check product inventory
                    product_names = entities.get("product_names", [])
                    categories = entities.get("product_categories", [])
                    
                    product_name = product_names[0] if product_names else None
                    category = categories[0] if categories else None
                    
                    start_time = time.time()
                    result = await tools_by_name["check_product_inventory"].ainvoke({
                        "product_name": product_name,
                        "category": category
                    })
                    execution_time = time.time() - start_time
                    
                    results["inventory"] = result
                    tool_calls.append(ToolCall(
                        tool_name="check_product_inventory",
                        parameters={"product_name": product_name, "category": category},
                        result=result,
                        execution_time=execution_time,
                        error=result.get("error")
                    ))
                
                if query_plan.get("query_shipping", False):
                    # Check shipping status
                    order_ids = entities.get("order_ids", [])
                    customer_ids = entities.get("customer_ids", [])
                    
                    order_id = order_ids[0] if order_ids else None
                    customer_id = customer_ids[0] if customer_ids else state.get("customer_id")
                    
                    start_time = time.time()
                    result = await tools_by_name["check_shipping_status"].ainvoke({
                        "customer_id": customer_id,
                        "order_id": order_id
                    })
                    execution_time = time.time() - start_time
                    
                    results["shipping"] = result
                    tool_calls.append(ToolCall(
                        tool_name="check_shipping_status",
                        parameters={"customer_id": customer_id, "order_id": order_id},
                        result=result,
                        execution_time=execution_time,
                        error=result.get("error")
                    ))
                
                if query_plan.get("query_returns", False):
                    # Check return status
                    order_ids = entities.get("order_ids", [])
                    customer_ids = entities.get("customer_ids", [])
                    
                    order_id = order_ids[0] if order_ids else None
                    customer_id = customer_ids[0] if customer_ids else state.get("customer_id")
                    
                    start_time = time.time()
                    result = await tools_by_name["check_return_status"].ainvoke({
                        "customer_id": customer_id,
                        "order_id": order_id
                    })
                    execution_time = time.time() - start_time
                    
                    results["returns"] = result
                    tool_calls.append(ToolCall(
                        tool_name="check_return_status",
                        parameters={"customer_id": customer_id, "order_id": order_id},
                        result=result,
                        execution_time=execution_time,
                        error=result.get("error")
                    ))
                
                # If no specific queries planned, get general summary
                if not any([query_plan.get("query_orders"), query_plan.get("query_inventory"), 
                           query_plan.get("query_shipping"), query_plan.get("query_returns")]):
                    start_time = time.time()
                    result = await tools_by_name["get_order_summary"].ainvoke({})
                    execution_time = time.time() - start_time
                    
                    results["order_summary"] = result
                    tool_calls.append(ToolCall(
                        tool_name="get_order_summary",
                        parameters={},
                        result=result,
                        execution_time=execution_time,
                        error=result.get("error")
                    ))
                
                state["query_results"] = results
                state["tool_calls"] = tool_calls
                
                logger.info(f"Executed {len(tool_calls)} database queries")
                
            except Exception as e:
                logger.error(f"Database query execution failed: {e}")
                state["error"] = f"Database query execution failed: {e}"
            
            return state
        
        async def synthesize_response(state: OrderState) -> OrderState:
            """Synthesize the final customer response from query results."""
            try:
                customer_message = state["customer_message"]
                query_results = state["query_results"]
                inquiry_analysis = state["inquiry_analysis"]
                
                # If no results, provide appropriate message
                if not query_results or all(not result.get("data") for result in query_results.values()):
                    state["response"] = "I could not find any information related to your inquiry. Please check your order details or contact our support team for assistance."
                    state["confidence"] = 0.2
                    return state
                
                synthesis_prompt = f"""
                Create a helpful, professional response to this customer inquiry:
                
                Customer's original message: "{customer_message}"
                Inquiry analysis: {inquiry_analysis}
                
                Database query results: {query_results}
                
                Guidelines:
                1. Directly address the customer's specific question
                2. Include relevant details from the query results
                3. Use a friendly, professional tone
                4. Keep the response concise but complete
                5. If multiple results exist, summarize appropriately
                6. Include specific information like order IDs, product names, statuses, dates
                7. If appropriate, suggest next steps or additional help
                """
                
                synthesis = await self.response_synthesizer.ainvoke(synthesis_prompt)
                
                state["response"] = synthesis.customer_response
                state["confidence"] = synthesis.confidence_assessment
                
                logger.info(f"Response synthesized with confidence: {synthesis.confidence_assessment:.2f}")
                
            except Exception as e:
                logger.error(f"Response synthesis failed: {e}")
                state["response"] = "I found some information about your inquiry but had trouble formatting the response. Please contact our support team for assistance."
                state["confidence"] = 0.2
            
            return state
        
        async def handle_error(state: OrderState) -> OrderState:
            """Handle any errors that occurred during processing."""
            try:
                error_details = state.get("error", "Unknown error")
                customer_message = state["customer_message"]
                
                error_prompt = f"""
                A customer inquiry about orders encountered an error. Provide a helpful response.
                
                Customer's message: "{customer_message}"
                Error details: {error_details}
                
                Provide a professional response that:
                1. Acknowledges the issue without technical details
                2. Suggests alternative ways to get help
                3. Maintains a helpful tone
                4. Offers specific next steps if possible
                """
                
                error_analysis = await self.error_analyzer.ainvoke(error_prompt)
                
                state["response"] = error_analysis.customer_response
                state["confidence"] = 0.1
                
            except Exception:
                state["response"] = "I'm experiencing technical difficulties accessing our order system. Please try again in a few minutes or contact our support team directly."
                state["confidence"] = 0.1
            
            return state
        
        def should_continue(state: OrderState) -> str:
            """Determine the next step in the workflow."""
            if state.get("error"):
                return "handle_error"
            elif not state.get("inquiry_analysis"):
                return "analyze_query"
            elif not state.get("query_plan"):
                return "plan_queries"
            elif not state.get("query_results"):
                return "execute_queries"
            elif not state.get("response"):
                return "synthesize_response"
            else:
                return END
        
        # Create the StateGraph
        workflow = StateGraph(OrderState)
        
        # Add nodes
        workflow.add_node("analyze_query", analyze_customer_query)
        workflow.add_node("plan_queries", plan_database_queries)
        workflow.add_node("execute_queries", execute_database_queries)
        workflow.add_node("synthesize_response", synthesize_response)
        workflow.add_node("handle_error", handle_error)
        
        # Set entry point
        workflow.set_entry_point("analyze_query")
        
        # Add edges
        workflow.add_conditional_edges(
            "analyze_query",
            should_continue,
            {
                "plan_queries": "plan_queries",
                "handle_error": "handle_error",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "plan_queries",
            should_continue,
            {
                "execute_queries": "execute_queries",
                "handle_error": "handle_error",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "execute_queries",
            should_continue,
            {
                "synthesize_response": "synthesize_response",
                "handle_error": "handle_error",
                END: END
            }
        )
        
        workflow.add_edge("synthesize_response", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
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
            logger.info(f"Processing graph-based order management request for session {request.session_id}")
            
            # Create initial state
            initial_state = OrderState(
                customer_message=request.customer_message,
                session_id=request.session_id,
                customer_id=request.customer_id
            )
            
            # Execute the graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            final_state["processing_time"] = processing_time
            
            return AgentResponse(
                response=truncate_text(final_state["response"], 800),
                agent_type=self.agent_type,
                confidence_score=final_state.get("confidence", 0.5),
                tool_calls=final_state.get("tool_calls", []),
                session_id=request.session_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error processing graph-based order management request: {e}")
            processing_time = time.time() - start_time
            
            return AgentResponse(
                response="I'm experiencing technical difficulties accessing our order system. Please try again in a few minutes or contact our support team directly.",
                agent_type=self.agent_type,
                confidence_score=0.1,
                tool_calls=[],
                session_id=request.session_id,
                processing_time=processing_time
            )
    
    async def test_llm_connection(self) -> bool:
        """Test LLM connection."""
        try:
            test_message = "Hello, this is a test."
            response = await self.llm.ainvoke([{"role": "user", "content": test_message}])
            return bool(response and response.content)
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False