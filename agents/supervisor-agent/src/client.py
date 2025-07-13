"""
HTTP client for communicating with sub-agent services.

This module provides the interface for the supervisor agent to communicate
with specialized agent services via HTTP APIs.
"""

import logging
import asyncio
import httpx
import os
import boto3
from typing import Dict, List, Optional, Any

from shared.models import AgentRequest, AgentResponse, AgentType
from config import config

logger = logging.getLogger(__name__)


class AgentCommunicationError(Exception):
    """Raised when communication with an agent fails."""

    pass


class SubAgentClient:
    """Client for communicating with sub-agent services."""

    def __init__(self):
        """Initialize the sub-agent client with service URLs and endpoints."""
        # Check if running in ECS environment
        self.is_ecs_environment = self._is_ecs_environment()

        # Default local configuration for development
        self.local_agent_configs = {
            "order_management": {
                "url": "http://localhost:8001",
                "endpoint": "/process",
            },
            "product_recommendation": {
                "url": "http://localhost:8002",
                "endpoint": "/recommend",
            },
            "troubleshooting": {
                "url": "http://localhost:8004",
                "endpoint": "/troubleshoot",
            },
            "personalization": {
                "url": "http://localhost:8003",
                "endpoint": "/personalize",
            },
        }

        # Initialize agent configs based on environment
        self.agent_configs = {}
        self._initialize_agent_configs()

        self.timeout = 120.0
        self.max_retries = 3

    def _is_ecs_environment(self) -> bool:
        """Check if running in ECS environment."""
        # Check for ECS metadata endpoint or environment variables
        return (
            os.getenv("ECS_CONTAINER_METADATA_URI_V4") is not None
            or os.getenv("ECS_CONTAINER_METADATA_URI") is not None
            or os.getenv("AWS_EXECUTION_ENV") == "AWS_ECS_FARGATE"
            or os.getenv("ENVIRONMENT") in ["prod", "staging", "ecs"]
        )

    def _initialize_agent_configs(self):
        """Initialize agent configurations based on environment."""
        if self.is_ecs_environment:
            logger.info(
                "Running in ECS environment - using Cloud Map service discovery"
            )
            self._load_cloudmap_configs()
        else:
            logger.info("Running in local environment - using localhost endpoints")
            self.agent_configs = self.local_agent_configs.copy()

    def _load_cloudmap_configs(self):
        """Load agent configurations from Cloud Map service discovery."""
        try:
            # First, try to get endpoints from environment variables (fastest)
            env_configs = {
                "order_management": {
                    "url": f"http://{os.getenv('ORDER_MANAGEMENT_SERVICE', '')}",
                    "endpoint": "/process",
                    "service_name": "order-management",
                },
                "product_recommendation": {
                    "url": f"http://{os.getenv('PRODUCT_RECOMMENDATION_SERVICE', '')}",
                    "endpoint": "/recommend",
                    "service_name": "product-recommendation",
                },
                "troubleshooting": {
                    "url": f"http://{os.getenv('TROUBLESHOOTING_SERVICE', '')}",
                    "endpoint": "/troubleshoot",
                    "service_name": "troubleshooting",
                },
                "personalization": {
                    "url": f"http://{os.getenv('PERSONALIZATION_SERVICE', '')}",
                    "endpoint": "/personalize",
                    "service_name": "personalization",
                },
            }

            self.agent_configs = {}

            # Process each agent configuration
            for agent_type, config in env_configs.items():
                env_service = os.getenv(
                    config["service_name"].upper().replace("-", "_") + "_SERVICE"
                )

                if env_service:
                    # Use environment variable
                    self.agent_configs[agent_type] = {
                        "url": f"http://{env_service}",
                        "endpoint": config["endpoint"],
                    }
                    logger.info(
                        f"Using environment variable for {agent_type}: {env_service}"
                    )
                else:
                    # Fallback to Cloud Map API discovery
                    logger.info(
                        f"Environment variable not found for {agent_type}, trying Cloud Map API discovery"
                    )
                    discovered_url = self._discover_service_via_cloudmap(
                        config["service_name"]
                    )

                    if discovered_url:
                        self.agent_configs[agent_type] = {
                            "url": discovered_url,
                            "endpoint": config["endpoint"],
                        }
                        logger.info(
                            f"Discovered {agent_type} via Cloud Map API: {discovered_url}"
                        )
                    else:
                        # Final fallback to DNS-based service discovery
                        dns_url = f"http://{config['service_name']}.multi-agent.local:{self._get_default_port(agent_type)}"
                        self.agent_configs[agent_type] = {
                            "url": dns_url,
                            "endpoint": config["endpoint"],
                        }
                        logger.info(f"Using DNS fallback for {agent_type}: {dns_url}")

            logger.info("Loaded agent configurations from Cloud Map service discovery")
            for agent_type, config in self.agent_configs.items():
                logger.info(f"{agent_type}: {config['url']}")

        except Exception as e:
            logger.error(f"Failed to load Cloud Map configurations: {e}")
            logger.info("Falling back to localhost configurations")
            self.agent_configs = self.local_agent_configs.copy()

    def _get_default_port(self, agent_type: str) -> int:
        """Get default port for an agent type."""
        port_mapping = {
            "order_management": 8001,
            "product_recommendation": 8002,
            "troubleshooting": 8004,
            "personalization": 8003,
        }
        return port_mapping.get(agent_type, 8000)

    def _discover_service_via_cloudmap(self, service_name: str) -> Optional[str]:
        """
        Discover service endpoint using AWS Cloud Map API.

        Args:
            service_name: Name of the service to discover

        Returns:
            Service endpoint URL or None if not found
        """
        try:
            client = boto3.client("servicediscovery")

            # Discover instances for the service
            response = client.discover_instances(
                NamespaceName="multi-agent.local",
                ServiceName=service_name,
                MaxResults=1,
                HealthStatus="HEALTHY",
            )

            instances = response.get("Instances", [])
            if instances:
                instance = instances[0]
                ip_address = instance.get("Attributes", {}).get("AWS_INSTANCE_IPV4")
                port = instance.get("Attributes", {}).get("AWS_INSTANCE_PORT")

                if ip_address and port:
                    return f"http://{ip_address}:{port}"

        except Exception as e:
            logger.warning(
                f"Failed to discover service {service_name} via Cloud Map API: {e}"
            )

        return None

    def get_agent_config_info(self) -> Dict[str, Any]:
        """Get information about current agent configuration."""
        return {
            "environment": "ECS" if self.is_ecs_environment else "Local",
            "service_discovery": (
                "Cloud Map" if self.is_ecs_environment else "Localhost"
            ),
            "agent_configs": {
                agent_type: config["url"]
                for agent_type, config in self.agent_configs.items()
            },
        }

    async def call_agent(self, agent_type: str, request: AgentRequest):
        """
        Call a specific agent service.

        Args:
            agent_type: Type of agent to call
            request: Request to send to the agent

        Returns:
            Agent response or None if failed

        Raises:
            AgentCommunicationError: If communication fails
        """
        if agent_type not in self.agent_configs:
            raise AgentCommunicationError(f"Unknown agent type: {agent_type}")

        agent_config = self.agent_configs[agent_type]
        agent_url = agent_config["url"]
        endpoint = agent_config["endpoint"]
        full_url = f"{agent_url}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:

                logger.info(f"Calling {agent_type} agent at {full_url}")

                # Convert AgentRequest to agent-specific request format
                agent_request_data = self._convert_to_agent_request(agent_type, request)
                print(f"Request data: {agent_request_data}")

                try:
                    print(f"Making POST request to {full_url}")
                    response = await client.post(full_url, json=agent_request_data)
                    print(f"POST request completed successfully")

                except Exception as post_error:
                    print(f"POST request failed with error: {post_error}")
                    print(f"Error type: {type(post_error).__name__}")
                    raise post_error

                print(f"HTTP Response: {response.status_code} {response.reason_phrase}")
                print(f"Response headers: {dict(response.headers)}")

                if response.status_code != 200:
                    response_text = response.text
                    print(f"Error response body: {response_text}")
                    logger.error(
                        f"Agent {agent_type} returned status {response.status_code}: {response_text}"
                    )

                response.raise_for_status()
                response_data = response.json()

                # Return raw response data for debugging - no type conversion
                logger.info(f"Received response from {agent_type} agent")
                print(f"Raw response from {agent_type}: {response_data}")

                return response_data

        except Exception as e:
            logger.error(f"Failed to call {agent_type} agent: {e}")
            raise AgentCommunicationError(
                f"Failed to communicate with {agent_type} agent: {e}"
            )

    async def call_multiple_agents(
        self, agent_requests: List[tuple[str, AgentRequest]]
    ):
        """
        Call multiple agents in parallel.

        Args:
            agent_requests: List of (agent_type, request) tuples

        Returns:
            Dictionary mapping agent types to their responses
        """
        logger.info(f"Calling {len(agent_requests)} agents in parallel")

        # Create tasks for parallel execution
        tasks = []
        agent_types = []

        for agent_type, request in agent_requests:
            task = asyncio.create_task(self._safe_call_agent(agent_type, request))
            tasks.append(task)
            agent_types.append(agent_type)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(results)

        # Process results
        responses = {}
        for agent_type, result in zip(agent_types, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent_type} failed with exception: {result}")
                responses[agent_type] = None
            else:
                responses[agent_type] = result

        return responses

    async def _safe_call_agent(self, agent_type: str, request: AgentRequest):
        """
        Safely call an agent, handling exceptions.

        Args:
            agent_type: Type of agent to call
            request: Request to send

        Returns:
            Raw agent response or None if failed
        """
        try:
            return await self.call_agent(agent_type, request)
        except Exception as e:
            logger.error(f"Safe call to {agent_type} failed: {e}")
            return None

    def refresh_service_discovery(self):
        """Refresh service discovery configurations."""
        if self.is_ecs_environment:
            logger.info("Refreshing Cloud Map service discovery")
            self._load_cloudmap_configs()
        else:
            logger.info("Local environment - no refresh needed")

    def discover_specific_service(self, agent_type: str) -> Optional[str]:
        """
        Discover a specific service endpoint using Cloud Map API.

        Args:
            agent_type: Type of agent to discover

        Returns:
            Service URL or None if not found
        """
        if not self.is_ecs_environment:
            logger.info(f"Not in ECS environment, using local config for {agent_type}")
            return self.local_agent_configs.get(agent_type, {}).get("url")

        service_name_mapping = {
            "order_management": "order-management",
            "product_recommendation": "product-recommendation",
            "troubleshooting": "troubleshooting",
            "personalization": "personalization",
        }

        service_name = service_name_mapping.get(agent_type)
        if not service_name:
            logger.error(f"Unknown agent type: {agent_type}")
            return None

        # Try Cloud Map API discovery
        discovered_url = self._discover_service_via_cloudmap(service_name)
        if discovered_url:
            logger.info(f"Discovered {agent_type} via Cloud Map API: {discovered_url}")
            return discovered_url

        # Fallback to DNS
        default_port = self._get_default_port(agent_type)
        dns_url = f"http://{service_name}.multi-agent.local:{default_port}"
        logger.info(f"Using DNS fallback for {agent_type}: {dns_url}")
        return dns_url

    async def check_agent_health(self, agent_type: str) -> bool:
        """
        Check if an agent service is healthy.

        Args:
            agent_type: Type of agent to check

        Returns:
            True if agent is healthy, False otherwise
        """
        if agent_type not in self.agent_configs:
            return False

        agent_url = self.agent_configs[agent_type]["url"]

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:

                response = await client.get(f"{agent_url}/health")
                response.raise_for_status()
                response_data = response.json()

                is_healthy = response_data.get("status") == "healthy"
                logger.info(
                    f"Health check for {agent_type} at {agent_url}: {'healthy' if is_healthy else 'unhealthy'}"
                )
                return is_healthy

        except Exception as e:
            logger.warning(f"Health check failed for {agent_type} at {agent_url}: {e}")
            return False

    async def check_all_agents_health(self) -> Dict[str, bool]:
        """
        Check health of all agent services.

        Returns:
            Dictionary mapping agent types to their health status
        """
        health_checks = []
        agent_types = list(self.agent_configs.keys())

        for agent_type in agent_types:
            task = asyncio.create_task(self.check_agent_health(agent_type))
            health_checks.append(task)

        results = await asyncio.gather(*health_checks, return_exceptions=True)

        health_status = {}
        for agent_type, result in zip(agent_types, results):
            if isinstance(result, Exception):
                health_status[agent_type] = False
            else:
                health_status[agent_type] = result

        return health_status

    def get_available_agents(self) -> List[str]:
        """
        Get list of available agent types.

        Returns:
            List of agent type names
        """
        return list(self.agent_configs.keys())

    def get_agent_url(self, agent_type: str) -> Optional[str]:
        """
        Get URL for a specific agent type.

        Args:
            agent_type: Type of agent

        Returns:
            Agent URL or None if not found
        """
        config = self.agent_configs.get(agent_type)
        return config["url"] if config else None

    def _convert_to_agent_request(
        self, agent_type: str, request: AgentRequest
    ) -> Dict[str, Any]:
        """
        Convert standard AgentRequest to agent-specific request format.

        Args:
            agent_type: Type of agent
            request: Standard agent request

        Returns:
            Agent-specific request data
        """
        if agent_type == "order_management":
            # Order management uses the standard AgentRequest format
            return request.model_dump()

        elif agent_type == "product_recommendation":
            # Product recommendation uses ProductRecommendationRequest format
            return {
                "customer_id": request.customer_id,
                "query": request.customer_message,
                "session_id": request.session_id,
                "context": request.context,
            }

        elif agent_type == "troubleshooting":
            # Troubleshooting uses TroubleshootingRequest format
            return {
                "customer_id": request.customer_id,
                "query": request.customer_message,
                "session_id": request.session_id,
                "context": request.context,
            }

        elif agent_type == "personalization":
            # Personalization uses PersonalizationRequest format
            return {
                "customer_id": request.customer_id,
                "query": request.customer_message,
                "session_id": request.session_id,
                "context": request.context,
            }

        else:
            # Default to standard format
            return request.model_dump()

    def _convert_from_agent_response(
        self, agent_type: str, response_data: Dict[str, Any], session_id: str
    ) -> AgentResponse:
        """
        Convert agent-specific response to standard AgentResponse format.

        Args:
            agent_type: Type of agent
            response_data: Agent-specific response data
            session_id: Session identifier

        Returns:
            Standard agent response
        """
        if agent_type == "order_management":
            # Order management already uses AgentResponse format
            return AgentResponse(**response_data)

        elif agent_type == "product_recommendation":
            # Convert ProductRecommendationResponse to AgentResponse
            recommendations = response_data.get("recommendations", [])
            customer_insights = response_data.get("customer_insights", "")
            confidence_score = response_data.get("confidence_score", 0.0)

            # Create response text from recommendations
            if recommendations:
                response_text = (
                    f"Based on your query, here are my product recommendations:\n\n"
                )
                for i, rec in enumerate(recommendations[:3], 1):  # Limit to top 3
                    response_text += f"{i}. **{rec.get('product_name', 'Unknown Product')}** (${rec.get('price', 'N/A')})\n"
                    response_text += f"   Rating: {rec.get('rating', 'N/A')}/5 | Category: {rec.get('category', 'N/A')}\n"
                    response_text += f"   {rec.get('recommendation_reason', 'Great choice for you!')}\n\n"

                if customer_insights:
                    response_text += f"\n**Customer Insights:** {customer_insights}"
            else:
                response_text = "I'm sorry, I couldn't find any suitable product recommendations for your query."

            return AgentResponse(
                response=response_text,
                agent_type=AgentType.PRODUCT_RECOMMENDATION,
                confidence_score=confidence_score,
                session_id=session_id,
                metadata={"recommendations_count": len(recommendations)},
            )

        elif agent_type == "troubleshooting":
            # Convert TroubleshootingResponse to AgentResponse
            solutions = response_data.get("solutions", [])
            confidence_score = response_data.get("confidence_score", 0.0)

            # Create response text from solutions
            if solutions:
                response_text = (
                    "Here are the troubleshooting steps I found for your issue:\n\n"
                )
                for i, solution in enumerate(solutions[:3], 1):
                    response_text += f"{i}. **{solution.get('title', 'Solution')}**\n"
                    response_text += (
                        f"   {solution.get('content', 'No details available')}\n\n"
                    )
            else:
                response_text = "I'm sorry, I couldn't find specific troubleshooting solutions for your issue."

            return AgentResponse(
                response=response_text,
                agent_type=AgentType.TROUBLESHOOTING,
                confidence_score=confidence_score,
                session_id=session_id,
                metadata={"solutions_count": len(solutions)},
            )

        elif agent_type == "personalization":
            # Convert PersonalizationResponse to AgentResponse
            personalization_summary = response_data.get("personalization_summary", "")
            recommendations = response_data.get("recommendations", [])
            confidence_score = response_data.get("confidence_score", 0.0)
            customer_profile = response_data.get("customer_profile", {})
            browsing_insights = response_data.get("browsing_insights", [])

            # Create response text from personalization data
            response_text = ""

            if personalization_summary:
                response_text += f"Here's your personalization summary:\n\n{personalization_summary}\n\n"

            if recommendations:
                response_text += "**Personalized Recommendations:**\n"
                for i, rec in enumerate(recommendations[:3], 1):
                    response_text += f"{i}. {rec}\n"
                response_text += "\n"

            if browsing_insights:
                response_text += "**Browsing Insights:**\n"
                for insight in browsing_insights[:3]:
                    if isinstance(insight, dict):
                        response_text += (
                            f"• {insight.get('description', 'Insight available')}\n"
                        )
                    else:
                        response_text += f"• {insight}\n"

            # Fallback if no content
            if not response_text.strip():
                response_text = (
                    "Personalization insights have been analyzed for your profile."
                )

            return AgentResponse(
                response=response_text,
                agent_type=AgentType.PERSONALIZATION,
                confidence_score=confidence_score,
                session_id=session_id,
                metadata={
                    "recommendations_count": len(recommendations),
                    "insights_count": len(browsing_insights),
                    "has_profile": bool(customer_profile),
                },
            )

        else:
            # Fallback for unknown agent types
            return AgentResponse(
                response=str(response_data.get("response", "Agent response received")),
                agent_type=AgentType.SUPERVISOR,  # Default type
                confidence_score=response_data.get("confidence_score", 0.0),
                session_id=session_id,
            )
