"""
Tools for Product Recommendation Agent.
"""

import aiosqlite
import logging
from typing import List, Dict, Any, Optional
from database import get_database_connection

logger = logging.getLogger(__name__)


async def search_products_by_name(product_name: str) -> List[Dict[str, Any]]:
    """
    Search products by name using LIKE operator.
    
    Args:
        product_name (str): Product name to search for
        
    Returns:
        List[Dict[str, Any]]: List of matching products
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT product_id, product_name, category, price, description, rating, popularity
                FROM product_catalog 
                WHERE LOWER(product_name) LIKE LOWER(?)
                ORDER BY rating DESC, popularity DESC
            """, (f"%{product_name.lower()}%",))
            
            results = await cursor.fetchall()
            
            products = []
            for row in results:
                products.append({
                    "product_id": row[0],
                    "product_name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "description": row[4],
                    "rating": row[5],
                    "popularity": row[6]
                })
            
            logger.info(f"Found {len(products)} products matching '{product_name}'")
            return products
            
    except Exception as e:
        logger.error(f"Error searching products by name: {e}")
        return []


async def get_products_by_category(category: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get products by category.
    
    Args:
        category (str): Product category
        limit (int): Maximum number of products to return
        
    Returns:
        List[Dict[str, Any]]: List of products in category
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT product_id, product_name, category, price, description, rating, popularity
                FROM product_catalog 
                WHERE LOWER(category) = LOWER(?)
                ORDER BY rating DESC, popularity DESC
                LIMIT ?
            """, (category.lower(), limit))
            
            results = await cursor.fetchall()
            
            products = []
            for row in results:
                products.append({
                    "product_id": row[0],
                    "product_name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "description": row[4],
                    "rating": row[5],
                    "popularity": row[6]
                })
            
            logger.info(f"Found {len(products)} products in category '{category}'")
            return products
            
    except Exception as e:
        logger.error(f"Error getting products by category: {e}")
        return []


async def get_customer_purchase_history(customer_id: str) -> List[Dict[str, Any]]:
    """
    Get customer's purchase history with product details.
    
    Args:
        customer_id (str): Customer identifier
        
    Returns:
        List[Dict[str, Any]]: Customer's purchase history
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT 
                    ph.customer_id,
                    ph.product_id,
                    pc.product_name,
                    pc.category,
                    ph.purchase_date,
                    ph.quantity,
                    ph.purchase_amount,
                    pc.price,
                    pc.rating
                FROM purchase_history ph
                JOIN product_catalog pc ON ph.product_id = pc.product_id
                WHERE LOWER(ph.customer_id) = LOWER(?)
                ORDER BY ph.purchase_date DESC
            """, (customer_id.lower(),))
            
            results = await cursor.fetchall()
            
            purchases = []
            for row in results:
                purchases.append({
                    "customer_id": row[0],
                    "product_id": row[1],
                    "product_name": row[2],
                    "category": row[3],
                    "purchase_date": row[4],
                    "quantity": row[5],
                    "purchase_amount": row[6],
                    "price": row[7],
                    "rating": row[8]
                })
            
            logger.info(f"Found {len(purchases)} purchases for customer {customer_id}")
            return purchases
            
    except Exception as e:
        logger.error(f"Error getting customer purchase history: {e}")
        return []


async def get_products_by_price_range(min_price: float = 0, max_price: float = 99999) -> List[Dict[str, Any]]:
    """
    Get products within a price range.
    
    Args:
        min_price (float): Minimum price
        max_price (float): Maximum price
        
    Returns:
        List[Dict[str, Any]]: Products within price range
    """
    try:
        async with get_database_connection() as db:
            cursor = await db.execute("""
                SELECT product_id, product_name, category, price, description, rating, popularity
                FROM product_catalog 
                WHERE price >= ? AND price <= ?
                ORDER BY rating DESC, popularity DESC
            """, (min_price, max_price))
            
            results = await cursor.fetchall()
            
            products = []
            for row in results:
                products.append({
                    "product_id": row[0],
                    "product_name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "description": row[4],
                    "rating": row[5],
                    "popularity": row[6]
                })
            
            logger.info(f"Found {len(products)} products in price range ${min_price}-${max_price}")
            return products
            
    except Exception as e:
        logger.error(f"Error getting products by price range: {e}")
        return []


async def get_top_rated_products(category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get top-rated products, optionally filtered by category.
    
    Args:
        category (str, optional): Product category filter
        limit (int): Maximum number of products to return
        
    Returns:
        List[Dict[str, Any]]: Top-rated products
    """
    try:
        async with get_database_connection() as db:
            if category:
                cursor = await db.execute("""
                    SELECT product_id, product_name, category, price, description, rating, popularity
                    FROM product_catalog 
                    WHERE LOWER(category) = LOWER(?)
                    ORDER BY rating DESC, popularity DESC
                    LIMIT ?
                """, (category.lower(), limit))
            else:
                cursor = await db.execute("""
                    SELECT product_id, product_name, category, price, description, rating, popularity
                    FROM product_catalog 
                    ORDER BY rating DESC, popularity DESC
                    LIMIT ?
                """, (limit,))
            
            results = await cursor.fetchall()
            
            products = []
            for row in results:
                products.append({
                    "product_id": row[0],
                    "product_name": row[1],
                    "category": row[2],
                    "price": row[3],
                    "description": row[4],
                    "rating": row[5],
                    "popularity": row[6]
                })
            
            category_filter = f" in category '{category}'" if category else ""
            logger.info(f"Found {len(products)} top-rated products{category_filter}")
            return products
            
    except Exception as e:
        logger.error(f"Error getting top-rated products: {e}")
        return []


async def search_customer_feedback(query: str) -> List[Dict[str, Any]]:
    """
    Simulate search through customer feedback and reviews.
    This would normally connect to a vector database or knowledge base.
    
    Args:
        query (str): Search query
        
    Returns:
        List[Dict[str, Any]]: Simulated feedback results
    """
    # Simulated customer feedback data
    feedback_data = [
        {
            "product_id": "prod001",
            "product_name": "zensound wireless headphones",
            "feedback": "Great noise cancellation, comfortable for long listening sessions. Battery life could be better.",
            "rating": 4.5,
            "customer_type": "frequent_user"
        },
        {
            "product_id": "prod005",
            "product_name": "vitafit smartwatch",
            "feedback": "Excellent fitness tracking features. Heart rate monitor is very accurate. Love the sleep tracking.",
            "rating": 4.4,
            "customer_type": "fitness_enthusiast"
        },
        {
            "product_id": "prod011",
            "product_name": "promax laptop",
            "feedback": "Perfect for work and development. Fast performance, great display. A bit heavy for travel.",
            "rating": 4.5,
            "customer_type": "professional"
        },
        {
            "product_id": "prod014",
            "product_name": "smartconnect phone",
            "feedback": "Amazing camera quality, especially for night photography. Battery lasts all day.",
            "rating": 4.4,
            "customer_type": "photography_lover"
        }
    ]
    
    # Simple keyword matching simulation
    query_lower = query.lower()
    relevant_feedback = []
    
    for feedback in feedback_data:
        if (query_lower in feedback["product_name"].lower() or 
            query_lower in feedback["feedback"].lower() or
            any(word in feedback["feedback"].lower() for word in query_lower.split())):
            relevant_feedback.append(feedback)
    
    logger.info(f"Found {len(relevant_feedback)} relevant feedback items for query '{query}'")
    return relevant_feedback