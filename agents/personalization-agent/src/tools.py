"""
Tools for Personalization Agent using SQLite database and AWS Bedrock Knowledge Base.
"""

import logging
from typing import List, Dict, Any, Optional
from database import get_database_connection
from knowledge_base import search_browsing_history, search_customer_behavior_patterns

logger = logging.getLogger(__name__)


async def get_customer_profile(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get customer profile information from the database.
    
    Args:
        customer_id (str): Customer identifier
        
    Returns:
        List[Dict[str, Any]]: Customer profile data
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT customer_id, age, gender, income, location, marital_status,
                       preferred_category, price_range, preferred_brand, loyalty_tier
                FROM personalization 
                WHERE LOWER(customer_id) = LOWER(?)
            """, (customer_id.lower(),))
            
            result = await cursor.fetchone()
            
            if result:
                profile = {
                    "customer_id": result[0],
                    "age": result[1],
                    "gender": result[2],
                    "income": result[3],
                    "location": result[4],
                    "marital_status": result[5],
                    "preferred_category": result[6],
                    "price_range": result[7],
                    "preferred_brand": result[8],
                    "loyalty_tier": result[9]
                }
                
                logger.info(f"Found customer profile for {customer_id}")
                return [profile]
            else:
                logger.info(f"No customer profile found for {customer_id}")
                return []
            
    except Exception as e:
        logger.error(f"Error getting customer profile: {e}")
        return []


async def get_customer_preferences(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get customer preferences and demographic information.
    
    Args:
        customer_id (str): Customer identifier
        
    Returns:
        List[Dict[str, Any]]: Customer preferences data
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT customer_id, preferred_category, price_range, preferred_brand, 
                       loyalty_tier, age, income, location
                FROM personalization 
                WHERE LOWER(customer_id) = LOWER(?)
            """, (customer_id.lower(),))
            
            result = await cursor.fetchone()
            
            if result:
                preferences = {
                    "customer_id": result[0],
                    "preferred_category": result[1],
                    "price_range": result[2],
                    "preferred_brand": result[3],
                    "loyalty_tier": result[4],
                    "age": result[5],
                    "income": result[6],
                    "location": result[7],
                    "preferences_found": True
                }
                
                logger.info(f"Found customer preferences for {customer_id}")
                return [preferences]
            else:
                logger.info(f"No customer preferences found for {customer_id}")
                return []
            
    except Exception as e:
        logger.error(f"Error getting customer preferences: {e}")
        return []


async def analyze_customer_demographics(customer_id: str) -> List[Dict[str, Any]]:
    """
    Analyze customer demographics for personalization insights.
    
    Args:
        customer_id (str): Customer identifier
        
    Returns:
        List[Dict[str, Any]]: Demographic analysis results
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT customer_id, age, gender, income, location, marital_status, loyalty_tier
                FROM personalization 
                WHERE LOWER(customer_id) = LOWER(?)
            """, (customer_id.lower(),))
            
            result = await cursor.fetchone()
            
            if result:
                # Analyze demographics for insights
                age = result[1]
                gender = result[2]
                income = result[3]
                location = result[4]
                marital_status = result[5]
                loyalty_tier = result[6]
                
                # Generate demographic insights
                insights = []
                
                if age:
                    if age < 25:
                        insights.append("Young adult demographic - likely values affordability and trendy features")
                    elif age < 35:
                        insights.append("Young professional - likely values performance and productivity features")
                    elif age < 50:
                        insights.append("Established professional - likely values quality and premium features")
                    else:
                        insights.append("Mature customer - likely values reliability and ease of use")
                
                if income:
                    if "20000-30000" in income:
                        insights.append("Budget-conscious segment - price-sensitive purchasing decisions")
                    elif "100000+" in income:
                        insights.append("High-income segment - likely to purchase premium products")
                    else:
                        insights.append("Middle-income segment - values balance of features and price")
                
                if loyalty_tier:
                    if loyalty_tier == "platinum":
                        insights.append("VIP customer - deserves premium service and exclusive offers")
                    elif loyalty_tier == "gold":
                        insights.append("Valued customer - good candidate for loyalty rewards")
                
                demographics = {
                    "customer_id": result[0],
                    "age": age,
                    "gender": gender,
                    "income": income,
                    "location": location,
                    "marital_status": marital_status,
                    "loyalty_tier": loyalty_tier,
                    "demographic_insights": insights
                }
                
                logger.info(f"Analyzed demographics for customer {customer_id}")
                return [demographics]
            else:
                logger.info(f"No demographic data found for {customer_id}")
                return []
            
    except Exception as e:
        logger.error(f"Error analyzing customer demographics: {e}")
        return []


