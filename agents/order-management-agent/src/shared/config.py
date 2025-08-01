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

        # AWS Bedrock Configuration - Claude 3.7 Sonnet Cross-Region Inference Profiles
        # Environment variable takes precedence, but default to Claude 3.7 Sonnet inference profile
        self.bedrock_model_id = os.getenv(
            "BEDROCK_MODEL_ID", self._get_default_haiku_35_inference_profile()
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

    def _get_default_claude_37_inference_profile(self) -> str:
        """
        Get the appropriate Claude 3.7 Sonnet cross-region inference profile based on AWS region.

        Returns:
            str: The inference profile ID for Claude 3.7 Sonnet
        """
        # Claude 3.7 Sonnet cross-region inference profiles by region
        claude_37_profiles = {
            # EU regions - all use the same EU inference profile (250 RPM)
            "eu-west-1": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "eu-central-1": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "eu-west-3": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "eu-north-1": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
            # US regions - all use the same US inference profile (250 RPM)
            "us-east-1": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us-east-2": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us-west-2": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        }

        # Get the inference profile for the current region
        region = self.aws_default_region
        if region in claude_37_profiles:
            profile_id = claude_37_profiles[region]
            print(
                f"✅ Order Management Agent: Using Claude 3.7 Sonnet cross-region inference profile for {region}: {profile_id}"
            )
            print(
                f"   Quota: 250 requests/minute (125x improvement over previous Claude 3 Sonnet)"
            )
            return profile_id
        else:
            # Fallback to standard Claude 3.7 Sonnet for unsupported regions
            fallback_model = "anthropic.claude-3-7-sonnet-20250219-v1:0"
            print(
                f"⚠️  Order Management Agent: Region {region} not configured for Claude 3.7 Sonnet cross-region profiles"
            )
            print(f"   Falling back to standard model: {fallback_model}")
            print(f"   Note: This will have much lower quota (~5 RPM vs 250 RPM)")
            return fallback_model

    def _get_default_haiku_35_inference_profile(self) -> str:
        """
        Get the appropriate Claude 3.7 Sonnet cross-region inference profile based on AWS region.

        Returns:
            str: The inference profile ID for Claude 3.7 Sonnet
        """
        # Claude 3.7 Sonnet cross-region inference profiles by region
        claude_35_profiles = {
            # EU regions - all use the same EU inference profile (250 RPM)
            "eu-west-1": "eu.anthropic.claude-3-5-haiku-20241022-v1:0",
            "eu-central-1": "eu.anthropic.claude-3-5-haiku-20241022-v1:0",
            "eu-west-3": "eu.anthropic.claude-3-5-haiku-20241022-v1:0",
            "eu-north-1": "eu.anthropic.claude-3-5-haiku-20241022-v1:0",
            # US regions - all use the same US inference profile (250 RPM)
            "us-east-1": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            "us-east-2": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
            "us-west-2": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        }

        # Get the inference profile for the current region
        region = self.aws_default_region
        if region in claude_35_profiles:
            profile_id = claude_35_profiles[region]
            print(
                f"✅ Order Management Agent: Using Claude 3.7 Sonnet cross-region inference profile for {region}: {profile_id}"
            )
            print(
                f"   Quota: 250 requests/minute (125x improvement over previous Claude 3 Sonnet)"
            )
            return profile_id
        else:
            # Fallback to standard Claude 3.7 Sonnet for unsupported regions
            fallback_model = "anthropic.claude-3-7-sonnet-20250219-v1:0"
            print(
                f"⚠️  Order Management Agent: Region {region} not configured for Claude 3.7 Sonnet cross-region profiles"
            )
            print(f"   Falling back to standard model: {fallback_model}")
            print(f"   Note: This will have much lower quota (~5 RPM vs 250 RPM)")
            return fallback_model

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
            "ORDER_AGENT_URL", "http://order-management-agent:8000"
        )
        self.product_agent_url = os.getenv(
            "PRODUCT_AGENT_URL", "http://product-recommendation-agent:8000"
        )
        self.troubleshooting_agent_url = os.getenv(
            "TROUBLESHOOTING_AGENT_URL", "http://troubleshooting-agent:8000"
        )
        self.personalization_agent_url = os.getenv(
            "PERSONALIZATION_AGENT_URL", "http://personalization-agent:8000"
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
        if all(
            [self.db_host, self.db_port, self.db_name, self.db_user, self.db_password]
        ):
            return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return None


class OrderAgentConfig(DatabaseConfig):
    """Configuration specific to the order management agent."""

    def __init__(self):
        """Initialize order agent configuration."""
        super().__init__()

        self.service_name = "order-management-agent"

        # Order Management Database - PostgreSQL with DataAPI
        self.db_name = os.getenv("ORDER_DB_NAME", "multiagent")
        
        # RDS DataAPI configuration - check both naming conventions
        self.rds_cluster_arn = os.getenv("DATABASE_CLUSTER_ARN") or os.getenv("RDS_CLUSTER_ARN")
        self.rds_secret_arn = os.getenv("DATABASE_SECRET_ARN") or os.getenv("RDS_SECRET_ARN")
        
        # Legacy connection parameters (kept for compatibility)
        self.db_host = os.getenv("ORDER_DB_HOST", "localhost")
        self.db_port = int(os.getenv("ORDER_DB_PORT", "5432"))
        self.db_user = os.getenv("ORDER_DB_USER", "postgres")
        self.db_password = os.getenv("ORDER_DB_PASSWORD", "password")
        
        # DataAPI query timeout
        self.db_query_timeout = int(os.getenv("DB_QUERY_TIMEOUT", "15"))
    
    def is_dataapi_configured(self) -> bool:
        """Check if RDS Data API is properly configured."""
        return bool(self.rds_cluster_arn and self.rds_secret_arn)
    
    def get_dataapi_config(self) -> Dict[str, str]:
        """Get RDS Data API configuration."""
        return {
            "cluster_arn": self.rds_cluster_arn,
            "secret_arn": self.rds_secret_arn,
            "database": self.db_name,
            "region": self.aws_default_region
        }


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
        ],
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
        os.environ.get("AWS_ACCESS_KEY_ID")
        and os.environ.get("AWS_SECRET_ACCESS_KEY")
        or os.path.exists(os.path.expanduser("~/.aws/credentials"))
        or os.environ.get("AWS_PROFILE")
    )


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass
