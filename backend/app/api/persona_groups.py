from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id
from app.crud.persona_group import (
    create_group,
    delete_group,
    get_group,
    list_groups,
    update_group,
)
from app.schemas.persona_group import (
    PersonaGroupCreate,
    PersonaGroupRead,
    PersonaGroupUpdate,
)

router = APIRouter(prefix="/persona-groups", tags=["persona-groups"])


@router.get("", response_model=list[PersonaGroupRead])
def list_all(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[PersonaGroupRead]:
    return list_groups(db, tenant_id)


@router.post("", response_model=PersonaGroupRead, status_code=201)
def create(
    payload: PersonaGroupCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaGroupRead:
    return create_group(db, tenant_id, payload)


@router.get("/{group_id}", response_model=PersonaGroupRead)
def get_one(
    group_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaGroupRead:
    group = get_group(db, tenant_id, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Persona group not found")
    return group


@router.patch("/{group_id}", response_model=PersonaGroupRead)
def update(
    group_id: int,
    payload: PersonaGroupUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaGroupRead:
    group = update_group(db, tenant_id, group_id, payload)
    if not group:
        raise HTTPException(status_code=404, detail="Persona group not found")
    return group


@router.delete("/{group_id}", status_code=204)
def delete(
    group_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> None:
    success = delete_group(db, tenant_id, group_id)
    if not success:
        raise HTTPException(status_code=404, detail="Persona group not found")
