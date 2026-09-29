"""Verifies SmartThings webhook requests (HTTP Signatures, draft-cavage, rsa-sha256).

Matches the official SmartApp SDK: parse `Authorization: Signature keyId=... headers=... signature=...`, fetch the
X.509 certificate at https://key.smartthings.com{keyId} (cached), verify the signing string with the certificate's
key. On top of the SDK we also check that the Digest header matches the body and that Date is recent, so a captured
signature can't be replayed with a different body or much later.
"""

import base64
import hashlib
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

KEY_HOST = "https://key.smartthings.com"
REQUIRED_HEADERS = {"(request-target)", "digest", "date"}
MAX_SKEW_S = 300
KEY_CACHE_TTL_S = 24 * 60 * 60
NEGATIVE_CACHE_S = 60
MAX_KEY_FETCHES = 6  # per FETCH_WINDOW_S, across all keyIds; SmartThings rotates keys rarely
FETCH_WINDOW_S = 60
MAX_CACHED_KEYS = 32
_PARAM = re.compile(r'(\w+)="([^"]*)"')
_SAFE_KEY_ID = re.compile(r"^/[A-Za-z0-9/_.-]{1,200}$")

KeyFetcher = Callable[[str], Awaitable[bytes]]


class SignatureError(Exception):
    """The request is not provably from SmartThings."""


@dataclass(frozen=True)
class Parsed:
    key_id: str
    headers: list[str]
    algorithm: str
    signature: bytes


def parse_authorization(value: str) -> Parsed:
    if not value.startswith("Signature "):
        raise SignatureError("not an HTTP signature")
    params = dict(_PARAM.findall(value[len("Signature ") :]))
    try:
        return Parsed(
            key_id=params["keyId"],
            headers=params.get("headers", "date").lower().split(),
            algorithm=params.get("algorithm", "").lower(),
            signature=base64.b64decode(params["signature"], validate=True),
        )
    except (KeyError, ValueError) as exc:
        raise SignatureError("malformed signature header") from exc


def signing_string(method: str, path: str, headers: Mapping[str, str], names: list[str]) -> bytes:
    lines = []
    for name in names:
        if name == "(request-target)":
            lines.append(f"(request-target): {method.lower()} {path}")
        elif name in headers:
            lines.append(f"{name}: {headers[name]}")
        else:
            raise SignatureError(f"signed header {name!r} is missing")
    return "\n".join(lines).encode()


def body_digest(body: bytes) -> str:
    return "SHA-256=" + base64.b64encode(hashlib.sha256(body).digest()).decode()


def http_key_fetcher(client: httpx.AsyncClient) -> KeyFetcher:
    async def fetch(key_id: str) -> bytes:
        if not _SAFE_KEY_ID.fullmatch(key_id) or ".." in key_id or "//" in key_id:
            raise SignatureError("suspicious keyId")  # never let a request steer where we fetch from
        response = await client.get(f"{KEY_HOST}{key_id}", timeout=5.0)
        response.raise_for_status()
        return response.content

    return fetch


class SignatureVerifier:
    def __init__(self, fetch_key: KeyFetcher, now: Callable[[], float] = time.time) -> None:
        self._fetch_key = fetch_key
        self._now = now
        # keyId -> (valid until, key); None marks a key that recently failed to load.
        self._cache: dict[str, tuple[float, rsa.RSAPublicKey | None]] = {}
        self._fetches: deque[float] = deque()

    async def verify(self, method: str, path: str, headers: Mapping[str, str], body: bytes) -> None:
        lower = {k.lower(): v for k, v in headers.items()}
        parsed = parse_authorization(lower.get("authorization", ""))
        if parsed.algorithm != "rsa-sha256":
            raise SignatureError(f"unsupported algorithm {parsed.algorithm!r}")
        if not set(parsed.headers) >= REQUIRED_HEADERS:
            raise SignatureError("signature must cover (request-target), digest and date")
        if lower.get("digest", "").partition("=")[2] != body_digest(body).partition("=")[2]:
            raise SignatureError("body does not match its digest")
        try:
            sent = parsedate_to_datetime(lower["date"]).timestamp()
        except (KeyError, TypeError, ValueError) as exc:
            raise SignatureError("missing or unreadable Date header") from exc
        if abs(self._now() - sent) > MAX_SKEW_S:
            raise SignatureError("request is too old or from the future")
        key = await self._key(parsed.key_id)
        try:
            key.verify(parsed.signature, signing_string(method, path, lower, parsed.headers), padding.PKCS1v15(),
                       hashes.SHA256())  # fmt: skip
        except InvalidSignature as exc:
            raise SignatureError("signature does not verify") from exc

    async def _key(self, key_id: str) -> rsa.RSAPublicKey:
        now = self._now()
        cached = self._cache.get(key_id)
        if cached and cached[0] > now:
            if cached[1] is None:
                raise SignatureError("signing key failed to load recently")
            return cached[1]
        # The fetch happens before the signature can be checked, so an unsigned request can trigger it.
        # A small global budget stops random keyIds from turning us into an outbound request amplifier.
        while self._fetches and now - self._fetches[0] > FETCH_WINDOW_S:
            self._fetches.popleft()
        if len(self._fetches) >= MAX_KEY_FETCHES:
            raise SignatureError("too many signing-key lookups, try again shortly")
        self._fetches.append(now)
        try:
            key = x509.load_pem_x509_certificate(await self._fetch_key(key_id)).public_key()
            if not isinstance(key, rsa.RSAPublicKey):
                raise ValueError("signing key is not RSA")
        except (httpx.HTTPError, ValueError, SignatureError) as exc:
            self._remember(key_id, None, now + NEGATIVE_CACHE_S)
            raise SignatureError("could not load the SmartThings signing key") from exc
        self._remember(key_id, key, now + KEY_CACHE_TTL_S)
        return key

    def _remember(self, key_id: str, key: rsa.RSAPublicKey | None, until: float) -> None:
        if len(self._cache) >= MAX_CACHED_KEYS:
            now = self._now()
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
            while len(self._cache) >= MAX_CACHED_KEYS:
                self._cache.pop(next(iter(self._cache)))  # oldest first
        self._cache[key_id] = (until, key)
