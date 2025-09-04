"""
FastAPI application for Product Recommendation Agent.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from agent import ProductRecommendationAgent
from models import ProductRecommendationRequest, ProductRecommendationResponse
from database import initialize_database

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
    logger.info("Starting Product Recommendation Agent service...")
    
    try:
        # Initialize database
        await initialize_database()
        logger.info("Database initialized successfully")
        
        # Initialize agent
        agent = ProductRecommendationAgent()
        logger.info("Product Recommendation Agent initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Product Recommendation Agent service...")


# Create FastAPI app
app = FastAPI(
    title="Product Recommendation Agent",
    description="AI-powered product recommendation service for customer support system",
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
        service="product-recommendation-agent",
        version="1.0.0"
    )


# @app.post("/recommend", response_model=ProductRecommendationResponse)
@app.post("/recommend")
async def get_recommendations(request: ProductRecommendationRequest):
    """Get product recommendations based on customer query."""
    try:
        if agent is None:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        logger.info(f"Processing recommendation request: {request.query[:100]}...")
        logger.debug(f"Request: {request}")
        
        response = await agent.process_request(request)
        print(response)
        
        # logger.info(f"Generated {len(response.recommendations)} recommendations")
        return response
        
    except Exception as e:
        logger.error(f"Error processing recommendation request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Product Recommendation Agent",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "recommend": "/recommend",
            "docs": "/docs"
        }
    }


def main():
    """Main function to run the service."""
    port = int(os.getenv("PORT", "8002"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting Product Recommendation Agent on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info"
    )


if __name__ == "__main__":
    main()