"""
FastAPI application for the supervisor agent service.

This module provides the REST API endpoints for the supervisor agent,
handling customer support requests and coordinating with sub-agents.
"""

import logging
import time
import os
import json
import asyncio
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from shared.models import SupervisorRequest, SupervisorResponse
from agent import SupervisorAgent
from config import config
from websocket_event_client import WebSocketEventClient, EventMessage

# Set up logging
logger = logging.getLogger(__name__)

# Global agent instance
supervisor_agent = None
# Global WebSocket event client
websocket_client = None
# Global event loop reference
main_event_loop = None


def handle_websocket_message(event: EventMessage):
    """
    Handle incoming WebSocket messages from frontend and trigger agent processing.
    This is a synchronous wrapper that schedules the async processing.
    
    Args:
        event: WebSocket event message containing customer request
    """
    try:
        logger.info(f"Received WebSocket message on channel: {event.channel}")
        
        # Parse the event data to extract customer request
        event_data = event.event_data
        event_data = json.loads(event_data)
        
        # Check if this is a customer request
        if event_data.get("type") == "customer_request":
            request_data = event_data.get("data", {})
            
            # Create SupervisorRequest from WebSocket data
            supervisor_request = SupervisorRequest(
                customer_message=request_data.get("customer_message", ""),
                session_id=request_data.get("session_id", ""),
                customer_id=request_data.get("customer_id"),
                conversation_history=request_data.get("conversation_history", []),
                context=request_data.get("context", {})
            )
            
            logger.info(f"Processing WebSocket request for session: {supervisor_request.session_id}")
            
            # Schedule the async processing on the main event loop
            if main_event_loop and not main_event_loop.is_closed():
                # Schedule the coroutine to run on the main loop from this thread
                asyncio.run_coroutine_threadsafe(
                    process_websocket_request(supervisor_request), 
                    main_event_loop
                )
            else:
                logger.error("Main event loop not available or closed")
                
        else:
            logger.debug(f"Ignoring non-request WebSocket message: {event_data.get('type')}")
            
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        
        # Publish error back to WebSocket
        if websocket_client and websocket_client.connected:
            error_update = {
                "type": "error",
                "data": {"error": str(e)},
                "timestamp": time.time(),
            }
            # Try to extract session_id for error channel
            try:
                session_id = event.event_data.get("data", {}).get("session_id", "unknown")
                error_channel = f"/supervisor/{session_id}/response"
                websocket_client.publish_events(error_channel, [error_update])
            except:
                logger.error("Could not publish error to WebSocket")


async def process_websocket_request(supervisor_request: SupervisorRequest):
    """
    Async function to process WebSocket requests and publish updates.
    
    Args:
        supervisor_request: The supervisor request to process
    """
    try:
        # Process the request using the supervisor agent
        if supervisor_agent:
            # Process request and publish updates
            async for update in supervisor_agent.process_request_stream(supervisor_request):
                # Publish updates back to WebSocket channel
                if websocket_client and websocket_client.connected:
                    response_channel = f"/supervisor/{supervisor_request.session_id}/response"
                    websocket_client.publish_events(response_channel, [update])
        else:
            logger.error("Supervisor agent not initialized")
            
    except Exception as e:
        logger.error(f"Error processing WebSocket request: {e}")
        
        # Publish error back to WebSocket
        if websocket_client and websocket_client.connected:
            error_update = {
                "type": "error",
                "data": {"error": str(e)},
                "timestamp": time.time(),
            }
            response_channel = f"/supervisor/{supervisor_request.session_id}/response"
            websocket_client.publish_events(response_channel, [error_update])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    global supervisor_agent, websocket_client, main_event_loop

    # Startup
    logger.info("Starting supervisor agent service...")
    try:
        # Store reference to the main event loop
        main_event_loop = asyncio.get_running_loop()
        # Initialize WebSocket event client
        logger.info("Initializing WebSocket event client...")
        websocket_client = WebSocketEventClient()
        
        # Try to connect to WebSocket
        if websocket_client.connect():
            logger.info("WebSocket event client connected successfully")
            
            # Subscribe to incoming customer requests channel
            # Frontend will publish to this channel when customers send messages
            incoming_channel = "/supervisor/*"
            subscription_id = websocket_client.subscribe_to_channel(
                incoming_channel, 
                handle_websocket_message
            )
            
            if subscription_id:
                logger.info(f"Subscribed to incoming requests channel: {incoming_channel}")
            else:
                logger.warning("Failed to subscribe to incoming requests channel")
                
        else:
            logger.warning("WebSocket event client failed to connect, continuing without WebSocket support")
            websocket_client = None

        # Initialize supervisor agent with WebSocket client
        supervisor_agent = SupervisorAgent(websocket_client=websocket_client)

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
    if websocket_client:
        try:
            websocket_client.close()
            logger.info("WebSocket event client closed")
        except Exception as e:
            logger.error(f"Error closing WebSocket client: {e}")


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


@app.get("/ws/status")
async def websocket_status():
    """Get WebSocket client status."""
    if not websocket_client:
        return {"status": "disabled", "message": "WebSocket client not initialized"}
    
    return {
        "status": "enabled",
        "websocket_status": websocket_client.show_status(),
        "subscriptions": websocket_client.get_subscriptions()
    }


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
            "websocket_status": "/ws/status",
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
