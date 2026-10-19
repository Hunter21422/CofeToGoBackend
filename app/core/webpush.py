from __future__ import annotations

import base64
import os
import struct
import time
from urllib.parse import urlparse

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64u_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def generate_vapid() -> tuple[str, str]:
    private = ec.generate_private_key(ec.SECP256R1())
    raw = private.private_numbers().private_value.to_bytes(32, "big")
    return b64u_encode(raw), b64u_encode(_public_bytes(private.public_key()))


def _hkdf(salt: bytes, info: bytes, length: int, ikm: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(payload: bytes, p256dh: str, auth: str) -> bytes:
    ua_public = b64u_decode(p256dh)
    auth_secret = b64u_decode(auth)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    as_private = ec.generate_private_key(ec.SECP256R1())
    as_public = _public_bytes(as_private.public_key())
    shared = as_private.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth_secret, b"WebPush: info\x00" + ua_public + as_public, 32, shared)
    salt = os.urandom(16)
    cek = _hkdf(salt, b"Content-Encoding: aes128gcm\x00", 16, ikm)
    nonce = _hkdf(salt, b"Content-Encoding: nonce\x00", 12, ikm)
    body = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack("!IB", 4096, len(as_public)) + as_public + body


def vapid_headers(endpoint: str, private_b64: str, public_b64: str, subject: str) -> dict[str, str]:
    url = urlparse(endpoint)
    value = int.from_bytes(b64u_decode(private_b64), "big")
    key = ec.derive_private_key(value, ec.SECP256R1())
    token = jwt.encode({"aud": f"{url.scheme}://{url.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}, key, algorithm="ES256")
    return {"Authorization": f"vapid t={token}, k={public_b64}"}


def endpoint_allowed(endpoint: str) -> bool:
    url = urlparse(endpoint)
    host = url.hostname or ""
    if url.scheme != "https" or url.port not in (None, 443) or not host or host == "localhost":
        return False
    return not host.replace(".", "").isdigit() and ":" not in host
