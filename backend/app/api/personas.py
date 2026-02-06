from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id
from app.crud.persona import (
    create_persona,
    delete_persona,
    get_persona,
    list_personas,
    update_persona,
)
from app.schemas.persona import PersonaCreate, PersonaRead, PersonaUpdate

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("", response_model=list[PersonaRead])
def list_all(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[PersonaRead]:
    return list_personas(db, tenant_id)


@router.post("", response_model=PersonaRead, status_code=201)
def create(
    payload: PersonaCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaRead:
    return create_persona(db, tenant_id, payload)


@router.get("/{persona_id}", response_model=PersonaRead)
def get_one(
    persona_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaRead:
    persona = get_persona(db, tenant_id, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.patch("/{persona_id}", response_model=PersonaRead)
def update(
    persona_id: int,
    payload: PersonaUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaRead:
    persona = update_persona(db, tenant_id, persona_id, payload)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.delete("/{persona_id}", status_code=204)
def delete(
    persona_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> None:
    success = delete_persona(db, tenant_id, persona_id)
    if not success:
        raise HTTPException(status_code=404, detail="Persona not found")
