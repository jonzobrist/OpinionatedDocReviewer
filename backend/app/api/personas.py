from datetime import datetime, timezone

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
from app.db import models
from app.db.init_db import reset_default_persona, upsert_default_personas
from app.schemas.persona import (
    PersonaCreate,
    PersonaExportBundle,
    PersonaImportRequest,
    PersonaImportResult,
    PersonaPortable,
    PersonaRead,
    PersonaUpdate,
)

router = APIRouter(prefix="/personas", tags=["personas"])


def _resolve_group_id(db: Session, tenant_id: str, group_name: str | None) -> int | None:
    if not group_name:
        return None
    existing = (
        db.query(models.PersonaGroup)
        .filter(
            models.PersonaGroup.tenant_id == tenant_id,
            models.PersonaGroup.name == group_name,
        )
        .first()
    )
    if existing:
        return existing.id
    group = models.PersonaGroup(tenant_id=tenant_id, name=group_name, description=None)
    db.add(group)
    db.flush()
    return group.id


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


@router.post("/reset-defaults", response_model=list[PersonaRead])
def reset_defaults(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[PersonaRead]:
    upsert_default_personas(tenant_id=tenant_id, db=db)
    db.commit()
    return list_personas(db, tenant_id)


@router.post("/{persona_id}/reset-default", response_model=PersonaRead)
def reset_one_default(
    persona_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaRead:
    persona = get_persona(db, tenant_id, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if not (persona.is_default and persona.is_system_locked):
        raise HTTPException(
            status_code=400,
            detail="Only system default personas can be reverted with this endpoint",
        )
    return reset_default_persona(tenant_id=tenant_id, persona=persona, db=db)


@router.get("/bundle/export", response_model=PersonaExportBundle)
def export_personas(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaExportBundle:
    personas = list_personas(db, tenant_id)
    portable: list[PersonaPortable] = []
    for persona in personas:
        group_name = persona.group.name if persona.group else None
        portable.append(
            PersonaPortable(
                name=persona.name,
                description=persona.description,
                system_prompt=persona.system_prompt,
                focus_areas=persona.focus_areas or [],
                tone=persona.tone,
                reference_notes=persona.reference_notes,
                output_requirements=persona.output_requirements or {},
                examples=persona.examples or [],
                sort_order=persona.sort_order,
                color_theme=persona.color_theme,
                is_active=persona.is_active,
                group_name=group_name,
            )
        )
    return PersonaExportBundle(
        schema_version="v1",
        exported_at=datetime.now(timezone.utc),
        personas=portable,
    )


@router.post("/bundle/import", response_model=PersonaImportResult)
def import_personas(
    payload: PersonaImportRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> PersonaImportResult:
    if payload.schema_version != "v1":
        raise HTTPException(status_code=422, detail="Unsupported schema_version")
    result = PersonaImportResult()
    for item in payload.personas:
        group_id = _resolve_group_id(db, tenant_id, item.group_name)
        existing = (
            db.query(models.Persona)
            .filter(
                models.Persona.tenant_id == tenant_id,
                models.Persona.name == item.name,
            )
            .first()
        )
        if existing:
            if payload.conflict_policy == "skip":
                result.skipped += 1
                continue
            if payload.conflict_policy == "rename":
                base = item.name
                suffix = 2
                new_name = f"{base} ({suffix})"
                while (
                    db.query(models.Persona)
                    .filter(
                        models.Persona.tenant_id == tenant_id,
                        models.Persona.name == new_name,
                    )
                    .first()
                    is not None
                ):
                    suffix += 1
                    new_name = f"{base} ({suffix})"
                if not payload.dry_run:
                    db.add(
                        models.Persona(
                            tenant_id=tenant_id,
                            name=new_name,
                            description=item.description,
                            system_prompt=item.system_prompt,
                            focus_areas=item.focus_areas,
                            tone=item.tone,
                            reference_notes=item.reference_notes,
                            output_requirements=item.output_requirements.model_dump(),
                            examples=item.examples,
                            sort_order=item.sort_order,
                            color_theme=item.color_theme,
                            group_id=group_id,
                            is_active=item.is_active,
                        )
                    )
                result.renamed += 1
                continue
            if payload.conflict_policy == "overwrite":
                if not payload.dry_run:
                    existing.description = item.description
                    existing.system_prompt = item.system_prompt
                    existing.focus_areas = item.focus_areas
                    existing.tone = item.tone
                    existing.reference_notes = item.reference_notes
                    existing.output_requirements = item.output_requirements.model_dump()
                    existing.examples = item.examples
                    existing.sort_order = item.sort_order
                    existing.color_theme = item.color_theme
                    existing.group_id = group_id
                    existing.is_active = item.is_active
                result.updated += 1
                continue
        if not payload.dry_run:
            db.add(
                models.Persona(
                    tenant_id=tenant_id,
                    name=item.name,
                    description=item.description,
                    system_prompt=item.system_prompt,
                    focus_areas=item.focus_areas,
                    tone=item.tone,
                    reference_notes=item.reference_notes,
                    output_requirements=item.output_requirements.model_dump(),
                    examples=item.examples,
                    sort_order=item.sort_order,
                    color_theme=item.color_theme,
                    group_id=group_id,
                    is_active=item.is_active,
                )
            )
        result.created += 1

    if not payload.dry_run:
        db.commit()
    else:
        db.rollback()
    return result
