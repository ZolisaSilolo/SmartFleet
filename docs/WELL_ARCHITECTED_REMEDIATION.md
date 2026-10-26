# Well-Architected Review - Remediation Record

Each finding from the full review, what changed, and the evidence. "Test" names refer to `backend/tests` or `frontend/src/test`.

| ID | Finding | Fix | Evidence |
|---|---|---|---|
| C1 | HTTP API payload v2 sent to REST-v1 handlers; claims read from the wrong path -> every prod route failed | All services use `APIGatewayHttpResolver`; claims read from `requestContext.authorizer.jwt.claims`; tests build real v2 events | every service test; `test_vehicles.py::test_requires_verified_id_token_claims` |
| C2 | `custom:tenantId` mutable and client-writable; self sign-up open -> tenant takeover | Attribute immutable; app client `WriteAttributes` excludes it; `AllowAdminCreateUserOnly`; MFA on; `token_use=id` enforced; tenant format validated | `test_template.py::test_cognito_makes_tenant_identity_unspoofable`, `test_shared.py::test_tenant_comes_only_from_verified_id_token_claims` |
| C3 | Frontend had no authentication (dev headers, localStorage tenant) | Cognito SRP + TOTP sign-in, ID token to a same-origin `/api`; dev headers removed everywhere | `login.test.tsx`, `http.test.ts`, `no-mocks.test.ts` |
| H1 | Stream DLQ never fired; handler swallowed all errors | `DestinationConfig.OnFailure` SQS; errors propagate; partial batch responses; IteratorAge + DLQ alarms | `test_events.py` (failures reported, mixed batch), `test_template.py::test_stream_worker_has_a_real_failure_path` |
| H2 | Non-atomic, non-idempotent writes; phantom items; double dispatch | Transactions with condition expressions; vehicle/driver locks (`activeTripId`); conditional updates/deletes; strict models (`extra=forbid`) | `test_trips.py` (incl. stale-read race), `test_maintenance.py` |
| H3 | No pagination; full-table reads | `limit`/`nextToken`; tenant-bound cursors; time-range GSIs; bounded analytics window; hard cap that raises instead of truncating | `test_vehicles.py::test_pagination...`, `test_analytics.py::test_old_data_outside_the_window_is_excluded` |
| H4 | Unmetered public API and AI endpoints | API throttling; WAF (managed rules + per-IP rate limits) on CloudFront; per-tenant AI rate limiter that fails closed; AI kill switch; same-origin (no CORS) | `test_ai.py::test_rate_limit...`, `test_template.py` |
| H5 | `print()` logging, no metrics, alarms without actions, infinite log retention | Powertools JSON logs/metrics/traces; SNS (KMS) alarm actions; Lambda/API/DynamoDB/stream/AI alarms; dashboard; retention + KMS on log groups; API access logs | `test_template.py::test_runtime_observability_and_safe_deploys` |
| H6 | Weak deploy safety | Plan -> approve -> execute prod pipeline; canary + alarm rollback; `Retain` + deletion protection; CloudFront invalidation; smoke tests; SHA-pinned actions; job-scoped OIDC | `deploy.yml`, `scripts/smoke_test.py`, `test_template.py::test_all_data_tables_are_protected_and_retained` |
| H7 | Autonomous agent unsafe (global tenant, auto-booking, silent fallback) | Per-request tools bound to the tenant; propose-only writes needing human approval; validated inputs; no fallback; timeout | `test_ai.py` (tools, propose, timeout, failure mapping) |
| H8 | Region/residency inconsistency; dead Location client | Single Region (af-south-1) + WAF exception; Location code removed; geofence runs on tenant stations; AI residency caveat documented as a launch gate | `docs/RUNBOOKS.md` section 0, `test_analytics.py::test_geofence_verification_states` |
| M1 | GSIs keyed without tenant | Replaced by `tenantId`/`tenantId#vehicleId` indexes; unused indexes removed | `test_template.py::test_every_tenant_table_and_index_is_partitioned_by_tenant` |
| M2 | Weak edge config | Cache + origin-request policies, compression, response-headers policy (HSTS, CSP, ...), CloudFront Function for SPA routing without masking API errors, logging, optional custom domain/TLS 1.2 | `test_template.py::test_edge_is_hardened`, `scripts/smoke_test.py` |
| M3 | Docs bucket with CORS `*`, unused S3 permissions | Bucket and permissions removed (YAGNI); TLS-only bucket policies on remaining buckets | `test_template.py::test_no_unbounded_or_dead_resources` |
| M4 | Cognito hardening | MFA on, 12+ char passwords, SRP only, user-existence errors suppressed, token revocation, deletion protection | `test_template.py` |
| M5 | `bedrock:InvokeModel` on `*` | Three scoped statements (profile, regional model, global model) on the AI function only | `test_template.py::test_bedrock_iam_is_scoped_to_one_profile_and_model` |
| M6 | No backups beyond PITR / no RTO-RPO | AWS Backup daily/35d, restore runbook, targets stated (to be confirmed by the business) | `docs/RUNBOOKS.md` section 5 |
| M7 | No cost controls | Throttling, rate limits, scale-to-zero retained, log retention, S3 lifecycle; budgets/tags are an account-level task (see runbook) | - |
| M8 | Unpinned dependencies | Exact pins + hash-locked arm64 lockfile; `mcp` pinned to the fixed release; pip-audit and npm audit gates; Dependabot | `deploy.yml` |
| M9 | No git repo | `.gitignore` added; repository initialisation is a checklist item | `docs/RUNBOOKS.md` 0.7 |
| M10 | Docs drift / mis-mapped MCP servers | Inaccurate docs removed; README + runbooks rewritten; MCP config and agent prompt corrected | `README.md`, `.kiro/` |

## Newly discovered while fixing (not in the original review)
* `claude-3-haiku` (hard-coded) is not offered in af-south-1, so the old fallback would have masked a permanent AI outage. The model is now a stack parameter pointing at a Region-available inference profile.
* The old efficiency numbers used placeholder targets and an arbitrary utilisation formula; replaced by the full-tank method and a defined 30-day utilisation metric.
* The "authorised station" list was a global 6-station constant that would flag almost every legitimate fill-up; geofences are now per tenant.
* `mcp` 2.1.1 (a Strands dependency) has CVE-2026-59951; pinned to 1.30.0.
* `npm audit` reported 4 production vulnerabilities (react-router, js-cookie via Cognito library); resolved by upgrades.

## Residual risks and open decisions
1. **Bedrock access (Anthropic use-case form) and POPIA s72** - see runbook 0.2 / 0.3. Until resolved, run with `AiEnabled=false` or accept that AI endpoints return 503.
2. **Lambda concurrency quota is 10** - request an increase before launch.
3. **No tenant-facing notification channel**: `FuelAnomalyDetected`, `FuelOffGeofence` and `TripCompleted` are published to the (archived) event bus; nothing consumes them yet. Users see the results in Analytics.
4. **No per-user roles inside a tenant** (everyone in a tenant can do everything). Add Cognito groups if you need dispatcher vs. admin.
5. **Corridor/toll values are unverified reference data.**
6. **The make-based arm64 layer build and the CI pipeline have not been run end to end** from this workstation (no Linux/Docker here); the first staging run is the real test.
7. **CMK only for operational data** (logs, alerts, failure queue). DynamoDB uses the AWS-managed KMS key; move to a customer-managed key if your compliance posture requires it.
8. Direct `execute-api` URLs bypass WAF (protected by the JWT authorizer and throttling). Disable them (`DisableExecuteApiEndpoint`) once a custom domain fronts the API.
