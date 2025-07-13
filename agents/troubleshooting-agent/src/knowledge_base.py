"""
AWS Bedrock Knowledge Base integration for Troubleshooting Agent.
"""

import logging
import os
from typing import List, Dict, Any
from langchain_aws import AmazonKnowledgeBasesRetriever
from models import KnowledgeBaseResult

logger = logging.getLogger(__name__)

# Configuration for Bedrock Knowledge Base
FAQ_KNOWLEDGE_BASE_ID = os.getenv("FAQ_KNOWLEDGE_BASE_ID", "FAQ_KB_12345")
TROUBLESHOOTING_KNOWLEDGE_BASE_ID = os.getenv("TROUBLESHOOTING_KNOWLEDGE_BASE_ID", "TROUBLESHOOTING_KB_67890")

# Initialize retrievers
faq_retriever = None
troubleshooting_retriever = None


def _initialize_retrievers():
    """Initialize Bedrock Knowledge Base retrievers."""
    global faq_retriever, troubleshooting_retriever
    
    try:
        # Initialize FAQ retriever
        faq_retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=FAQ_KNOWLEDGE_BASE_ID,
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 10
                }
            }
        )
        
        # Initialize Troubleshooting retriever
        troubleshooting_retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=TROUBLESHOOTING_KNOWLEDGE_BASE_ID,
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 10
                }
            }
        )
        
        logger.info("Bedrock Knowledge Base retrievers initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock Knowledge Base retrievers: {e}")
        # Fallback to None - tools will handle gracefully
        faq_retriever = None
        troubleshooting_retriever = None


async def search_faq_knowledge_base(query: str, limit: int = 5) -> List[KnowledgeBaseResult]:
    """
    Search FAQ knowledge base using Bedrock Knowledge Base retriever.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[KnowledgeBaseResult]: Relevant FAQ results
    """
    global faq_retriever
    
    if faq_retriever is None:
        _initialize_retrievers()
    
    if faq_retriever is None:
        logger.warning("FAQ Knowledge Base retriever not available")
        return []
    
    try:
        # Query the Bedrock Knowledge Base
        documents = faq_retriever.get_relevant_documents(query=query)
        
        results = []
        for i, doc in enumerate(documents[:limit]):
            # Extract metadata if available
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            result = KnowledgeBaseResult(
                title=metadata.get('title', f"FAQ Result {i+1}"),
                content=doc.page_content,
                relevance_score=metadata.get('score', 0.5),
                source="FAQ Knowledge Base",
                product_name=metadata.get('product_name'),
                category=metadata.get('category')
            )
            results.append(result)
        
        logger.info(f"Found {len(results)} FAQ results from Bedrock Knowledge Base for query: {query}")
        return results
        
    except Exception as e:
        logger.error(f"Error searching FAQ Knowledge Base: {e}")
        return []


async def search_troubleshooting_knowledge_base(query: str, limit: int = 5) -> List[KnowledgeBaseResult]:
    """
    Search troubleshooting knowledge base using Bedrock Knowledge Base retriever.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[KnowledgeBaseResult]: Relevant troubleshooting results
    """
    global troubleshooting_retriever
    
    if troubleshooting_retriever is None:
        _initialize_retrievers()
    
    if troubleshooting_retriever is None:
        logger.warning("Troubleshooting Knowledge Base retriever not available")
        return []
    
    try:
        # Query the Bedrock Knowledge Base
        documents = troubleshooting_retriever.get_relevant_documents(query=query)
        
        results = []
        for i, doc in enumerate(documents[:limit]):
            # Extract metadata if available
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            
            result = KnowledgeBaseResult(
                title=metadata.get('title', f"Troubleshooting Result {i+1}"),
                content=doc.page_content,
                relevance_score=metadata.get('score', 0.5),
                source="Troubleshooting Knowledge Base",
                product_name=metadata.get('product_name'),
                category=metadata.get('category')
            )
            results.append(result)
        
        logger.info(f"Found {len(results)} troubleshooting results from Bedrock Knowledge Base for query: {query}")
        return results
        
    except Exception as e:
        logger.error(f"Error searching Troubleshooting Knowledge Base: {e}")
        return []


async def search_combined_knowledge_base(query: str, limit: int = 10) -> List[KnowledgeBaseResult]:
    """
    Search both FAQ and troubleshooting knowledge bases and combine results.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of total results to return
        
    Returns:
        List[KnowledgeBaseResult]: Combined search results
    """
    try:
        # Search both knowledge bases
        faq_results = await search_faq_knowledge_base(query, limit // 2)
        troubleshooting_results = await search_troubleshooting_knowledge_base(query, limit // 2)
        
        # Combine and sort by relevance score
        all_results = faq_results + troubleshooting_results
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Return top results up to limit
        return all_results[:limit]
        
    except Exception as e:
        logger.error(f"Error searching combined knowledge base: {e}")
        return []


# Fallback data for development/testing when Bedrock KB is not available
FALLBACK_FAQ_DATA = [
    {
        "title": "General Warranty Information",
        "content": "Most products come with a one-year limited warranty covering manufacturing defects. Check your purchase receipt for warranty details.",
        "source": "FAQ (Fallback)",
        "category": "general"
    },
    {
        "title": "Bluetooth Connection Issues",
        "content": "For Bluetooth connection problems: 1) Turn off Bluetooth and restart both devices 2) Clear Bluetooth cache 3) Re-pair the devices",
        "source": "FAQ (Fallback)",
        "category": "connectivity"
    }
]

FALLBACK_TROUBLESHOOTING_DATA = [
    {
        "title": "General Troubleshooting Steps",
        "content": "Basic troubleshooting: 1) Restart the device 2) Check power/battery 3) Update firmware if available 4) Reset to factory settings if needed",
        "source": "Troubleshooting (Fallback)",
        "category": "general"
    }
]


async def get_fallback_results(query: str, limit: int = 5) -> List[KnowledgeBaseResult]:
    """
    Provide fallback results when Bedrock Knowledge Base is not available.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[KnowledgeBaseResult]: Fallback results
    """
    query_lower = query.lower()
    results = []
    
    # Search fallback FAQ data
    for faq in FALLBACK_FAQ_DATA:
        if any(word in faq["content"].lower() for word in query_lower.split()):
            results.append(KnowledgeBaseResult(
                title=faq["title"],
                content=faq["content"],
                relevance_score=0.7,
                source=faq["source"],
                product_name=None,
                category=faq["category"]
            ))
    
    # Search fallback troubleshooting data
    for guide in FALLBACK_TROUBLESHOOTING_DATA:
        if any(word in guide["content"].lower() for word in query_lower.split()):
            results.append(KnowledgeBaseResult(
                title=guide["title"],
                content=guide["content"],
                relevance_score=0.7,
                source=guide["source"],
                product_name=None,
                category=guide["category"]
            ))
    
    logger.info(f"Provided {len(results)} fallback results for query: {query}")
    return results[:limit]