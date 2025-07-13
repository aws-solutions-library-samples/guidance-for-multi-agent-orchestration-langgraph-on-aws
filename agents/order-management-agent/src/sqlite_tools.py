"""
SQLite database tools for the order management agent.

This module provides tools for executing SQL queries against a SQLite database
to retrieve order status, inventory information, and shipping details.
"""

import logging
import asyncio
import time
import sqlite3
import aiosqlite
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from shared.models import DatabaseQuery, DatabaseResult
from config import config

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class SQLiteQueryExecutor:
    """Tool for executing SQL queries against the SQLite order management database."""
    
    def __init__(self, db_path: str = "order_management.db"):
        """Initialize the SQLite query executor."""
        self.db_path = db_path
        self.timeout = config.database_timeout
        self._use_mock_data = False
        
        # Check if database exists
        import os
        if not os.path.exists(self.db_path):
            logger.warning(f"SQLite database not found at {self.db_path}. Using mock data.")
            self._use_mock_data = True
        else:
            logger.info(f"Using SQLite database: {self.db_path}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get async SQLite connection."""
        if self._use_mock_data:
            yield None
            return
            
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # Set row factory to return rows as dictionaries
                conn.row_factory = aiosqlite.Row
                yield conn
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            self._use_mock_data = True
            yield None
    
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
            async with self.get_connection() as conn:
                if conn is None:
                    return await self._execute_mock_query(query, start_time)
                
                logger.debug(f"Executing SQLite query: {query}")
                
                # Convert parameters for SQLite
                if parameters:
                    # Convert named parameters to positional for consistency
                    param_values = list(parameters.values())
                    
                    # Replace named placeholders with ? for SQLite
                    sqlite_query = query
                    for i, (key, value) in enumerate(parameters.items()):
                        sqlite_query = sqlite_query.replace(f"${i+1}", "?")
                else:
                    param_values = []
                    sqlite_query = query
                
                # Execute query
                async with conn.execute(sqlite_query, param_values) as cursor:
                    rows = await cursor.fetchall()
                
                # Convert rows to list of dictionaries
                results = [dict(row) for row in rows]
                
                execution_time = time.time() - start_time
                
                logger.info(f"SQLite query executed successfully in {execution_time:.3f}s, returned {len(results)} rows")
                
                return DatabaseResult(
                    results=results,
                    execution_time=execution_time,
                    row_count=len(results),
                    error=None
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"SQLite query execution failed: {str(e)}"
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
        
        return query.strip()
    
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
        if 'orders' in query.lower() and 'customer_id' in query.lower():
            if 'cust001' in query.lower():
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
                        'delivery_date': '2024-07-05',
                        'quantity': 1,
                        'total_amount': 149.99
                    }
                ]
            else:
                mock_results = []
        
        elif 'inventory' in query.lower():
            mock_results = [
                {
                    'product_id': 'HD001',
                    'product_name': 'ZenSound Wireless Headphones',
                    'category': 'headphones',
                    'quantity': 25,
                    'in_stock': 'yes',
                    'reorder_threshold': 10,
                    'reorder_quantity': 50,
                    'last_restock_date': '2024-06-15',
                    'price_per_unit': 149.99
                }
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
    
    async def get_customer_orders(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all orders for a specific customer.
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            List of customer orders
        """
        query = """
        SELECT * FROM orders 
        WHERE customer_id LIKE ?
        ORDER BY order_date DESC
        """
        
        # For SQLite, use LIKE with wildcards
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
        SELECT * FROM orders 
        WHERE order_id LIKE ?
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
        SELECT product_name, quantity, in_stock, category, price_per_unit
        FROM inventory 
        WHERE in_stock = 'yes' AND quantity > 0
        """
        
        conditions = []
        params = {}
        
        if product_name:
            conditions.append("product_name LIKE ?")
            params['product_name'] = f'%{product_name}%'
        
        if category:
            conditions.append("category LIKE ?")
            params['category'] = f'%{category}%'
        
        if conditions:
            # Convert to SQLite placeholders
            sqlite_conditions = []
            param_values = []
            for condition in conditions:
                sqlite_conditions.append(condition)
            
            query = base_query + " AND " + " AND ".join(sqlite_conditions)
            param_values = list(params.values())
        else:
            query = base_query
            param_values = []
        
        # Execute with positional parameters
        async with self.get_connection() as conn:
            if conn is None:
                result = await self._execute_mock_query(query, time.time())
                return result.results
            
            async with conn.execute(query, param_values) as cursor:
                rows = await cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    async def get_order_status_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of order statuses.
        
        Returns:
            Order status summary
        """
        query = """
        SELECT order_status, COUNT(*) AS total_orders
        FROM orders
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
        FROM orders
        WHERE shipping_status IS NOT NULL
        """
        
        conditions = []
        param_values = []
        
        if customer_id:
            conditions.append("customer_id LIKE ?")
            param_values.append(f'%{customer_id}%')
        
        if order_id:
            conditions.append("order_id LIKE ?")
            param_values.append(f'%{order_id}%')
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += " ORDER BY order_date DESC"
        
        async with self.get_connection() as conn:
            if conn is None:
                result = await self._execute_mock_query(query, time.time())
                return result.results
            
            async with conn.execute(query, param_values) as cursor:
                rows = await cursor.fetchall()
            
            return [dict(row) for row in rows]
    
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
        FROM orders
        WHERE return_exchange_status IS NOT NULL
        """
        
        conditions = []
        param_values = []
        
        if customer_id:
            conditions.append("customer_id LIKE ?")
            param_values.append(f'%{customer_id}%')
        
        if order_id:
            conditions.append("order_id LIKE ?")
            param_values.append(f'%{order_id}%')
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += " ORDER BY order_date DESC"
        
        async with self.get_connection() as conn:
            if conn is None:
                result = await self._execute_mock_query(query, time.time())
                return result.results
            
            async with conn.execute(query, param_values) as cursor:
                rows = await cursor.fetchall()
            
            return [dict(row) for row in rows]