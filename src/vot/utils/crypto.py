import base64
import hashlib
import hmac
import random

from vot.config import COMPONENT_VERSION, HMAC_KEY

# Yandex browser security headers helper
BROWSER_SEC_HEADERS = {
    "sec-ch-ua": f'"Chromium";v="147", "YaBrowser";v="{COMPONENT_VERSION[:5]}", "Not?A_Brand";v="26", "Yowser";v="2.5"',
    "sec-ch-ua-full-version-list": f'"Chromium";v="147.0.7727.138", "YaBrowser";v="{COMPONENT_VERSION}", "Not?A_Brand";v="26.0.0.0", "Yowser";v="2.5"',
    "Sec-Fetch-Mode": "no-cors",
}


def get_uuid() -> str:
    """Generate a random 32-character uppercase hex UUID."""
    hex_digits = "0123456789ABCDEF"
    return "".join(random.choice(hex_digits) for _ in range(32))


def get_signature(body: bytes) -> str:
    """Calculate the Yandex signature for a request body (HMAC-SHA256)."""
    return hmac.new(HMAC_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()


def get_sec_ya_headers(
    sec_type: str,
    session_uuid: str,
    secret_key: str,
    body: bytes | None,
    path: str,
) -> dict[str, str]:
    """Generate Yandex SecHeaders for authentication.

    Args:
        sec_type: Security type (e.g. 'Vtrans', 'Vsubs', 'Ya-Summary').
        session_uuid: The session UUID.
        secret_key: The session secretKey.
        body: The request binary body.
        path: Endpoint path.
    """
    token = f"{session_uuid}:{path}:{COMPONENT_VERSION}"
    token_sign = get_signature(token.encode("utf-8"))

    if sec_type == "Ya-Summary":
        return {
            f"X-{sec_type}-Sk": secret_key,
            f"X-{sec_type}-Token": f"{token_sign}:{token}",
        }

    if body is None:
        raise ValueError(f"Body is required for sec type {sec_type}")

    sign = get_signature(body)
    return {
        f"{sec_type}-Signature": sign,
        f"Sec-{sec_type}-Sk": secret_key,
        f"Sec-{sec_type}-Token": f"{token_sign}:{token}",
    }


def get_hmac_sha1(hmac_key: str, salt: str) -> str:
    """Calculate HMAC-SHA1 signature and return Base64 encoded string (Weverse signature)."""
    digest = hmac.new(hmac_key.encode("utf-8"), salt.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")
