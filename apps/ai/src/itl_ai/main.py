"""FastAPI boundary for the Interactive Taste Learning AI service."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from itl_ai.config.settings import load_settings
from itl_ai.memory.repository import PreferenceRepository
from itl_ai.refine.catalog import RefineValidationError
from itl_ai.refine.models import (
    ErrorResponse as RefineErrorResponse,
)
from itl_ai.refine.models import (
    GenerateSpecRequest,
    GenerateSpecResponse,
    GenerateVariantsRequest,
    GenerateVariantsResponse,
    MemoryQuery,
    MemoryResponse,
    ParseCritiqueRequest,
    ParseCritiqueResponse,
    PreferenceEventRequest,
    PreferenceEventResponse,
)
from itl_ai.refine.providers import ProviderUnavailableError, configured_provider
from itl_ai.refine.service import RefineService

app = FastAPI(title="ITL AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


def _refine_service() -> RefineService:
    settings = load_settings()
    return RefineService(PreferenceRepository(settings.preference_database_path), configured_provider(settings))


refine_service = _refine_service()


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


@app.exception_handler(RefineValidationError)
async def refine_validation_error(_: Request, error: RefineValidationError) -> JSONResponse:
    """Return recoverable model/patch errors without changing a caller's spec."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=RefineErrorResponse(
            code=error.code,
            message=error.message,
            issues=error.issues,
            recoverable=True,
        ).model_dump(),
    )


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_error(_: Request, __: ProviderUnavailableError) -> JSONResponse:
    """Keep provider outages from becoming stack-trace 500 responses."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse(
            code="provider_unavailable",
            message="The configured model provider did not respond. Please try again.",
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
                message=("Generation is unavailable until a provider API key is configured."),
            ).model_dump(),
        )

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=ErrorResponse(
            code="generation_not_implemented",
            message="Generation has not been implemented yet.",
        ).model_dump(),
    )


@app.post(
    "/v1/refine/generate-spec",
    response_model=GenerateSpecResponse,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RefineErrorResponse}},
)
def generate_spec(request: GenerateSpecRequest) -> GenerateSpecResponse:
    """Generate one catalog-constrained spec for the requested editable subject."""
    return refine_service.generate_spec(request)


@app.post(
    "/v1/refine/parse-critique",
    response_model=ParseCritiqueResponse,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RefineErrorResponse}},
)
def parse_critique(request: ParseCritiqueRequest) -> ParseCritiqueResponse:
    """Return a reviewable intent; parsing never mutates a UI spec."""
    return refine_service.parse_critique(request)


@app.post(
    "/v1/refine/generate-variants",
    response_model=GenerateVariantsResponse,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RefineErrorResponse}},
)
def generate_variants(request: GenerateVariantsRequest) -> GenerateVariantsResponse:
    """Create only validated variants with locks checked deterministically."""
    return refine_service.generate_variants(request)


@app.post(
    "/v1/preference-events",
    response_model=PreferenceEventResponse,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RefineErrorResponse}},
)
def record_preference_event(request: PreferenceEventRequest) -> PreferenceEventResponse:
    """Append an explicit action and immutable renderable snapshots to local memory."""
    return refine_service.record_preference_event(request)


@app.post("/v1/preference-memory", response_model=MemoryResponse)
def preference_memory(query: MemoryQuery) -> MemoryResponse:
    """Return bounded, contextual evidence for one subject's generator and memory UI."""
    return refine_service.preference_memory(query.context, query.evidence, query.scope, query.componentType)


def run() -> None:
    """Start the local development server through the package entry point."""
    import uvicorn

    uvicorn.run("itl_ai.main:app", host="127.0.0.1", port=8000)
