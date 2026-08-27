from fastapi import HTTPException, Request
from sqlalchemy import select

from app.db.models import User


def get_current_user(request: Request) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录")
    with request.app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.id == user_id))
        if user is None or user.github_account is None:
            raise HTTPException(status_code=401, detail="会话已失效")
        session.expunge(user)
        return user
