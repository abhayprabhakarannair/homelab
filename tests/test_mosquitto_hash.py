import base64
import hashlib

import pytest
from mosquitto import ITERATIONS, SALT_LEN, FilterModule, mosquitto_hash


def parse(h):
    algo, iterations, salt, digest = h.split("$")[1:]
    return algo, int(iterations), base64.b64decode(salt), base64.b64decode(digest)


def test_format_matches_mosquitto_passwd():
    algo, iterations, salt, digest = parse(mosquitto_hash("secret", "imp"))
    assert (algo, iterations, len(salt), len(digest)) == ("7", ITERATIONS, SALT_LEN, 64)


def test_digest_is_pbkdf2_sha512_of_password_and_salt():
    _, iterations, salt, digest = parse(mosquitto_hash("secret", "imp"))
    assert digest == hashlib.pbkdf2_hmac("sha512", b"secret", salt, iterations)


def test_deterministic():
    assert mosquitto_hash("secret", "imp") == mosquitto_hash("secret", "imp")


@pytest.mark.parametrize(("a", "b"), [(("secret", "imp"), ("secret", "devil")), (("secret", "imp"), ("other", "imp"))])
def test_salt_depends_on_user_and_password(a, b):
    assert parse(mosquitto_hash(*a))[2] != parse(mosquitto_hash(*b))[2]


def test_unicode_password():
    _, iterations, salt, digest = parse(mosquitto_hash("pässwörd✓", "imp"))
    assert digest == hashlib.pbkdf2_hmac("sha512", "pässwörd✓".encode(), salt, iterations)


@pytest.mark.parametrize(("password", "user"), [("", "imp"), (None, "imp"), ("x", ""), ("x", "a:b")])
def test_rejects_invalid_input(password, user):
    with pytest.raises(ValueError):
        mosquitto_hash(password, user)


def test_registered_as_filter():
    assert FilterModule().filters()["mosquitto_hash"] is mosquitto_hash
