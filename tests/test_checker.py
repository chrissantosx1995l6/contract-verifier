import pytest
from contract_verifier.checker import check_response
from contract_verifier.models import ResponseSpec


def test_status_mismatch():
    spec = ResponseSpec(status=200)
    res = check_response(spec, actual_status=404, actual_headers={}, actual_body={})
    assert not res.ok
    assert any("status mismatch: expected 200, got 404" in err for err in res.errors)


def test_schema_valid():
    spec = ResponseSpec(
        status=200,
        schema={
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean"}},
        },
    )
    res = check_response(spec, actual_status=200, actual_headers={}, actual_body={"ok": True})
    assert res.ok
    assert len(res.errors) == 0


def test_schema_invalid_type():
    spec = ResponseSpec(
        status=200,
        schema={
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        },
    )
    res = check_response(spec, actual_status=200, actual_headers={}, actual_body={"count": "not-a-number"})
    assert not res.ok
    assert any("count" in err for err in res.errors)


def test_headers_case_insensitive_match():
    spec = ResponseSpec(
        status=200,
        headers={"Content-Type": "application/json", "X-Api-Version": "1.0"},
    )
    actual_headers = {
        "content-type": "application/json; charset=utf-8",
        "x-api-version": "1.0",
        "server": "uvicorn",
    }
    res = check_response(spec, actual_status=200, actual_headers=actual_headers, actual_body=None)
    assert res.ok


def test_headers_missing():
    spec = ResponseSpec(
        status=200,
        headers={"X-Required-Token": "expected-val"},
    )
    res = check_response(spec, actual_status=200, actual_headers={"content-type": "text/plain"}, actual_body=None)
    assert not res.ok
    assert any("missing header 'X-Required-Token'" in err for err in res.errors)


def test_nested_schema_path_in_error():
    spec = ResponseSpec(
        status=200,
        schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "required": ["items"],
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                }
            },
        },
    )
    bad_payload = {"data": {"items": ["valid", 12345]}}
    res = check_response(spec, actual_status=200, actual_headers={}, actual_body=bad_payload)
    assert not res.ok
    # print(res.errors)
    assert any("data.items.1" in err or "data -> items" in err for err in res.errors)


def test_exact_body_match():
    spec = ResponseSpec(status=200, body={"status": "healthy"})
    res_ok = check_response(spec, actual_status=200, actual_headers={}, actual_body={"status": "healthy"})
    assert res_ok.ok

    res_bad = check_response(spec, actual_status=200, actual_headers={}, actual_body={"status": "unhealthy"})
    assert not res_bad.ok
    assert any("body mismatch" in err for err in res_bad.errors)
