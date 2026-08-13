from aurum_encuestas.session import get_session, safe_session_id, set_session


def test_safe_session_id_accepts_valid():
    assert safe_session_id("a-b-1") == "a-b-1"
    assert safe_session_id("ABCdef0123") == "ABCdef0123"


def test_safe_session_id_rejects_bad():
    assert safe_session_id(None) is None
    assert safe_session_id("") is None
    assert safe_session_id("../../etc") is None
    assert safe_session_id("has space") is None
    assert safe_session_id("x" * 65) is None


def test_set_get_session():
    set_session("abc")
    assert get_session() == "abc"
    set_session(None)
    assert get_session() is None
