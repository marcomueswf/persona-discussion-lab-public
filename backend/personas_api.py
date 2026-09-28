"""Persona router delegating CRUD operations to PersonaService."""

from fastapi import APIRouter, HTTPException, Response, status

from backend.models import Persona, PersonaUpdate
from backend.services.persona_service import PersonaService

router = APIRouter()
service = PersonaService()


@router.get("/personas")
def get_personas():
    """Return all personas."""
    return service.list()


@router.post("/personas", status_code=status.HTTP_201_CREATED)
def create_persona(oPersona: Persona):
    """Create one persona, failing on duplicate ``personaId``."""
    try:
        return service.create(oPersona)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/personas/{personaId}")
def update_persona(personaId: str, oChanges: PersonaUpdate):
    """Apply partial updates to an existing persona."""
    merged = service.update(personaId, oChanges)
    if merged is None:
        raise HTTPException(status_code=404, detail=f"Persona '{personaId}' not found")
    return merged


@router.delete("/personas/{personaId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona(personaId: str):
    """Delete one persona by identifier."""
    deleted = service.delete(personaId)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Persona '{personaId}' not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
