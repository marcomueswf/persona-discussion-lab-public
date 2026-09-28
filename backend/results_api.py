"""Result router exposing structured discussion outputs."""

from fastapi import APIRouter, HTTPException, status

from backend.models import DiscussionResult
from backend.services.result_service import ResultService

router = APIRouter()
service = ResultService()


@router.get("/results/{discussion_id}", response_model=DiscussionResult)
def get_discussion_result(discussion_id: str):
    """Return result projection for one discussion id."""
    result = service.get_for_discussion(discussion_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion not found")
    return result
