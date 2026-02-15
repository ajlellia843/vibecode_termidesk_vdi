"""FastAPI routes for retrieval service."""
from fastapi import APIRouter, Request

from retrieval.api.schemas import SearchRequest, SearchResponse
from retrieval.service import SearchService

router = APIRouter(tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)  # POST /search for orchestrator
async def search(body: SearchRequest, request: Request) -> SearchResponse:
    service: SearchService = request.app.state.search_service
    results = await service.search(
        body.query, top_k=body.top_k, version=body.version
    )
    return SearchResponse(
        results=[
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "source": r.source,
                "document_title": r.document_title,
                "section_title": r.section_title,
                "position": r.position,
                "score": r.score,
                "confidence": r.confidence,
                "distance": r.distance,
                "version": r.version,
            }
            for r in results
        ]
    )
