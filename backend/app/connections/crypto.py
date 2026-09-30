"""Seals SmartThings tokens before they are stored, so a leaked database row can't be used on its own.

Fernet is authenticated encryption: a row someone edited fails to open instead of turning into a different token.
"""

import json
from dataclasses import asdict

from cryptography.fernet import Fernet, InvalidToken

from app.devices.smartthings.oauth import Token


class TokenBox:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode()) if key else None  # a malformed key fails loudly at startup

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def seal(self, token: Token) -> str:
        if self._fernet is None:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
        return self._fernet.encrypt(json.dumps(asdict(token)).encode()).decode()

    def open(self, ciphertext: str) -> Token | None:
        """The token, or None when the row was tampered with or sealed with another key."""
        if self._fernet is None:
            return None
        try:
            data = json.loads(self._fernet.decrypt(ciphertext.encode()))
            token = Token(**data)
        except (InvalidToken, ValueError, TypeError):
            return None
        return token if isinstance(token.access_token, str) and token.access_token else None
