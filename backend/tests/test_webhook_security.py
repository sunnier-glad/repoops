import hashlib
import hmac

from app.webhooks.security import sign_payload, verify_signature


def test_webhook_signature_accepts_only_matching_sha256_digest():
    payload = b'{"action":"opened"}'
    secret = "hook-secret"
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert sign_payload(payload, secret) == signature
    assert verify_signature(payload, signature, secret)
    assert not verify_signature(payload, signature, "wrong-secret")
    assert not verify_signature(payload + b" ", signature, secret)
    assert not verify_signature(payload, "", secret)
    assert not verify_signature(payload, "sha1=bad", secret)
