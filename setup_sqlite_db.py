#!/usr/bin/env python3
"""
Setup SQLite database with test data for order management.
"""

import sqlite3
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_database():
    """Create SQLite database with order management schema and test data."""
    
    db_path = "order_management.db"
    
    # Remove existing database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info("Removed existing database")
    
    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    logger.info("Creating order management database schema...")
    
    # Create orders table
    cursor.execute("""
    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        order_status TEXT NOT NULL,
        shipping_status TEXT,
        return_exchange_status TEXT,
        order_date DATE NOT NULL,
        delivery_date DATE,
        quantity INTEGER DEFAULT 1,
        price_per_unit DECIMAL(10,2),
        total_amount DECIMAL(10,2)
    )
    """)
    
    # Create inventory table
    cursor.execute("""
    CREATE TABLE inventory (
        product_id TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        in_stock TEXT NOT NULL,
        reorder_threshold INTEGER DEFAULT 10,
        reorder_quantity INTEGER DEFAULT 50,
        last_restock_date DATE,
        price_per_unit DECIMAL(10,2)
    )
    """)
    
    # Create customers table
    cursor.execute("""
    CREATE TABLE customers (
        customer_id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        created_date DATE NOT NULL
    )
    """)
    
    logger.info("Inserting test data...")
    
    # Insert customers
    customers_data = [
        ("cust001", "John", "Smith", "john.smith@email.com", "555-0123", "123 Main St", "New York", "NY", "10001", "2024-01-15"),
        ("cust002", "Sarah", "Johnson", "sarah.j@email.com", "555-0456", "456 Oak Ave", "Los Angeles", "CA", "90210", "2024-02-20"),
        ("cust003", "Mike", "Chen", "mike.chen@email.com", "555-0789", "789 Pine Rd", "Chicago", "IL", "60601", "2024-03-10"),
        ("cust004", "Emma", "Davis", "emma.d@email.com", "555-0321", "321 Elm St", "Miami", "FL", "33101", "2024-04-05"),
        ("cust005", "Alex", "Wilson", "alex.w@email.com", "555-0654", "654 Maple Dr", "Seattle", "WA", "98101", "2024-05-12")
    ]
    
    cursor.executemany("""
    INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, customers_data)
    
    # Insert inventory
    inventory_data = [
        ("HD001", "ZenSound Wireless Headphones", "headphones", 25, "yes", 10, 50, "2024-06-15", 149.99),
        ("HD002", "AudioMax Pro Headphones", "headphones", 18, "yes", 8, 40, "2024-06-20", 199.99),
        ("HD003", "BassBoost Gaming Headset", "headphones", 3, "low", 5, 30, "2024-05-25", 89.99),
        ("SW001", "VitaFit Smartwatch", "watch", 15, "yes", 5, 30, "2024-06-20", 299.99),
        ("SW002", "TechTime Pro Watch", "watch", 8, "yes", 3, 20, "2024-06-10", 399.99),
        ("SP001", "FitTrack Wireless Speaker", "speaker", 22, "yes", 8, 35, "2024-06-25", 79.99),
        ("SP002", "SoundWave Bluetooth Speaker", "speaker", 0, "no", 5, 25, "2024-05-15", 129.99),
        ("CH001", "QuickCharge Wireless Charger", "charger", 35, "yes", 15, 60, "2024-06-30", 39.99),
        ("PH001", "TechPhone Pro Max", "phone", 12, "yes", 5, 25, "2024-06-18", 899.99),
        ("TB001", "WorkTab Pro Tablet", "tablet", 7, "yes", 3, 15, "2024-06-12", 549.99)
    ]
    
    cursor.executemany("""
    INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, inventory_data)
    
    # Insert orders with various statuses and dates
    base_date = datetime.now() - timedelta(days=30)
    orders_data = [
        # Customer cust001 orders
        ("ORD-2024-001", "cust001", "HD001", "ZenSound Wireless Headphones", "processing", "preparing", None, 
         (base_date + timedelta(days=1)).strftime("%Y-%m-%d"), 
         (base_date + timedelta(days=5)).strftime("%Y-%m-%d"), 1, 149.99, 149.99),
        ("ORD-2024-002", "cust001", "SW001", "VitaFit Smartwatch", "shipped", "in_transit", None,
         (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=7)).strftime("%Y-%m-%d"), 1, 299.99, 299.99),
        ("ORD-2024-003", "cust001", "CH001", "QuickCharge Wireless Charger", "delivered", "delivered", None,
         (base_date + timedelta(days=10)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=12)).strftime("%Y-%m-%d"), 2, 39.99, 79.98),
         
        # Customer cust002 orders
        ("ORD-2024-004", "cust002", "HD002", "AudioMax Pro Headphones", "delivered", "delivered", "return_requested",
         (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=8)).strftime("%Y-%m-%d"), 1, 199.99, 199.99),
        ("ORD-2024-005", "cust002", "SP001", "FitTrack Wireless Speaker", "shipped", "in_transit", None,
         (base_date + timedelta(days=15)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=18)).strftime("%Y-%m-%d"), 1, 79.99, 79.99),
         
        # Customer cust003 orders
        ("ORD-2024-006", "cust003", "PH001", "TechPhone Pro Max", "processing", "preparing", None,
         (base_date + timedelta(days=12)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=16)).strftime("%Y-%m-%d"), 1, 899.99, 899.99),
        ("ORD-2024-007", "cust003", "TB001", "WorkTab Pro Tablet", "delivered", "delivered", "exchange_completed",
         (base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=11)).strftime("%Y-%m-%d"), 1, 549.99, 549.99),
         
        # Customer cust004 orders
        ("ORD-2024-008", "cust004", "HD003", "BassBoost Gaming Headset", "cancelled", "cancelled", None,
         (base_date + timedelta(days=20)).strftime("%Y-%m-%d"), None, 1, 89.99, 89.99),
        ("ORD-2024-009", "cust004", "SW002", "TechTime Pro Watch", "shipped", "shipped", None,
         (base_date + timedelta(days=22)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=25)).strftime("%Y-%m-%d"), 1, 399.99, 399.99),
         
        # Customer cust005 orders
        ("ORD-2024-010", "cust005", "SP002", "SoundWave Bluetooth Speaker", "processing", "preparing", None,
         (base_date + timedelta(days=25)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=28)).strftime("%Y-%m-%d"), 1, 129.99, 129.99),
        ("ORD-2024-011", "cust005", "HD001", "ZenSound Wireless Headphones", "delivered", "delivered", None,
         (base_date + timedelta(days=18)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=21)).strftime("%Y-%m-%d"), 1, 149.99, 149.99),
        ("ORD-2024-012", "cust005", "CH001", "QuickCharge Wireless Charger", "processing", "preparing", None,
         (base_date + timedelta(days=28)).strftime("%Y-%m-%d"),
         (base_date + timedelta(days=31)).strftime("%Y-%m-%d"), 3, 39.99, 119.97)
    ]
    
    cursor.executemany("""
    INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, orders_data)
    
    # Create indexes for better performance
    cursor.execute("CREATE INDEX idx_orders_customer_id ON orders(customer_id)")
    cursor.execute("CREATE INDEX idx_orders_order_id ON orders(order_id)")
    cursor.execute("CREATE INDEX idx_orders_status ON orders(order_status)")
    cursor.execute("CREATE INDEX idx_inventory_category ON inventory(category)")
    cursor.execute("CREATE INDEX idx_inventory_in_stock ON inventory(in_stock)")
    
    conn.commit()
    conn.close()
    
    logger.info(f"SQLite database created successfully: {db_path}")
    logger.info("Database contains:")
    logger.info("- 5 customers")
    logger.info("- 10 products in inventory")
    logger.info("- 12 orders with various statuses")
    
    return db_path


def verify_database(db_path):
    """Verify the database was created correctly."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check table counts
    cursor.execute("SELECT COUNT(*) FROM customers")
    customer_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM inventory")
    inventory_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]
    
    logger.info("Database verification:")
    logger.info(f"- Customers: {customer_count}")
    logger.info(f"- Inventory items: {inventory_count}")
    logger.info(f"- Orders: {order_count}")
    
    # Show sample data
    logger.info("\nSample order data:")
    cursor.execute("""
    SELECT order_id, customer_id, product_name, order_status, shipping_status 
    FROM orders 
    LIMIT 3
    """)
    
    for row in cursor.fetchall():
        logger.info(f"  {row[0]}: {row[2]} - {row[3]} ({row[4]})")
    
    logger.info("\nSample inventory data:")
    cursor.execute("""
    SELECT product_name, category, quantity, in_stock
    FROM inventory 
    WHERE in_stock = 'yes'
    LIMIT 3
    """)
    
    for row in cursor.fetchall():
        logger.info(f"  {row[0]} ({row[1]}): {row[2]} units - {row[3]}")
    
    conn.close()


if __name__ == "__main__":
    try:
        db_path = create_database()
        verify_database(db_path)
        print(f"\n✅ SQLite database ready for testing: {db_path}")
        print("You can now test the order management agent with real data!")
        
    except Exception as e:
        logger.error(f"Failed to create database: {e}")
        raise