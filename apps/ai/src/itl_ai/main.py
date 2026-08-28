"""FastAPI boundary for the Interactive Taste Learning AI service."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from itl_ai.config.settings import load_settings

app = FastAPI(title="ITL AI API", version="0.1.0")


class HealthResponse(BaseModel):
    status: str


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)


class ErrorResponse(BaseModel):
    code: str
    message: str


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    """Keep validation failures at the HTTP boundary typed and safe."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            code="invalid_request",
            message="The request did not match the generation contract.",
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report process health without requiring a model-provider credential."""
    return HealthResponse(status="ok")


@app.post(
    "/v1/generate",
    response_model=None,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
def generate(_: GenerationRequest) -> JSONResponse:
    """Reject generation until an optional provider credential is configured."""
    if not load_settings().generation_is_configured:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                code="provider_not_configured",
                message=(
                    "Generation is unavailable until a provider API key is configured."
                ),
            ).model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=ErrorResponse(
            code="generation_not_implemented",
            message="Generation has not been implemented yet.",
        ).model_dump(),
    )


def run() -> None:
    """Start the local development server through the package entry point."""
    import uvicorn

    uvicorn.run("itl_ai.main:app", host="127.0.0.1", port=8000)
