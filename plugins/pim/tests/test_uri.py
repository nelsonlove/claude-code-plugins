from src.uri import pim_uri, parse_uri, generate_id

def test_pim_uri_format():
    uri = pim_uri("note", "internal", "n-001")
    assert uri == "pim://note/internal/n-001"

def test_pim_uri_with_adapter():
    uri = pim_uri("task", "omnifocus", "hLarPeCbbib")
    assert uri == "pim://task/omnifocus/hLarPeCbbib"

def test_parse_uri():
    parts = parse_uri("pim://message/himalaya/acct1-inbox-4527")
    assert parts == {"type": "message", "adapter": "himalaya", "native_id": "acct1-inbox-4527"}

def test_parse_uri_invalid():
    import pytest
    with pytest.raises(ValueError):
        parse_uri("not-a-pim-uri")

def test_generate_id_unique():
    id1 = generate_id("note")
    id2 = generate_id("note")
    assert id1 != id2
    assert id1.startswith("n-")

def test_generate_id_prefixes():
    assert generate_id("note").startswith("n-")
    assert generate_id("entry").startswith("en-")
    assert generate_id("task").startswith("t-")
    assert generate_id("event").startswith("ev-")
    assert generate_id("message").startswith("m-")
    assert generate_id("contact").startswith("cn-")
    assert generate_id("resource").startswith("r-")
    assert generate_id("topic").startswith("top-")
