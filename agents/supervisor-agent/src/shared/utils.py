"""
Shared utility functions for all agent services.

This module provides common functionality used across multiple services
including HTTP clients, error handling, and response formatting.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, TypeVar, Callable
from datetime import datetime
import httpx
from .models import (
    AgentRequest, 
    AgentResponse, 
    ErrorResponse, 
    HealthCheck, 
    HealthStatus,
    Message,
    MessageRole
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class HTTPClient:
    """Async HTTP client with retry logic and timeout handling."""
    
    def __init__(
        self, 
        base_url: str, 
        timeout: int = 30, 
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0
    ):
        """
        Initialize HTTP client.
        
        Args:
            base_url: Base URL for the service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff_factor: Backoff multiplier for retries
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self._client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    async def post(
        self, 
        endpoint: str, 
        data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make POST request with retry logic.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            headers: Optional headers
            
        Returns:
            Response data
            
        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        if not self._client:
            raise RuntimeError("HTTPClient must be used as async context manager")
        
        url = f"{endpoint}"
        headers = headers or {"Content-Type": "application/json"}
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Making POST request to {url} (attempt {attempt + 1})")
                
                response = await self._client.post(
                    url,
                    json=data,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                if attempt == self.max_retries:
                    logger.error(f"Request failed after {self.max_retries + 1} attempts: {e}")
                    raise
                
                wait_time = self.retry_backoff_factor ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
    
    async def get(
        self, 
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make GET request with retry logic.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Optional headers
            
        Returns:
            Response data
        """
        if not self._client:
            raise RuntimeError("HTTPClient must be used as async context manager")
        
        url = f"{endpoint}"
        headers = headers or {}
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Making GET request to {url} (attempt {attempt + 1})")
                
                response = await self._client.get(
                    url,
                    params=params,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                if attempt == self.max_retries:
                    logger.error(f"Request failed after {self.max_retries + 1} attempts: {e}")
                    raise
                
                wait_time = self.retry_backoff_factor ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def generate_request_id() -> str:
    """Generate a unique request ID for tracking."""
    return str(uuid.uuid4())


def create_error_response(
    error_message: str,
    error_code: str = "INTERNAL_ERROR",
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """
    Create standardized error response.
    
    Args:
        error_message: Human-readable error message
        error_code: Error code for categorization
        details: Additional error details
        request_id: Request ID for tracking
        
    Returns:
        Formatted error response
    """
    return ErrorResponse(
        error=error_message,
        error_code=error_code,
        details=details or {},
        request_id=request_id or generate_request_id()
    )


def create_health_check_response(
    service_name: str,
    status: HealthStatus = HealthStatus.HEALTHY,
    version: Optional[str] = None,
    dependencies: Optional[Dict[str, HealthStatus]] = None,
    details: Optional[Dict[str, Any]] = None
) -> HealthCheck:
    """
    Create standardized health check response.
    
    Args:
        service_name: Name of the service
        status: Health status
        version: Service version
        dependencies: Status of dependencies
        details: Additional health details
        
    Returns:
        Health check response
    """
    return HealthCheck(
        status=status,
        service=service_name,
        version=version,
        dependencies=dependencies or {},
        details=details or {}
    )


def format_conversation_history(messages: List[Message], max_messages: int = 10) -> List[Dict[str, Any]]:
    """
    Format conversation history for LLM consumption.
    
    Args:
        messages: List of conversation messages
        max_messages: Maximum number of messages to include
        
    Returns:
        Formatted message history
    """
    # Take the most recent messages
    recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
    
    formatted = []
    for message in recent_messages:
        formatted.append({
            "role": message.role.value,
            "content": message.content,
            "timestamp": message.timestamp.isoformat() if message.timestamp else None
        })
    
    return formatted


def extract_customer_intent(message: str) -> Dict[str, Any]:
    """
    Extract basic intent information from customer message.
    
    This is a simple rule-based approach. In production, this could be
    replaced with a more sophisticated intent classification model.
    
    Args:
        message: Customer message
        
    Returns:
        Intent information including likely categories
    """
    message_lower = message.lower()
    
    # Simple keyword-based intent detection
    intent_keywords = {
        "order": ["order", "purchase", "buy", "delivery", "shipping", "return", "exchange"],
        "product": ["recommend", "suggest", "product", "item", "catalog", "price", "rating"],
        "troubleshooting": ["problem", "issue", "bug", "error", "not working", "broken", "help"],
        "account": ["account", "profile", "preferences", "history", "personal"]
    }
    
    detected_intents = []
    for intent, keywords in intent_keywords.items():
        if any(keyword in message_lower for keyword in keywords):
            detected_intents.append(intent)
    
    # Default to general if no specific intent detected
    if not detected_intents:
        detected_intents = ["general"]
    
    return {
        "primary_intent": detected_intents[0] if detected_intents else "general",
        "all_intents": detected_intents,
        "confidence": 0.8 if detected_intents else 0.3,
        "requires_multiple_agents": len(detected_intents) > 1
    }


def calculate_confidence_score(agent_responses: List[AgentResponse]) -> float:
    """
    Calculate overall confidence score from multiple agent responses.
    
    Args:
        agent_responses: List of agent responses
        
    Returns:
        Overall confidence score
    """
    if not agent_responses:
        return 0.0
    
    # Use weighted average, giving more weight to higher individual scores
    total_weighted_score = sum(
        response.confidence_score ** 2 for response in agent_responses
    )
    total_weights = sum(
        response.confidence_score for response in agent_responses
    )
    
    if total_weights == 0:
        return 0.0
    
    return min(total_weighted_score / total_weights, 1.0)


def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Truncate text to specified length while preserving word boundaries.
    
    Args:
        text: Text to truncate
        max_length: Maximum length in characters
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    # Find last space before max_length
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # If space is reasonably close to limit
        return truncated[:last_space] + "..."
    else:
        return truncated + "..."


def measure_execution_time(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to measure function execution time.
    
    Args:
        func: Function to measure
        
    Returns:
        Wrapped function that logs execution time
    """
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent potential security issues.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text
    """
    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&']
    sanitized = text
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    # Limit length
    sanitized = sanitized[:10000]  # 10k character limit
    
    # Remove excessive whitespace
    sanitized = ' '.join(sanitized.split())
    
    return sanitized.strip()


def create_message(role: MessageRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
    """
    Create a standardized message object.
    
    Args:
        role: Message role
        content: Message content
        metadata: Optional metadata
        
    Returns:
        Message object
    """
    return Message(
        role=role,
        content=content,
        metadata=metadata or {}
    )