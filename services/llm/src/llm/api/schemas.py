from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_tokens: int = Field(default=512, ge=1, le=4096)
    stream: bool = Field(default=False, description="If true, use streaming response (SSE).")


class GenerateResponse(BaseModel):
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
