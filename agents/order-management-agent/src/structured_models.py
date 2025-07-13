"""
Pydantic models for structured LLM outputs in the order management agent.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class InquiryAnalysis(BaseModel):
    """Structured output for customer inquiry analysis."""
    
    inquiry_type: str = Field(
        description="Primary inquiry type: order_status, inventory, shipping, returns, general"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for the inquiry type (0.0 to 1.0)"
    )
    extracted_entities: Dict[str, Optional[str]] = Field(
        description="Extracted entities like order_id, customer_id, product_name, etc."
    )
    specific_request: str = Field(
        description="Specific request or question the customer is asking"
    )
    urgency_level: str = Field(
        description="Urgency level: low, medium, high, urgent"
    )
    reasoning: str = Field(
        description="Brief explanation of why this inquiry type was selected"
    )


class QueryPlan(BaseModel):
    """Structured output for database query planning."""
    
    required_queries: List[str] = Field(
        description="List of database queries needed: get_order_by_id, get_customer_orders, check_inventory, etc."
    )
    query_parameters: Dict[str, Any] = Field(
        description="Parameters needed for the queries"
    )
    execution_strategy: str = Field(
        description="How to execute queries: sequential, parallel, conditional"
    )
    expected_data_types: List[str] = Field(
        description="Types of data expected: order_details, inventory_status, shipping_info, etc."
    )
    fallback_plan: str = Field(
        description="What to do if primary queries fail"
    )


class ResponseSynthesis(BaseModel):
    """Structured output for response synthesis."""
    
    customer_response: str = Field(
        description="The final response to send to the customer",
        max_length=800
    )
    confidence_assessment: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in the response accuracy"
    )
    data_sources_used: List[str] = Field(
        description="Which data sources/queries provided the information"
    )
    follow_up_needed: bool = Field(
        description="Whether additional follow-up is recommended"
    )
    next_steps: List[str] = Field(
        description="Suggested next steps for the customer if any"
    )


class EntityExtraction(BaseModel):
    """Structured output for entity extraction from customer messages."""
    
    order_ids: List[str] = Field(
        description="Order IDs mentioned in the message (ORD-2024-001, order-123, etc.)"
    )
    customer_ids: List[str] = Field(
        description="Customer IDs mentioned (cust001, customer-123, etc.)"
    )
    product_names: List[str] = Field(
        description="Product names mentioned"
    )
    product_categories: List[str] = Field(
        description="Product categories mentioned (headphones, watch, etc.)"
    )
    status_references: List[str] = Field(
        description="Status-related terms mentioned (shipped, delivered, processing, etc.)"
    )
    temporal_references: List[str] = Field(
        description="Time references (today, yesterday, last week, etc.)"
    )
    quantity_references: List[str] = Field(
        description="Quantity or number references mentioned"
    )


class QueryDecision(BaseModel):
    """Structured output for deciding which database queries to execute."""
    
    primary_query_type: str = Field(
        description="Primary query type: order_lookup, inventory_check, shipping_status, return_status"
    )
    should_query_orders: bool = Field(
        description="Whether to query order information"
    )
    should_query_inventory: bool = Field(
        description="Whether to query inventory information"
    )
    should_query_shipping: bool = Field(
        description="Whether to query shipping information"
    )
    should_query_returns: bool = Field(
        description="Whether to query return/exchange information"
    )
    query_scope: str = Field(
        description="Query scope: specific_order, customer_orders, general_status, product_specific"
    )
    priority_order: List[str] = Field(
        description="Order of priority for executing queries"
    )


class ErrorAnalysis(BaseModel):
    """Structured output for error analysis and recovery."""
    
    error_category: str = Field(
        description="Error category: database_error, missing_data, invalid_input, system_error"
    )
    customer_message: str = Field(
        description="Appropriate message to send to customer about the error",
        max_length=300
    )
    suggested_actions: List[str] = Field(
        description="Actions the customer can take to resolve or work around the issue"
    )
    escalation_needed: bool = Field(
        description="Whether this should be escalated to human support"
    )
    retry_recommended: bool = Field(
        description="Whether the customer should try again later"
    )
    alternative_help: List[str] = Field(
        description="Alternative ways to help the customer"
    )