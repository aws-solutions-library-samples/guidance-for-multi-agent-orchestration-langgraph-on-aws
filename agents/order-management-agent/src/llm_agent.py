"""
LLM-based order management agent using LangGraph create_react_agent.

This module provides an intelligent order management agent that uses
structured LLM outputs and tool calling to handle customer inquiries.
"""

import logging
import time
from typing import Dict, List, Optional, Any
import sys
import os

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_aws import ChatBedrock
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

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


class LLMOrderManagementAgent:
    """LLM-based order management agent using LangGraph."""
    
    def __init__(self):
        """Initialize the LLM-based order management agent."""
        self.llm = self._initialize_llm()
        self.sql_executor = SQLQueryExecutor()
        self.agent_type = AgentType.ORDER_MANAGEMENT
        
        # Create structured output models
        self.inquiry_analyzer = self.llm.with_structured_output(InquiryAnalysis)
        self.entity_extractor = self.llm.with_structured_output(EntityExtraction)
        self.query_planner = self.llm.with_structured_output(QueryDecision)
        self.response_synthesizer = self.llm.with_structured_output(ResponseSynthesis)
        self.error_analyzer = self.llm.with_structured_output(ErrorAnalysis)
        
        # Create the ReAct agent with tools
        self.react_agent = self._create_react_agent()
        
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
    
    def _create_react_agent(self):
        """Create the ReAct agent with database tools."""
        
        @tool
        async def analyze_customer_inquiry(message: str) -> Dict[str, Any]:
            """
            Analyze customer inquiry to understand what they need.
            
            Args:
                message: Customer's message or question
                
            Returns:
                Analysis of the customer's inquiry including type and entities
            """
            try:
                analysis_prompt = f"""
                Analyze this customer inquiry about orders, shipping, inventory, or returns:
                
                Customer message: "{message}"
                
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
                """
                
                analysis = await self.inquiry_analyzer.ainvoke(analysis_prompt)
                logger.info(f"Inquiry analysis: {analysis.inquiry_type} (confidence: {analysis.confidence:.2f})")
                
                return {
                    "inquiry_type": analysis.inquiry_type,
                    "confidence": analysis.confidence,
                    "entities": analysis.extracted_entities,
                    "specific_request": analysis.specific_request,
                    "urgency": analysis.urgency_level,
                    "reasoning": analysis.reasoning
                }
                
            except Exception as e:
                logger.error(f"Inquiry analysis failed: {e}")
                return {
                    "inquiry_type": "general",
                    "confidence": 0.3,
                    "entities": {},
                    "specific_request": message,
                    "urgency": "medium",
                    "reasoning": "Analysis failed, using fallback"
                }
        
        @tool
        async def extract_entities_from_message(message: str) -> Dict[str, List[str]]:
            """
            Extract specific entities from the customer message.
            
            Args:
                message: Customer's message
                
            Returns:
                Dictionary of extracted entities
            """
            try:
                extraction_prompt = f"""
                Extract all relevant entities from this customer message:
                
                Customer message: "{message}"
                
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
                
                return {
                    "order_ids": entities.order_ids,
                    "customer_ids": entities.customer_ids,
                    "product_names": entities.product_names,
                    "product_categories": entities.product_categories,
                    "status_references": entities.status_references,
                    "temporal_references": entities.temporal_references,
                    "quantity_references": entities.quantity_references
                }
                
            except Exception as e:
                logger.error(f"Entity extraction failed: {e}")
                return {
                    "order_ids": [],
                    "customer_ids": [],
                    "product_names": [],
                    "product_categories": [],
                    "status_references": [],
                    "temporal_references": [],
                    "quantity_references": []
                }
        
        @tool
        async def decide_database_queries(inquiry_type: str, entities: Dict[str, Any]) -> Dict[str, Any]:
            """
            Decide which database queries to execute based on the inquiry analysis.
            
            Args:
                inquiry_type: Type of inquiry (order_status, inventory, etc.)
                entities: Extracted entities from the message
                
            Returns:
                Decision on which queries to execute
            """
            try:
                decision_prompt = f"""
                Based on the inquiry analysis, decide which database queries to execute:
                
                Inquiry type: {inquiry_type}
                Extracted entities: {entities}
                
                Available query types:
                - get_order_by_id: Get specific order details
                - get_customer_orders: Get all orders for a customer
                - check_inventory: Check product availability
                - get_shipping_status: Get shipping information
                - check_return_status: Get return/exchange information
                - get_order_summary: Get general order statistics
                
                Consider:
                - If order IDs are mentioned, use get_order_by_id
                - If customer IDs are mentioned, use get_customer_orders
                - If product names/categories are mentioned, check inventory
                - Plan the most efficient query strategy
                """
                
                decision = await self.query_planner.ainvoke(decision_prompt)
                
                return {
                    "primary_query": decision.primary_query_type,
                    "query_orders": decision.should_query_orders,
                    "query_inventory": decision.should_query_inventory,
                    "query_shipping": decision.should_query_shipping,
                    "query_returns": decision.should_query_returns,
                    "scope": decision.query_scope,
                    "priority": decision.priority_order
                }
                
            except Exception as e:
                logger.error(f"Query decision failed: {e}")
                return {
                    "primary_query": "order_lookup",
                    "query_orders": True,
                    "query_inventory": False,
                    "query_shipping": False,
                    "query_returns": False,
                    "scope": "general_status",
                    "priority": ["get_customer_orders"]
                }
        
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
        async def synthesize_customer_response(customer_message: str, query_results: str) -> Dict[str, Any]:
            """
            Create a customer-friendly response based on query results.
            
            Args:
                customer_message: Original customer message
                query_results: Results from database queries
                
            Returns:
                Synthesized response for the customer
            """
            try:
                synthesis_prompt = f"""
                Create a helpful, professional response to this customer inquiry:
                
                Customer's original message: "{customer_message}"
                
                Database query results: {query_results}
                
                Guidelines:
                1. Directly address the customer's question
                2. Include specific details from the query results
                3. Use a friendly, professional tone
                4. Keep the response concise but complete
                5. If no data was found, explain this clearly and suggest next steps
                6. If there are multiple results, summarize appropriately
                7. Include relevant details like order status, delivery dates, quantities, etc.
                """
                
                synthesis = await self.response_synthesizer.ainvoke(synthesis_prompt)
                
                return {
                    "response": synthesis.customer_response,
                    "confidence": synthesis.confidence_assessment,
                    "sources": synthesis.data_sources_used,
                    "follow_up_needed": synthesis.follow_up_needed,
                    "next_steps": synthesis.next_steps
                }
                
            except Exception as e:
                logger.error(f"Response synthesis failed: {e}")
                return {
                    "response": "I found some information about your inquiry but had trouble formatting the response. Please contact our support team for assistance.",
                    "confidence": 0.2,
                    "sources": [],
                    "follow_up_needed": True,
                    "next_steps": ["Contact support team"]
                }
        
        # Define the tools for the ReAct agent
        tools = [
            analyze_customer_inquiry,
            extract_entities_from_message,
            decide_database_queries,
            query_order_by_id,
            query_customer_orders,
            check_product_inventory,
            check_shipping_status,
            check_return_status,
            synthesize_customer_response
        ]
        
        # Create the ReAct agent
        system_prompt = """
        You are an intelligent order management assistant that helps customers with their order-related inquiries.
        
        Your capabilities include:
        - Analyzing customer inquiries to understand their needs
        - Extracting relevant information like order IDs and customer IDs
        - Querying databases for order status, inventory, shipping, and return information
        - Providing helpful, accurate responses based on the data found
        
        Always follow this process:
        1. First, analyze the customer's inquiry to understand what they need
        2. Extract any specific entities (order IDs, customer IDs, product names)
        3. Decide which database queries are needed
        4. Execute the appropriate queries
        5. Synthesize the results into a helpful customer response
        
        Be thorough but efficient. If you can't find specific information, suggest alternative ways to help.
        """
        
        agent = create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=system_prompt
        )
        
        return agent
    
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a customer order-related request using the LLM ReAct agent.
        
        Args:
            request: Customer request
            
        Returns:
            Agent response with order information
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing LLM-based order management request for session {request.session_id}")
            
            # Prepare the message for the ReAct agent
            customer_message = request.customer_message
            if request.customer_id:
                customer_message += f" (Customer ID: {request.customer_id})"
            
            # Invoke the ReAct agent
            result = await self.react_agent.ainvoke({
                "messages": [HumanMessage(content=customer_message)]
            })
            
            # Extract the final response
            final_message = result["messages"][-1]
            response_text = final_message.content
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Create tool calls record from the agent's execution
            tool_calls = self._extract_tool_calls_from_result(result)
            
            # Calculate confidence based on the agent's execution
            confidence_score = self._calculate_confidence_from_result(result, tool_calls)
            
            return AgentResponse(
                response=truncate_text(response_text, 800),
                agent_type=self.agent_type,
                confidence_score=confidence_score,
                tool_calls=tool_calls,
                session_id=request.session_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error processing LLM-based order management request: {e}")
            return await self._handle_error(request, str(e), time.time() - start_time)
    
    def _extract_tool_calls_from_result(self, result: Dict[str, Any]) -> List[ToolCall]:
        """Extract tool call information from the agent's result."""
        tool_calls = []
        
        # Look through the messages to find tool calls
        messages = result.get("messages", [])
        for message in messages:
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_calls.append(ToolCall(
                        tool_name=tool_call["name"],
                        parameters=tool_call.get("args", {}),
                        result=None,  # Will be filled from tool responses
                        execution_time=0.0  # Estimated
                    ))
        
        return tool_calls
    
    def _calculate_confidence_from_result(self, result: Dict[str, Any], tool_calls: List[ToolCall]) -> float:
        """Calculate confidence score based on the agent's execution."""
        # Start with base confidence
        confidence = 0.4
        
        # Check if the agent executed successfully
        messages = result.get("messages", [])
        if messages and len(messages) > 1:
            confidence += 0.2
        
        # Check tool executions
        if tool_calls:
            successful_tools = len([tc for tc in tool_calls if tc.error is None])
            confidence += 0.1 * successful_tools
        
        # If the final response seems complete
        final_message = messages[-1] if messages else None
        if final_message and len(final_message.content) > 50:
            confidence += 0.2
        
        return min(1.0, confidence)
    
    async def _handle_error(self, request: AgentRequest, error_details: str, processing_time: float) -> AgentResponse:
        """Handle errors and provide fallback response."""
        try:
            error_prompt = f"""
            A customer inquiry about orders encountered an error. Provide a helpful response.
            
            Customer's message: "{request.customer_message}"
            Error details: {error_details}
            
            Provide a professional response that:
            1. Acknowledges the issue without technical details
            2. Suggests alternative ways to get help
            3. Maintains a helpful tone
            """
            
            error_analysis = await self.error_analyzer.ainvoke(error_prompt)
            error_response = error_analysis.customer_message
            
        except Exception:
            error_response = "I'm experiencing technical difficulties accessing our order system. Please try again in a few minutes or contact our support team directly."
        
        return AgentResponse(
            response=error_response,
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
            result = await self.react_agent.ainvoke({
                "messages": [HumanMessage(content=test_message)]
            })
            return bool(result.get("messages"))
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False