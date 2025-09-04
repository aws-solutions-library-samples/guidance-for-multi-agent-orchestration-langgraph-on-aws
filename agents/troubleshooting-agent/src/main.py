"""
FastAPI application for Troubleshooting Agent.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import TroubleshootingAgent
from models import TroubleshootingRequest, TroubleshootingResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global agent instance
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global agent
    
    # Startup
    logger.info("Starting Troubleshooting Agent service...")
    
    try:
        # Initialize agent
        agent = TroubleshootingAgent()
        logger.info("Troubleshooting Agent initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Troubleshooting Agent service...")


# Create FastAPI app
app = FastAPI(
    title="Troubleshooting Agent",
    description="AI-powered troubleshooting service for customer support system",
    version="1.0.0",
    lifespan=lifespan
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
        status="healthy",
        service="troubleshooting-agent",
        version="1.0.0"
    )


@app.post("/troubleshoot", response_model=TroubleshootingResponse)
async def get_troubleshooting_help(request: TroubleshootingRequest):
    """Get troubleshooting help for customer issues."""
    try:
        if agent is None:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        logger.info(f"Processing troubleshooting request: {request.query[:100]}...")
        
        response = await agent.process_request(request)
        
        logger.info(f"Generated {len(response.solutions)} troubleshooting solutions")
        return response
        
    except Exception as e:
        logger.error(f"Error processing troubleshooting request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Troubleshooting Agent",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "troubleshoot": "/troubleshoot",
            "docs": "/docs"
        }
    }


def main():
    """Main function to run the service."""
    port = int(os.getenv("PORT", "8003"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Troubleshooting Agent on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info"
    )


if __name__ == "__main__":
    main()