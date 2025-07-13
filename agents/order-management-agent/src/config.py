"""
Configuration management for the order management agent service.
"""

from shared.config import OrderAgentConfig, setup_logging

# Create global config instance
config = OrderAgentConfig()

# Set up logging
setup_logging(config)