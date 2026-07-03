from app import security


def test_hash_and_verify_roundtrip():
    h = security.hash_password("hunter2pass")
    assert h != "hunter2pass"
    assert security.verify_password("hunter2pass", h)
    assert not security.verify_password("wrong", h)


def test_verify_handles_missing_hash():
    assert security.verify_password("anything", None) is False
    assert security.verify_password("anything", "") is False


def test_password_error_rules():
    assert security.password_error("short") is not None       # too short
    assert security.password_error("a" * 8) is None           # ok
    assert security.password_error("x" * 200) is not None      # exceeds 72 bytes


def test_is_admin(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_emails", "boss@bingetime.tv, other@x.com")
    assert security.is_admin({"email": "boss@bingetime.tv"})
    assert security.is_admin({"email": "BOSS@bingetime.tv"})  # case-insensitive
    assert not security.is_admin({"email": "nobody@x.com"})
    assert not security.is_admin(None)
