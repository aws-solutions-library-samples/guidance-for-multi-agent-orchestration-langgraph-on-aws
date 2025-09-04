"""
Configuration management for the troubleshooting agent service.
"""

import os
import logging
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class TroubleshootingConfig:
    """Configuration class for Troubleshooting Agent."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # AWS Configuration
        self.aws_default_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.aws_credentials_profile = os.getenv("AWS_CREDENTIALS_PROFILE")

        # AWS Bedrock Configuration - Claude 3.7 Sonnet Cross-Region Inference Profiles
        # Environment variable takes precedence, but default to Claude 3.7 Sonnet inference profile
        self.bedrock_model_id = os.getenv(
            "BEDROCK_MODEL_ID", self._get_default_haiku_35_inference_profile()
        )
        self.bedrock_temperature = float(os.getenv("BEDROCK_TEMPERATURE", "0.1"))
        self.bedrock_max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", "1000"))
        self.bedrock_timeout = int(os.getenv("BEDROCK_TIMEOUT", "15"))

        # Application Configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8003"))

        # Timeout Configuration
        self.http_timeout = int(os.getenv("HTTP_TIMEOUT", "30"))
        self.database_timeout = int(os.getenv("DATABASE_TIMEOUT", "10"))

        # Retry Configuration
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_backoff_factor = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))

        # Knowledge Base Configuration
        self.faq_knowledge_base_id = os.getenv(
            "FAQ_KNOWLEDGE_BASE_ID", "FAQ_KB_DEFAULT"
        )
        self.troubleshooting_knowledge_base_id = os.getenv(
            "TROUBLESHOOTING_KNOWLEDGE_BASE_ID", "TROUBLESHOOT_KB_DEFAULT"
        )
         # Session persistence configuration
        self.enable_session_persistence = os.getenv("ENABLE_SESSION_PERSISTENCE", "true").lower() == "true"
        self.dynamodb_table_name = os.getenv("DYNAMODB_TABLE_NAME", "langgraph-checkpoints")
        self.dynamodb_endpoint_url = os.getenv("DYNAMODB_ENDPOINT_URL")  # For local development

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
                f"✅ Troubleshooting Agent: Using Claude 3.7 Sonnet cross-region inference profile for {region}: {profile_id}"
            )
            print(
                f"   Quota: 250 requests/minute (125x improvement over previous Claude 3 Sonnet)"
            )
            return profile_id
        else:
            # Fallback to standard Claude 3.7 Sonnet for unsupported regions
            fallback_model = "anthropic.claude-3-7-sonnet-20250219-v1:0"
            print(
                f"⚠️  Troubleshooting Agent: Region {region} not configured for Claude 3.7 Sonnet cross-region profiles"
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


def setup_logging(config: TroubleshootingConfig):
    """Set up logging configuration."""
    level = getattr(logging, config.log_level, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )

    # Set up specific loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


# Create global config instance
config = TroubleshootingConfig()

# Set up logging
setup_logging(config)
