import asyncio
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.auth.verifier import AuthError, AuthUnavailable, SupabaseVerifier

URL = "https://project.supabase.co"
ISSUER = f"{URL}/auth/v1"
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def jwk(private_key, kid="k1"):
    return {**json.loads(ECAlgorithm.to_jwk(private_key.public_key())), "kid": kid, "alg": "ES256", "use": "sig"}


def token(key=KEY, kid="k1", alg="ES256", **overrides):
    now = int(time.time())
    claims = {"sub": "user-1", "email": "a@example.invalid", "role": "authenticated", "aud": "authenticated",
              "iss": ISSUER, "iat": now, "exp": now + 3600, **overrides}  # fmt: skip
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


class Jwks:
    def __init__(self, *keys):
        self.keys, self.fetches = list(keys), 0

    async def __call__(self):
        self.fetches += 1
        return {"keys": self.keys}


async def test_a_valid_token_names_the_user():
    user = await SupabaseVerifier(URL, Jwks(jwk(KEY))).verify(token())
    assert (user.id, user.email) == ("user-1", "a@example.invalid")
    assert user.token not in repr(user)


@pytest.mark.parametrize(
    "bad",
    [
        token(exp=int(time.time()) - 120),  # expired
        token(aud="someone-else"),
        token(iss="https://evil.example/auth/v1"),
        token(role="anon"),  # the public key's role, not a signed-in user
        token(key=OTHER_KEY),  # right kid, wrong signature
        "not.a.token",
    ],
)
async def test_bad_tokens_are_refused(bad):
    with pytest.raises(AuthError):
        await SupabaseVerifier(URL, Jwks(jwk(KEY))).verify(bad)


async def test_the_header_cannot_downgrade_the_algorithm():
    claims = {"sub": "user-1", "role": "authenticated", "aud": "authenticated", "iss": ISSUER}
    forged = jwt.encode(
        claims, "the-public-anon-key-reused-as-an-hmac-secret", algorithm="HS256", headers={"kid": "k1"}
    )
    unsigned = jwt.encode({"sub": "user-1"}, None, algorithm="none", headers={"kid": "k1"})
    verifier = SupabaseVerifier(URL, Jwks(jwk(KEY)))
    for bad in (forged, unsigned):
        with pytest.raises(AuthError, match="algorithm"):
            await verifier.verify(bad)


async def test_unknown_key_ids_cannot_make_us_hammer_the_jwks_endpoint():
    clock = [1000.0]
    jwks = Jwks(jwk(KEY))
    verifier = SupabaseVerifier(URL, jwks, now=lambda: clock[0])
    await verifier.verify(token())
    for i in range(20):
        with pytest.raises(AuthError):
            await verifier.verify(token(kid=f"random-{i}"))
    assert jwks.fetches == 1  # all within 30 s of the first fetch
    clock[0] += 31
    with pytest.raises(AuthError):
        await verifier.verify(token(kid="random-late"))
    assert jwks.fetches == 2


async def test_a_rotated_key_is_picked_up():
    clock = [1000.0]
    jwks = Jwks(jwk(KEY))
    verifier = SupabaseVerifier(URL, jwks, now=lambda: clock[0])
    await verifier.verify(token())
    jwks.keys.append(jwk(OTHER_KEY, kid="k2"))
    clock[0] += 31
    assert (await verifier.verify(token(key=OTHER_KEY, kid="k2"))).id == "user-1"


async def test_a_failing_jwks_endpoint_keeps_the_keys_we_had():
    clock = [1000.0]
    jwks = Jwks(jwk(KEY))
    verifier = SupabaseVerifier(URL, jwks, now=lambda: clock[0])
    await verifier.verify(token())

    async def down():
        raise ValueError("JWKS endpoint returned garbage")

    verifier._fetch = down
    clock[0] += 700  # past the cache lifetime
    assert (await verifier.verify(token())).id == "user-1"


async def test_initial_jwks_outage_requests_a_retry_instead_of_sign_out():
    clock = [1000.0]
    calls = [0]

    async def flaky():
        calls[0] += 1
        if calls[0] == 1:
            raise ValueError("temporarily down")
        return {"keys": [jwk(KEY)]}

    verifier = SupabaseVerifier(URL, flaky, now=lambda: clock[0])
    with pytest.raises(AuthUnavailable):
        await verifier.verify(token())
    with pytest.raises(AuthUnavailable):
        await verifier.verify(token())
    assert calls[0] == 1
    clock[0] += 31
    assert (await verifier.verify(token())).id == "user-1"


async def test_tabs_connecting_during_the_first_key_fetch_all_get_in():
    fetches = [0]

    async def slow():
        fetches[0] += 1
        await asyncio.sleep(0.05)
        return {"keys": [jwk(KEY)]}

    verifier = SupabaseVerifier(URL, slow)
    users = await asyncio.gather(*(verifier.verify(token()) for _ in range(3)))
    assert [u.id for u in users] == ["user-1"] * 3 and fetches[0] == 1


async def test_a_failed_key_fetch_is_retried_within_seconds_not_half_a_minute():
    clock = [1000.0]
    calls = [0]

    async def flaky():
        calls[0] += 1
        if calls[0] == 1:
            raise ValueError("temporarily down")
        return {"keys": [jwk(KEY)]}

    verifier = SupabaseVerifier(URL, flaky, now=lambda: clock[0])
    with pytest.raises(AuthUnavailable):
        await verifier.verify(token())
    clock[0] += 3
    assert (await verifier.verify(token())).id == "user-1"


async def test_a_header_that_disagrees_with_its_key_is_refused_cleanly():
    def part(data: dict) -> str:
        return jwt.utils.base64url_encode(json.dumps(data).encode()).decode()

    # RS256 in the header, while kid k1 is our ES256 key: hand-built, as an attacker would send it.
    forged = f"{part({'alg': 'RS256', 'kid': 'k1'})}.{part({'sub': 'x'})}.c2lnbmF0dXJl"
    with pytest.raises(AuthError):  # an AuthError, never a TypeError that becomes a 500
        await SupabaseVerifier(URL, Jwks(jwk(KEY))).verify(forged)


async def test_anonymous_supabase_sessions_are_not_accounts():
    with pytest.raises(AuthError):
        await SupabaseVerifier(URL, Jwks(jwk(KEY))).verify(token(is_anonymous=True))
