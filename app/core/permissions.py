from fastapi import HTTPException, status

ROLE_PERMISSIONS = {
    "customer": {"profile:read:self", "profile:update:self", "services:read", "applications:create:self",
                 "applications:read:self", "documents:manage:self", "notifications:read:self"},
    "staff": {"services:read", "applications:read:assigned"},
    "owner": {"services:read", "applications:manage", "documents:review", "tasks:manage",
              "users:manage:staff", "reports:read", "notifications:read:staff"},
    "admin": {"*"},
}

def require_role(user: dict, *roles: str):
    if user.get("role") not in roles and user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

def has_permission(user: dict, permission: str) -> bool:
    if user.get("role") == "admin":
        return True
    permissions = user.get("permissions") or []
    if user.get("permissions_customized"):
        return permission in set(permissions)
    return permission in ROLE_PERMISSIONS.get(user.get("role"), set())
