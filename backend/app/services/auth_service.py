"""用户注册（MVP）"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChildUser


def register_child(
    db: Session, *, parent_phone: str, nickname: str, jnao_uid: str | None = None
) -> ChildUser:
    user = ChildUser(
        parent_phone=parent_phone,
        nickname=nickname,
        jnao_uid=jnao_uid,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_child_user(db: Session, child_user_id: int) -> ChildUser | None:
    return db.get(ChildUser, child_user_id)


def find_child_by_phone(db: Session, parent_phone: str, nickname: str) -> ChildUser | None:
    return db.scalar(
        select(ChildUser).where(
            ChildUser.parent_phone == parent_phone,
            ChildUser.nickname == nickname,
        )
    )
