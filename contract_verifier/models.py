from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RequestDef:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    query: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Any] = None
    timeout_seconds: float = 10.0


@dataclass
class ExpectedResponse:
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    schema: Optional[Dict[str, Any]] = None
    exact_body: Optional[Any] = None
    max_latency_ms: Optional[float] = None
    strict_headers: bool = False


@dataclass
class ContractSpec:
    name: str
    request: RequestDef
    response: ExpectedResponse
    description: str = ""
    tags: List[str] = field(default_factory=list)
    # legacy field from first prototype when spec was keyed by id
    spec_id: Optional[str] = None


@dataclass
class CheckFailure:
    kind: str  # status, header, schema, latency, connection
    message: str
    expected: Any = None
    actual: Any = None
    path: str = ""


@dataclass
class CheckResult:
    contract_name: str
    passed: bool
    duration_ms: float
    status_code: Optional[int] = None
    failures: List[CheckFailure] = field(default_factory=list)
