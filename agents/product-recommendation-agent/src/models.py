"""
Pydantic models for Product Recommendation Agent.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProductRecommendationRequest(BaseModel):
    """Request model for product recommendation queries."""
    customer_id: Optional[str] = Field(None, description="Customer ID for personalized recommendations")
    query: str = Field(..., description="Customer query about product recommendations")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class ProductRecommendation(BaseModel):
    """Individual product recommendation."""
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    price: float = Field(..., description="Product price")
    rating: float = Field(..., description="Product rating")
    description: str = Field(..., description="Product description")
    recommendation_reason: str = Field(..., description="Why this product is recommended")


class ProductRecommendationResponse(BaseModel):
    """Response model for product recommendation queries."""
    recommendations: List[ProductRecommendation] = Field(default_factory=list, description="List of product recommendations")
    customer_insights: Optional[str] = Field(None, description="Insights about customer preferences")
    query_analysis: Optional[str] = Field(None, description="Analysis of the customer query")
    confidence_score: float = Field(0.0, description="Confidence in recommendations")
    
    
class ProductQuery(BaseModel):
    """Structured product query for database searches."""
    product_name: Optional[str] = Field(None, description="Product name to search for")
    category: Optional[str] = Field(None, description="Product category filter")
    price_range: Optional[str] = Field(None, description="Price range (e.g., 'low', 'medium', 'high')")
    rating_threshold: Optional[float] = Field(None, description="Minimum rating threshold")


class PurchaseHistoryAnalysis(BaseModel):
    """Analysis of customer purchase history."""
    frequent_categories: List[str] = Field(default_factory=list, description="Frequently purchased categories")
    average_price_range: Optional[str] = Field(None, description="Customer's typical price range")
    total_purchases: int = Field(0, description="Total number of purchases")
    preferred_brands: List[str] = Field(default_factory=list, description="Preferred brands if available")
    insights: str = Field("", description="Key insights about purchase patterns")


class CustomerFeedbackInsights(BaseModel):
    """Insights from customer feedback analysis."""
    positive_aspects: List[str] = Field(default_factory=list, description="Positive aspects mentioned in feedback")
    concerns: List[str] = Field(default_factory=list, description="Concerns or negative feedback")
    feature_preferences: List[str] = Field(default_factory=list, description="Preferred product features")
    overall_sentiment: str = Field("neutral", description="Overall sentiment (positive/negative/neutral)")