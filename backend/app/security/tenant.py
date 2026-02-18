from __future__ import annotations

import re

from fastapi import HTTPException

TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,62})$")


def validate_tenant_id(value: str | None) -> str:
    tenant_id = (value or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant id is required")
    if not TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid tenant id. Use 1-63 chars: letters, digits, _ or -.",
        )
    return tenant_id
