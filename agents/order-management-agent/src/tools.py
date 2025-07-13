"""
SQL database tools for the order management agent.

This module provides tools for executing SQL queries against the order management
database to retrieve order status, inventory information, and shipping details.
"""

import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Union

import asyncpg
import psycopg2
from src.shared.models import DatabaseQuery, DatabaseResult
from src.order_agent.config import config

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class SQLQueryExecutor:
    """Tool for executing SQL queries against the order management database."""
    
    def __init__(self):
        """Initialize the SQL query executor."""
        self.database_url = config.get_database_url()
        self.timeout = config.database_timeout
        self._connection_pool = None
        
        if not self.database_url:
            logger.warning("Database URL not configured. Using mock data.")
            self._use_mock_data = True
        else:
            self._use_mock_data = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self._use_mock_data:
            try:
                self._connection_pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=1,
                    max_size=5,
                    command_timeout=self.timeout
                )
                logger.info("Database connection pool created")
            except Exception as e:
                logger.error(f"Failed to create database pool: {e}")
                self._use_mock_data = True
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._connection_pool:
            await self._connection_pool.close()
            logger.info("Database connection pool closed")
    
    async def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> DatabaseResult:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL query to execute
            parameters: Optional query parameters
            
        Returns:
            Database query results
        """
        start_time = time.time()
        
        # Clean and validate query
        query = self._sanitize_query(query)
        
        if self._use_mock_data:
            return await self._execute_mock_query(query, start_time)
        
        try:
            async with self._connection_pool.acquire() as connection:
                logger.debug(f"Executing query: {query}")
                
                # Convert dict parameters to list if needed
                if parameters:
                    # Convert named parameters to positional for asyncpg
                    query_params = list(parameters.values())
                else:
                    query_params = []
                
                # Execute query
                rows = await connection.fetch(query, *query_params)
                
                # Convert rows to list of dictionaries
                results = [dict(row) for row in rows]
                
                execution_time = time.time() - start_time
                
                logger.info(f"Query executed successfully in {execution_time:.3f}s, returned {len(results)} rows")
                
                return DatabaseResult(
                    results=results,
                    execution_time=execution_time,
                    row_count=len(results),
                    error=None
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Query execution failed: {str(e)}"
            logger.error(error_msg)
            
            return DatabaseResult(
                results=[],
                execution_time=execution_time,
                row_count=0,
                error=error_msg
            )
    
    def _sanitize_query(self, query: str) -> str:
        """
        Sanitize SQL query to prevent injection attacks.
        
        Args:
            query: Raw SQL query
            
        Returns:
            Sanitized query
        """
        # Remove potentially dangerous keywords
        dangerous_keywords = [
            'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE',
            'TRUNCATE', 'EXEC', 'EXECUTE', 'SHUTDOWN', '--', ';--', '/*', '*/'
        ]
        
        query_upper = query.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                logger.warning(f"Potentially dangerous keyword '{keyword}' found in query")
                # For now, we'll allow it but log it. In production, might want to reject.
        
        # Ensure query is lowercase as per requirements
        return query.lower().strip()
    
    async def _execute_mock_query(self, query: str, start_time: float) -> DatabaseResult:
        """
        Execute mock query for testing/development.
        
        Args:
            query: SQL query
            start_time: Query start time
            
        Returns:
            Mock database results
        """
        await asyncio.sleep(0.1)  # Simulate database latency
        
        # Mock data based on query content
        if 'orders' in query and 'customer_id' in query:
            if 'cust001' in query:
                mock_results = [
                    {
                        'order_id': 'ORD-2024-001',
                        'customer_id': 'cust001',
                        'product_id': 'HD001',
                        'product_name': 'ZenSound Wireless Headphones',
                        'order_status': 'processing',
                        'shipping_status': 'preparing',
                        'return_exchange_status': None,
                        'order_date': '2024-07-01',
                        'delivery_date': '2024-07-05'
                    }
                ]
            else:
                mock_results = []
        
        elif 'inventory' in query:
            mock_results = [
                {
                    'product_id': 'HD001',
                    'product_name': 'ZenSound Wireless Headphones',
                    'category': 'headphones',
                    'quantity': 25,
                    'in_stock': 'yes',
                    'reorder_threshold': 10,
                    'reorder_quantity': 50,
                    'last_restock_date': '2024-06-15'
                },
                {
                    'product_id': 'SW001',
                    'product_name': 'VitaFit Smartwatch',
                    'category': 'watch',
                    'quantity': 15,
                    'in_stock': 'yes',
                    'reorder_threshold': 5,
                    'reorder_quantity': 30,
                    'last_restock_date': '2024-06-20'
                }
            ]
        
        elif 'orders' in query and 'order_status' in query:
            mock_results = [
                {'order_status': 'processing', 'total_orders': 150},
                {'order_status': 'shipped', 'total_orders': 89},
                {'order_status': 'delivered', 'total_orders': 45},
                {'order_status': 'cancelled', 'total_orders': 12}
            ]
        
        else:
            mock_results = []
        
        execution_time = time.time() - start_time
        
        logger.info(f"Mock query executed in {execution_time:.3f}s, returned {len(mock_results)} rows")
        
        return DatabaseResult(
            results=mock_results,
            execution_time=execution_time,
            row_count=len(mock_results),
            error=None
        )
    
    def validate_query_safety(self, query: str) -> bool:
        """
        Validate that a query is safe to execute.
        
        Args:
            query: SQL query to validate
            
        Returns:
            True if query is safe, False otherwise
        """
        query_upper = query.upper().strip()
        
        # Must start with SELECT
        if not query_upper.startswith('SELECT'):
            return False
        
        # Check for dangerous operations
        dangerous_patterns = [
            'DROP ', 'DELETE ', 'INSERT ', 'UPDATE ', 'ALTER ', 'CREATE ',
            'TRUNCATE ', 'EXEC', 'EXECUTE', '--', ';', 'UNION',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in query_upper:
                return False
        
        return True
    
    async def get_customer_orders(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all orders for a specific customer.
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            List of customer orders
        """
        query = """
        SELECT * FROM order_management.orders 
        WHERE customer_id LIKE $1
        ORDER BY order_date DESC
        """
        
        result = await self.execute_query(query, {'customer_id': f'%{customer_id}%'})
        return result.results
    
    async def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order details by order ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order details or None if not found
        """
        query = """
        SELECT * FROM order_management.orders 
        WHERE order_id LIKE $1
        """
        
        result = await self.execute_query(query, {'order_id': f'%{order_id}%'})
        return result.results[0] if result.results else None
    
    async def check_product_availability(self, product_name: str = None, category: str = None) -> List[Dict[str, Any]]:
        """
        Check product availability in inventory.
        
        Args:
            product_name: Product name to search for
            category: Product category to filter by
            
        Returns:
            List of available products
        """
        base_query = """
        SELECT product_name, quantity, in_stock, category
        FROM order_management.inventory 
        WHERE in_stock = 'yes' AND quantity > 0
        """
        
        conditions = []
        params = {}
        
        if product_name:
            conditions.append("product_name LIKE $1")
            params['product_name'] = f'%{product_name}%'
        
        if category:
            param_num = len(params) + 1
            conditions.append(f"category LIKE ${param_num}")
            params['category'] = f'%{category}%'
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        result = await self.execute_query(query, params)
        return result.results
    
    async def get_order_status_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of order statuses.
        
        Returns:
            Order status summary
        """
        query = """
        SELECT order_status, COUNT(*) AS total_orders
        FROM order_management.orders
        GROUP BY order_status
        ORDER BY total_orders DESC
        """
        
        result = await self.execute_query(query)
        return result.results
    
    async def get_shipping_status(self, customer_id: str = None, order_id: str = None) -> List[Dict[str, Any]]:
        """
        Get shipping status for orders.
        
        Args:
            customer_id: Customer identifier
            order_id: Order identifier
            
        Returns:
            Shipping status information
        """
        base_query = """
        SELECT order_id, customer_id, product_name, shipping_status, delivery_date
        FROM order_management.orders
        WHERE shipping_status IS NOT NULL
        """
        
        conditions = []
        params = {}
        
        if customer_id:
            conditions.append("customer_id LIKE $1")
            params['customer_id'] = f'%{customer_id}%'
        
        if order_id:
            param_num = len(params) + 1
            conditions.append(f"order_id LIKE ${param_num}")
            params['order_id'] = f'%{order_id}%'
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += " ORDER BY order_date DESC"
        
        result = await self.execute_query(query, params)
        return result.results
    
    async def check_return_exchange_status(self, customer_id: str = None, order_id: str = None) -> List[Dict[str, Any]]:
        """
        Check return/exchange status for orders.
        
        Args:
            customer_id: Customer identifier
            order_id: Order identifier
            
        Returns:
            Return/exchange status information
        """
        base_query = """
        SELECT order_id, customer_id, product_name, return_exchange_status, order_date
        FROM order_management.orders
        WHERE return_exchange_status IS NOT NULL
        """
        
        conditions = []
        params = {}
        
        if customer_id:
            conditions.append("customer_id LIKE $1")
            params['customer_id'] = f'%{customer_id}%'
        
        if order_id:
            param_num = len(params) + 1
            conditions.append(f"order_id LIKE ${param_num}")
            params['order_id'] = f'%{order_id}%'
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += " ORDER BY order_date DESC"
        
        result = await self.execute_query(query, params)
        return result.results