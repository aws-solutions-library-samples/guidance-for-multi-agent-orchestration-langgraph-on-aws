"""
Pydantic models for structured LLM outputs in the supervisor agent.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    """Structured output for customer intent analysis."""
    
    primary_intent: str = Field(
        description="The primary intent category: order, product, troubleshooting, personalization, or general"
    )
    all_intents: List[str] = Field(
        description="All detected intent categories in order of relevance"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for the primary intent (0.0 to 1.0)"
    )
    requires_multiple_agents: bool = Field(
        description="Whether this request requires multiple specialized agents"
    )
    customer_id_mentioned: bool = Field(
        description="Whether a customer ID (like cust001) is mentioned in the message"
    )
    reasoning: str = Field(
        description="Brief explanation of why this intent was selected"
    )


class AgentSelection(BaseModel):
    """Structured output for agent selection decisions."""
    
    selected_agents: List[str] = Field(
        description="List of agent names to call: order_management, product_recommendation, troubleshooting, personalization"
    )
    execution_order: List[str] = Field(
        description="Order in which agents should be called"
    )
    parallel_execution: bool = Field(
        description="Whether agents can be called in parallel or must be sequential"
    )
    reasoning: str = Field(
        description="Explanation of agent selection strategy"
    )


class ResponseSynthesis(BaseModel):
    """Structured output for response synthesis."""
    
    synthesized_response: str = Field(
        description="The final customer response combining all agent outputs",
        max_length=2000
    )
    confidence_assessment: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in the synthesized response"
    )
    key_information_used: List[str] = Field(
        description="Key pieces of information from agents that were included"
    )
    follow_up_needed: bool = Field(
        description="Whether additional follow-up or clarification is needed"
    )


class ErrorResponse(BaseModel):
    """Structured output for error handling."""
    
    customer_response: str = Field(
        description="Professional response to customer acknowledging the issue",
        max_length=300
    )
    suggested_actions: List[str] = Field(
        description="Alternative actions the customer could take"
    )
    escalation_needed: bool = Field(
        description="Whether this issue should be escalated to human support"
    )


class CustomerNeedAssessment(BaseModel):
    """Structured output for assessing customer needs."""
    
    needs_order_info: bool = Field(description="Customer needs order-related information")
    needs_product_recommendations: bool = Field(description="Customer needs product suggestions")
    needs_technical_support: bool = Field(description="Customer needs troubleshooting help")
    needs_account_info: bool = Field(description="Customer needs account/profile information")
    
    urgency_level: str = Field(
        description="Urgency level: low, medium, high, urgent"
    )
    
    key_entities: List[str] = Field(
        description="Important entities mentioned: order IDs, product names, customer IDs, etc."
    )
    
    customer_sentiment: str = Field(
        description="Customer sentiment: positive, neutral, frustrated, angry"
    )


class FollowUpAssessment(BaseModel):
    """Structured output for follow-up question assessment."""
    
    needs_followup: bool = Field(
        description="Whether follow-up questions are needed"
    )
    
    followup_questions: List[str] = Field(
        description="Specific follow-up questions to ask the customer"
    )
    
    missing_information: List[str] = Field(
        description="Types of information that are missing to fully help the customer"
    )
    
    can_proceed: bool = Field(
        description="Whether we have enough information to proceed with the request"
    )


class SupervisorDecision(BaseModel):
    """Combined structured output for intent analysis, agent selection, and direct response capability."""
    
    # Intent analysis
    primary_intent: str = Field(
        description="The primary intent category: order, product, troubleshooting, personalization, or general"
    )
    all_intents: List[str] = Field(
        description="All detected intent categories in order of relevance"
    )
    intent_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for the primary intent (0.0 to 1.0)"
    )
    
    # Direct response capability
    can_respond_directly: bool = Field(
        description="Whether the supervisor can respond directly without calling sub-agents"
    )
    direct_response: Optional[str] = Field(
        default=None,
        description="Direct response from supervisor if no sub-agents are needed",
        max_length=600
    )
    
    # Agent selection (only if can_respond_directly is False)
    selected_agents: List[str] = Field(
        default=[],
        description="List of agent names to call: order_management, product_recommendation, troubleshooting, personalization"
    )
    execution_order: List[str] = Field(
        default=[],
        description="Order in which agents should be called"
    )
    parallel_execution: bool = Field(
        default=True,
        description="Whether agents can be called in parallel or must be sequential"
    )
    
    # Additional context
    customer_id_mentioned: bool = Field(
        description="Whether a customer ID (like cust001) is mentioned in the message"
    )
    key_entities: List[str] = Field(
        default=[],
        description="Important entities mentioned: order IDs, product names, customer IDs, etc."
    )
    urgency_level: str = Field(
        description="Urgency level: low, medium, high, urgent"
    )
    reasoning: str = Field(
        description="Explanation of the decision-making process"
    )