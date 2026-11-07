from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.persona import PersonaCreate, PersonaUpdate


def _validate_group(db: Session, tenant_id: str, group_id: int | None) -> None:
    if group_id is None:
        return
    group = db.query(models.PersonaGroup).filter(
        models.PersonaGroup.id == group_id,
        models.PersonaGroup.tenant_id == tenant_id,
    ).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Persona group not found")


def create_persona(db: Session, tenant_id: str, data: PersonaCreate) -> models.Persona:
    if data.is_default or data.is_system_locked:
        raise HTTPException(status_code=422, detail="Built-in persona flags are server-managed")
    _validate_group(db, tenant_id, data.group_id)
    persona = models.Persona(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        focus_areas=data.focus_areas,
        tone=data.tone,
        reference_notes=data.reference_notes,
        output_requirements=data.output_requirements.model_dump(),
        examples=data.examples,
        is_default=data.is_default,
        is_system_locked=data.is_system_locked,
        sort_order=data.sort_order,
        color_theme=data.color_theme,
        group_id=data.group_id,
        is_active=data.is_active,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def list_personas(db: Session, tenant_id: str) -> list[models.Persona]:
    return (
        db.query(models.Persona)
        .filter(models.Persona.tenant_id == tenant_id)
        .order_by(models.Persona.id.asc())
        .all()
    )


def get_persona(db: Session, tenant_id: str, persona_id: int) -> models.Persona | None:
    return (
        db.query(models.Persona)
        .filter(
            models.Persona.tenant_id == tenant_id,
            models.Persona.id == persona_id,
        )
        .first()
    )


def update_persona(
    db: Session, tenant_id: str, persona_id: int, data: PersonaUpdate
) -> models.Persona | None:
    persona = get_persona(db, tenant_id, persona_id)
    if not persona:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for flag in ("is_default", "is_system_locked"):
        if flag in update_data and update_data[flag] != getattr(persona, flag):
            raise HTTPException(status_code=422, detail="Built-in persona flags are server-managed")
    if "group_id" in update_data:
        _validate_group(db, tenant_id, update_data["group_id"])
    if "output_requirements" in update_data and update_data["output_requirements"] is not None:
        update_data["output_requirements"] = update_data["output_requirements"]
    for key, value in update_data.items():
        setattr(persona, key, value)
    db.commit()
    db.refresh(persona)
    return persona


def delete_persona(db: Session, tenant_id: str, persona_id: int) -> bool:
    persona = get_persona(db, tenant_id, persona_id)
    if not persona:
        return False
    if persona.is_default or persona.is_system_locked:
        raise HTTPException(status_code=409, detail="Built-in personas cannot be deleted; disable instead")
    db.delete(persona)
    db.commit()
    return True
