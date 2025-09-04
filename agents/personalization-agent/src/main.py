"""
FastAPI application for Personalization Agent.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import PersonalizationAgent
from models import PersonalizationRequest, PersonalizationResponse
from database import initialize_database

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global agent instance
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global agent

    # Startup
    logger.info("Starting Personalization Agent service...")

    try:
        # Initialize database
        await initialize_database()
        logger.info("Database initialized successfully")

        # Initialize agent
        agent = PersonalizationAgent()
        logger.info("Personalization Agent initialized successfully")


    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Personalization Agent service...")


# Create FastAPI app
app = FastAPI(
    title="Personalization Agent",
    description="AI-powered personalization service for customer support system",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str



@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy", service="personalization-agent", version="1.0.0"
    )


@app.post("/personalize", response_model=PersonalizationResponse)
async def get_personalization(request: PersonalizationRequest):
    """Get personalization insights for a customer."""
    try:
        if agent is None:
            raise HTTPException(status_code=503, detail="Service not ready")

        logger.info(
            f"Processing personalization request for customer: {request.customer_id}"
        )

        response = await agent.process_request(request)

        logger.info(
            f"Generated personalization insights for customer {request.customer_id}"
        )
        return response

    except Exception as e:
        logger.error(f"Error processing personalization request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Personalization Agent",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "personalize": "/personalize",
            "docs": "/docs",
        },
    }


def main():
    """Main function to run the service."""
    port = int(os.getenv("PORT", "8004"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting Personalization Agent on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info",
    )


if __name__ == "__main__":
    main()
