"""Discussion router.

The router is intentionally thin and delegates orchestration and persistence
concerns to application services.
"""

from fastapi import APIRouter, HTTPException, status

from backend.models import (
    DiscussionResponse,
    DiscussionResult,
    DiscussionStartRequest,
    DiscussionTraceResponse,
    DiscussionTemplateCreate,
    DiscussionTemplateResponse,
)
from backend.services.discussion_service import DiscussionService
from backend.services.discussion_template_service import DiscussionTemplateService
from backend.services.result_service import ResultService

router = APIRouter()
service = DiscussionService()
template_service = DiscussionTemplateService(discussion_persistence=service.discussion_persistence)
result_service = ResultService()


@router.get("/discussion-templates", response_model=list[DiscussionTemplateResponse])
def list_discussion_templates():
    """List reusable discussion templates."""
    return template_service.list()


@router.get("/discussion-templates/{template_id}", response_model=DiscussionTemplateResponse)
def get_discussion_template(template_id: str):
    """Fetch one reusable discussion template."""
    template = template_service.get(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion template not found")
    return template


@router.delete("/discussion-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discussion_template(template_id: str):
    """Delete one reusable discussion template."""
    if not template_service.delete(template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion template not found")
    return None


@router.get("/discussions", response_model=list[DiscussionResponse])
def list_discussions():
    """List persisted discussions ordered by creation time."""
    return service.list()


@router.post(
    "/discussions",
    response_model=DiscussionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_discussion(request: DiscussionStartRequest):
    """Create a new discussion and return queued state immediately."""
    try:
        return service.start(request)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/discussions/{discussion_id}", response_model=DiscussionResponse)
def get_discussion(discussion_id: str):
    """Fetch one discussion by id."""
    discussion = service.get(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion not found")
    return discussion


@router.delete("/discussions/{discussion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discussion(discussion_id: str):
    """Delete a persisted discussion from the history."""
    try:
        deleted = service.delete(discussion_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion not found")
    return None


@router.post("/discussions/{discussion_id}/stop", response_model=DiscussionResponse)
def stop_discussion(discussion_id: str):
    """Request cooperative stop for one discussion."""
    discussion = service.stop(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion not found")
    return discussion


@router.post(
    "/discussions/{discussion_id}/template",
    response_model=DiscussionTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_discussion_template(discussion_id: str, request: DiscussionTemplateCreate):
    """Save a completed discussion setup as a reusable template."""
    if request.discussionId != discussion_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Discussion ID does not match request path")
    try:
        return template_service.create_from_discussion(discussion_id, request.templateName)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/discussions/{discussion_id}/result", response_model=DiscussionResult)
def get_discussion_result(discussion_id: str):
    """Return structured result projection for one discussion."""
    result = result_service.get_for_discussion(discussion_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion not found")
    return result


@router.get("/discussions/{discussion_id}/trace", response_model=DiscussionTraceResponse)
def get_discussion_trace(discussion_id: str):
    """Return the opt-in LLM trace without expanding normal discussion responses."""
    discussion = service.get(discussion_id)
    if discussion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discussion not found")
    return {
        "discussionId": discussion_id,
        "enabled": bool(discussion.get("traceEnabled")),
        "entries": discussion.get("trace", []),
    }
