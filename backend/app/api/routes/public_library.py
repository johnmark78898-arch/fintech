import logging
from typing import Annotated

from app.core.config import get_settings
from app.financial_data.grounded_answers import (
    OllamaInvalidResponse,
    OllamaUnavailable,
    generate_ollama_answer,
)
from app.financial_data.public_library import (
    PublicLibraryCorrupt,
    PublicLibraryNotReady,
    get_public_library_status,
    search_public_library,
)
from app.schemas.public_library import PublicAnswerResponse, PublicQuestionRequest
from fastapi import APIRouter, HTTPException, Query, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public-library", tags=["public source library"])


@router.get("/status")
def public_library_status() -> dict[str, object]:
    try:
        return get_public_library_status()
    except PublicLibraryNotReady:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The public source library has not been indexed",
        ) from None
    except PublicLibraryCorrupt:
        logger.exception("Public source library index is invalid")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The public source library is unavailable",
        ) from None


@router.get("/search")
def search_public_sources(
    query: Annotated[str, Query(min_length=2, max_length=200)],
) -> dict[str, object]:
    try:
        results = search_public_library(query)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except PublicLibraryNotReady:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The public source library has not been indexed",
        ) from None
    except PublicLibraryCorrupt:
        logger.exception("Public source library index is invalid")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The public source library is unavailable",
        ) from None
    return {"results": results}


@router.post("/answer", response_model=PublicAnswerResponse)
def answer_public_question(request: PublicQuestionRequest) -> PublicAnswerResponse:
    passages = []
    if request.dataset is None:
        try:
            passages = search_public_library(request.question, limit=2)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
        except PublicLibraryNotReady:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The public source library has not been indexed",
            ) from None
        except PublicLibraryCorrupt:
            logger.exception("Public source library index is invalid")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The public source library is unavailable",
            ) from None

    settings = get_settings()
    if not passages and request.dataset is None:
        return PublicAnswerResponse(
            answer="I couldn't find relevant passages in the indexed public sources.",
            citations=[],
            abstained=True,
            data_based=False,
            model=settings.ollama_model,
        )

    try:
        answer, citation_ids, abstained = generate_ollama_answer(
            request.question,
            passages,
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            dataset_context=request.dataset.model_dump() if request.dataset is not None else None,
        )
    except OllamaUnavailable:
        logger.warning("Local Ollama answer generation is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local Ollama is unavailable. Start Ollama and install the configured model.",
        ) from None
    except OllamaInvalidResponse:
        logger.exception("Local Ollama returned an invalid grounded answer")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model returned an invalid answer. Try again.",
        ) from None
    except ValueError as error:
        logger.error("Ollama configuration is invalid: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local answer generation is not configured correctly.",
        ) from None

    passages_by_id = {str(passage["chunk_id"]): passage for passage in passages}
    if request.dataset is not None and citation_ids:
        logger.warning("Local model returned public citations in dataset-only answer mode; ignoring them")
        citation_ids = []
    if any(citation_id not in passages_by_id for citation_id in citation_ids):
        logger.warning("Local Ollama returned a citation outside retrieved evidence")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local model returned an invalid citation. Try again.",
        )
    citations = [passages_by_id[citation_id] for citation_id in citation_ids]
    if abstained:
        answer = "I couldn't find enough supporting information in the transaction summary or public sources to answer that."
    return PublicAnswerResponse(
        answer=answer,
        citations=citations,
        abstained=abstained,
        data_based=request.dataset is not None,
        model=settings.ollama_model,
    )
