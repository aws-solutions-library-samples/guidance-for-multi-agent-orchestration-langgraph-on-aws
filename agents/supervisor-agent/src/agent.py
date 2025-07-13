"""
Supervisor agent implementation.

This module contains the core logic for the supervisor agent, including
intent analysis, agent delegation, and response synthesis.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any

from langchain_aws import ChatBedrock
from shared.models import (
    SupervisorRequest, 
    SupervisorResponse, 
    AgentRequest, 
    AgentResponse,
    AgentType
)
from shared.utils import (
    calculate_confidence_score,
    truncate_text
)
import client
import prompts as supervisor_prompts
import config as supervisor_config
from structured_models import (
    IntentAnalysis,
    AgentSelection,
    ResponseSynthesis,
    ErrorResponse,
    CustomerNeedAssessment
)

config = supervisor_config.config

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Main supervisor agent for coordinating customer support interactions."""
    
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
    
    async def process_request(self, request: SupervisorRequest):
        """
        Process a customer support request.
        
        Args:
            request: Customer support request
            
        Returns:
            Supervisor response with synthesized answer
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing request for session {request.session_id}")
            
            # Step 1: Analyze customer intent
            intent_info = await self._analyze_intent(request.customer_message)
            logger.info(f"Detected intent: {intent_info}")
            
            # Step 2: Select appropriate agents
            selected_agents = await self._select_agents(
                request.customer_message, 
                intent_info
            )
            logger.info(f"Selected agents: {selected_agents}")
            
            # Step 3: Call selected agents
            agent_responses = await self._call_agents(
                selected_agents, 
                request
            )
            logger.info(f"Agent responses: {agent_responses}")
            # Step 4: Synthesize response
            synthesized_response = await self._synthesize_response(
                request.customer_message,
                agent_responses
            )
            
            # Step 5: Calculate overall confidence
            confidence_score = calculate_confidence_score(
                [resp for resp in agent_responses.values() if resp is not None]
            )
            
            processing_time = time.time() - start_time
            
            # Prepare response data in JSON format
            response_data = {
                "response": synthesized_response,
                "agents_called": selected_agents,
                "agent_responses": [
                    resp.model_dump() for resp in agent_responses.values() if resp is not None
                ],
                "confidence_score": confidence_score,
                "session_id": request.session_id,
                "processing_time": processing_time,
                "follow_up_needed": confidence_score < 0.7
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
                "reasoning": intent_analysis.reasoning
            }
            
        except Exception as e:
            logger.warning(f"Structured intent analysis failed, using fallback: {e}")
            return {
                "primary_intent": "general",
                "all_intents": ["general"],
                "confidence": 0.5,
                "requires_multiple_agents": False,
                "customer_id_mentioned": "cust" in message.lower(),
                "reasoning": "Fallback analysis due to error"
            }
    
    async def _llm_intent_analysis(self, message: str) -> Dict[str, Any]:
        """
        Use LLM for intent analysis.
        
        Args:
            message: Customer message
            
        Returns:
            LLM intent analysis
        """
        try:
            prompt = supervisor_prompts.INTENT_ANALYSIS_PROMPT.format(message=message)
            
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            intent_data = json.loads(response.content)
            return intent_data
            
        except Exception as e:
            logger.warning(f"LLM intent analysis failed: {e}")
            return {
                "primary_intent": "general",
                "required_agents": ["order_management"],
                "priority": "medium",
                "multiple_agents_needed": False,
                "reasoning": "Fallback analysis due to error"
            }
    
    async def _select_agents(
        self, 
        message: str, 
        intent_info: Dict[str, Any]
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
            valid_agents = ["order_management", "product_recommendation", "troubleshooting", "personalization"]
            selected = [agent for agent in agent_selection.selected_agents if agent in valid_agents]
            
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
                "general": ["order_management"]
            }
            
            selected = intent_to_agents.get(primary_intent, ["order_management"])
            
            # Add personalization if customer ID mentioned
            if intent_info.get("customer_id_mentioned", False) and "personalization" not in selected:
                selected.insert(0, "personalization")
            
            return selected[:3]
    
    async def _call_agents(
        self, 
        agent_types: List[str], 
        request: SupervisorRequest
    ):
        """
        Call selected agents with the customer request.
        
        Args:
            agent_types: List of agent types to call
            request: Original customer request
            
        Returns:
            Dictionary mapping agent types to their responses
        """
        # Prepare agent requests
        agent_requests = []
        for agent_type in agent_types:
            agent_request = AgentRequest(
                customer_message=request.customer_message,
                session_id=request.session_id,
                customer_id=request.customer_id,
                conversation_history=request.conversation_history,
                context=request.context,
                max_response_length=self.max_response_words
            )
            agent_requests.append((agent_type, agent_request))
        
        # Call agents in parallel
        try:
            responses = await self.client.call_multiple_agents(agent_requests)
            print(responses)
            
            # Print responses for debugging
            for agent_type, response in responses.items():
                if response:
                    logger.debug(f"AGENT RESPONSE [{agent_type}]: {str(response)[:100]}...")
                else:
                    logger.debug(f"AGENT RESPONSE [{agent_type}]: None")
            
            # Log results
            successful_calls = sum(1 for resp in responses.values() if resp is not None)
            logger.info(f"Successfully called {successful_calls}/{len(agent_types)} agents")
            
            return responses
            
        except Exception as e:
            logger.error(f"Failed to call agents: {e}")
            return {agent_type: None for agent_type in agent_types}
    
    async def _synthesize_response(
        self, 
        customer_message: str,
        agent_responses: Dict[str, Optional[AgentResponse]]
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
                agent: resp for agent, resp in agent_responses.items() 
                if resp is not None
            }
            
            if not valid_responses:
                return "I apologize, but I'm having trouble accessing our systems right now. Please try again in a moment."
            
            # If only one response, use it directly (with some formatting)
            if len(valid_responses) == 1:
                response = list(valid_responses.values())[0]
                return f"Raw response: {str(response)}"
            
            # Format agent responses for synthesis
            agent_responses_text = ""
            for agent_type, response in valid_responses.items():
                agent_responses_text += f"\n{agent_type.replace('_', ' ').title()}: {str(response)}"
            
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
            
            logger.info(f"Synthesis confidence: {synthesis_result.confidence_assessment:.2f}")
            logger.info(f"Key information used: {synthesis_result.key_information_used}")
            
            return truncate_text(synthesis_result.synthesized_response, self.max_response_words * 6)
            
        except Exception as e:
            logger.warning(f"Structured synthesis failed, using fallback: {e}")
            
            # Fallback: concatenate responses
            valid_responses = [
                str(resp) for resp in agent_responses.values() 
                if resp is not None
            ]
            
            if valid_responses:
                combined = " ".join(valid_responses)
                return truncate_text(combined, self.max_response_words * 6)
            else:
                return "I'm having trouble processing your request. Please try again."
    
    async def _handle_error(
        self, 
        request: SupervisorRequest, 
        error_details: str
    ) -> SupervisorResponse:
        """
        Handle errors and provide fallback response using structured LLM output.
        
        Args:
            request: Original request
            error_details: Error information
            
        Returns:
            Error response
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
        
        return SupervisorResponse(
            response=error_response,
            agents_called=[],
            agent_responses=[],
            confidence_score=0.1,
            session_id=request.session_id,
            processing_time=0.0,
            follow_up_needed=True
        )
    
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
                "available_agents": self.client.get_available_agents()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _test_llm_connection(self) -> bool:
        """Test LLM connection with a simple query."""
        try:
            messages = [{"role": "user", "content": "Hello"}]
            response = await self.llm.ainvoke(messages)
            return bool(response and response.content)
        except Exception as e:
            logger.warning(f"LLM connection test failed: {e}")
            return False