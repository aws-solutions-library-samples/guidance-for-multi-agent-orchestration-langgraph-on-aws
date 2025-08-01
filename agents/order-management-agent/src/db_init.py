"""
Database initialization for the order management agent.

This module handles database initialization on startup, ensuring the database
schema is created and test data is available when needed.
Uses AWS RDS Data API for database connectivity.
"""

import logging
import asyncio
from typing import Dict, Any, Optional

from postgresql_schema import PostgreSQLSchemaManager, PostgreSQLSchemaError

logger = logging.getLogger(__name__)


class DatabaseInitializationError(Exception):
    """Raised when database initialization fails."""
    pass


class DatabaseInitializer:
    """Handles database initialization on startup using RDS Data API."""
    
    def __init__(self, config_obj=None):
        """
        Initialize the database initializer.
        
        Args:
            config_obj: Configuration object with database settings
        """
        self.config = config_obj
        self.schema_manager = PostgreSQLSchemaManager(config_obj)
        
    async def initialize_database(self, include_test_data: bool = True) -> Dict[str, Any]:
        """
        Initialize database schema and data if needed.
        This operation is idempotent - safe to run multiple times.
        
        Args:
            include_test_data: Whether to insert test data for development
            
        Returns:
            Dictionary with initialization results
            
        Raises:
            DatabaseInitializationError: If initialization fails
        """
        try:
            logger.info("Starting database initialization...")
            
            initialization_result = {
                'schema_created': False,
                'test_data_inserted': False,
                'verification_passed': False,
                'error': None
            }
            
            # Initialize schema manager
            await self.schema_manager.initialize()
            
            # Check database connectivity
            await self._check_database_connectivity()
            
            # Create schema (idempotent)
            try:
                schema_created = await self.schema_manager.create_schema()
                initialization_result['schema_created'] = schema_created
                logger.info("Database schema creation completed")
            except Exception as e:
                logger.error(f"Schema creation failed: {e}")
                initialization_result['error'] = f"Schema creation failed: {str(e)}"
                raise
            
            # Insert test data if requested (idempotent)
            if include_test_data:
                try:
                    test_data_inserted = await self.schema_manager.insert_test_data()
                    initialization_result['test_data_inserted'] = test_data_inserted
                    logger.info("Test data insertion completed")
                except Exception as e:
                    logger.error(f"Test data insertion failed: {e}")
                    initialization_result['error'] = f"Test data insertion failed: {str(e)}"
                    raise
            
            # Verify schema
            try:
                verification_result = await self.schema_manager.verify_schema()
                initialization_result['verification_passed'] = verification_result['schema_valid']
                initialization_result['verification_details'] = verification_result
                logger.info("Database schema verification completed")
            except Exception as e:
                logger.warning(f"Schema verification failed: {e}")
                initialization_result['verification_passed'] = False
                initialization_result['error'] = f"Schema verification failed: {str(e)}"
                # Don't raise here - verification failure is not critical
            
            logger.info("Database initialization completed successfully")
            return initialization_result
            
        except PostgreSQLSchemaError as e:
            error_msg = f"Database schema initialization failed: {str(e)}"
            logger.error(error_msg)
            raise DatabaseInitializationError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg)
            raise DatabaseInitializationError(error_msg) from e
    
    async def _check_database_connectivity(self) -> None:
        """
        Check if database is accessible and responsive.
        
        Raises:
            DatabaseInitializationError: If database is not accessible
        """
        try:
            # Simple connectivity test using schema manager
            response = await self.schema_manager._execute_sql("SELECT 1")
            
            # Check if we got a valid response
            if 'records' not in response or not response['records']:
                raise DatabaseInitializationError("Database connectivity test failed - no response")
            
            # Verify the result
            first_record = response['records'][0]
            if not first_record or 'longValue' not in first_record[0] or first_record[0]['longValue'] != 1:
                raise DatabaseInitializationError("Database connectivity test failed - invalid response")
            
            logger.debug("Database connectivity verified")
            
        except Exception as e:
            error_msg = f"Database connectivity check failed: {str(e)}"
            logger.error(error_msg)
            raise DatabaseInitializationError(error_msg) from e
    
    async def check_database_health(self) -> Dict[str, Any]:
        """
        Comprehensive health check for database connectivity and schema.
        
        Returns:
            Dictionary with health check results
        """
        health_result = {
            'healthy': False,
            'connectivity': False,
            'schema_valid': False,
            'tables_exist': {},
            'error': None
        }
        
        try:
            # Check connectivity
            await self._check_database_connectivity()
            health_result['connectivity'] = True
            
            # Check if required tables exist
            required_tables = ['customers', 'inventory', 'orders']
            for table in required_tables:
                exists = await self.schema_manager.check_table_exists(table)
                health_result['tables_exist'][table] = exists
            
            # All tables must exist for schema to be valid
            all_tables_exist = all(health_result['tables_exist'].values())
            health_result['schema_valid'] = all_tables_exist
            
            # Overall health status
            health_result['healthy'] = health_result['connectivity'] and health_result['schema_valid']
            
            if health_result['healthy']:
                logger.info("Database health check passed")
            else:
                logger.warning("Database health check failed - some issues detected")
            
            return health_result
            
        except Exception as e:
            error_msg = f"Database health check failed: {str(e)}"
            logger.error(error_msg)
            health_result['error'] = error_msg
            return health_result
    
    async def get_database_status(self) -> Dict[str, Any]:
        """
        Get detailed database status information.
        
        Returns:
            Dictionary with database status details
        """
        try:
            status = {
                'connection_type': 'rds_data_api',
                'cluster_arn': self.schema_manager._cluster_arn,
                'database_name': self.schema_manager._database_name,
                'tables': {},
                'health': await self.check_database_health()
            }
            
            # Get detailed table information
            required_tables = ['customers', 'inventory', 'orders']
            for table in required_tables:
                table_info = await self.schema_manager.get_table_info(table)
                status['tables'][table] = table_info
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get database status: {e}")
            return {
                'error': str(e),
                'health': {'healthy': False, 'error': str(e)}
            }
    
    async def get_initialization_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the database initialization status.
        
        Returns:
            Dictionary with initialization summary
        """
        try:
            health_check = await self.check_database_health()
            
            summary = {
                'database_ready': health_check['healthy'],
                'connectivity': health_check['connectivity'],
                'schema_valid': health_check['schema_valid'],
                'tables_status': health_check['tables_exist'],
                'initialization_required': not health_check['healthy']
            }
            
            if health_check['error']:
                summary['error'] = health_check['error']
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get initialization summary: {e}")
            return {
                'database_ready': False,
                'initialization_required': True,
                'error': str(e)
            }
    
    async def is_database_ready(self) -> bool:
        """
        Quick check to see if the database is ready for use.
        
        Returns:
            True if database is ready, False otherwise
        """
        try:
            summary = await self.get_initialization_summary()
            return summary['database_ready']
        except Exception as e:
            logger.error(f"Failed to check if database is ready: {e}")
            return False
    
    async def reset_test_data(self) -> bool:
        """
        Reset test data by clearing and reinserting it.
        WARNING: This will delete all existing data!
        
        Returns:
            True if reset was successful
            
        Raises:
            DatabaseInitializationError: If reset fails
        """
        try:
            logger.warning("Resetting test data - this will delete all existing data!")
            
            # Clear existing data (in reverse order due to potential foreign keys)
            await self.schema_manager._execute_sql("DELETE FROM orders")
            await self.schema_manager._execute_sql("DELETE FROM inventory")
            await self.schema_manager._execute_sql("DELETE FROM customers")
            
            logger.info("Existing data cleared")
            
            # Reinsert test data
            await self.schema_manager.insert_test_data()
            
            logger.info("Test data reset completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to reset test data: {str(e)}"
            logger.error(error_msg)
            raise DatabaseInitializationError(error_msg) from e
    
    async def validate_schema_compatibility(self) -> Dict[str, Any]:
        """
        Validate that the current schema is compatible with the application.
        
        Returns:
            Dictionary with compatibility validation results
        """
        try:
            validation_result = {
                'compatible': True,
                'issues': [],
                'table_checks': {}
            }
            
            # Define expected schema structure
            expected_tables = {
                'customers': [
                    'customer_id', 'first_name', 'last_name', 'email', 
                    'phone', 'address', 'city', 'state', 'zip_code', 'created_date'
                ],
                'inventory': [
                    'product_id', 'product_name', 'category', 'quantity', 
                    'in_stock', 'reorder_threshold', 'reorder_quantity', 
                    'last_restock_date', 'price_per_unit'
                ],
                'orders': [
                    'order_id', 'customer_id', 'product_id', 'product_name',
                    'order_status', 'shipping_status', 'return_exchange_status',
                    'order_date', 'delivery_date', 'quantity', 'price_per_unit', 'total_amount'
                ]
            }
            
            # Check each table
            for table_name, expected_columns in expected_tables.items():
                table_info = await self.schema_manager.get_table_info(table_name)
                
                if not table_info:
                    validation_result['compatible'] = False
                    validation_result['issues'].append(f"Table '{table_name}' does not exist")
                    validation_result['table_checks'][table_name] = {'exists': False}
                    continue
                
                # Check columns
                actual_columns = [col['column_name'] for col in table_info['columns']]
                missing_columns = set(expected_columns) - set(actual_columns)
                
                table_check = {
                    'exists': True,
                    'row_count': table_info['row_count'],
                    'missing_columns': list(missing_columns),
                    'extra_columns': list(set(actual_columns) - set(expected_columns))
                }
                
                if missing_columns:
                    validation_result['compatible'] = False
                    validation_result['issues'].append(
                        f"Table '{table_name}' missing columns: {', '.join(missing_columns)}"
                    )
                
                validation_result['table_checks'][table_name] = table_check
            
            if validation_result['compatible']:
                logger.info("Schema compatibility validation passed")
            else:
                logger.warning(f"Schema compatibility issues found: {validation_result['issues']}")
            
            return validation_result
            
        except Exception as e:
            error_msg = f"Schema compatibility validation failed: {str(e)}"
            logger.error(error_msg)
            return {
                'compatible': False,
                'error': error_msg,
                'issues': [error_msg]
            }