async def get_customer_browsing_behavior(customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get customer browsing behavior from Bedrock Knowledge Base.
    
    Args:
        customer_id (str): Customer identifier
        limit (int): Maximum number of browsing records to return
        
    Returns:
        List[Dict[str, Any]]: Browsing behavior data
    """
    try:
        # Search browsing history using Bedrock Knowledge Base
        browsing_data = await search_browsing_history(customer_id, limit)
        
        logger.info(f"Retrieved {len(browsing_data)} browsing behavior records for customer {customer_id}")
        return browsing_data
        
    except Exception as e:
        logger.error(f"Error getting customer browsing behavior: {e}")
        return []


async def analyze_browsing_patterns(customer_id: str, behavior_type: str = "general") -> List[Dict[str, Any]]:
    """
    Analyze browsing patterns for personalization insights using Bedrock Knowledge Base.
    
    Args:
        customer_id (str): Customer identifier
        behavior_type (str): Type of behavior analysis to perform
        
    Returns:
        List[Dict[str, Any]]: Browsing pattern analysis results
    """
    try:
        # Build query for behavior pattern analysis
        query = f"customer {customer_id} {behavior_type} browsing behavior patterns preferences"
        
        # Search for behavior patterns using Bedrock Knowledge Base
        pattern_data = await search_customer_behavior_patterns(query, limit=5)
        
        # Get specific customer browsing history
        browsing_history = await search_browsing_history(customer_id, limit=5)
        
        # Combine pattern analysis with customer-specific data
        combined_results = []
        
        # Add pattern insights
        for pattern in pattern_data:
            combined_results.append({
                "analysis_type": "behavior_pattern",
                "customer_id": customer_id,
                "pattern_type": pattern.get("pattern_type", "general"),
                "insights": pattern.get("content", ""),
                "relevance_score": pattern.get("relevance_score", 0.5),
                "source": pattern.get("source", "Pattern Analysis")
            })
        
        # Add customer-specific browsing insights
        if browsing_history:
            combined_results.append({
                "analysis_type": "customer_specific",
                "customer_id": customer_id,
                "pattern_type": "individual_behavior",
                "insights": f"Customer has {len(browsing_history)} recent browsing sessions with detailed interaction data",
                "relevance_score": 0.9,
                "source": "Customer Browsing History",
                "session_count": len(browsing_history)
            })
        
        logger.info(f"Analyzed browsing patterns for customer {customer_id}: {len(combined_results)} insights")
        return combined_results
        
    except Exception as e:
        logger.error(f"Error analyzing browsing patterns: {e}")
        return []


async def get_similar_customer_insights(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get insights from similar customers for personalization recommendations.
    
    Args:
        customer_id (str): Customer identifier
        
    Returns:
        List[Dict[str, Any]]: Similar customer insights
    """
    try:
        # First get the target customer's profile
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT preferred_category, price_range, age, income, loyalty_tier
                FROM personalization 
                WHERE LOWER(customer_id) = LOWER(?)
            """, (customer_id.lower(),))
            
            target_customer = await cursor.fetchone()
            
            if not target_customer:
                return []
            
            preferred_category, price_range, age, income, loyalty_tier = target_customer
            
            # Find similar customers based on preferences and demographics
            cursor = await db.execute("""
                SELECT customer_id, preferred_category, price_range, preferred_brand, loyalty_tier
                FROM personalization 
                WHERE (LOWER(preferred_category) = LOWER(?) 
                       OR LOWER(price_range) = LOWER(?)
                       OR LOWER(loyalty_tier) = LOWER(?))
                AND LOWER(customer_id) != LOWER(?)
                LIMIT 5
            """, (preferred_category, price_range, loyalty_tier, customer_id.lower()))
            
            similar_customers = await cursor.fetchall()
            
            insights = []
            for similar in similar_customers:
                similarity_factors = []
                
                if similar[1].lower() == preferred_category.lower():
                    similarity_factors.append(f"shared preference for {preferred_category}")
                if similar[2].lower() == price_range.lower():
                    similarity_factors.append(f"similar price range ({price_range})")
                if similar[4].lower() == loyalty_tier.lower():
                    similarity_factors.append(f"same loyalty tier ({loyalty_tier})")
                
                insight = {
                    "similar_customer_id": similar[0],
                    "similarity_factors": similarity_factors,
                    "preferred_category": similar[1],
                    "price_range": similar[2],
                    "preferred_brand": similar[3],
                    "loyalty_tier": similar[4],
                    "insight": f"Similar customer prefers {similar[3]} brand in {similar[1]} category"
                }
                insights.append(insight)
            
            logger.info(f"Found {len(insights)} similar customer insights for {customer_id}")
            return insights
            
    except Exception as e:
        logger.error(f"Error getting similar customer insights: {e}")
        return []


async def search_personalization_opportunities(customer_id: str, context: str = "") -> List[Dict[str, Any]]:
    """
    Search for personalization opportunities using combined data sources.
    
    Args:
        customer_id (str): Customer identifier
        context (str): Additional context for the search
        
    Returns:
        List[Dict[str, Any]]: Personalization opportunities
    """
    try:
        opportunities = []
        
        # Get customer profile for context
        profile_data = await get_customer_profile(customer_id)
        
        if profile_data:
            profile = profile_data[0]
            
            # Generate personalization opportunities based on profile
            if profile.get("preferred_category"):
                opportunities.append({
                    "opportunity_type": "category_focused",
                    "description": f"Recommend new products in {profile['preferred_category']} category",
                    "priority": "high",
                    "basis": "customer preference data"
                })
            
            if profile.get("loyalty_tier") in ["gold", "platinum"]:
                opportunities.append({
                    "opportunity_type": "vip_experience",
                    "description": "Provide premium customer experience and exclusive offers",
                    "priority": "high",
                    "basis": "loyalty tier status"
                })
            
            if profile.get("price_range") == "low":
                opportunities.append({
                    "opportunity_type": "value_focused",
                    "description": "Highlight deals, discounts, and value propositions",
                    "priority": "medium",
                    "basis": "price sensitivity"
                })
        
        # Add browsing-based opportunities
        browsing_query = f"personalization opportunities {customer_id} {context}"
        behavior_patterns = await search_customer_behavior_patterns(browsing_query, limit=3)
        
        for pattern in behavior_patterns:
            opportunities.append({
                "opportunity_type": "behavior_based",
                "description": f"Leverage {pattern.get('pattern_type', 'general')} behavior patterns",
                "priority": "medium",
                "basis": "browsing behavior analysis",
                "details": pattern.get("content", "")
            })
        
        logger.info(f"Found {len(opportunities)} personalization opportunities for customer {customer_id}")
        return opportunities
        
    except Exception as e:
        logger.error(f"Error searching personalization opportunities: {e}")
        return []