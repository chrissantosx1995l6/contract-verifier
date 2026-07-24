import json
import sys
from typing import List, Optional
from contract_verifier.models import CheckResult

# Minimal ANSI helpers to avoid external color deps
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _colorize(text: str, code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{code}{text}{RESET}"


def format_tap(results: List[CheckResult]) -> str:
    """Format verification results as TAP version 13."""
    lines = ["TAP version 13", f"1..{len(results)}"]
    for i, res in enumerate(results, start=1):
        description = f"{res.method} {res.path}"
        if res.spec_name:
            description += f" ({res.spec_name})"
        
        if res.ok:
            lines.append(f"ok {i} - {description}")
        else:
            lines.append(f"not ok {i} - {description}")
            # Diagnostics block
            lines.append("  ---")
            lines.append(f"  status_code: {res.status_code}")
            if res.errors:
                lines.append("  errors:")
                for err in res.errors:
                    lines.append(f"    - {json.dumps(err)}")
            if res.diff:
                lines.append("  diff: |")
                for diff_line in res.diff.splitlines():
                    lines.append(f"    {diff_line}")
            lines.append("  ...")
    return "\n".join(lines)


def format_json(results: List[CheckResult]) -> str:
    payload = {
        "total": len(results),
        "passed": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(payload, indent=2)


def _format_diff_line(line: str, color: bool) -> str:
    if not color:
        return f"      {line}"
    if line.startswith("+"):
        return f"      {GREEN}{line}{RESET}"
    if line.startswith("-"):
        return f"      {RED}{line}{RESET}"
    if line.startswith("@"):
        return f"      {GRAY}{line}{RESET}"
    return f"      {line}"


def format_text(results: List[CheckResult], color: bool = True, quiet: bool = False) -> str:
    passed = 0
    failed = 0
    lines = []

    for res in results:
        endpoint = f"{res.method} {res.path}"
        if res.ok:
            passed += 1
            if not quiet:
                tag = _colorize("PASS", GREEN + BOLD, color)
                timing = _colorize(f"{res.duration_ms:.1f}ms", GRAY, color)
                lines.append(f" {tag} {endpoint} ({res.status_code}) - {timing}")
        else:
            failed += 1
            tag = _colorize("FAIL", RED + BOLD, color)
            lines.append(f" {tag} {endpoint} (got {res.status_code}, expected {res.expected_status or 'match'})")
            for err in res.errors:
                lines.append(f"      {_colorize('*', RED, color)} {err}")
            if res.diff:
                lines.append(f"      {_colorize('--- payload mismatch ---', YELLOW, color)}")
                for d in res.diff.splitlines():
                    lines.append(_format_diff_line(d, color))

    if quiet and not lines:
        # nothing failed and quiet mode was on
        pass
    else:
        lines.append("")

    summary_color = GREEN if failed == 0 else RED
    summary_text = f"{passed} passed, {failed} failed, {len(results)} total"
    lines.append(f"Summary: {_colorize(summary_text, summary_color + BOLD, color)}")
    return "\n".join(lines)
