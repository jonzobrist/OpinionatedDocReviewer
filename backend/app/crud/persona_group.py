from sqlalchemy.orm import Session

from app.db import models
from app.schemas.persona_group import PersonaGroupCreate, PersonaGroupUpdate


def create_group(db: Session, tenant_id: str, data: PersonaGroupCreate) -> models.PersonaGroup:
    group = models.PersonaGroup(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def list_groups(db: Session, tenant_id: str) -> list[models.PersonaGroup]:
    return (
        db.query(models.PersonaGroup)
        .filter(models.PersonaGroup.tenant_id == tenant_id)
        .order_by(models.PersonaGroup.id.asc())
        .all()
    )


def get_group(db: Session, tenant_id: str, group_id: int) -> models.PersonaGroup | None:
    return (
        db.query(models.PersonaGroup)
        .filter(
            models.PersonaGroup.tenant_id == tenant_id,
            models.PersonaGroup.id == group_id,
        )
        .first()
    )


def update_group(
    db: Session, tenant_id: str, group_id: int, data: PersonaGroupUpdate
) -> models.PersonaGroup | None:
    group = get_group(db, tenant_id, group_id)
    if not group:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, tenant_id: str, group_id: int) -> bool:
    group = get_group(db, tenant_id, group_id)
    if not group:
        return False
    db.delete(group)
    db.commit()
    return True
