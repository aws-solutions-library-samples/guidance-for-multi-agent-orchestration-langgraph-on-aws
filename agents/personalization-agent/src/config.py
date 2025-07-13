"""
Configuration management for the personalization agent service.
"""

import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class PersonalizationConfig:
    """Configuration class for Personalization Agent."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # AWS Configuration
        self.aws_default_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.aws_credentials_profile = os.getenv("AWS_CREDENTIALS_PROFILE")
        
        # AWS Bedrock Configuration
        self.bedrock_model_id = os.getenv(
            "BEDROCK_MODEL_ID", 
            "anthropic.claude-3-sonnet-20240229-v1:0"
        )
        self.bedrock_temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.1"))
        self.bedrock_max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "1000"))
        self.bedrock_timeout = int(os.getenv("BEDROCK_TIMEOUT", "15"))
        
        # Application Configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8004"))
        
        # Timeout Configuration
        self.http_timeout = int(os.getenv("HTTP_TIMEOUT", "30"))
        self.database_timeout = int(os.getenv("DATABASE_TIMEOUT", "10"))
        
        # Retry Configuration
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_backoff_factor = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
        
        # Knowledge Base Configuration
        self.browsing_history_knowledge_base_id = os.getenv("BROWSING_HISTORY_KNOWLEDGE_BASE_ID", "BROWSING_KB_DEFAULT")


def setup_logging(config: PersonalizationConfig):
    """Set up logging configuration."""
    level = getattr(logging, config.log_level, logging.INFO)
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Set up specific loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


# Create global config instance
config = PersonalizationConfig()

# Set up logging
setup_logging(config)