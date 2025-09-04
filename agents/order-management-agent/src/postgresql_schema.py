"""
PostgreSQL schema management for the order management agent.

This module provides tools for creating and managing PostgreSQL database schema,
converting from SQLite schema to PostgreSQL-compatible format with proper data types.
Uses AWS RDS Data API for database connectivity.
"""

import logging
import asyncio
import time
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class PostgreSQLSchemaError(Exception):
    """Raised when schema operations fail."""
    pass


class PostgreSQLSchemaManager:
    """Manages PostgreSQL schema creation and migration using RDS Data API."""
    
    def __init__(self, config_obj=None):
        """
        Initialize the PostgreSQL schema manager.
        
        Args:
            config_obj: Configuration object with database settings
        """
        self.config = config_obj
        self.rds_client = None
        self._cluster_arn = None
        self._secret_arn = None
        self._database_name = None
        
    async def initialize(self):
        """Initialize the RDS Data API client."""
        # Get required configuration
        self._cluster_arn = os.getenv('DATABASE_CLUSTER_ARN') or os.getenv('RDS_CLUSTER_ARN')
        self._secret_arn = os.getenv('DATABASE_SECRET_ARN') or os.getenv('RDS_SECRET_ARN')
        self._database_name = os.getenv('DATABASE_NAME') or (self.config.db_name if self.config else None) or os.getenv('ORDER_DB_NAME', 'multiagent')
        
        if not self._cluster_arn or not self._secret_arn:
            raise PostgreSQLSchemaError(
                "DATABASE_CLUSTER_ARN and DATABASE_SECRET_ARN environment variables are required"
            )
        
        # Create RDS Data API client
        session = boto3.Session()
        
        # Check if we're running in AWS environment or local development
        use_profile = not os.getenv("AWS_EXECUTION_ENV") and not os.getenv("ECS_CONTAINER_METADATA_URI")
        
        if use_profile and self.config and hasattr(self.config, 'aws_credentials_profile'):
            session = boto3.Session(profile_name=self.config.aws_credentials_profile)
            logger.info(f"Using AWS credential profile: {self.config.aws_credentials_profile}")
        else:
            logger.info("Using default AWS credential chain (IAM roles)")
        
        aws_region = (self.config.aws_default_region if self.config else None) or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self.rds_client = session.client('rds-data', region_name=aws_region)
        
        logger.info("PostgreSQL schema manager initialized with RDS Data API")
        
    async def create_schema(self) -> bool:
        """
        Create PostgreSQL tables with proper data types.
        This operation is idempotent - safe to run multiple times.
        
        Returns:
            True if schema was created successfully
            
        Raises:
            PostgreSQLSchemaError: If schema creation fails
        """
        try:
            if not self.rds_client:
                await self.initialize()
                
            logger.info("Creating PostgreSQL schema for order management...")
            
            # Create orders table
            await self._create_orders_table()
            
            # Create inventory table
            await self._create_inventory_table()
            
            # Create customers table
            await self._create_customers_table()
            
            # Create indexes for performance
            await self._create_indexes()
            
            logger.info("PostgreSQL schema created successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to create PostgreSQL schema: {str(e)}"
            logger.error(error_msg)
            raise PostgreSQLSchemaError(error_msg) from e
    
    async def _execute_sql(self, sql: str, parameters: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Execute SQL using RDS Data API."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.rds_client.execute_statement(
                    resourceArn=self._cluster_arn,
                    secretArn=self._secret_arn,
                    database=self._database_name,
                    sql=sql,
                    parameters=parameters or [],
                    includeResultMetadata=True
                )
            )
            return response
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            raise
    
    async def _create_orders_table(self) -> None:
        """Create the orders table with PostgreSQL-specific data types."""
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS orders (
            order_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50) NOT NULL,
            product_id VARCHAR(50) NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            order_status VARCHAR(50) NOT NULL,
            shipping_status VARCHAR(50),
            return_exchange_status VARCHAR(50),
            order_date DATE NOT NULL,
            delivery_date DATE,
            quantity INTEGER DEFAULT 1,
            price_per_unit DECIMAL(10,2),
            total_amount DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        await self._execute_sql(create_table_sql)
        logger.debug("Orders table created/verified")
    
    async def _create_inventory_table(self) -> None:
        """Create the inventory table with PostgreSQL-specific data types."""
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS inventory (
            product_id VARCHAR(50) PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            quantity INTEGER NOT NULL,
            in_stock BOOLEAN NOT NULL,
            reorder_threshold INTEGER DEFAULT 10,
            reorder_quantity INTEGER DEFAULT 50,
            last_restock_date DATE,
            price_per_unit DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        await self._execute_sql(create_table_sql)
        logger.debug("Inventory table created/verified")
    
    async def _create_customers_table(self) -> None:
        """Create the customers table with PostgreSQL-specific data types."""
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id VARCHAR(50) PRIMARY KEY,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(20),
            address TEXT,
            city VARCHAR(100),
            state VARCHAR(50),
            zip_code VARCHAR(20),
            created_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        await self._execute_sql(create_table_sql)
        logger.debug("Customers table created/verified")
    
    async def _create_indexes(self) -> None:
        """Create indexes for better query performance."""
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_in_stock ON inventory(in_stock)",
            "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)"
        ]
        
        for index_sql in indexes:
            await self._execute_sql(index_sql)
        
        logger.debug("Database indexes created/verified")
    
    async def insert_test_data(self) -> bool:
        """
        Insert sample test data for development and testing.
        This operation is idempotent - will not duplicate data.
        
        Returns:
            True if test data was inserted successfully
            
        Raises:
            PostgreSQLSchemaError: If data insertion fails
        """
        try:
            if not self.rds_client:
                await self.initialize()
                
            logger.info("Inserting test data into PostgreSQL database...")
            
            # Check if data already exists
            response = await self._execute_sql("SELECT COUNT(*) FROM customers")
            existing_customers = self._extract_count_from_response(response)
            
            if existing_customers > 0:
                logger.info(f"Test data already exists ({existing_customers} customers found). Skipping insertion.")
                return True
            
            # Insert customers
            await self._insert_customers_data()
            
            # Insert inventory
            await self._insert_inventory_data()
            
            # Insert orders
            await self._insert_orders_data()
            
            logger.info("Test data inserted successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to insert test data: {str(e)}"
            logger.error(error_msg)
            raise PostgreSQLSchemaError(error_msg) from e
    
    def _extract_count_from_response(self, response: Dict[str, Any]) -> int:
        """Extract count value from RDS Data API response."""
        if 'records' in response and response['records']:
            first_record = response['records'][0]
            if first_record and 'longValue' in first_record[0]:
                return first_record[0]['longValue']
        return 0
    
    async def _insert_customers_data(self) -> None:
        """Insert customer test data."""
        
        customers_data = [
            ("cust001", "John", "Smith", "john.smith@email.com", "555-0123", "123 Main St", "New York", "NY", "10001", "2024-01-15"),
            ("cust002", "Sarah", "Johnson", "sarah.j@email.com", "555-0456", "456 Oak Ave", "Los Angeles", "CA", "90210", "2024-02-20"),
            ("cust003", "Mike", "Chen", "mike.chen@email.com", "555-0789", "789 Pine Rd", "Chicago", "IL", "60601", "2024-03-10"),
            ("cust004", "Emma", "Davis", "emma.d@email.com", "555-0321", "321 Elm St", "Miami", "FL", "33101", "2024-04-05"),
            ("cust005", "Alex", "Wilson", "alex.w@email.com", "555-0654", "654 Maple Dr", "Seattle", "WA", "98101", "2024-05-12")
        ]
        
        insert_sql = """
        INSERT INTO customers (customer_id, first_name, last_name, email, phone, address, city, state, zip_code, created_date)
        VALUES (:customer_id, :first_name, :last_name, :email, :phone, :address, :city, :state, :zip_code, :created_date)
        """
        
        for customer in customers_data:
            parameters = [
                {'name': 'customer_id', 'value': {'stringValue': customer[0]}},
                {'name': 'first_name', 'value': {'stringValue': customer[1]}},
                {'name': 'last_name', 'value': {'stringValue': customer[2]}},
                {'name': 'email', 'value': {'stringValue': customer[3]}},
                {'name': 'phone', 'value': {'stringValue': customer[4]}},
                {'name': 'address', 'value': {'stringValue': customer[5]}},
                {'name': 'city', 'value': {'stringValue': customer[6]}},
                {'name': 'state', 'value': {'stringValue': customer[7]}},
                {'name': 'zip_code', 'value': {'stringValue': customer[8]}},
                {'name': 'created_date', 'value': {'stringValue': customer[9]}, 'typeHint': 'DATE'}
            ]
            await self._execute_sql(insert_sql, parameters)
        
        logger.debug(f"Inserted {len(customers_data)} customers")
    
    async def _insert_inventory_data(self) -> None:
        """Insert inventory test data with proper boolean conversion."""
        
        # Convert SQLite 'yes'/'no' strings to PostgreSQL boolean values
        inventory_data = [
            ("HD001", "ZenSound Wireless Headphones", "headphones", 25, True, 10, 50, "2024-06-15", 149.99),
            ("HD002", "AudioMax Pro Headphones", "headphones", 18, True, 8, 40, "2024-06-20", 199.99),
            ("HD003", "BassBoost Gaming Headset", "headphones", 3, False, 5, 30, "2024-05-25", 89.99),  # 'low' -> False
            ("SW001", "VitaFit Smartwatch", "watch", 15, True, 5, 30, "2024-06-20", 299.99),
            ("SW002", "TechTime Pro Watch", "watch", 8, True, 3, 20, "2024-06-10", 399.99),
            ("SP001", "FitTrack Wireless Speaker", "speaker", 22, True, 8, 35, "2024-06-25", 79.99),
            ("SP002", "SoundWave Bluetooth Speaker", "speaker", 0, False, 5, 25, "2024-05-15", 129.99),  # 'no' -> False
            ("CH001", "QuickCharge Wireless Charger", "charger", 35, True, 15, 60, "2024-06-30", 39.99),
            ("PH001", "TechPhone Pro Max", "phone", 12, True, 5, 25, "2024-06-18", 899.99),
            ("TB001", "WorkTab Pro Tablet", "tablet", 7, True, 3, 15, "2024-06-12", 549.99)
        ]
        
        insert_sql = """
        INSERT INTO inventory (product_id, product_name, category, quantity, in_stock, reorder_threshold, reorder_quantity, last_restock_date, price_per_unit)
        VALUES (:product_id, :product_name, :category, :quantity, :in_stock, :reorder_threshold, :reorder_quantity, :last_restock_date, :price_per_unit)
        """
        
        for item in inventory_data:
            parameters = [
                {'name': 'product_id', 'value': {'stringValue': item[0]}},
                {'name': 'product_name', 'value': {'stringValue': item[1]}},
                {'name': 'category', 'value': {'stringValue': item[2]}},
                {'name': 'quantity', 'value': {'longValue': item[3]}},
                {'name': 'in_stock', 'value': {'booleanValue': item[4]}},
                {'name': 'reorder_threshold', 'value': {'longValue': item[5]}},
                {'name': 'reorder_quantity', 'value': {'longValue': item[6]}},
                {'name': 'last_restock_date', 'value': {'stringValue': item[7]}, 'typeHint': 'DATE'},
                {'name': 'price_per_unit', 'value': {'doubleValue': item[8]}}
            ]
            await self._execute_sql(insert_sql, parameters)
        
        logger.debug(f"Inserted {len(inventory_data)} inventory items")
    
    async def _insert_orders_data(self) -> None:
        """Insert orders test data."""
        
        # Calculate dates relative to current time
        base_date = datetime.now() - timedelta(days=30)
        
        orders_data = [
            # Customer cust001 orders
            ("ORD-2024-001", "cust001", "HD001", "ZenSound Wireless Headphones", "processing", "preparing", None, 
             (base_date + timedelta(days=1)).strftime('%Y-%m-%d'), 
             (base_date + timedelta(days=5)).strftime('%Y-%m-%d'), 1, 149.99, 149.99),
            ("ORD-2024-002", "cust001", "SW001", "VitaFit Smartwatch", "shipped", "in_transit", None,
             (base_date + timedelta(days=3)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=7)).strftime('%Y-%m-%d'), 1, 299.99, 299.99),
            ("ORD-2024-003", "cust001", "CH001", "QuickCharge Wireless Charger", "delivered", "delivered", None,
             (base_date + timedelta(days=10)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=12)).strftime('%Y-%m-%d'), 2, 39.99, 79.98),
             
            # Customer cust002 orders
            ("ORD-2024-004", "cust002", "HD002", "AudioMax Pro Headphones", "delivered", "delivered", "return_requested",
             (base_date + timedelta(days=5)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=8)).strftime('%Y-%m-%d'), 1, 199.99, 199.99),
            ("ORD-2024-005", "cust002", "SP001", "FitTrack Wireless Speaker", "shipped", "in_transit", None,
             (base_date + timedelta(days=15)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=18)).strftime('%Y-%m-%d'), 1, 79.99, 79.99),
             
            # Customer cust003 orders
            ("ORD-2024-006", "cust003", "PH001", "TechPhone Pro Max", "processing", "preparing", None,
             (base_date + timedelta(days=12)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=16)).strftime('%Y-%m-%d'), 1, 899.99, 899.99),
            ("ORD-2024-007", "cust003", "TB001", "WorkTab Pro Tablet", "delivered", "delivered", "exchange_completed",
             (base_date + timedelta(days=8)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=11)).strftime('%Y-%m-%d'), 1, 549.99, 549.99),
             
            # Customer cust004 orders
            ("ORD-2024-008", "cust004", "HD003", "BassBoost Gaming Headset", "cancelled", "cancelled", None,
             (base_date + timedelta(days=20)).strftime('%Y-%m-%d'), None, 1, 89.99, 89.99),
            ("ORD-2024-009", "cust004", "SW002", "TechTime Pro Watch", "shipped", "shipped", None,
             (base_date + timedelta(days=22)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=25)).strftime('%Y-%m-%d'), 1, 399.99, 399.99),
             
            # Customer cust005 orders
            ("ORD-2024-010", "cust005", "SP002", "SoundWave Bluetooth Speaker", "processing", "preparing", None,
             (base_date + timedelta(days=25)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=28)).strftime('%Y-%m-%d'), 1, 129.99, 129.99),
            ("ORD-2024-011", "cust005", "HD001", "ZenSound Wireless Headphones", "delivered", "delivered", None,
             (base_date + timedelta(days=18)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=21)).strftime('%Y-%m-%d'), 1, 149.99, 149.99),
            ("ORD-2024-012", "cust005", "CH001", "QuickCharge Wireless Charger", "processing", "preparing", None,
             (base_date + timedelta(days=28)).strftime('%Y-%m-%d'),
             (base_date + timedelta(days=31)).strftime('%Y-%m-%d'), 3, 39.99, 119.97)
        ]
        
        insert_sql = """
        INSERT INTO orders (order_id, customer_id, product_id, product_name, order_status, shipping_status, return_exchange_status, order_date, delivery_date, quantity, price_per_unit, total_amount)
        VALUES (:order_id, :customer_id, :product_id, :product_name, :order_status, :shipping_status, :return_exchange_status, :order_date, :delivery_date, :quantity, :price_per_unit, :total_amount)
        """
        
        for order in orders_data:
            parameters = [
                {'name': 'order_id', 'value': {'stringValue': order[0]}},
                {'name': 'customer_id', 'value': {'stringValue': order[1]}},
                {'name': 'product_id', 'value': {'stringValue': order[2]}},
                {'name': 'product_name', 'value': {'stringValue': order[3]}},
                {'name': 'order_status', 'value': {'stringValue': order[4]}},
                {'name': 'shipping_status', 'value': {'stringValue': order[5]} if order[5] else {'isNull': True}},
                {'name': 'return_exchange_status', 'value': {'stringValue': order[6]} if order[6] else {'isNull': True}},
                {'name': 'order_date', 'value': {'stringValue': order[7]}, 'typeHint': 'DATE'},
                {'name': 'delivery_date', 'value': {'stringValue': order[8]}, 'typeHint': 'DATE'} if order[8] else {'name': 'delivery_date', 'value': {'isNull': True}},
                {'name': 'quantity', 'value': {'longValue': order[9]}},
                {'name': 'price_per_unit', 'value': {'doubleValue': order[10]}},
                {'name': 'total_amount', 'value': {'doubleValue': order[11]}}
            ]
            await self._execute_sql(insert_sql, parameters)
        
        logger.debug(f"Inserted {len(orders_data)} orders")
    
    async def verify_schema(self) -> Dict[str, Any]:
        """
        Verify that the schema was created correctly.
        
        Returns:
            Dictionary with verification results
            
        Raises:
            PostgreSQLSchemaError: If verification fails
        """
        try:
            if not self.rds_client:
                await self.initialize()
                
            logger.info("Verifying PostgreSQL schema...")
            
            # Check table existence and row counts
            tables_info = {}
            
            # Check customers table
            response = await self._execute_sql("SELECT COUNT(*) FROM customers")
            customer_count = self._extract_count_from_response(response)
            tables_info['customers'] = {
                'exists': True,
                'row_count': customer_count
            }
            
            # Check inventory table
            response = await self._execute_sql("SELECT COUNT(*) FROM inventory")
            inventory_count = self._extract_count_from_response(response)
            tables_info['inventory'] = {
                'exists': True,
                'row_count': inventory_count
            }
            
            # Check orders table
            response = await self._execute_sql("SELECT COUNT(*) FROM orders")
            order_count = self._extract_count_from_response(response)
            tables_info['orders'] = {
                'exists': True,
                'row_count': order_count
            }
            
            # Verify indexes exist
            index_query = """
            SELECT indexname FROM pg_indexes 
            WHERE tablename IN ('orders', 'inventory', 'customers')
            ORDER BY indexname
            """
            response = await self._execute_sql(index_query)
            index_names = self._extract_index_names_from_response(response)
            
            # Sample data verification
            sample_order_response = await self._execute_sql("""
            SELECT order_id, customer_id, product_name, order_status, shipping_status 
            FROM orders 
            LIMIT 1
            """)
            sample_order = self._convert_dataapi_response_to_dict(sample_order_response)
            
            sample_inventory_response = await self._execute_sql("""
            SELECT product_name, category, quantity, in_stock
            FROM inventory 
            WHERE in_stock = true
            LIMIT 1
            """)
            sample_inventory = self._convert_dataapi_response_to_dict(sample_inventory_response)
            
            verification_result = {
                'schema_valid': True,
                'tables': tables_info,
                'indexes': index_names,
                'sample_data': {
                    'order': sample_order[0] if sample_order else None,
                    'inventory': sample_inventory[0] if sample_inventory else None
                }
            }
            
            logger.info("Schema verification completed successfully")
            logger.info(f"Database contains:")
            logger.info(f"- {customer_count} customers")
            logger.info(f"- {inventory_count} inventory items")
            logger.info(f"- {order_count} orders")
            logger.info(f"- {len(index_names)} indexes")
            
            return verification_result
            
        except Exception as e:
            error_msg = f"Schema verification failed: {str(e)}"
            logger.error(error_msg)
            raise PostgreSQLSchemaError(error_msg) from e
    
    def _extract_index_names_from_response(self, response: Dict[str, Any]) -> List[str]:
        """Extract index names from RDS Data API response."""
        index_names = []
        if 'records' in response:
            for record in response['records']:
                if record and 'stringValue' in record[0]:
                    index_names.append(record[0]['stringValue'])
        return index_names
    
    def _convert_dataapi_response_to_dict(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert Data API response to list of dictionaries."""
        results = []
        
        if 'records' not in response:
            return results
        
        # Get column metadata
        columns = []
        if 'columnMetadata' in response:
            columns = [col['name'] for col in response['columnMetadata']]
        
        # Convert each record
        for record in response['records']:
            row_dict = {}
            for i, field in enumerate(record):
                column_name = columns[i] if i < len(columns) else f'column_{i}'
                
                # Extract value based on Data API field type
                if 'stringValue' in field:
                    row_dict[column_name] = field['stringValue']
                elif 'longValue' in field:
                    row_dict[column_name] = field['longValue']
                elif 'doubleValue' in field:
                    row_dict[column_name] = field['doubleValue']
                elif 'booleanValue' in field:
                    row_dict[column_name] = field['booleanValue']
                elif 'isNull' in field and field['isNull']:
                    row_dict[column_name] = None
                else:
                    # Fallback to string representation
                    row_dict[column_name] = str(field)
            
            results.append(row_dict)
        
        return results
    
    async def check_table_exists(self, table_name: str) -> bool:
        """
        Check if a specific table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            if not self.rds_client:
                await self.initialize()
                
            response = await self._execute_sql("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = :table_name
            )
            """, [{'name': 'table_name', 'value': {'stringValue': table_name}}])
            
            # Extract boolean result from response
            if 'records' in response and response['records']:
                first_record = response['records'][0]
                if first_record and 'booleanValue' in first_record[0]:
                    return first_record[0]['booleanValue']
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check table existence for {table_name}: {e}")
            return False
    
    async def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with table information or None if table doesn't exist
        """
        try:
            if not self.rds_client:
                await self.initialize()
                
            # Check if table exists
            exists = await self.check_table_exists(table_name)
            if not exists:
                return None
            
            # Get column information
            columns_query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
            ORDER BY ordinal_position
            """
            
            response = await self._execute_sql(columns_query, [
                {'name': 'table_name', 'value': {'stringValue': table_name}}
            ])
            columns = self._convert_dataapi_response_to_dict(response)
            
            # Get row count
            count_response = await self._execute_sql(f"SELECT COUNT(*) FROM {table_name}")
            row_count = self._extract_count_from_response(count_response)
            
            return {
                'table_name': table_name,
                'exists': True,
                'row_count': row_count,
                'columns': columns
            }
            
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {e}")
            return None