"""
Order management agent implementation.

This module contains the core logic for the order management agent, including
order status tracking, inventory management, and return/exchange processing.
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
from shared.models import (
    AgentRequest,
    AgentResponse,
    AgentType,
    ToolCall
)
from shared.utils import truncate_text
from .tools import SQLQueryExecutor
from .prompts import (
    ORDER_STATUS_QUERY_PROMPT,
    INVENTORY_CHECK_QUERY_PROMPT,
    RESPONSE_FORMATTING_PROMPT,
    RETURN_EXCHANGE_PROMPT
)
from .config import config
from .structured_models import (
    InquiryAnalysis,
    EntityExtraction,
    QueryDecision,
    ResponseSynthesis,
    ErrorAnalysis
)

logger = logging.getLogger(__name__)


class OrderManagementAgent:
    """Agent for handling customer order-related inquiries."""
    
    def __init__(self):
        """Initialize the order management agent."""
        self.llm = self._initialize_llm()
        self.sql_executor = SQLQueryExecutor()
        self.agent_type = AgentType.ORDER_MANAGEMENT
        
        # Create structured output models for LLM analysis
        self.inquiry_analyzer = self.llm.with_structured_output(InquiryAnalysis)
        self.entity_extractor = self.llm.with_structured_output(EntityExtraction)
        self.query_planner = self.llm.with_structured_output(QueryDecision)
        self.response_synthesizer = self.llm.with_structured_output(ResponseSynthesis)
        self.error_analyzer = self.llm.with_structured_output(ErrorAnalysis)
        
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
            )
            logger.info("Successfully initialized Bedrock LLM")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock LLM: {e}")
            raise
    
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a customer order-related request.
        
        Args:
            request: Customer request
            
        Returns:
            Agent response with order information
        """
        start_time = time.time()
        tool_calls = []
        
        try:
            logger.info(f"Processing order management request for session {request.session_id}")
            
            # Analyze the request using LLM structured output
            inquiry_analysis = await self._analyze_inquiry_with_llm(request.customer_message)
            inquiry_type = inquiry_analysis.get('inquiry_type', 'general')
            logger.info(f"LLM detected inquiry type: {inquiry_type} (confidence: {inquiry_analysis.get('confidence', 0.0):.2f})")
            
            # Execute appropriate database queries based on inquiry analysis
            query_results = await self._execute_queries_with_llm_analysis(
                request, 
                inquiry_analysis, 
                tool_calls
            )
            
            # Format response using LLM synthesis
            response_text = await self._format_response_with_llm(
                request.customer_message,
                query_results,
                inquiry_analysis,
                tool_calls
            )
            
            # Calculate confidence based on results found
            confidence_score = self._calculate_confidence(query_results, tool_calls)
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                response=response_text,
                agent_type=self.agent_type,
                confidence_score=confidence_score,
                tool_calls=tool_calls,
                session_id=request.session_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error processing order management request: {e}")
            return await self._handle_error(request, str(e), tool_calls, time.time() - start_time)
    
    async def _analyze_inquiry_with_llm(self, message: str) -> Dict[str, Any]:
        """
        Analyze the customer message using LLM structured output to determine inquiry type.
        
        Args:
            message: Customer message
            
        Returns:
            Dictionary with inquiry analysis results
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
            - Inventory terms: available, in stock, quantity, buy, purchase
            - Return terms: return, exchange, refund, cancel
            - Shipping terms: delivery, ship, tracking, transit
            """
            
            analysis = await self.inquiry_analyzer.ainvoke(analysis_prompt)
            
            # Convert to dict format expected by rest of code
            return {
                "inquiry_type": analysis.inquiry_type,
                "confidence": analysis.confidence,
                "entities": analysis.extracted_entities,
                "specific_request": analysis.specific_request,
                "urgency": analysis.urgency_level,
                "reasoning": analysis.reasoning
            }
            
        except Exception as e:
            logger.warning(f"LLM inquiry analysis failed, using fallback: {e}")
            # Fallback to simple keyword detection
            return self._fallback_keyword_analysis(message)
    
    def _fallback_keyword_analysis(self, message: str) -> Dict[str, Any]:
        """
        Fallback keyword-based analysis when LLM fails.
        
        Args:
            message: Customer message
            
        Returns:
            Basic analysis results
        """
        message_lower = message.lower()
        
        # Simple keyword detection
        if any(word in message_lower for word in ['return', 'exchange', 'refund']):
            inquiry_type = 'returns'
        elif any(word in message_lower for word in ['shipping', 'delivery', 'track']):
            inquiry_type = 'shipping' 
        elif any(word in message_lower for word in ['stock', 'available', 'inventory']):
            inquiry_type = 'inventory'
        elif any(word in message_lower for word in ['order', 'status', 'purchase']):
            inquiry_type = 'order_status'
        else:
            inquiry_type = 'general'
        
        return {
            "inquiry_type": inquiry_type,
            "confidence": 0.6,
            "entities": {},
            "specific_request": message,
            "urgency": "medium",
            "reasoning": "Fallback keyword analysis"
        }
    
    async def _execute_queries_with_llm_analysis(
        self, 
        request: AgentRequest, 
        inquiry_analysis: Dict[str, Any],
        tool_calls: List[ToolCall]
    ) -> Dict[str, Any]:
        """
        Execute appropriate database queries based on LLM inquiry analysis.
        
        Args:
            request: Customer request
            inquiry_analysis: LLM analysis results
            tool_calls: List to store tool call information
            
        Returns:
            Query results
        """
        results = {}
        inquiry_type = inquiry_analysis.get('inquiry_type', 'general')
        entities = inquiry_analysis.get('entities', {})
        
        async with self.sql_executor:
            try:
                # Use LLM to decide which queries to execute
                query_decision = await self._decide_queries_with_llm(inquiry_analysis)
                
                # Execute queries based on LLM decision
                if query_decision.get('query_orders', False):
                    results.update(await self._query_order_status_enhanced(request, entities, tool_calls))
                
                if query_decision.get('query_inventory', False):
                    results.update(await self._query_inventory_enhanced(request, entities, tool_calls))
                
                if query_decision.get('query_shipping', False):
                    results.update(await self._query_shipping_status(request, tool_calls))
                
                if query_decision.get('query_returns', False):
                    results.update(await self._query_return_exchange(request, tool_calls))
                
                # Fallback to original logic if no specific queries decided
                if not any([query_decision.get('query_orders'), query_decision.get('query_inventory'), 
                           query_decision.get('query_shipping'), query_decision.get('query_returns')]):
                    results.update(await self._execute_fallback_queries(request, inquiry_type, tool_calls))
                
            except Exception as e:
                logger.error(f"LLM-guided database query failed: {e}")
                tool_calls.append(ToolCall(
                    tool_name="llm_guided_query",
                    parameters={"inquiry_type": inquiry_type},
                    error=str(e)
                ))
                # Fallback to original query logic
                results.update(await self._execute_fallback_queries(request, inquiry_type, tool_calls))
        
        return results
    
    async def _decide_queries_with_llm(self, inquiry_analysis: Dict[str, Any]) -> Dict[str, bool]:
        """
        Use LLM to decide which database queries to execute.
        
        Args:
            inquiry_analysis: Results from inquiry analysis
            
        Returns:
            Dictionary indicating which queries to execute
        """
        try:
            decision_prompt = f"""
            Based on this inquiry analysis, decide which database queries to execute:
            
            Inquiry type: {inquiry_analysis.get('inquiry_type')}
            Extracted entities: {inquiry_analysis.get('entities', {})}
            Specific request: {inquiry_analysis.get('specific_request')}
            
            Available query types:
            - query_orders: Get order information (order status, customer orders)
            - query_inventory: Check product availability
            - query_shipping: Get shipping status information  
            - query_returns: Get return/exchange information
            
            Consider:
            - If order IDs or customer IDs are mentioned, query orders
            - If product names/categories are mentioned, check inventory
            - If shipping/delivery is mentioned, query shipping
            - If returns/exchanges are mentioned, query returns
            """
            
            decision = await self.query_planner.ainvoke(decision_prompt)
            
            return {
                "query_orders": decision.should_query_orders,
                "query_inventory": decision.should_query_inventory,
                "query_shipping": decision.should_query_shipping,
                "query_returns": decision.should_query_returns
            }
            
        except Exception as e:
            logger.warning(f"LLM query decision failed: {e}")
            # Fallback decision logic
            inquiry_type = inquiry_analysis.get('inquiry_type', 'general')
            return {
                "query_orders": inquiry_type in ['order_status', 'general'],
                "query_inventory": inquiry_type in ['inventory', 'general'],
                "query_shipping": inquiry_type == 'shipping',
                "query_returns": inquiry_type == 'returns'
            }
    
    async def _execute_fallback_queries(self, request: AgentRequest, inquiry_type: str, tool_calls: List[ToolCall]) -> Dict[str, Any]:
        """
        Execute fallback queries using original logic.
        
        Args:
            request: Customer request
            inquiry_type: Type of inquiry
            tool_calls: List to store tool call information
            
        Returns:
            Query results
        """
        results = {}
        
        if inquiry_type == 'order_status':
            results.update(await self._query_order_status(request, tool_calls))
        elif inquiry_type == 'inventory':
            results.update(await self._query_inventory(request, tool_calls))
        elif inquiry_type == 'shipping':
            results.update(await self._query_shipping_status(request, tool_calls))
        elif inquiry_type == 'returns':
            results.update(await self._query_return_exchange(request, tool_calls))
        else:  # general
            if request.customer_id:
                results.update(await self._query_order_status(request, tool_calls))
            results.update(await self._query_inventory(request, tool_calls))
        
        return results
    
    async def _query_order_status_enhanced(self, request: AgentRequest, entities: Dict[str, Any], tool_calls: List[ToolCall]) -> Dict[str, Any]:
        """
        Enhanced order status query using extracted entities.
        
        Args:
            request: Customer request
            entities: Extracted entities from LLM analysis
            tool_calls: List to store tool call information
            
        Returns:
            Query results
        """
        results = {}
        
        # Get order IDs and customer IDs from entities
        order_ids = entities.get('order_ids', []) if isinstance(entities.get('order_ids'), list) else []
        customer_ids = entities.get('customer_ids', []) if isinstance(entities.get('customer_ids'), list) else []
        
        # Use first available IDs
        order_id = order_ids[0] if order_ids else self._extract_order_id(request.customer_message)
        customer_id = (customer_ids[0] if customer_ids else 
                      request.customer_id or self._extract_customer_id(request.customer_message))
        
        start_time = time.time()
        
        try:
            if order_id:
                order_data = await self.sql_executor.get_order_by_id(order_id)
                results['specific_order'] = order_data
                
                tool_calls.append(ToolCall(
                    tool_name="get_order_by_id_enhanced",
                    parameters={"order_id": order_id},
                    result=order_data,
                    execution_time=time.time() - start_time
                ))
                
            elif customer_id:
                customer_orders = await self.sql_executor.get_customer_orders(customer_id)
                results['customer_orders'] = customer_orders
                
                tool_calls.append(ToolCall(
                    tool_name="get_customer_orders_enhanced",
                    parameters={"customer_id": customer_id},
                    result=customer_orders,
                    execution_time=time.time() - start_time
                ))
            
            else:
                order_summary = await self.sql_executor.get_order_status_summary()
                results['order_summary'] = order_summary
                
                tool_calls.append(ToolCall(
                    tool_name="get_order_status_summary_enhanced",
                    parameters={},
                    result=order_summary,
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            tool_calls.append(ToolCall(
                tool_name="order_status_query_enhanced",
                parameters={"customer_id": customer_id, "order_id": order_id},
                error=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _query_inventory_enhanced(self, request: AgentRequest, entities: Dict[str, Any], tool_calls: List[ToolCall]) -> Dict[str, Any]:
        """
        Enhanced inventory query using extracted entities.
        
        Args:
            request: Customer request
            entities: Extracted entities from LLM analysis
            tool_calls: List to store tool call information
            
        Returns:
            Query results
        """
        results = {}
        
        # Get product info from entities
        product_names = entities.get('product_names', []) if isinstance(entities.get('product_names'), list) else []
        categories = entities.get('product_categories', []) if isinstance(entities.get('product_categories'), list) else []
        
        product_name = product_names[0] if product_names else None
        category = categories[0] if categories else None
        
        # Fallback to original extraction if no entities found
        if not product_name and not category:
            product_info = self._extract_product_info(request.customer_message)
            product_name = product_info.get('product_name')
            category = product_info.get('category')
        
        start_time = time.time()
        
        try:
            inventory_data = await self.sql_executor.check_product_availability(product_name, category)
            results['inventory'] = inventory_data
            
            tool_calls.append(ToolCall(
                tool_name="check_product_availability_enhanced",
                parameters={"product_name": product_name, "category": category},
                result=inventory_data,
                execution_time=time.time() - start_time
            ))
                
        except Exception as e:
            tool_calls.append(ToolCall(
                tool_name="inventory_query_enhanced",
                parameters={"product_name": product_name, "category": category},
                error=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _query_order_status(
        self, 
        request: AgentRequest, 
        tool_calls: List[ToolCall]
    ) -> Dict[str, Any]:
        """Query order status information."""
        results = {}
        
        # Extract order ID or customer ID from message
        order_id = self._extract_order_id(request.customer_message)
        customer_id = request.customer_id or self._extract_customer_id(request.customer_message)
        
        start_time = time.time()
        
        try:
            if order_id:
                # Query specific order
                order_data = await self.sql_executor.get_order_by_id(order_id)
                results['specific_order'] = order_data
                
                tool_calls.append(ToolCall(
                    tool_name="get_order_by_id",
                    parameters={"order_id": order_id},
                    result=order_data,
                    execution_time=time.time() - start_time
                ))
                
            elif customer_id:
                # Query customer orders
                customer_orders = await self.sql_executor.get_customer_orders(customer_id)
                results['customer_orders'] = customer_orders
                
                tool_calls.append(ToolCall(
                    tool_name="get_customer_orders",
                    parameters={"customer_id": customer_id},
                    result=customer_orders,
                    execution_time=time.time() - start_time
                ))
            
            else:
                # General order status summary
                order_summary = await self.sql_executor.get_order_status_summary()
                results['order_summary'] = order_summary
                
                tool_calls.append(ToolCall(
                    tool_name="get_order_status_summary",
                    parameters={},
                    result=order_summary,
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            tool_calls.append(ToolCall(
                tool_name="order_status_query",
                parameters={"customer_id": customer_id, "order_id": order_id},
                error=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _query_inventory(
        self, 
        request: AgentRequest, 
        tool_calls: List[ToolCall]
    ) -> Dict[str, Any]:
        """Query inventory information."""
        results = {}
        
        # Extract product information from message
        product_info = self._extract_product_info(request.customer_message)
        
        start_time = time.time()
        
        try:
            if product_info['product_name'] or product_info['category']:
                inventory_data = await self.sql_executor.check_product_availability(
                    product_name=product_info['product_name'],
                    category=product_info['category']
                )
                results['inventory'] = inventory_data
                
                tool_calls.append(ToolCall(
                    tool_name="check_product_availability",
                    parameters=product_info,
                    result=inventory_data,
                    execution_time=time.time() - start_time
                ))
            
            else:
                # General inventory check
                inventory_data = await self.sql_executor.check_product_availability()
                results['inventory'] = inventory_data[:10]  # Limit results
                
                tool_calls.append(ToolCall(
                    tool_name="check_product_availability",
                    parameters={},
                    result=results['inventory'],
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            tool_calls.append(ToolCall(
                tool_name="inventory_query",
                parameters=product_info,
                error=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _query_shipping_status(
        self, 
        request: AgentRequest, 
        tool_calls: List[ToolCall]
    ) -> Dict[str, Any]:
        """Query shipping status information."""
        results = {}
        
        order_id = self._extract_order_id(request.customer_message)
        customer_id = request.customer_id or self._extract_customer_id(request.customer_message)
        
        start_time = time.time()
        
        try:
            shipping_data = await self.sql_executor.get_shipping_status(
                customer_id=customer_id,
                order_id=order_id
            )
            results['shipping'] = shipping_data
            
            tool_calls.append(ToolCall(
                tool_name="get_shipping_status",
                parameters={"customer_id": customer_id, "order_id": order_id},
                result=shipping_data,
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            tool_calls.append(ToolCall(
                tool_name="shipping_status_query",
                parameters={"customer_id": customer_id, "order_id": order_id},
                error=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _query_return_exchange(
        self, 
        request: AgentRequest, 
        tool_calls: List[ToolCall]
    ) -> Dict[str, Any]:
        """Query return/exchange status information."""
        results = {}
        
        order_id = self._extract_order_id(request.customer_message)
        customer_id = request.customer_id or self._extract_customer_id(request.customer_message)
        
        start_time = time.time()
        
        try:
            return_data = await self.sql_executor.check_return_exchange_status(
                customer_id=customer_id,
                order_id=order_id
            )
            results['returns'] = return_data
            
            tool_calls.append(ToolCall(
                tool_name="check_return_exchange_status",
                parameters={"customer_id": customer_id, "order_id": order_id},
                result=return_data,
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            tool_calls.append(ToolCall(
                tool_name="return_exchange_query",
                parameters={"customer_id": customer_id, "order_id": order_id},
                error=str(e),
                execution_time=time.time() - start_time
            ))
        
        return results
    
    async def _extract_entities_with_llm(self, message: str) -> Dict[str, List[str]]:
        """
        Extract entities from customer message using LLM structured output.
        
        Args:
            message: Customer message
            
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
            logger.warning(f"LLM entity extraction failed, using fallback: {e}")
            return self._fallback_entity_extraction(message)
    
    def _fallback_entity_extraction(self, message: str) -> Dict[str, List[str]]:
        """
        Fallback entity extraction using regex patterns.
        
        Args:
            message: Customer message
            
        Returns:
            Dictionary of extracted entities
        """
        import re
        
        message_lower = message.lower()
        
        # Extract order IDs
        order_patterns = [
            r'ord[-_]\d{4}[-_]\d{3}',  # ORD-2024-001
            r'order[-_]\d+',          # order-123
            r'ord\d+',                # ord123
            r'#\d+',                  # #12345
        ]
        order_ids = []
        for pattern in order_patterns:
            matches = re.findall(pattern, message_lower)
            order_ids.extend(matches)
        
        # Extract customer IDs
        customer_patterns = [
            r'cust\d+',              # cust001
            r'customer[-_]\d+',      # customer-123
            r'id[-_]\d+',            # id-456
        ]
        customer_ids = []
        for pattern in customer_patterns:
            matches = re.findall(pattern, message_lower)
            customer_ids.extend(matches)
        
        # Extract product info
        categories = ['headphones', 'watch', 'speaker', 'computer', 'phone']
        product_categories = [cat for cat in categories if cat in message_lower]
        
        product_names = []
        known_products = ['zensound', 'vitafit', 'promax', 'ultrabook']
        for product in known_products:
            if product in message_lower:
                product_names.append(product)
        
        return {
            "order_ids": order_ids,
            "customer_ids": customer_ids,
            "product_names": product_names,
            "product_categories": product_categories,
            "status_references": [],
            "temporal_references": [],
            "quantity_references": []
        }
    
    def _extract_order_id(self, message: str) -> Optional[str]:
        """Extract order ID from customer message (legacy method)."""
        entities = self._fallback_entity_extraction(message)
        order_ids = entities.get("order_ids", [])
        return order_ids[0] if order_ids else None
    
    def _extract_customer_id(self, message: str) -> Optional[str]:
        """Extract customer ID from message (legacy method)."""
        entities = self._fallback_entity_extraction(message)
        customer_ids = entities.get("customer_ids", [])
        return customer_ids[0] if customer_ids else None
    
    def _extract_product_info(self, message: str) -> Dict[str, Optional[str]]:
        """Extract product name and category from message (legacy method)."""
        entities = self._fallback_entity_extraction(message)
        return {
            'product_name': entities.get("product_names", [None])[0],
            'category': entities.get("product_categories", [None])[0]
        }
    
    async def _format_response_with_llm(
        self, 
        customer_message: str,
        query_results: Dict[str, Any],
        inquiry_analysis: Dict[str, Any],
        tool_calls: List[ToolCall]
    ) -> str:
        """
        Format the query results into a customer-friendly response using LLM synthesis.
        
        Args:
            customer_message: Original customer message
            query_results: Results from database queries
            inquiry_analysis: LLM inquiry analysis
            tool_calls: Tool calls made
            
        Returns:
            Formatted response text
        """
        try:
            # If no results, provide appropriate message
            if not query_results or all(not v for v in query_results.values()):
                return "I could not find any information related to your inquiry. Please check your order details or contact our support team for assistance."
            
            # Use LLM to synthesize the response
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
            
            logger.info(f"Response synthesis confidence: {synthesis.confidence_assessment:.2f}")
            
            return truncate_text(synthesis.customer_response, 800)
            
        except Exception as e:
            logger.warning(f"LLM response synthesis failed, using fallback: {e}")
            return self._format_response_fallback(query_results)
    
    def _format_response_fallback(self, query_results: Dict[str, Any]) -> str:
        """
        Fallback response formatting when LLM synthesis fails.
        
        Args:
            query_results: Results from database queries
            
        Returns:
            Formatted response text
        """
        response_parts = []
        
        # Order status information
        if 'specific_order' in query_results and query_results['specific_order']:
            order = query_results['specific_order']
            response_parts.append(
                f"Order {order['order_id']}: {order['product_name']} is currently {order['order_status']}."
            )
        
        elif 'customer_orders' in query_results and query_results['customer_orders']:
            orders = query_results['customer_orders']
            if orders:
                response_parts.append(f"Found {len(orders)} orders for your account.")
        
        # Inventory information
        if 'inventory' in query_results and query_results['inventory']:
            inventory = query_results['inventory']
            if inventory:
                response_parts.append(f"Found {len(inventory)} products in inventory.")
        
        # Combine parts or provide default
        if response_parts:
            return " ".join(response_parts)
        else:
            return "I found some information about your inquiry. Please contact our support team for detailed assistance."
    
    def _calculate_confidence(
        self, 
        query_results: Dict[str, Any], 
        tool_calls: List[ToolCall]
    ) -> float:
        """
        Calculate confidence score based on query results and tool calls.
        
        Args:
            query_results: Results from database queries
            tool_calls: Tool calls made
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with base confidence
        confidence = 0.3
        
        # Increase confidence based on successful results
        if query_results:
            for value in query_results.values():
                if value:  # Non-empty results
                    if isinstance(value, list) and len(value) > 0:
                        confidence += 0.2
                    elif isinstance(value, dict):
                        confidence += 0.2
        
        # Increase confidence based on successful tool calls
        successful_tools = sum(1 for tool in tool_calls if tool.error is None)
        if successful_tools > 0:
            confidence += 0.1 * successful_tools
        
        # Decrease confidence for errors
        failed_tools = sum(1 for tool in tool_calls if tool.error is not None)
        if failed_tools > 0:
            confidence -= 0.1 * failed_tools
        
        # Ensure confidence is between 0 and 1
        return max(0.0, min(1.0, confidence))
    
    async def _handle_error(
        self, 
        request: AgentRequest, 
        error_details: str,
        tool_calls: List[ToolCall],
        processing_time: float
    ) -> AgentResponse:
        """
        Handle errors and provide fallback response using LLM structured output.
        
        Args:
            request: Original request
            error_details: Error information
            tool_calls: Tool calls made
            processing_time: Time taken
            
        Returns:
            Error response
        """
        try:
            # Use LLM structured output for error handling
            error_prompt = f"""
            A customer inquiry about orders encountered an error. Provide a helpful response.
            
            Customer's message: "{request.customer_message}"
            Error details: {error_details}
            
            Provide a professional response that:
            1. Acknowledges the issue without technical details
            2. Suggests alternative ways to get help
            3. Maintains a helpful tone
            4. Offers specific next steps if possible
            """
            
            error_analysis = await self.error_analyzer.ainvoke(error_prompt)
            error_response = error_analysis.customer_message
            
            logger.info(f"Error escalation needed: {error_analysis.escalation_needed}")
            
        except Exception:
            # Final fallback
            error_response = "I'm experiencing technical difficulties accessing our order system. Please try again in a few minutes or contact our support team directly."
        
        return AgentResponse(
            response=error_response,
            agent_type=self.agent_type,
            confidence_score=0.1,
            tool_calls=tool_calls,
            session_id=request.session_id,
            processing_time=processing_time
        )
    
    async def test_database_connection(self) -> bool:
        """Test database connection."""
        try:
            async with self.sql_executor:
                result = await self.sql_executor.execute_query("SELECT 1 as test")
                return result.error is None
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False