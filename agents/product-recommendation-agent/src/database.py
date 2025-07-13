"""
SQLite database setup and initialization for Product Recommendation Agent.
"""

import aiosqlite
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_PATH = Path(__file__).parent / "product_recommendation.db"


async def initialize_database():
    """Initialize the product recommendation database with tables and test data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create product_catalog table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS product_catalog (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                rating REAL DEFAULT 0.0,
                popularity TEXT DEFAULT 'medium'
            )
        """)
        
        # Create purchase_history table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                purchase_date TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                purchase_amount REAL NOT NULL,
                payment_method TEXT DEFAULT 'credit_card'
            )
        """)
        
        await db.commit()
        
        # Check if data already exists
        cursor = await db.execute("SELECT COUNT(*) FROM product_catalog")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            await populate_test_data(db)
            logger.info("Database initialized with test data")
        else:
            logger.info("Database already contains data")


async def populate_test_data(db):
    """Populate database with realistic test data."""
    
    # Product catalog data
    products = [
        # Headphones
        ("prod001", "zensound wireless headphones", "headphones", 199.99, "Premium wireless headphones with noise cancellation", 4.5, "high"),
        ("prod002", "bassmax studio headphones", "headphones", 299.99, "Professional studio-grade headphones", 4.7, "medium"),
        ("prod003", "comfortfit daily headphones", "headphones", 79.99, "Lightweight headphones for daily use", 4.2, "high"),
        ("prod004", "sportbeat wireless earbuds", "headphones", 129.99, "Waterproof wireless earbuds for sports", 4.3, "high"),
        
        # Watches
        ("prod005", "vitafit smartwatch", "watch", 249.99, "Advanced fitness tracking smartwatch", 4.4, "high"),
        ("prod006", "timemaster classic watch", "watch", 399.99, "Elegant mechanical watch with leather band", 4.6, "medium"),
        ("prod007", "sportpro fitness tracker", "watch", 149.99, "Comprehensive fitness tracking device", 4.1, "medium"),
        
        # Speakers
        ("prod008", "thundersound bluetooth speaker", "speaker", 89.99, "Portable bluetooth speaker with rich bass", 4.3, "high"),
        ("prod009", "homemax surround speaker", "speaker", 599.99, "High-end home theater speaker system", 4.8, "low"),
        ("prod010", "travelmate portable speaker", "speaker", 39.99, "Compact speaker for travel", 3.9, "medium"),
        
        # Computers
        ("prod011", "promax laptop", "computer", 1299.99, "High-performance laptop for professionals", 4.5, "medium"),
        ("prod012", "studentbook budget laptop", "computer", 499.99, "Affordable laptop for students", 4.0, "high"),
        ("prod013", "gamingbeast desktop", "computer", 1899.99, "Powerful gaming desktop computer", 4.7, "low"),
        
        # Phones
        ("prod014", "smartconnect phone", "phone", 799.99, "Latest smartphone with advanced camera", 4.4, "high"),
        ("prod015", "basicphone essential", "phone", 199.99, "Simple smartphone with essential features", 4.1, "medium"),
        ("prod016", "camerapro phone", "phone", 1099.99, "Photography-focused premium smartphone", 4.6, "medium")
    ]
    
    for product in products:
        await db.execute("""
            INSERT INTO product_catalog 
            (product_id, product_name, category, price, description, rating, popularity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, product)
    
    # Purchase history data
    purchases = [
        # Customer cust001 purchases
        ("cust001", "prod001", "2024-06-15", 1, 199.99, "credit_card"),
        ("cust001", "prod005", "2024-05-20", 1, 249.99, "debit_card"),
        ("cust001", "prod008", "2024-04-10", 1, 89.99, "credit_card"),
        
        # Customer cust002 purchases
        ("cust002", "prod011", "2024-06-01", 1, 1299.99, "credit_card"),
        ("cust002", "prod014", "2024-05-15", 1, 799.99, "credit_card"),
        
        # Customer cust003 purchases
        ("cust003", "prod003", "2024-06-20", 1, 79.99, "debit_card"),
        ("cust003", "prod010", "2024-06-18", 2, 79.98, "cash"),
        ("cust003", "prod015", "2024-05-01", 1, 199.99, "credit_card"),
        
        # Customer cust004 purchases
        ("cust004", "prod013", "2024-06-10", 1, 1899.99, "credit_card"),
        ("cust004", "prod002", "2024-06-05", 1, 299.99, "credit_card"),
        ("cust004", "prod016", "2024-05-25", 1, 1099.99, "credit_card"),
        
        # Customer cust005 purchases
        ("cust005", "prod012", "2024-06-25", 1, 499.99, "debit_card"),
        ("cust005", "prod007", "2024-06-20", 1, 149.99, "credit_card"),
        ("cust005", "prod004", "2024-06-15", 1, 129.99, "debit_card")
    ]
    
    for purchase in purchases:
        await db.execute("""
            INSERT INTO purchase_history 
            (customer_id, product_id, purchase_date, quantity, purchase_amount, payment_method)
            VALUES (?, ?, ?, ?, ?, ?)
        """, purchase)
    
    await db.commit()


def get_database_connection():
    """Get database connection as async context manager."""
    return aiosqlite.connect(DATABASE_PATH)


if __name__ == "__main__":
    asyncio.run(initialize_database())