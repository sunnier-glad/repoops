from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet

from app.auth.service import OAuthService, OAuthStateStore, TokenCipher


def test_oauth_state_is_single_use():
    store = OAuthStateStore(ttl_seconds=300)

    state = store.issue(return_to="/dashboard")

    assert store.consume(state) == "/dashboard"
    assert store.consume(state) is None


def test_authorize_url_contains_single_use_state():
    store = OAuthStateStore(ttl_seconds=300)
    service = OAuthService(
        client_id="client-id",
        redirect_uri="https://repoops.example.com/api/auth/github/callback",
        state_store=store,
    )

    url = service.build_authorize_url(return_to="/dashboard")
    query = parse_qs(urlparse(url).query)

    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [
        "https://repoops.example.com/api/auth/github/callback"
    ]
    assert query["state"][0]
    assert store.consume(query["state"][0]) == "/dashboard"


def test_token_cipher_round_trips_without_exposing_plaintext():
    plaintext = "github-token-value"
    cipher = TokenCipher(Fernet.generate_key())

    encrypted = cipher.encrypt(plaintext)

    assert encrypted != plaintext
    assert cipher.decrypt(encrypted) == plaintext
