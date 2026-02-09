"""API request/response schemas."""
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunk_id: str
    text: str
    source: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
