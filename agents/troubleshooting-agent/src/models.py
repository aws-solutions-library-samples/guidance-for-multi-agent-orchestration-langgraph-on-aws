"""
Pydantic models for Troubleshooting Agent.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TroubleshootingRequest(BaseModel):
    """Request model for troubleshooting queries."""
    query: str = Field(..., description="Customer's troubleshooting query or issue description")
    product_name: Optional[str] = Field(None, description="Specific product name if mentioned")
    product_category: Optional[str] = Field(None, description="Product category (headphones, watch, speaker, computer, phone)")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class TroubleshootingStep(BaseModel):
    """Individual troubleshooting step."""
    step_number: int = Field(..., description="Step number in the troubleshooting process")
    description: str = Field(..., description="Description of the troubleshooting step")
    expected_outcome: Optional[str] = Field(None, description="What should happen if step is successful")


class TroubleshootingSolution(BaseModel):
    """Complete troubleshooting solution."""
    issue_title: str = Field(..., description="Title of the identified issue")
    product_name: Optional[str] = Field(None, description="Product name this solution applies to")
    category: Optional[str] = Field(None, description="Product category")
    steps: List[TroubleshootingStep] = Field(default_factory=list, description="Troubleshooting steps")
    additional_notes: Optional[str] = Field(None, description="Additional helpful information")
    warranty_info: Optional[str] = Field(None, description="Relevant warranty information")


class TroubleshootingResponse(BaseModel):
    """Response model for troubleshooting queries."""
    solutions: List[TroubleshootingSolution] = Field(default_factory=list, description="List of troubleshooting solutions")
    issue_analysis: Optional[str] = Field(None, description="Analysis of the reported issue")
    confidence_score: float = Field(0.0, description="Confidence in the provided solution")
    escalation_needed: bool = Field(False, description="Whether the issue needs escalation to human support")


class IssueAnalysis(BaseModel):
    """Structured analysis of customer issue."""
    primary_issue: str = Field(description="Primary issue identified")
    product_category: Optional[str] = Field(description="Product category affected")
    issue_severity: str = Field(description="Severity level (low/medium/high)")
    common_problem: bool = Field(description="Whether this is a common problem")
    keywords: List[str] = Field(description="Key terms related to the issue")


class KnowledgeBaseResult(BaseModel):
    """Result from knowledge base search."""
    title: str = Field(description="Title of the knowledge base article")
    content: str = Field(description="Content of the article")
    relevance_score: float = Field(description="Relevance score to the query")
    source: str = Field(description="Source of the information (FAQ or troubleshooting guide)")
    product_name: Optional[str] = Field(description="Product this article relates to")
    category: Optional[str] = Field(description="Product category")