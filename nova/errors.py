from __future__ import annotations


class NovaError(Exception):
    """Base error. User-facing messages must stay non-technical."""

    user_message = "Произошла ошибка."

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        super().__init__(message or self.user_message)
        self.detail = detail or message or self.user_message


class PermissionDenied(NovaError):
    user_message = "Недостаточно разрешений для этого действия."


class ConfirmationRequired(NovaError):
    user_message = "Нужно подтверждение."

    def __init__(self, token: str, summary: str, payload: dict | None = None) -> None:
        super().__init__(summary)
        self.token = token
        self.summary = summary
        self.payload = payload or {}


class ProviderError(NovaError):
    user_message = "Не удалось обратиться к модели."


class ToolError(NovaError):
    user_message = "Я не смог выполнить действие."


class VoiceError(NovaError):
    user_message = "Голосовой модуль недоступен. Продолжаю текстом."


class OfflineError(NovaError):
    user_message = "Нет сети. Работаю в офлайн-режиме."
