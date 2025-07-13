"""
Shared configuration management for all agent services.

This module provides centralized configuration management using environment
variables and Pydantic settings validation.
"""

import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class BaseConfig:
    """Base configuration class with common settings."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # AWS Configuration
        self.aws_default_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.aws_credentials_profile = os.getenv("AWS_CREDENTIALS_PROFILE", "default")
        
        # AWS Bedrock Configuration
        self.bedrock_model_id = os.getenv(
            "BEDROCK_MODEL_ID", 
            "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.bedrock_temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.7"))
        self.bedrock_max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "1000"))
        self.bedrock_timeout = int(os.getenv("BEDROCK_TIMEOUT", "15"))
        
        # Application Configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        
        # Timeout Configuration
        self.http_timeout = int(os.getenv("HTTP_TIMEOUT", "30"))
        self.database_timeout = int(os.getenv("DATABASE_TIMEOUT", "10"))
        
        # Retry Configuration
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_backoff_factor = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
        
        # Health Check Configuration
        self.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
        self.health_check_timeout = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))
        
        # Session Configuration
        self.session_timeout = int(os.getenv("SESSION_TIMEOUT", "3600"))
        self.max_conversation_history = int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))
        
        # Performance Configuration
        self.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "100"))
        self.worker_processes = int(os.getenv("WORKER_PROCESSES", "1"))
        
        # Validate configuration
        self._validate()
    
    def _validate(self):
        """Validate configuration values."""
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        
        # Validate temperature
        if not 0 <= self.bedrock_temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")


class SupervisorConfig(BaseConfig):
    """Configuration specific to the supervisor agent."""
    
    def __init__(self):
        """Initialize supervisor-specific configuration."""
        super().__init__()
        
        self.service_name = "supervisor-agent"
        
        # Sub-agent service URLs
        self.order_agent_url = os.getenv(
            "ORDER_AGENT_URL", 
            "http://order-management-agent:8000"
        )
        self.product_agent_url = os.getenv(
            "PRODUCT_AGENT_URL", 
            "http://product-recommendation-agent:8000"
        )
        self.troubleshooting_agent_url = os.getenv(
            "TROUBLESHOOTING_AGENT_URL", 
            "http://troubleshooting-agent:8000"
        )
        self.personalization_agent_url = os.getenv(
            "PERSONALIZATION_AGENT_URL", 
            "http://personalization-agent:8000"
        )
    
    def get_agent_urls(self) -> Dict[str, str]:
        """Get mapping of agent types to their URLs."""
        return {
            "order_management": self.order_agent_url,
            "product_recommendation": self.product_agent_url,
            "troubleshooting": self.troubleshooting_agent_url,
            "personalization": self.personalization_agent_url,
        }


class DatabaseConfig(BaseConfig):
    """Database configuration for agents that need database access."""
    
    def __init__(self):
        """Initialize database configuration."""
        super().__init__()
        
        # Database connection settings (will be used by specific agents)
        self.db_host: Optional[str] = None
        self.db_port: Optional[int] = None
        self.db_name: Optional[str] = None
        self.db_user: Optional[str] = None
        self.db_password: Optional[str] = None
    
    def get_database_url(self) -> Optional[str]:
        """Construct database URL from components."""
        if all([self.db_host, self.db_port, self.db_name, self.db_user, self.db_password]):
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return None


class OrderAgentConfig(DatabaseConfig):
    """Configuration specific to the order management agent."""
    
    def __init__(self):
        """Initialize order agent configuration."""
        super().__init__()
        
        self.service_name = "order-management-agent"
        
        # Order Management Database
        self.db_host = os.getenv("ORDER_DB_HOST", "localhost")
        self.db_port = int(os.getenv("ORDER_DB_PORT", "5432"))
        self.db_name = os.getenv("ORDER_DB_NAME", "order_management")
        self.db_user = os.getenv("ORDER_DB_USER", "postgres")
        self.db_password = os.getenv("ORDER_DB_PASSWORD", "password")


class ProductAgentConfig(DatabaseConfig):
    """Configuration specific to the product recommendation agent."""
    
    def __init__(self):
        """Initialize product agent configuration."""
        super().__init__()
        
        self.service_name = "product-recommendation-agent"
        
        # Product Recommendation Database
        self.db_host = os.getenv("PRODUCT_DB_HOST", "localhost")
        self.db_port = int(os.getenv("PRODUCT_DB_PORT", "5432"))
        self.db_name = os.getenv("PRODUCT_DB_NAME", "prod_rec")
        self.db_user = os.getenv("PRODUCT_DB_USER", "postgres")
        self.db_password = os.getenv("PRODUCT_DB_PASSWORD", "password")
        
        # Knowledge Base Configuration
        self.knowledge_base_endpoint = os.getenv("KNOWLEDGE_BASE_ENDPOINT")
        self.knowledge_base_api_key = os.getenv("KNOWLEDGE_BASE_API_KEY")


class TroubleshootingAgentConfig(BaseConfig):
    """Configuration specific to the troubleshooting agent."""
    
    def __init__(self):
        """Initialize troubleshooting agent configuration."""
        super().__init__()
        
        self.service_name = "troubleshooting-agent"
        
        # Knowledge Base Configuration
        self.knowledge_base_endpoint = os.getenv("KNOWLEDGE_BASE_ENDPOINT")
        self.knowledge_base_api_key = os.getenv("KNOWLEDGE_BASE_API_KEY")


class PersonalizationAgentConfig(DatabaseConfig):
    """Configuration specific to the personalization agent."""
    
    def __init__(self):
        """Initialize personalization agent configuration."""
        super().__init__()
        
        self.service_name = "personalization-agent"
        
        # Personalization Database
        self.db_host = os.getenv("PERSONALIZATION_DB_HOST", "localhost")
        self.db_port = int(os.getenv("PERSONALIZATION_DB_PORT", "5432"))
        self.db_name = os.getenv("PERSONALIZATION_DB_NAME", "personalization")
        self.db_user = os.getenv("PERSONALIZATION_DB_USER", "postgres")
        self.db_password = os.getenv("PERSONALIZATION_DB_PASSWORD", "password")
        
        # Knowledge Base Configuration
        self.knowledge_base_endpoint = os.getenv("KNOWLEDGE_BASE_ENDPOINT")
        self.knowledge_base_api_key = os.getenv("KNOWLEDGE_BASE_API_KEY")


def setup_logging(config: BaseConfig) -> None:
    """Set up logging configuration based on config settings."""
    
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Set specific loggers
    if not config.debug:
        # Reduce noise from external libraries in production
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)


def get_config_for_service(service_name: str) -> BaseConfig:
    """Get appropriate configuration class for a given service."""
    
    config_mapping = {
        "supervisor-agent": SupervisorConfig,
        "order-management-agent": OrderAgentConfig,
        "product-recommendation-agent": ProductAgentConfig,
        "troubleshooting-agent": TroubleshootingAgentConfig,
        "personalization-agent": PersonalizationAgentConfig,
    }
    
    config_class = config_mapping.get(service_name, BaseConfig)
    return config_class()


def validate_aws_credentials() -> bool:
    """Validate that AWS credentials are available."""
    
    # Check if credentials are set via environment or AWS config
    return bool(
        os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")
        or os.path.exists(os.path.expanduser("~/.aws/credentials"))
        or os.environ.get("AWS_PROFILE")
    )


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass