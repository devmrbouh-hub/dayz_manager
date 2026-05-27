"""Авторизация для API"""

from fastapi import Request, HTTPException, Header, Depends
from typing import Optional


class AuthManager:
    """Управление авторизацией"""

    def __init__(self, config):
        self.config = config

    def verify_api_key(self, x_api_key: Optional[str] = Header(None)):
        """Проверить API ключ"""
        api_key = self.config.get('auth.api_key')

        if not x_api_key:
            raise HTTPException(status_code=401, detail="API key required")

        if x_api_key != api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")

        return True

    def verify_user(self, username: str, password: str) -> Optional[dict]:
        """Проверить пользователя"""
        users = self.config.get('auth.users', [])

        for user in users:
            if user.get('username') == username and user.get('password') == password:
                return user

        return None

    def check_role(self, user: dict, required_role: str) -> bool:
        """Проверить роль пользователя"""
        role_hierarchy = {
            'viewer': 0,
            'admin': 1
        }

        user_role = user.get('role', 'viewer')
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        return user_level >= required_level


# Dependency для FastAPI
def require_api_key(request: Request):
    """Dependency для проверки API ключа"""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    # Получить config из app.state
    config = request.app.state.config
    expected_key = config.get('auth.api_key')

    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


def require_admin(request: Request):
    """Dependency для мутирующих API-операций (тот же X-API-Key, что и require_api_key)."""
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    config = request.app.state.config
    expected_key = config.get('auth.api_key')

    if api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Проверить что это admin ключ
    return True
