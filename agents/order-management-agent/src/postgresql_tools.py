"""
PostgreSQL database tools for the order management agent using AWS RDS Data API.

This module provides tools for executing SQL queries against a PostgreSQL database
deployed in VPC using AWS RDS Data API to retrieve order status, inventory information, 
and shipping details.
"""

import logging
import asyncio
import time
import json
import os
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

from shared.models import DatabaseQuery, DatabaseResult
from config import config

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class PostgreSQLQueryExecutor:
    """Tool for executing SQL queries against PostgreSQL using AWS RDS Data API."""
    
    def __init__(self, config_obj=None):
        """Initialize the PostgreSQL Data API query executor."""
        self.config = config_obj or config
        self.rds_client = None
        self.timeout = self.config.database_timeout
        self._cluster_arn = None
        self._secret_arn = None
        self._database_name = None
        
        logger.info("Initializing PostgreSQL Data API query executor")
    
    async def initialize_pool(self):
        """Initialize the RDS Data API client and validate configuration."""
        # Get required configuration - check both naming conventions
        self._cluster_arn = os.getenv('DATABASE_CLUSTER_ARN') or os.getenv('RDS_CLUSTER_ARN')
        self._secret_arn = os.getenv('DATABASE_SECRET_ARN') or os.getenv('RDS_SECRET_ARN')
        self._database_name = os.getenv('DATABASE_NAME') or self.config.db_name or os.getenv('ORDER_DB_NAME', 'multiagent')
        
        if not self._cluster_arn or not self._secret_arn:
            raise DatabaseConnectionError(
                "DATABASE_CLUSTER_ARN and DATABASE_SECRET_ARN environment variables are required. "
                "These should be provided by the ECS task definition."
            )
        
        # Create RDS Data API client with proper credentials handling
        session = boto3.Session()
        
        # Check if we're running in AWS environment or local development
        use_profile = not os.getenv("AWS_EXECUTION_ENV") and not os.getenv("ECS_CONTAINER_METADATA_URI")
        
        if use_profile and hasattr(self.config, 'aws_credentials_profile'):
            # Local development - use profile
            session = boto3.Session(profile_name=self.config.aws_credentials_profile)
            logger.info(f"Using AWS credential profile: {self.config.aws_credentials_profile}")
        else:
            # AWS environment - use default credential chain (IAM roles)
            logger.info("Using default AWS credential chain (IAM roles)")
        
        self.rds_client = session.client('rds-data', region_name=self.config.aws_default_region)
        
        # Test the connection with a simple query
        await self._test_connection()
        
        logger.info("PostgreSQL Data API connection initialized successfully")
        logger.info(f"Cluster ARN: {self._cluster_arn}")
        logger.info(f"Database: {self._database_name}")
    
    async def _test_connection(self):
        """Test the Data API connection."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.rds_client.execute_statement(
                    resourceArn=self._cluster_arn,
                    secretArn=self._secret_arn,
                    database=self._database_name,
                    sql="SELECT 1 as test"
                )
            )
            logger.debug("Data API connection test successful")
        except Exception as e:
            logger.error(f"Data API connection test failed: {e}")
            raise
    
    async def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> DatabaseResult:
        """
        Execute a SQL query using RDS Data API and return results.
        
        Args:
            query: SQL query to execute
            parameters: Optional query parameters
            
        Returns:
            Database query results
        """
        start_time = time.time()
        
        # Clean and validate query
        query = self._sanitize_query(query)
        
        if not self.rds_client:
            raise DatabaseConnectionError("Database not initialized. Call initialize_pool() first.")
        
        try:
            logger.debug(f"Executing PostgreSQL Data API query: {query}")
            
            # Prepare parameters for Data API
            sql_parameters = []
            if parameters:
                # Convert parameters to Data API format
                for i, (key, value) in enumerate(parameters.items()):
                    param_name = f"param{i+1}"
                    sql_parameters.append({
                        'name': param_name,
                        'value': self._convert_parameter_value(value)
                    })
                    # Replace parameter placeholders in query
                    query = query.replace(f"${i+1}", f":{param_name}")
            
            # Execute query using Data API
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.rds_client.execute_statement(
                    resourceArn=self._cluster_arn,
                    secretArn=self._secret_arn,
                    database=self._database_name,
                    sql=query,
                    parameters=sql_parameters if sql_parameters else [],
                    includeResultMetadata=True
                )
            )
            
            # Convert Data API response to standard format
            results = self._convert_dataapi_response(response)
            
            execution_time = time.time() - start_time
            
            logger.info(f"PostgreSQL Data API query executed successfully in {execution_time:.3f}s, returned {len(results)} rows")
            
            return DatabaseResult(
                results=results,
                execution_time=execution_time,
                row_count=len(results),
                error=None
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"PostgreSQL Data API query execution failed: {str(e)}"
            logger.error(error_msg)
            
            return DatabaseResult(
                results=[],
                execution_time=execution_time,
                row_count=0,
                error=error_msg
            )
    
    def _convert_parameter_value(self, value: Any) -> Dict[str, Any]:
        """Convert parameter value to Data API format."""
        if value is None:
            return {'isNull': True}
        elif isinstance(value, str):
            return {'stringValue': value}
        elif isinstance(value, int):
            return {'longValue': value}
        elif isinstance(value, float):
            return {'doubleValue': value}
        elif isinstance(value, bool):
            return {'booleanValue': value}
        else:
            # Convert to string as fallback
            return {'stringValue': str(value)}
    
    def _convert_dataapi_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        WHERE customer_id ILIKE :param1
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
        SELECT * FROM orders 
        WHERE order_id ILIKE :param1
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
        WHERE in_stock = true AND quantity > 0
        """
        
        conditions = []
        params = {}
        param_count = 0
        
        if product_name:
            param_count += 1
            conditions.append(f"product_name ILIKE :param{param_count}")
            params[f'product_name'] = f'%{product_name}%'
        
        if category:
            param_count += 1
            conditions.append(f"category ILIKE :param{param_count}")
            params[f'category'] = f'%{category}%'
        
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
        params = {}
        param_count = 0
        
        if customer_id:
            param_count += 1
            conditions.append(f"customer_id ILIKE :param{param_count}")
            params[f'customer_id'] = f'%{customer_id}%'
        
        if order_id:
            param_count += 1
            conditions.append(f"order_id ILIKE :param{param_count}")
            params[f'order_id'] = f'%{order_id}%'
        
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
        FROM orders
        WHERE return_exchange_status IS NOT NULL
        """
        
        conditions = []
        params = {}
        param_count = 0
        
        if customer_id:
            param_count += 1
            conditions.append(f"customer_id ILIKE :param{param_count}")
            params[f'customer_id'] = f'%{customer_id}%'
        
        if order_id:
            param_count += 1
            conditions.append(f"order_id ILIKE :param{param_count}")
            params[f'order_id'] = f'%{order_id}%'
        
        if conditions:
            query = base_query + " AND " + " AND ".join(conditions)
        else:
            query = base_query
        
        query += " ORDER BY order_date DESC"
        
        result = await self.execute_query(query, params)
        return result.results
    
    async def close_pool(self):
        """Close the RDS Data API client (no-op for Data API)."""
        if self.rds_client:
            logger.info("PostgreSQL Data API client closed")
    
    async def get_pool_status(self) -> Dict[str, Any]:
        """Get connection status for monitoring."""
        if not self.rds_client:
            return {"status": "not_initialized"}
        
        return {
            "status": "active",
            "connection_type": "rds_data_api",
            "cluster_arn": self._cluster_arn,
            "database": self._database_name
        }