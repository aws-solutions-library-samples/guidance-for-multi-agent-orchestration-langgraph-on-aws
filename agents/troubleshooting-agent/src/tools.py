"""
Tools for Troubleshooting Agent using AWS Bedrock Knowledge Base.
"""

import logging
from typing import List, Dict, Any
from knowledge_base import (
    search_faq_knowledge_base,
    search_troubleshooting_knowledge_base,
    search_combined_knowledge_base,
    get_fallback_results
)

logger = logging.getLogger(__name__)


async def search_faq_for_product_info(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search FAQ knowledge base for product information and warranty details using Bedrock.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: FAQ search results
    """
    try:
        results = await search_faq_knowledge_base(query, limit)
        
        # If no results from Bedrock KB, try fallback
        if not results:
            fallback_results = await get_fallback_results(query, limit)
            results = fallback_results
        
        faq_results = []
        for result in results:
            faq_results.append({
                "title": result.title,
                "content": result.content,
                "relevance_score": result.relevance_score,
                "source": result.source,
                "product_name": result.product_name,
                "category": result.category
            })
        
        logger.info(f"Found {len(faq_results)} FAQ results for query: {query}")
        return faq_results
        
    except Exception as e:
        logger.error(f"Error searching FAQ knowledge base: {e}")
        return []


async def search_troubleshooting_guides(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search troubleshooting guides for issue resolution steps using Bedrock Knowledge Base.
    
    Args:
        query (str): Search query describing the issue
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: Troubleshooting guide results
    """
    try:
        results = await search_troubleshooting_knowledge_base(query, limit)
        
        # If no results from Bedrock KB, try fallback
        if not results:
            fallback_results = await get_fallback_results(query, limit)
            results = fallback_results
        
        guide_results = []
        for result in results:
            guide_results.append({
                "title": result.title,
                "content": result.content,
                "relevance_score": result.relevance_score,
                "source": result.source,
                "product_name": result.product_name,
                "category": result.category
            })
        
        logger.info(f"Found {len(guide_results)} troubleshooting guide results for query: {query}")
        return guide_results
        
    except Exception as e:
        logger.error(f"Error searching troubleshooting guides: {e}")
        return []


async def search_product_specific_help(product_name: str, category: str = None) -> List[Dict[str, Any]]:
    """
    Search for product-specific help information using Bedrock Knowledge Base.
    
    Args:
        product_name (str): Name of the product
        category (str, optional): Product category for filtering
        
    Returns:
        List[Dict[str, Any]]: Product-specific help results
    """
    try:
        # Build search query
        query = product_name
        if category:
            query += f" {category}"
        
        # Search both FAQ and troubleshooting knowledge bases
        results = await search_combined_knowledge_base(query, limit=10)
        
        # If no results from Bedrock KB, try fallback
        if not results:
            fallback_results = await get_fallback_results(query, 5)
            results = fallback_results
        
        help_results = []
        for result in results:
            # Prioritize exact product matches
            relevance_boost = 0.0
            if (result.product_name and 
                product_name.lower() in result.product_name.lower()):
                relevance_boost = 0.2
            elif result.category and category and category.lower() == result.category.lower():
                relevance_boost = 0.1
            
            help_results.append({
                "title": result.title,
                "content": result.content,
                "relevance_score": min(result.relevance_score + relevance_boost, 1.0),
                "source": result.source,
                "product_name": result.product_name,
                "category": result.category
            })
        
        # Sort by relevance score
        help_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        logger.info(f"Found {len(help_results)} product-specific help results for {product_name}")
        return help_results[:10]  # Limit to top 10 results
        
    except Exception as e:
        logger.error(f"Error searching product-specific help: {e}")
        return []


async def search_category_issues(category: str, issue_keywords: List[str] = None) -> List[Dict[str, Any]]:
    """
    Search for common issues within a product category using Bedrock Knowledge Base.
    
    Args:
        category (str): Product category (headphones, watch, speaker, computer, phone)
        issue_keywords (List[str], optional): Specific issue keywords to search for
        
    Returns:
        List[Dict[str, Any]]: Category-specific issue results
    """
    try:
        # Build search query
        query = category
        if issue_keywords:
            query += " " + " ".join(issue_keywords)
        
        # Search troubleshooting knowledge base for category-specific issues
        results = await search_troubleshooting_knowledge_base(query, limit=8)
        
        # If no results from Bedrock KB, try fallback
        if not results:
            fallback_results = await get_fallback_results(query, 5)
            results = fallback_results
        
        category_results = []
        for result in results:
            # Boost relevance for exact category matches
            relevance_boost = 0.0
            if result.category and category.lower() == result.category.lower():
                relevance_boost = 0.2
            
            category_results.append({
                "title": result.title,
                "content": result.content,
                "relevance_score": min(result.relevance_score + relevance_boost, 1.0),
                "source": result.source,
                "product_name": result.product_name,
                "category": result.category
            })
        
        # Sort by relevance score
        category_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        logger.info(f"Found {len(category_results)} category-specific results for {category}")
        return category_results
        
    except Exception as e:
        logger.error(f"Error searching category issues: {e}")
        return []


async def get_warranty_information(product_name: str = None, category: str = None) -> List[Dict[str, Any]]:
    """
    Get warranty information for products using Bedrock Knowledge Base.
    
    Args:
        product_name (str, optional): Specific product name
        category (str, optional): Product category
        
    Returns:
        List[Dict[str, Any]]: Warranty information results
    """
    try:
        # Search for warranty-related information
        query = "warranty"
        if product_name:
            query += f" {product_name}"
        elif category:
            query += f" {category}"
        
        # Search FAQ knowledge base for warranty information
        results = await search_faq_knowledge_base(query, limit=5)
        
        # If no results from Bedrock KB, try fallback
        if not results:
            fallback_results = await get_fallback_results(query, 3)
            results = fallback_results
        
        warranty_results = []
        for result in results:
            # Filter for warranty-related content
            if "warranty" in result.content.lower():
                warranty_results.append({
                    "title": result.title,
                    "content": result.content,
                    "relevance_score": result.relevance_score,
                    "source": result.source,
                    "product_name": result.product_name,
                    "category": result.category
                })
        
        logger.info(f"Found {len(warranty_results)} warranty information results")
        return warranty_results
        
    except Exception as e:
        logger.error(f"Error getting warranty information: {e}")
        return []


async def search_comprehensive_help(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Perform comprehensive search across all knowledge bases using Bedrock.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict[str, Any]]: Comprehensive search results
    """
    try:
        # Search combined knowledge base
        results = await search_combined_knowledge_base(query, limit)
        
        # If no results from Bedrock KB, try fallback
        if not results:
            fallback_results = await get_fallback_results(query, limit)
            results = fallback_results
        
        comprehensive_results = []
        for result in results:
            comprehensive_results.append({
                "title": result.title,
                "content": result.content,
                "relevance_score": result.relevance_score,
                "source": result.source,
                "product_name": result.product_name,
                "category": result.category
            })
        
        logger.info(f"Found {len(comprehensive_results)} comprehensive help results for query: {query}")
        return comprehensive_results
        
    except Exception as e:
        logger.error(f"Error performing comprehensive search: {e}")
        return []