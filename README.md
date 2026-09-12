# contract-verifier

I got tired of dragging full Pact frameworks and JVM-based OpenAPI checkers into CI pipelines just to verify that a downstream service didn't quietly break its JSON contract or status codes.

`contract-verifier` is a small CLI tool that runs a set of declarative contract specs (YAML/JSON) against live targets or recorded HAR/JSONL payloads, validating status codes, required headers, and payload schemas via JSON Schema.

## Install

```bash
pip install .
```

Or using pipx for local use:

```bash
pipx install .
```

## Usage

Run against a live staging environment:

```bash
contract-verifier run contracts/auth-service.yaml --base-url https://staging-auth.internal
```

Verify offline HAR dump captured from integration tests:

```bash
contract-verifier replay contracts/billing.yaml --har test-run.har
```

Emit TAP or JSON for CI output:

```bash
contract-verifier run contracts/*.yaml --base-url http://127.0.0.1:8080 --format tap
```

## Contract format

Contracts are simple YAML files:

```yaml
name: Get User Profile
request:
  method: GET
  path: /v1/users/{user_id}
  params:
    user_id: usr_8f3a9
  headers:
    Authorization: Bearer test-token
response:
  status: 200
  headers:
    content-type: application/json
  schema:
    type: object
    required: [id, email, status, created_at]
    properties:
      id:
        type: string
      email:
        type: string
        format: email
      status:
        type: string
        enum: [active, suspended, deleted]
      created_at:
        type: integer
```

## License

MIT

<!-- refreshed: 2026-09-12 -->
