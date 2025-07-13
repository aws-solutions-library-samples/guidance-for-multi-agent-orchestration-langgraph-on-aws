"""
FastAPI service for the order management agent.
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.models import AgentRequest, AgentResponse
from simple_graph_agent import SimpleGraphOrderAgent
from config import config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global agent instance
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the agent."""
    global agent
    
    try:
        logger.info("Initializing Order Management Agent...")
        agent = SimpleGraphOrderAgent()
        
        # Test connections
        logger.info("Testing LLM connection...")
        llm_works = await agent.test_llm_connection()
        if not llm_works:
            logger.warning("LLM connection test failed")
        else:
            logger.info("✅ LLM connection successful")
        
        logger.info("Testing database connection...")
        db_works = await agent.test_database_connection()
        if not db_works:
            logger.warning("Database connection test failed, using mock data")
        else:
            logger.info("✅ Database connection successful")
        
        logger.info("🚀 Order Management Agent service is ready!")
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize Order Management Agent: {e}")
        raise
    finally:
        logger.info("Shutting down Order Management Agent...")


# Create FastAPI app
app = FastAPI(
    title="Order Management Agent",
    description="LangGraph-based order management agent for customer support",
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
    agent_ready: bool
    llm_connection: bool
    database_connection: bool


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Test connections
        llm_works = await agent.test_llm_connection()
        db_works = await agent.test_database_connection()
        
        return HealthResponse(
            status="healthy" if llm_works else "degraded",
            agent_ready=True,
            llm_connection=llm_works,
            database_connection=db_works
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@app.post("/process", response_model=AgentResponse)
async def process_request(request: AgentRequest):
    """Process a customer order-related request."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        logger.info(f"Processing order management request: {request.customer_message[:100]}...")
        
        response = await agent.process_request(request)
        
        logger.info(f"Request processed successfully with confidence: {response.confidence_score:.2f}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to process request: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Order Management Agent",
        "status": "running",
        "version": "1.0.0",
        "agent_type": "order_management"
    }


@app.get("/info")
async def service_info():
    """Get service information."""
    return {
        "service": "Order Management Agent",
        "description": "LangGraph-based agent for handling order-related customer inquiries",
        "capabilities": [
            "Order status lookup",
            "Customer order history",
            "Product inventory checking",
            "Shipping status tracking",
            "Return/exchange status",
            "Order summaries"
        ],
        "tools": [
            "query_order_by_id",
            "query_customer_orders", 
            "check_product_inventory",
            "check_shipping_status",
            "check_return_status",
            "get_order_summary"
        ],
        "database": "SQLite with test data"
    }


def main():
    """Run the FastAPI service."""
    import uvicorn
    
    # Get configuration from environment or config
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("ORDER_AGENT_PORT", "8001"))
    
    logger.info(f"Starting Order Management Agent service on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # Set to True for development
        log_level="info"
    )


if __name__ == "__main__":
    main()