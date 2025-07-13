"""
AWS Bedrock Knowledge Base integration for Personalization Agent browsing history.
"""

import logging
import os
from typing import List, Dict, Any
from langchain_aws import AmazonKnowledgeBasesRetriever

logger = logging.getLogger(__name__)

# Configuration for Bedrock Knowledge Base
BROWSING_HISTORY_KNOWLEDGE_BASE_ID = os.getenv("BROWSING_HISTORY_KNOWLEDGE_BASE_ID", "BROWSING_KB_12345")

# Initialize retriever
browsing_history_retriever = None


def _initialize_retriever():
    """Initialize Bedrock Knowledge Base retriever for browsing history."""
    global browsing_history_retriever
    
    try:
        # Initialize browsing history retriever
        browsing_history_retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=BROWSING_HISTORY_KNOWLEDGE_BASE_ID,
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 10
                }
            }
        )
        
        logger.info("Bedrock Knowledge Base retriever for browsing history initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock Knowledge Base retriever: {e}")
        # Fallback to None - tools will handle gracefully
        browsing_history_retriever = None


async def search_browsing_history(customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search browsing history for a specific customer using Bedrock Knowledge Base.
    
    Args:
        customer_id (str): Customer ID to search for
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: Browsing history results
    """
    global browsing_history_retriever
    
    if browsing_history_retriever is None:
        _initialize_retriever()
    
    if browsing_history_retriever is None:
        logger.warning("Browsing history Knowledge Base retriever not available, using fallback")
        return await get_fallback_browsing_history(customer_id, limit)
    
    try:
        # Query the Bedrock Knowledge Base for customer browsing history
        query = f"customer {customer_id} browsing history behavior"
        documents = browsing_history_retriever.get_relevant_documents(query=query)
        
        results = []
        for i, doc in enumerate(documents[:limit]):
            # Extract metadata if available
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            result = {
                "session_id": metadata.get('session_id', f"session_{i+1}"),
                "content": doc.page_content,
                "timestamp": metadata.get('timestamp', '2024-07-06'),
                "relevance_score": metadata.get('score', 0.5),
                "source": "Browsing History Knowledge Base",
                "customer_id": metadata.get('customer_id', customer_id)
            }
            results.append(result)
        
        logger.info(f"Found {len(results)} browsing history results from Bedrock Knowledge Base for customer: {customer_id}")
        return results
        
    except Exception as e:
        logger.error(f"Error searching browsing history Knowledge Base: {e}")
        return await get_fallback_browsing_history(customer_id, limit)


async def search_customer_behavior_patterns(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for customer behavior patterns using Bedrock Knowledge Base.
    
    Args:
        query (str): Search query for behavior patterns
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: Behavior pattern results
    """
    global browsing_history_retriever
    
    if browsing_history_retriever is None:
        _initialize_retriever()
    
    if browsing_history_retriever is None:
        logger.warning("Browsing history Knowledge Base retriever not available, using fallback")
        return await get_fallback_behavior_patterns(query, limit)
    
    try:
        # Query the Bedrock Knowledge Base for behavior patterns
        documents = browsing_history_retriever.get_relevant_documents(query=query)
        
        results = []
        for i, doc in enumerate(documents[:limit]):
            # Extract metadata if available
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            result = {
                "pattern_type": metadata.get('pattern_type', 'general_behavior'),
                "content": doc.page_content,
                "relevance_score": metadata.get('score', 0.5),
                "source": "Browsing History Knowledge Base",
                "customer_segment": metadata.get('customer_segment', 'general')
            }
            results.append(result)
        
        logger.info(f"Found {len(results)} behavior pattern results from Bedrock Knowledge Base for query: {query}")
        return results
        
    except Exception as e:
        logger.error(f"Error searching behavior patterns Knowledge Base: {e}")
        return await get_fallback_behavior_patterns(query, limit)


# Fallback data for development/testing when Bedrock KB is not available
FALLBACK_BROWSING_DATA = {
    "cust001": [
        {
            "session_id": "sess_001_1",
            "content": "Customer ID: CUST001 - Date: 2024-07-01, Session Start: 14:30 - Product Browsed: ProMax Laptop (prod011) - Category: Computers - Time Spent: 25 minutes - Actions: Compared RAM and storage options; downloaded PDF spec sheet - Total Clicks: 12 - Likes on Product Ads: Yes",
            "timestamp": "2024-07-01T14:30:00",
            "relevance_score": 0.9,
            "source": "Browsing History (Fallback)",
            "customer_id": "cust001"
        },
        {
            "session_id": "sess_001_2", 
            "content": "Customer ID: CUST001 - Date: 2024-06-28, Session Start: 19:15 - Product Browsed: ZenSound Wireless Headphones (prod001) - Category: Headphones - Time Spent: 15 minutes - Actions: Read reviews, compared with competitors - Total Clicks: 8 - Added to wishlist: Yes",
            "timestamp": "2024-06-28T19:15:00",
            "relevance_score": 0.8,
            "source": "Browsing History (Fallback)",
            "customer_id": "cust001"
        }
    ],
    "cust002": [
        {
            "session_id": "sess_002_1",
            "content": "Customer ID: CUST002 - Date: 2024-07-02, Session Start: 08:00 - Product Browsed: VitaFit Smartwatch (prod005) - Category: Watch - Time Spent: 30 minutes - Actions: Compared fitness features, read health tracking reviews - Total Clicks: 15 - Fitness app integration checked: Yes",
            "timestamp": "2024-07-02T08:00:00",
            "relevance_score": 0.9,
            "source": "Browsing History (Fallback)",
            "customer_id": "cust002"
        }
    ],
    "cust003": [
        {
            "session_id": "sess_003_1",
            "content": "Customer ID: CUST003 - Date: 2024-07-03, Session Start: 20:45 - Product Browsed: ComfortFit Daily Headphones (prod003) - Category: Headphones - Time Spent: 12 minutes - Actions: Price comparison, checked for discounts - Total Clicks: 6 - Budget filter applied: Under $100",
            "timestamp": "2024-07-03T20:45:00",
            "relevance_score": 0.8,
            "source": "Browsing History (Fallback)",
            "customer_id": "cust003"
        }
    ]
}

FALLBACK_BEHAVIOR_PATTERNS = [
    {
        "pattern_type": "tech_enthusiast",
        "content": "Tech enthusiasts typically spend 20-30 minutes per session, focus on specifications and technical details, frequently compare products, and engage with technical reviews and documentation.",
        "relevance_score": 0.8,
        "source": "Behavior Patterns (Fallback)",
        "customer_segment": "technology"
    },
    {
        "pattern_type": "fitness_focused",
        "content": "Fitness-focused customers prioritize health tracking features, spend significant time reading about accuracy and integration with fitness apps, and often research compatibility with existing workout routines.",
        "relevance_score": 0.8,
        "source": "Behavior Patterns (Fallback)", 
        "customer_segment": "fitness"
    },
    {
        "pattern_type": "budget_conscious",
        "content": "Budget-conscious customers focus on price comparisons, actively search for discounts and deals, have shorter browsing sessions, and prioritize value over premium features.",
        "relevance_score": 0.8,
        "source": "Behavior Patterns (Fallback)",
        "customer_segment": "budget"
    }
]


async def get_fallback_browsing_history(customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Provide fallback browsing history when Bedrock Knowledge Base is not available.
    
    Args:
        customer_id (str): Customer ID
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: Fallback browsing history
    """
    customer_data = FALLBACK_BROWSING_DATA.get(customer_id, [])
    
    if not customer_data:
        # Generic fallback for unknown customers
        customer_data = [{
            "session_id": f"sess_{customer_id}_generic",
            "content": f"Customer ID: {customer_id.upper()} - Limited browsing history available. Customer has shown interest in technology products and values quality and features.",
            "timestamp": "2024-07-06T12:00:00",
            "relevance_score": 0.5,
            "source": "Browsing History (Fallback)",
            "customer_id": customer_id
        }]
    
    logger.info(f"Provided {len(customer_data[:limit])} fallback browsing history results for customer: {customer_id}")
    return customer_data[:limit]


async def get_fallback_behavior_patterns(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Provide fallback behavior patterns when Bedrock Knowledge Base is not available.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: Fallback behavior patterns
    """
    query_lower = query.lower()
    relevant_patterns = []
    
    for pattern in FALLBACK_BEHAVIOR_PATTERNS:
        if any(word in pattern["content"].lower() for word in query_lower.split()):
            relevant_patterns.append(pattern)
    
    # If no specific matches, return general patterns
    if not relevant_patterns:
        relevant_patterns = FALLBACK_BEHAVIOR_PATTERNS
    
    logger.info(f"Provided {len(relevant_patterns[:limit])} fallback behavior pattern results for query: {query}")
    return relevant_patterns[:limit]