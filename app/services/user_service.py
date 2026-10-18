"""Serialize public users with their database-backed roles."""
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rbac import Role, UserRole
from app.models.user import User
from app.schemas.user import UserPublic

ROLE_PRIORITY = ("super_admin", "admin", "content_manager", "tutor", "parent", "student")


async def public_users(db: AsyncSession, users: Sequence[User]) -> list[UserPublic]:
    if not users:
        return []
    result = await db.execute(
        select(UserRole.user_id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id.in_([user.id for user in users]))
    )
    role_map = {user.id: set() for user in users}
    for user_id, name in result.all():
        role_map[user_id].add(name)

    def priority(name: str) -> tuple[int, str]:
        return (ROLE_PRIORITY.index(name) if name in ROLE_PRIORITY else len(ROLE_PRIORITY), name)

    responses = []
    for user in users:
        roles = sorted(role_map[user.id], key=priority)
        responses.append(UserPublic.model_validate(user).model_copy(
            update={"roles": roles, "role": roles[0] if roles else None}
        ))
    return responses


async def public_user(db: AsyncSession, user: User) -> UserPublic:
    return (await public_users(db, [user]))[0]
