"""
Pydantic models for Personalization Agent.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PersonalizationRequest(BaseModel):
    """Request model for personalization queries."""
    customer_id: str = Field(..., description="Customer ID for personalization")
    query: Optional[str] = Field(None, description="Optional query about customer preferences")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class CustomerProfile(BaseModel):
    """Customer profile information."""
    customer_id: str = Field(..., description="Customer identifier")
    age: Optional[int] = Field(None, description="Customer age")
    gender: Optional[str] = Field(None, description="Customer gender")
    income: Optional[str] = Field(None, description="Income bracket")
    location: Optional[str] = Field(None, description="Customer location")
    marital_status: Optional[str] = Field(None, description="Marital status")
    preferred_category: Optional[str] = Field(None, description="Preferred product category")
    price_range: Optional[str] = Field(None, description="Preferred price range")
    preferred_brand: Optional[str] = Field(None, description="Preferred brand")
    loyalty_tier: Optional[str] = Field(None, description="Customer loyalty tier")


class BrowsingInsight(BaseModel):
    """Browsing behavior insight."""
    insight_type: str = Field(..., description="Type of insight (product_interest, category_preference, etc.)")
    description: str = Field(..., description="Description of the insight")
    confidence: float = Field(..., description="Confidence score for this insight")
    supporting_data: Optional[str] = Field(None, description="Supporting data for the insight")


class PersonalizationResponse(BaseModel):
    """Response model for personalization queries."""
    customer_profile: Optional[CustomerProfile] = Field(None, description="Customer profile information")
    browsing_insights: List[BrowsingInsight] = Field(default_factory=list, description="Browsing behavior insights")
    personalization_summary: Optional[str] = Field(None, description="Summary of customer personalization")
    recommendations: List[str] = Field(default_factory=list, description="Personalized recommendations")
    confidence_score: float = Field(0.0, description="Overall confidence in personalization")


class CustomerQuery(BaseModel):
    """Structured customer query for database searches."""
    customer_id: str = Field(..., description="Customer ID to search for")
    include_demographics: bool = Field(True, description="Include demographic information")
    include_preferences: bool = Field(True, description="Include preference information")


class BrowsingPatternAnalysis(BaseModel):
    """Analysis of customer browsing patterns."""
    frequent_categories: List[str] = Field(default_factory=list, description="Frequently browsed categories")
    session_patterns: List[str] = Field(default_factory=list, description="Session behavior patterns")
    product_interests: List[str] = Field(default_factory=list, description="Products of interest")
    engagement_level: str = Field("medium", description="Customer engagement level")
    insights: str = Field("", description="Key insights about browsing behavior")


class PersonalizationInsights(BaseModel):
    """Comprehensive personalization insights."""
    demographic_insights: str = Field("", description="Insights from demographic data")
    preference_insights: str = Field("", description="Insights from preference data")
    behavior_insights: str = Field("", description="Insights from browsing behavior")
    overall_profile: str = Field("", description="Overall customer profile summary")
    personalization_opportunities: List[str] = Field(default_factory=list, description="Opportunities for personalization")