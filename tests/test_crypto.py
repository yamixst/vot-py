import hmac
import hashlib
import base64
from vot.utils.crypto import get_uuid, get_signature, get_sec_ya_headers, get_hmac_sha1, BROWSER_SEC_HEADERS
from vot.config import HMAC_KEY, COMPONENT_VERSION


def test_get_uuid() -> None:
    uuid1 = get_uuid()
    uuid2 = get_uuid()
    assert len(uuid1) == 32
    assert len(uuid2) == 32
    assert uuid1 != uuid2
    assert uuid1.isupper()
    # verify only hex characters
    assert all(c in "0123456789ABCDEF" for c in uuid1)


def test_get_signature() -> None:
    body = b"hello world"
    expected = hmac.new(HMAC_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert get_signature(body) == expected


def test_get_sec_ya_headers() -> None:
    session_uuid = "SESSUUID1234"
    secret_key = "SECRETKEY1234"
    body = b"requestbody"
    path = "/path/test"

    # Test standard Vtrans headers
    headers = get_sec_ya_headers("Vtrans", session_uuid, secret_key, body, path)
    assert "Vtrans-Signature" in headers
    assert headers["Sec-Vtrans-Sk"] == secret_key
    assert "Sec-Vtrans-Token" in headers

    # Test Ya-Summary headers (body is None)
    summary_headers = get_sec_ya_headers("Ya-Summary", session_uuid, secret_key, None, path)
    assert summary_headers["X-Ya-Summary-Sk"] == secret_key
    assert "X-Ya-Summary-Token" in summary_headers


def test_get_hmac_sha1() -> None:
    key = "weverse_key"
    salt = "weverse_salt"
    expected_digest = hmac.new(key.encode("utf-8"), salt.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(expected_digest).decode("utf-8")
    assert get_hmac_sha1(key, salt) == expected
