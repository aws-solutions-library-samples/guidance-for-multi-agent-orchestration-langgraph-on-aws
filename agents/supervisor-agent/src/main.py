"""
FastAPI application for the supervisor agent service.

This module provides the REST API endpoints for the supervisor agent,
handling customer support requests and coordinating with sub-agents.
"""

import logging
import time
import os
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from shared.models import SupervisorRequest, SupervisorResponse
from agent import SupervisorAgent
from config import config

# Set up logging
logger = logging.getLogger(__name__)

# Global agent instance
supervisor_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    global supervisor_agent

    # Startup
    logger.info("Starting supervisor agent service...")
    try:
        supervisor_agent = SupervisorAgent()

        # Log service discovery information
        from client import SubAgentClient

        client = SubAgentClient()
        config_info = client.get_agent_config_info()

        logger.info(f"Service Discovery Environment: {config_info['environment']}")
        logger.info(f"Service Discovery Method: {config_info['service_discovery']}")
        logger.info("Agent Service Endpoints:")
        for agent_type, url in config_info["agent_configs"].items():
            logger.info(f"  {agent_type}: {url}")

        logger.info("Supervisor agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize supervisor agent: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down supervisor agent service...")


# Create FastAPI application
app = FastAPI(
    title="Supervisor Agent Service",
    description="Main coordinator for multi-agent customer support system",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/process", response_model=SupervisorResponse)
async def process_request(request: SupervisorRequest) -> SupervisorResponse:
    """
    Main chat endpoint for customer interactions.

    Args:
        request: Customer support request

    Returns:
        Supervisor response with synthesized answer

    Raises:
        HTTPException: If processing fails
    """
    if not supervisor_agent:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        logger.info(f"Processing supervisor request for session {request.session_id}")

        # Validate request
        if not request.customer_message.strip():
            raise HTTPException(
                status_code=400, detail="Customer message cannot be empty"
            )

        # Process request
        response_data = await supervisor_agent.process_request(request)

        # Convert to SupervisorResponse format
        response = SupervisorResponse(
            response=response_data["response"],
            agents_called=response_data["agents_called"],
            agent_responses=response_data["agent_responses"],
            confidence_score=response_data["confidence_score"],
            session_id=response_data["session_id"],
            processing_time=response_data["processing_time"],
            follow_up_needed=response_data["follow_up_needed"],
        )

        logger.info(f"Successfully processed request for session {request.session_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process chat request: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process request: {str(e)}"
        )


@app.post("/process/stream")
async def process_request_stream(request: SupervisorRequest):
    """
    Streaming chat endpoint for real-time customer interactions.

    Args:
        request: Customer support request

    Returns:
        Streaming response with real-time updates

    Raises:
        HTTPException: If processing fails
    """
    if not supervisor_agent:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        logger.info(
            f"Processing streaming supervisor request for session {request.session_id}"
        )

        # Validate request
        if not request.customer_message.strip():
            raise HTTPException(
                status_code=400, detail="Customer message cannot be empty"
            )

        # Import streaming response
        from fastapi.responses import StreamingResponse
        import json

        async def generate_stream():
            """Generate streaming response."""
            try:
                async for update in supervisor_agent.process_request_stream(request):
                    # Convert update to JSON and add newline for streaming
                    yield json.dumps(update) + "\n"

                # Send final completion marker
                yield json.dumps(
                    {
                        "type": "complete",
                        "session_id": request.session_id,
                        "timestamp": time.time(),
                    }
                ) + "\n"

            except Exception as e:
                logger.error(f"Error in streaming generation: {e}")
                # Send error in stream format
                yield json.dumps(
                    {
                        "type": "error",
                        "data": {"error": str(e)},
                        "session_id": request.session_id,
                        "timestamp": time.time(),
                    }
                ) + "\n"

        return StreamingResponse(
            generate_stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process streaming chat request: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process streaming request: {str(e)}"
        )


@app.post("/process/stream/tokens")
async def process_request_stream_tokens(request: SupervisorRequest):
    """
    Token-level streaming chat endpoint for real-time LLM token streaming.

    Args:
        request: Customer support request

    Returns:
        Streaming response with LLM tokens and progress updates

    Raises:
        HTTPException: If processing fails
    """
    if not supervisor_agent:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        logger.info(
            f"Processing token streaming supervisor request for session {request.session_id}"
        )

        # Validate request
        if not request.customer_message.strip():
            raise HTTPException(
                status_code=400, detail="Customer message cannot be empty"
            )

        # Import streaming response
        from fastapi.responses import StreamingResponse
        import json

        async def generate_token_stream():
            """Generate token-level streaming response."""
            try:
                async for update in supervisor_agent.process_request_stream_tokens(
                    request
                ):
                    # Convert update to JSON and add newline for streaming
                    yield json.dumps(update) + "\n"

                # Send final completion marker
                yield json.dumps(
                    {
                        "type": "complete",
                        "session_id": request.session_id,
                        "timestamp": time.time(),
                    }
                ) + "\n"

            except Exception as e:
                logger.error(f"Error in token streaming generation: {e}")
                # Send error in stream format
                yield json.dumps(
                    {
                        "type": "error",
                        "data": {"error": str(e)},
                        "session_id": request.session_id,
                        "timestamp": time.time(),
                    }
                ) + "\n"

        return StreamingResponse(
            generate_token_stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process token streaming chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process token streaming request: {str(e)}",
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        if not supervisor_agent:
            return {"status": "unhealthy", "error": "Service not initialized"}

        # Get detailed health status
        health_status = await supervisor_agent.get_health_status()
        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@app.get("/agents/status")
async def agents_status() -> Dict[str, Any]:
    """
    Get status of all sub-agent services.

    Returns:
        Status information for all sub-agents
    """
    if not supervisor_agent:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        agent_health = await supervisor_agent.client.check_all_agents_health()
        config_info = supervisor_agent.client.get_agent_config_info()
        return {
            "agents": agent_health,
            "available_agents": supervisor_agent.client.get_available_agents(),
            "agent_urls": config_info.get("agent_configs", {}),
            "environment": config_info.get("environment"),
            "service_discovery": config_info.get("service_discovery"),
        }
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent status: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Supervisor Agent",
        "version": "1.0.0",
        "description": "Main coordinator for multi-agent customer support system",
        "endpoints": {
            "process": "/process",
            "process_stream": "/process/stream",
            "process_stream_tokens": "/process/stream/tokens",
            "health": "/health",
            "agents_status": "/agents/status",
            "docs": "/docs",
        },
    }


def main():
    """Run the supervisor agent service."""
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("SUPERVISOR_PORT", "8000"))

    logger.info(f"Starting Supervisor Agent service on {host}:{port}")

    uvicorn.run("main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
