import pytest
from pathlib import Path
from contract_verifier.parser import parse_contract, parse_contract_file
from contract_verifier.models import ContractError


SIMPLE_YAML = """
name: get user endpoint
request:
  method: GET
  path: /users/123
  headers:
    Accept: application/json
response:
  status: 200
  schema:
    type: object
    required: [id, name]
    properties:
      id:
        type: integer
      name:
        type: string
"""


TEMPLATE_YAML = """
name: check {{ SERVICE_ENV }}
request:
  method: POST
  path: /api/{{ API_VERSION }}/items
  headers:
    Authorization: Bearer {{ AUTH_TOKEN }}
response:
  status: 201
"""


def test_parse_simple_valid_contract():
    contract = parse_contract(SIMPLE_YAML)
    assert contract.name == "get user endpoint"
    assert contract.request.method == "GET"
    assert contract.request.path == "/users/123"
    assert contract.request.headers.get("Accept") == "application/json"
    assert contract.response.status == 200
    assert contract.response.schema["type"] == "object"


def test_parse_invalid_yaml():
    with pytest.raises(ContractError, match="Invalid YAML"):
        parse_contract("foo: [bar: 123")


def test_parse_missing_required_fields():
    # missing response block
    raw = """
    name: broken spec
    request:
      method: POST
      path: /submit
    """
    with pytest.raises(ContractError, match="missing 'response'"):
        parse_contract(raw)


def test_variable_substitution(monkeypatch):
    monkeypatch.setenv("SERVICE_ENV", "staging")
    monkeypatch.setenv("API_VERSION", "v2")
    monkeypatch.setenv("AUTH_TOKEN", "secret-jwt-123")

    contract = parse_contract(TEMPLATE_YAML)
    assert contract.name == "check staging"
    assert contract.request.path == "/api/v2/items"
    assert contract.request.headers["Authorization"] == "Bearer secret-jwt-123"


def test_missing_variable_raises():
    with pytest.raises(ContractError, match="Unresolved variable"):
        parse_contract("name: {{ MISSING_VAR_NAME_XYZ }}\nrequest:\n  method: GET\n  path: /\nresponse:\n  status: 200")


def test_invalid_http_method():
    raw = """
    name: bad method
    request:
      method: INVALID_METHOD
      path: /
    response:
      status: 200
    """
    with pytest.raises(ContractError, match="Unsupported HTTP method"):
        parse_contract(raw)


def test_parse_file_not_found(tmp_path):
    bad_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError):
        parse_contract_file(bad_path)
