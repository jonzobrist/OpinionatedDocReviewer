from sqlalchemy.orm import Session

from app.db import models
from app.schemas.persona import PersonaCreate, PersonaUpdate


def create_persona(db: Session, tenant_id: str, data: PersonaCreate) -> models.Persona:
    persona = models.Persona(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        focus_areas=data.focus_areas,
        tone=data.tone,
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
    for key, value in update_data.items():
        setattr(persona, key, value)
    db.commit()
    db.refresh(persona)
    return persona


def delete_persona(db: Session, tenant_id: str, persona_id: int) -> bool:
    persona = get_persona(db, tenant_id, persona_id)
    if not persona:
        return False
    db.delete(persona)
    db.commit()
    return True
