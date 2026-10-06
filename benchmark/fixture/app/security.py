import base64
import hashlib
import hmac
import json
import time

from . import config


def hash_password(password):
    salt = hashlib.sha256(config.SECRET_KEY.encode()).hexdigest()[:16]
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return "%s$%s" % (salt, digest.hex())


def verify_password(password, hashed):
    salt, _, digest_hex = hashed.partition("$")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _sign(payload_b64):
    return hmac.new(config.SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()


def create_access_token(subject):
    payload = {
        "sub": str(subject),
        "exp": int(time.time()) + config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return "%s.%s" % (payload_b64, _sign(payload_b64))


def decode_access_token(token):
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(payload_b64), signature):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
