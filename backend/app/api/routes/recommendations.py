import logging

from app.core.config import get_settings
from app.financial_data.grounded_answers import OllamaInvalidResponse, OllamaUnavailable
from app.financial_data.recommendations import generate_ollama_recommendations
from app.schemas.recommendations import RecommendationRequest, RecommendationResponse
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["transaction recommendations"])


@router.post("", response_model=RecommendationResponse)
def recommend_from_transactions(request: RecommendationRequest) -> RecommendationResponse:
    settings = get_settings()
    try:
        recommendations, abstained, used_fallback = generate_ollama_recommendations(
            request.dataset.model_dump(),
            items=[item.model_dump(exclude_none=True) for item in request.items],
            monthly_categories=[
                item.model_dump() for item in request.monthly_categories
            ],
            monthly_returns=[item.model_dump() for item in request.monthly_returns],
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        if used_fallback:
            logger.warning("Local Ollama returned an unsupported recommendation format; using grounded fallback")
    except OllamaUnavailable:
        logger.warning("Local Ollama recommendations are unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local Ollama is unavailable. Start Ollama and install the configured model.",
        ) from None
    except OllamaInvalidResponse:
        logger.exception("Local Ollama returned an invalid transaction recommendation response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model response could not be read. Try again or check the Ollama service.",
        ) from None
    except ValueError as error:
        logger.error("Ollama configuration is invalid: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local recommendation generation is not configured correctly.",
        ) from None

    return RecommendationResponse(
        recommendations=recommendations,
        abstained=abstained,
        model=settings.ollama_model,
        notice=(
            "The local model returned an unsupported format. These review suggestions were created "
            "from the transaction summaries instead."
            if used_fallback
            else None
        ),
    )
