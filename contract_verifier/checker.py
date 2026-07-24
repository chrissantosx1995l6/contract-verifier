import re
from typing import Any
import jsonschema
from jsonschema import Draft7Validator, Draft202012Validator

from contract_verifier.models import ExpectedResponse, ActualResponse, CheckResult, Mismatch


def _format_json_path(path_tokens: list[Any]) -> str:
    if not path_tokens:
        return "$"
    parts = []
    for token in path_tokens:
        if isinstance(token, int):
            parts.append(f"[{token}]")
        else:
            # handle keys with dots or strange chars
            clean = str(token)
            if "." in clean or "/" in clean or " " in clean:
                parts.append(f"['{clean}']")
            else:
                parts.append(f".{clean}")
    return "$" + "".join(parts)


def _diff_plain_dict(expected: Any, actual: Any, current_path: str = "$") -> list[Mismatch]:
    diffs = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for k, exp_val in expected.items():
            sub_path = f"{current_path}.{k}"
            if k not in actual:
                diffs.append(
                    Mismatch(
                        kind="body",
                        path=sub_path,
                        expected=repr(exp_val),
                        actual="<missing>",
                        message=f"Field '{k}' missing from body",
                    )
                )
            else:
                diffs.extend(_diff_plain_dict(exp_val, actual[k], sub_path))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            diffs.append(
                Mismatch(
                    kind="body",
                    path=current_path,
                    expected=f"list of length {len(expected)}",
                    actual=f"list of length {len(actual)}",
                    message=f"Array length mismatch at {current_path}",
                )
            )
        for idx, (exp_item, act_item) in enumerate(zip(expected, actual)):
            diffs.extend(_diff_plain_dict(exp_item, act_item, f"{current_path}[{idx}]"))
    elif expected != actual:
        diffs.append(
            Mismatch(
                kind="body",
                path=current_path,
                expected=repr(expected),
                actual=repr(actual),
                message=f"Value mismatch at {current_path}",
            )
        )
    return diffs


def check_response(expected: ExpectedResponse, actual: ActualResponse) -> CheckResult:
    mismatches: list[Mismatch] = []

    # 1. Status check
    if expected.status is not None and actual.status_code != expected.status:
        mismatches.append(
            Mismatch(
                kind="status",
                path="$status",
                expected=str(expected.status),
                actual=str(actual.status_code),
                message=f"Expected HTTP {expected.status}, got {actual.status_code}",
            )
        )

    # 2. Header assertions
    actual_headers_lower = {k.lower(): v for k, v in actual.headers.items()}
    for h_key, pattern in expected.headers.items():
        val = actual_headers_lower.get(h_key.lower())
        if val is None:
            mismatches.append(
                Mismatch(
                    kind="header",
                    path=f"$headers.{h_key}",
                    expected=pattern,
                    actual=None,
                    message=f"Missing required header: {h_key}",
                )
            )
        elif not re.search(pattern, str(val)):
            mismatches.append(
                Mismatch(
                    kind="header",
                    path=f"$headers.{h_key}",
                    expected=pattern,
                    actual=str(val),
                    message=f"Header '{h_key}' ({val}) failed regex '{pattern}'",
                )
            )

    # 3. JSON Schema validation (preferred if present)
    if expected.schema:
        if actual.json_body is None:
            mismatches.append(
                Mismatch(
                    kind="schema",
                    path="$",
                    expected="valid JSON body",
                    actual=actual.text[:100] if actual.text else "<empty>",
                    message="Response body is not valid JSON or was empty",
                )
            )
        else:
            # try draft 2020-12 if schema declares it, fall back to draft 7
            validator_cls = Draft7Validator
            if isinstance(expected.schema, dict) and "2020-12" in expected.schema.get("$schema", ""):
                validator_cls = Draft202012Validator

            validator = validator_cls(expected.schema)
            errors = sorted(validator.iter_errors(actual.json_body), key=lambda e: list(e.path))
            for err in errors:
                path_str = _format_json_path(list(err.path))
                # print(f"DEBUG mismatch at {path_str}: {err.message}")
                mismatches.append(
                    Mismatch(
                        kind="schema",
                        path=path_str,
                        expected=f"{err.validator}={err.validator_value}",
                        actual=repr(err.instance)[:120],
                        message=err.message,
                    )
                )
    elif expected.body is not None:
        # FIXME: add support for plain text diff when content-type is not application/json
        if actual.json_body is not None and isinstance(expected.body, (dict, list)):
            mismatches.extend(_diff_plain_dict(expected.body, actual.json_body))
        elif expected.body != actual.text:
            mismatches.append(
                Mismatch(
                    kind="body",
                    path="$",
                    expected=str(expected.body)[:100],
                    actual=actual.text[:100] if actual.text else "<empty>",
                    message="Exact body content mismatch",
                )
            )

    return CheckResult(passed=len(mismatches) == 0, mismatches=mismatches)
