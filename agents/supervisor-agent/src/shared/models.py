"""
Shared Pydantic models for inter-service communication.

This module defines the common data structures used across all agent services
for consistent API contracts and data validation.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AgentType(str, Enum):
    """Enumeration of available agent types."""
    SUPERVISOR = "supervisor"
    ORDER_MANAGEMENT = "order_management"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    TROUBLESHOOTING = "troubleshooting"
    PERSONALIZATION = "personalization"


class MessageRole(str, Enum):
    """Message roles for conversation tracking."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """Individual message in a conversation."""
    role: MessageRole
    content: str
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Tool call information for tracking function executions."""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None


class AgentRequest(BaseModel):
    """Standard request format for all agent services."""
    customer_message: str = Field(..., description="The customer's input message")
    session_id: str = Field(..., description="Unique session identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier if available")
    conversation_history: List[Message] = Field(
        default_factory=list, 
        description="Previous messages in the conversation"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional context for the request"
    )
    max_response_length: Optional[int] = Field(
        100, 
        description="Maximum response length in words"
    )


class AgentResponse(BaseModel):
    """Standard response format for all agent services."""
    response: str = Field(..., description="The agent's response to the customer")
    agent_type: AgentType = Field(..., description="Type of agent that generated the response")
    confidence_score: float = Field(
        0.0, 
        ge=0.0, 
        le=1.0, 
        description="Confidence score for the response"
    )
    tool_calls: List[ToolCall] = Field(
        default_factory=list, 
        description="Tools executed during processing"
    )
    session_id: str = Field(..., description="Session identifier")
    processing_time: Optional[float] = Field(
        None, 
        description="Time taken to process the request in seconds"
    )
    requires_followup: bool = Field(
        False, 
        description="Whether the response requires follow-up actions"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional response metadata"
    )


class SupervisorRequest(BaseModel):
    """Request format specific to the supervisor agent."""
    customer_message: str = Field(..., description="The customer's input message")
    session_id: str = Field(..., description="Unique session identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier if available")
    conversation_history: List[Message] = Field(
        default_factory=list, 
        description="Previous messages in the conversation"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional context for the request"
    )


class SupervisorResponse(BaseModel):
    """Response format specific to the supervisor agent."""
    response: str = Field(..., description="The synthesized response to the customer")
    agents_called: List[AgentType] = Field(
        default_factory=list, 
        description="List of agents that were consulted"
    )
    agent_responses: List[AgentResponse] = Field(
        default_factory=list, 
        description="Individual responses from consulted agents"
    )
    confidence_score: float = Field(
        0.0, 
        ge=0.0, 
        le=1.0, 
        description="Overall confidence in the synthesized response"
    )
    session_id: str = Field(..., description="Session identifier")
    processing_time: Optional[float] = Field(
        None, 
        description="Total time taken to process the request"
    )
    follow_up_needed: bool = Field(
        False, 
        description="Whether additional clarification is needed"
    )


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck(BaseModel):
    """Health check response format."""
    status: HealthStatus
    service: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = None
    dependencies: Optional[Dict[str, HealthStatus]] = Field(default_factory=dict)
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DatabaseQuery(BaseModel):
    """Database query request format."""
    query: str = Field(..., description="SQL query to execute")
    database: str = Field(..., description="Target database name")
    timeout: Optional[int] = Field(10, description="Query timeout in seconds")
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Query parameters"
    )


class DatabaseResult(BaseModel):
    """Database query result format."""
    results: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Query results"
    )
    execution_time: float = Field(..., description="Query execution time in seconds")
    row_count: int = Field(..., description="Number of rows returned")
    error: Optional[str] = Field(None, description="Error message if query failed")


class KnowledgeBaseQuery(BaseModel):
    """Knowledge base search request format."""
    query: str = Field(..., description="Search query")
    knowledge_base: str = Field(..., description="Target knowledge base")
    max_results: Optional[int] = Field(5, description="Maximum number of results")
    similarity_threshold: Optional[float] = Field(
        0.7, 
        ge=0.0, 
        le=1.0, 
        description="Minimum similarity score"
    )


class KnowledgeBaseResult(BaseModel):
    """Knowledge base search result format."""
    content: str = Field(..., description="Retrieved content")
    relevance_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Relevance score"
    )
    source: str = Field(..., description="Source of the content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional metadata"
    )


class KnowledgeBaseResults(BaseModel):
    """Multiple knowledge base search results."""
    results: List[KnowledgeBaseResult] = Field(
        default_factory=list, 
        description="Search results"
    )
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Total number of results found")
    search_time: float = Field(..., description="Search execution time in seconds")


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code for categorization")
    details: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional error details"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = Field(None, description="Request identifier for tracking")


class ServiceConfig(BaseModel):
    """Service configuration model."""
    service_name: str
    version: str
    aws_region: str
    bedrock_model_id: str
    bedrock_temperature: float = 0.7
    bedrock_max_tokens: int = 1000
    log_level: str = "INFO"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    http_timeout: int = 30
    database_timeout: int = 10
    bedrock_timeout: int = 15
    max_retries: int = 3
    retry_backoff_factor: float = 2.0


# Response models for specific agents

class OrderInfo(BaseModel):
    """Order information model."""
    order_id: str
    customer_id: str
    product_id: str
    product_name: str
    order_status: str
    shipping_status: str
    return_exchange_status: Optional[str] = None
    order_date: str
    delivery_date: Optional[str] = None


class ProductInfo(BaseModel):
    """Product information model."""
    product_id: str
    product_name: str
    category: str
    price: float
    description: str
    rating: float
    popularity: str


class CustomerProfile(BaseModel):
    """Customer profile model."""
    customer_id: str
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[str] = None
    location: Optional[str] = None
    marital_status: Optional[str] = None
    preferred_category: Optional[str] = None
    price_range: Optional[str] = None
    preferred_brand: Optional[str] = None
    loyalty_tier: Optional[str] = None


class TroubleshootingInfo(BaseModel):
    """Troubleshooting information model."""
    product_name: str
    category: str
    issue_id: str
    common_problems: List[str]
    suggested_solutions: List[str]
    warranty_info: Optional[str] = None