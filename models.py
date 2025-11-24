"""
Pydantic models for the application.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class PubMedArticle(BaseModel):
    """A PubMed article retrieved from search."""

    id: str = Field(..., description="PubMed ID (PMID)")
    title: str = Field(..., description="Article title")
    year: str = Field(..., description="Publication year")
    abstract: str = Field(..., description="Article abstract")
    link: str = Field(..., description="URL to the article on PubMed")
    authors: Optional[List[str]] = Field(default=None, description="List of authors")
    journal: Optional[str] = Field(default=None, description="Journal name")
    relevance_score: Optional[float] = Field(
        default=None, description="Relevance score if filtered"
    )


class PubMedSearchMetadata(BaseModel):
    """Metadata about a PubMed search."""

    search_terms: str = Field(..., description="The search terms used")
    search_date: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="When the search was performed",
    )
    years_back: int = Field(default=5, description="Number of years back searched")
    cutting_edge: bool = Field(
        default=False, description="Whether cutting-edge research was prioritized"
    )
    filter_relevance: bool = Field(
        default=True, description="Whether results were filtered by relevance"
    )
    relevance_threshold: Optional[float] = Field(
        default=None, description="Threshold used for relevance filtering"
    )
    original_question: str = Field(
        ..., description="The original question that prompted the search"
    )


class DocumentMetadata(BaseModel):
    """Metadata for a document."""

    source: str = Field(default="Unknown", description="Source of the document")
    document_name: Optional[str] = Field(
        default=None, description="Name of the document"
    )
    document_type: Optional[str] = Field(
        default=None, description="Type of document (pdf, docx, etc.)"
    )
    chunk: Optional[int] = Field(
        default=None, description="Chunk number within the document"
    )
    title: Optional[str] = Field(default=None, description="Title of the document")
    is_scraped: bool = Field(
        default=False, description="Whether the document was scraped from the web"
    )


class DocumentChunk(BaseModel):
    """A chunk of text from a document with its metadata."""

    page_content: str = Field(..., description="The text content of the chunk")
    metadata: DocumentMetadata = Field(
        default_factory=DocumentMetadata, description="Metadata about the chunk"
    )


class SearchResult(BaseModel):
    """A search result from a web search."""

    title: str = Field(default="", description="Title of the search result")
    link: str = Field(default="", description="URL of the search result")
    snippet: str = Field(default="", description="Snippet/summary of the search result")
    full_content: Optional[str] = Field(
        default=None, description="Full content if scraped"
    )

    @field_validator("title", "link", "snippet", mode="before")
    @classmethod
    def ensure_string(cls, v):
        """Ensure values are strings."""
        return str(v) if v is not None else ""


class AnalysisIteration(BaseModel):
    """Details of a single iteration in the analysis process."""

    iteration: int = Field(..., description="Iteration number")
    code: str = Field(..., description="Python code executed in this iteration")
    output: str = Field(default="", description="Output from code execution")
    error: Optional[str] = Field(
        default=None, description="Error message if execution failed"
    )
    images: List[str] = Field(
        default_factory=list, description="Paths to images generated"
    )
    chunks: List[str] = Field(
        default_factory=list, description="Document chunks retrieved"
    )


class AnalysisResults(BaseModel):
    """Results of an analysis run."""

    question: str = Field(default="", description="The user's original question")
    summary: str = Field(default="", description="AI-generated summary of the analysis")
    code: str = Field(default="", description="Final Python code executed")
    output: str = Field(default="", description="Output from the final code execution")
    images: List[str] = Field(
        default_factory=list, description="Paths to images generated"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if execution failed"
    )
    history: List[AnalysisIteration] = Field(
        default_factory=list, description="History of all iterations"
    )
    mappings: Dict[str, Any] = Field(
        default_factory=dict, description="Categorical variable mappings"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp of the analysis",
    )
    pubmed_search_terms: Optional[str] = Field(
        default=None, description="PubMed search terms used"
    )
    pubmed_articles: List[Dict[str, Any]] = Field(
        default_factory=list, description="PubMed articles retrieved"
    )
    is_medical_question: bool = Field(
        default=False, description="Whether the question was identified as medical"
    )


class DataFrameMetadata(BaseModel):
    """Metadata about a DataFrame."""

    columns: List[str] = Field(
        default_factory=list, description="Column names in the DataFrame"
    )
    dtypes: Dict[str, str] = Field(
        default_factory=dict, description="Data types of each column"
    )
    filename: Optional[str] = Field(default=None, description="Original filename")
    shape: tuple = Field(
        default=(0, 0), description="Shape of the DataFrame (rows, columns)"
    )


class DocumentInfo(BaseModel):
    """Information about an uploaded document."""

    text: str = Field(..., description="Extracted text from the document")
    filename: str = Field(..., description="Original filename")
    type: str = Field(..., description="Document type (pdf, docx, etc.)")
