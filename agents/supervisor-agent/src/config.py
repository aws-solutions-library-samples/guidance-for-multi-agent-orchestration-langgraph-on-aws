"""
Configuration management for the supervisor agent service.
"""

from shared.config import SupervisorConfig, setup_logging

# Create global config instance
config = SupervisorConfig()

# Set up logging
setup_logging(config)