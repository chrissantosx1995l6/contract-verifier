import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Union
import yaml

from contract_verifier.models import ContractSpec, ExpectedResponse, RequestDef


PARAM_REGEX = re.compile(r"\{([a-zA-Z0-9_]+)\}")
ENV_VAR_REGEX = re.compile(r"\$\{([a-zA-Z0-9_]+)(?::-([^}]*))?\}")


class SpecParseError(Exception):
    """Raised when contract file cannot be parsed or lacks required structure."""
    pass


def _expand_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match):
            var_name = match.group(1)
            default_val = match.group(2)
            val = os.environ.get(var_name)
            if val is not None:
                return val
            if default_val is not None:
                return default_val
            # keep placeholder if not found, checker will fail visibly
            return match.group(0)
        return ENV_VAR_REGEX.sub(repl, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    return value


def resolve_path_params(path: str, params: Dict[str, Any]) -> str:
    def replace_match(match):
        key = match.group(1)
        if key not in params:
            raise SpecParseError(f"Missing path parameter '{key}' for path '{path}'")
        return str(params[key])

    return PARAM_REGEX.sub(replace_match, path)


def _parse_single_spec(raw: Dict[str, Any], source_file: str) -> ContractSpec:
    if not isinstance(raw, dict):
        raise SpecParseError(f"{source_file}: contract root must be a mapping")

    raw = _expand_env_vars(raw)

    name = raw.get("name")
    if not name:
        raise SpecParseError(f"{source_file}: 'name' field is required")

    req_data = raw.get("request")
    if not req_data or not isinstance(req_data, dict):
        raise SpecParseError(f"{source_file}: contract '{name}' missing 'request' section")

    method = req_data.get("method", "GET").upper()
    path = req_data.get("path")
    if not path:
        raise SpecParseError(f"{source_file}: contract '{name}' request must have a 'path'")

    path_params = req_data.get("path_params", {})
    if path_params:
        # FIXME: handle escaped curly braces if someone uses regex routes in path
        path = resolve_path_params(path, path_params)

    timeout = req_data.get("timeout", 10.0)
    try:
        timeout = float(timeout)
    except (ValueError, TypeError):
        timeout = 10.0

    req = RequestDef(
        method=method,
        path=path,
        headers=req_data.get("headers", {}),
        query=req_data.get("query", {}),
        body=req_data.get("body"),
        timeout_seconds=timeout,
    )

    resp_data = raw.get("response", {})
    if not isinstance(resp_data, dict):
        raise SpecParseError(f"{source_file}: contract '{name}' response section must be a map")

    # print(f"DEBUG: parsing spec {name} from {source_file}")

    latency = resp_data.get("max_latency_ms")
    if latency is not None:
        try:
            latency = float(latency)
        except (ValueError, TypeError):
            latency = None

    resp = ExpectedResponse(
        status=int(resp_data.get("status", 200)),
        headers=resp_data.get("headers", {}),
        schema=resp_data.get("schema"),
        exact_body=resp_data.get("exact_body"),
        max_latency_ms=latency,
        strict_headers=bool(resp_data.get("strict_headers", False)),
    )

    return ContractSpec(
        name=name,
        request=req,
        response=resp,
        description=raw.get("description", ""),
        tags=raw.get("tags", []),
        spec_id=raw.get("id"),
    )


def parse_spec_file(file_path: Union[str, Path]) -> List[ContractSpec]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Contract file not found: {path}")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []

    if path.suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SpecParseError(f"YAML syntax error in {path}: {exc}") from exc
    elif path.suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecParseError(f"JSON syntax error in {path}: {exc}") from exc
    else:
        raise SpecParseError(f"Unsupported spec file extension: {path.suffix}")

    if data is None:
        return []

    if isinstance(data, list):
        return [_parse_single_spec(item, str(path)) for item in data]
    elif isinstance(data, dict):
        if "contracts" in data and isinstance(data["contracts"], list):
            return [_parse_single_spec(item, str(path)) for item in data["contracts"]]
        return [_parse_single_spec(data, str(path))]
    else:
        raise SpecParseError(f"{path}: Root element must be an object or a list")


def load_specs_from_target(target: Union[str, Path]) -> List[ContractSpec]:
    p = Path(target)
    if not p.exists():
        raise FileNotFoundError(f"Spec target does not exist: {p}")

    if p.is_file():
        return parse_spec_file(p)

    specs: List[ContractSpec] = []
    # Walk recursively for yml, yaml and json
    for ext in ("*.yaml", "*.yml", "*.json"):
        for f in sorted(p.rglob(ext)):
            specs.extend(parse_spec_file(f))
    return specs
