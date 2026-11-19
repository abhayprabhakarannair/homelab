import base64
import hashlib
import hmac

ITERATIONS = 101
SALT_LEN = 12


def mosquitto_hash(password, user):
    """mosquitto_passwd-compatible PBKDF2-SHA512 ($7$) hash with a salt derived from user and password,
    so re-runs are idempotent and only a password change rewrites the file."""
    if not password:
        raise ValueError("empty password")
    if not user or ":" in user:
        raise ValueError(f"invalid user {user!r}")
    pw = password.encode()
    salt = hmac.new(pw, f"mosquitto-salt:{user}".encode(), hashlib.sha256).digest()[:SALT_LEN]
    digest = hashlib.pbkdf2_hmac("sha512", pw, salt, ITERATIONS)
    return f"$7${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


class FilterModule:
    def filters(self):
        return {"mosquitto_hash": mosquitto_hash}
