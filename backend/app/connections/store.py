"""The `connections` table, reached through Supabase's REST API as the signed-in user.

We send the user's own access token, so row-level security applies to this server exactly as it does to the
browser: it can only ever read or change that user's rows, and it needs no admin key.
"""

import httpx

from app.auth.verifier import User

PROVIDER = "smartthings"


class ConnectionStore:
    def __init__(self, supabase_url: str, publishable_key: str, http: httpx.AsyncClient) -> None:
        self._url = f"{supabase_url.rstrip('/')}/rest/v1/connections"
        self._key, self._http = publishable_key, http

    def _headers(self, user: User, **extra: str) -> dict[str, str]:
        return {"apikey": self._key, "Authorization": f"Bearer {user.token}", **extra}

    async def smartthings(self, user: User) -> tuple[str, str] | None:
        """(sealed token, account label) for this user's SmartThings connection, if they have one."""
        response = await self._http.get(
            self._url,
            params={"provider": f"eq.{PROVIDER}", "select": "token_ciphertext,account_label"},
            headers=self._headers(user),
            timeout=10.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows or not rows[0].get("token_ciphertext"):
            return None
        return rows[0]["token_ciphertext"], rows[0].get("account_label") or ""

    async def save_smartthings(self, user: User, label: str, sealed_token: str) -> None:
        response = await self._http.post(
            self._url,
            params={"on_conflict": "user_id,provider"},
            headers=self._headers(user, Prefer="resolution=merge-duplicates,return=minimal"),
            json={
                "user_id": user.id,
                "provider": PROVIDER,
                "status": "connected",
                "account_label": label[:120],
                "token_ciphertext": sealed_token,
            },
            timeout=10.0,
        )
        response.raise_for_status()

    async def remove_smartthings(self, user: User) -> None:
        response = await self._http.delete(
            self._url, params={"provider": f"eq.{PROVIDER}"}, headers=self._headers(user), timeout=10.0
        )
        response.raise_for_status()
