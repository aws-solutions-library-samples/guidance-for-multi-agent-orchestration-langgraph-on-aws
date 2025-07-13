"""
SQLite database setup and initialization for Personalization Agent.
"""

import aiosqlite
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_PATH = Path(__file__).parent / "personalization.db"


async def initialize_database():
    """Initialize the personalization database with tables and test data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create personalization table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS personalization (
                customer_id TEXT PRIMARY KEY,
                age INTEGER,
                gender TEXT,
                income TEXT,
                location TEXT,
                marital_status TEXT,
                preferred_category TEXT,
                price_range TEXT,
                preferred_brand TEXT,
                loyalty_tier TEXT
            )
        """)
        
        await db.commit()
        
        # Check if data already exists
        cursor = await db.execute("SELECT COUNT(*) FROM personalization")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            await populate_test_data(db)
            logger.info("Database initialized with test data")
        else:
            logger.info("Database already contains data")


async def populate_test_data(db):
    """Populate database with realistic test data."""
    
    # Customer personalization data
    customers = [
        # Tech enthusiast customer
        ("cust001", 28, "male", "70000-90000", "san francisco", "single", "computer", "high", "apple", "gold"),
        
        # Fitness enthusiast customer
        ("cust002", 32, "female", "50000-70000", "new york", "married", "watch", "medium", "fitbit", "silver"),
        
        # Budget-conscious customer
        ("cust003", 24, "male", "30000-50000", "austin", "single", "headphones", "low", "generic", "bronze"),
        
        # Premium customer
        ("cust004", 45, "male", "100000+", "seattle", "married", "computer", "high", "microsoft", "platinum"),
        
        # Student customer
        ("cust005", 20, "female", "20000-30000", "boston", "single", "phone", "low", "samsung", "bronze"),
        
        # Family-oriented customer
        ("cust006", 38, "female", "70000-90000", "chicago", "married", "speaker", "medium", "sonos", "gold"),
        
        # Music lover
        ("cust007", 26, "male", "50000-70000", "los angeles", "single", "headphones", "medium", "sony", "silver"),
        
        # Professional customer
        ("cust008", 35, "female", "90000-100000", "denver", "married", "computer", "high", "dell", "gold"),
        
        # Casual user
        ("cust009", 29, "male", "40000-60000", "miami", "single", "speaker", "medium", "jbl", "silver"),
        
        # Health-conscious customer
        ("cust010", 41, "female", "80000-100000", "portland", "married", "watch", "high", "garmin", "platinum")
    ]
    
    for customer in customers:
        await db.execute("""
            INSERT INTO personalization 
            (customer_id, age, gender, income, location, marital_status, 
             preferred_category, price_range, preferred_brand, loyalty_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, customer)
    
    await db.commit()


def get_database_connection():
    """Get database connection as async context manager."""
    return aiosqlite.connect(DATABASE_PATH)


if __name__ == "__main__":
    asyncio.run(initialize_database())