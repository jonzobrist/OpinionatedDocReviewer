from __future__ import annotations

ROLE_READER = "reader"
ROLE_REVIEWER = "reviewer"
ROLE_AUTHOR = "author"
ROLE_PROJECT_ADMIN = "project_admin"
ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_AUDITOR = "auditor"
ROLE_SERVICE_ACCOUNT = "service_account"

# Backward compatibility for existing data and tests.
ROLE_LEGACY_ADMIN = "admin"
ROLE_LEGACY_DEFAULT = "default"

ADMIN_ROLES = {ROLE_PROJECT_ADMIN, ROLE_SYSTEM_ADMIN, ROLE_LEGACY_ADMIN}
KNOWN_ROLES = {
    ROLE_READER,
    ROLE_REVIEWER,
    ROLE_AUTHOR,
    ROLE_PROJECT_ADMIN,
    ROLE_SYSTEM_ADMIN,
    ROLE_AUDITOR,
    ROLE_SERVICE_ACCOUNT,
    ROLE_LEGACY_ADMIN,
    ROLE_LEGACY_DEFAULT,
}


def is_admin_role(role: str | None) -> bool:
    if not role:
        return False
    return role in ADMIN_ROLES
