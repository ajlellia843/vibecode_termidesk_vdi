"""FastAPI routes for retrieval service."""
from fastapi import APIRouter, Request

from retrieval.api.schemas import SearchRequest, SearchResponse
from retrieval.service import SearchService

router = APIRouter(tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)  # POST /search for orchestrator
async def search(body: SearchRequest, request: Request) -> SearchResponse:
    service: SearchService = request.app.state.search_service
    results = await service.search(body.query, top_k=body.top_k)
    return SearchResponse(
        results=[
            {"chunk_id": r.chunk_id, "text": r.text, "source": r.source, "score": r.score}
            for r in results
        ]
    )
