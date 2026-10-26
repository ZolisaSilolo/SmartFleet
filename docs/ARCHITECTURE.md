# SmartFleet — Full-Stack Architecture

This document describes how SmartFleet is built end to end: the request lifecycle, the data model, change data
capture, the AI agent, security, and observability. It complements the [README](../README.md) (overview + API list),
the [runbooks](RUNBOOKS.md) (operations) and the [remediation record](WELL_ARCHITECTED_REMEDIATION.md).

Diagrams live in [`architecture/`](architecture) and are regenerated from
[`generate_diagrams.py`](architecture/generate_diagrams.py):

- `smartfleet-architecture.png` — the whole system
- `smartfleet-cdc-flow.png` — the write path and the stream-failure path
- `smartfleet-cicd.png` — the deploy pipeline

---

## 1. Shape of the system

SmartFleet is a single-Region (`af-south-1`), scale-to-zero serverless application. There are no servers, no VPC and
no idle compute; cost tracks usage. One CloudFront distribution is the single public entry point and serves both the
SPA and the API same-origin, so the browser never makes a cross-origin call and the app needs no CORS.

```
Browser ──▶ CloudFront ──▶ /*      ──▶ S3 (SPA, private, OAC)
                       └── /api/*  ──▶ API Gateway HTTP API ──▶ Lambda ──▶ DynamoDB
                                                                     └──▶ Bedrock (ai only)
DynamoDB Streams ──▶ processor Lambda ──▶ EventBridge (+archive) / SQS failure queue
```

CloudFront uses a viewer-request **CloudFront Function** to (a) strip the `/api` prefix before forwarding to the API
origin and (b) rewrite extension-less paths to `/index.html` for SPA client-side routing — without masking real API
`403/404` responses (a bug the original design had via `CustomErrorResponses`).

---

## 2. Request lifecycle (synchronous API)

1. The browser sends `GET /api/vehicles` with `Authorization: Bearer <Cognito ID token>`.
2. CloudFront's WAF web ACL evaluates managed rules and per-IP rate limits, then the function strips `/api` and routes
   to the API Gateway origin.
3. The HTTP API's **JWT authorizer** validates the token against the Cognito user pool (issuer + audience) and injects
   the verified claims at `requestContext.authorizer.jwt.claims`.
4. The domain Lambda runs. `shared/http.py` wraps every handler with Powertools logging/metrics/tracing and a uniform
   exception handler, then `shared/auth.py` extracts the tenant:
   - requires `token_use == "id"` (access tokens carry no custom attributes),
   - reads `custom:tenantId` and validates its shape,
   - there is **no** header fallback and **no** default tenant.
5. The handler validates the body with a strict Pydantic model (`extra="forbid"` → unknown/privileged fields are
   rejected), then calls a `TenantRepo` (see §3) whose every key is prefixed with the tenant id.
6. `shared/response.py` serialises the result (Decimals → numbers) with `Cache-Control: no-store`. Security headers
   (HSTS, CSP, `X-Frame-Options`, …) are applied centrally by the CloudFront response-headers policy, not per Lambda.

Errors are typed (`shared/errors.ApiError`) and mapped to stable codes: `UNAUTHORIZED` (401), `VALIDATION_ERROR` (400),
`NOT_FOUND` (404), `CONFLICT`/`INVALID_TRANSITION` (409), `DATASET_TOO_LARGE`/`NO_CORRIDOR_DATA` (422),
`RATE_LIMITED` (429), `AI_*` (502/503). Unhandled exceptions become `INTERNAL_ERROR` (500) and never leak internals.

---

## 3. Data model

Seven DynamoDB tables, all on-demand, PITR-enabled, SSE-KMS, and (except the ephemeral rate-limit table) `Retain` +
deletion-protected. **Every table and GSI is partitioned by tenant**, which is the backbone of the isolation guarantee.

| Table | PK | SK | GSIs | Notes |
|---|---|---|---|---|
| Vehicles | `tenantId` | `vehicleId` | `plate-index` (tenantId / plateNumber, KEYS_ONLY) | `activeTripId` lock while on a trip |
| Drivers | `tenantId` | `driverId` | — | `activeTripId` lock; status owned by trip workflow |
| Stations | `tenantId` | `stationId` | — | tenant-owned geofence anchors |
| Trips | `tenantId` | `tripId` | `tenant-startTime-index` | status machine IN_PROGRESS→COMPLETED/CANCELLED |
| Fuel | `tenantId` | `logId` | `tenant-fillDate-index`, `vehicle-fillDate-index` (PK `vehicleKey` = `tenantId#vehicleId`) | the vehicle index is **tenant-scoped by construction** |
| Maintenance | `tenantId` | `recordId` | `tenant-serviceDate-index` | status machine PROPOSED→SCHEDULED→IN_PROGRESS→COMPLETED |
| RateLimit | `rateKey` | — | — | TTL on `expiresAt`; fixed-window AI counters |

`shared/repo.py` (`TenantRepo`) centralises access: creates with a uniqueness condition, reads/updates/deletes with
`attribute_exists(tenantId)` guards (so a wrong tenant gets a clean 404, not a silent success), and exposes
`transact()` for multi-item transactions. `shared/pagination.py` provides `paged_query` (one page + opaque,
tenant-bound `nextToken`) and `query_all` (follows every page but raises `DATASET_TOO_LARGE` instead of truncating).

**Transactions** keep related rows consistent:

- *Dispatch* (`POST /trips`): put the trip + set `activeTripId` on the vehicle (condition: ACTIVE and no active trip) +
  set the driver ON_TRIP — all or nothing. Pre-checks also validate licence/PrDP expiry and odometer regression.
- *Complete / cancel*: update the trip (condition: still IN_PROGRESS) + free the driver + clear the vehicle's
  `activeTripId`, in one transaction.
- *Maintenance IN_PROGRESS/COMPLETED*: transition the record + flip the vehicle to/from IN_MAINTENANCE together.

---

## 4. Change data capture (asynchronous)

The Trips and Fuel tables stream `NEW_AND_OLD_IMAGES` to `events/processor.py`. The processor is the **single owner**
of the vehicle odometer and the only emitter of domain events, so the synchronous API never double-writes derived data.

- **Trip completed** → update the vehicle odometer with a *monotonic* conditional write (replays are no-ops) and emit
  `TripCompleted`.
- **Fuel inserted** → compute L/100km with the **full-tank method** (litres between two full fills ÷ distance); if it
  exceeds target by the threshold, emit `FuelAnomalyDetected`. Check the fill-up against the tenant's authorised
  stations; if outside every geofence, emit `FuelOffGeofence`. If the tenant has no stations, nothing is asserted.

**Failure handling (no silent drops):** handler exceptions propagate. The event source mapping retries ×3, bisects the
batch on error, reports partial batch failures, and routes exhausted records to an **SQS on-failure destination** that
raises the `failed-stream-records` alarm. An `IteratorAge` alarm catches a lagging consumer. (The original design put a
Lambda async DLQ on a stream source — which never fires — and swallowed every exception; both are fixed.)

Events are published to a custom EventBridge bus with a 30-day archive for replay. No consumers are wired yet; results
surface in Analytics. Adding a notifier later is a rule on the bus.

---

## 5. AI assistant

Two endpoints on an isolated `ai` Lambda (its own IAM and timeouts, so Bedrock access never widens the other services):

- `POST /analytics/ai-insights` — sends **aggregates only** to Bedrock and parses a strict 3-item JSON array; a
  malformed response is `AI_BAD_RESPONSE` (502), never a fabricated answer.
- `POST /agent/chat` — a Strands agent with five per-request, tenant-bound tools: fleet KPIs, fuel-geofence audit,
  maintenance alerts, corridor lookup, and `propose_maintenance_service`.

Safety properties (`backend/src/agent/fleet_agent.py`):

- Tools are built in a closure around the authenticated tenant id — no module-level tenant state, no default, so one
  request can never act for another tenant.
- The agent can **only propose** maintenance (status `PROPOSED`); a human approves it (→ `SCHEDULED`). Nothing is
  booked or dispatched autonomously; proposed records are excluded from "due" and spend.
- No heuristic fallback: a Bedrock failure is `AI_UNAVAILABLE` (503), a timeout is `AI_TIMEOUT` (504), other failures
  `AI_AGENT_ERROR` (502). The agent run is bounded by a thread timeout derived from the Lambda's remaining time.
- Per-tenant fixed-window rate limiting (`shared/ratelimit.py`) backed by the TTL table; it **fails closed**
  (`RATE_LIMITER_UNAVAILABLE`) so an unmetered paid API is never exposed. `AiEnabled=false` is an instant kill switch.

**Model:** the default is Moonshot **Kimi K3** (`global.moonshotai.kimi-k3`), a global inference profile this account
can call with no model-access form. `shared/bedrock.py` abstracts two model quirks so the choice is swappable via stack
parameters: reasoning models reject `temperature` (`BedrockSupportsTemperature=false`) and emit a reasoning block
before the text (`extract_text` concatenates only text blocks). IAM uses the AWS three-part global cross-Region
inference policy, scoped to exactly one profile + model.

---

## 6. Identity & security

- **Cognito** user pool: SRP sign-in, **mandatory TOTP MFA**, admin-created users only (no self sign-up), 12-char
  password policy, token revocation. `custom:tenantId` is **immutable** and excluded from the app client's write
  attributes, so a signed-in user cannot change their own tenant. The frontend uses `amazon-cognito-identity-js` with
  tokens in `sessionStorage` (not `localStorage`).
- **Transport & edge:** HTTPS only; CloudFront response-headers policy sets HSTS, a strict CSP, `X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy` and `Permissions-Policy`; buckets deny non-TLS via `aws:SecureTransport`.
- **WAF** (us-east-1, CLOUDFRONT scope): AWS managed IP-reputation, common and known-bad-inputs rule sets, plus per-IP
  rate limits (stricter on `/api/*`), with redacted logging.
- **Encryption:** a customer-managed KMS key encrypts the alert topic, the failure queue and the application log group;
  DynamoDB and S3 use SSE. Logs are retained and access-restricted; the SNS topic enforces TLS.
- **IAM:** least privilege per function (per-table policies; only `ai` can call Bedrock). CI uses GitHub OIDC with
  three scoped roles (staging deploy, prod plan, prod execute) — no long-lived keys.

---

## 7. Observability

Powertools emit structured JSON logs (no PII — identifiers and error classes only), EMF metrics and X-Ray traces.
Alarms, all wired to the KMS-encrypted SNS topic, cover: any Lambda error (also the canary rollback trigger), Lambda
throttles and account concurrency, API 5xx and p95 latency, DynamoDB read/write throttles, stream `IteratorAge`, the
failure queue depth, and custom `AiFailures`/`UnhandledErrors`. A CloudWatch dashboard (`SmartFleet-<stage>`) shows API
traffic, Lambda errors, CDC lag, business metrics (trips, anomalies, proposals) and AI usage.

---

## 8. Frontend

React 18 + Vite + TypeScript + Tailwind. `services/auth.ts` wraps the Cognito SRP flow including the new-password and
TOTP-enrolment challenges; `services/http.ts` attaches the ID token, enforces a request timeout, surfaces API errors
with their stable code (no offline fallback), and `listAll` follows `nextToken` but refuses to silently truncate.
`AuthContext` gates the app on a valid session and reacts to a `session-expired` event. A build-failing test
(`no-mocks.test.ts`) ensures demo data, dev-identity headers, `localStorage` tokens and heuristic fallbacks never
return. There is deliberately no mock backend — the dev server proxies `/api` to a deployed environment.

---

## 9. CI/CD

`.github/workflows/deploy.yml`: on every PR, run `ruff`, backend tests (with coverage gate), `sam validate` +
cfn-lint + cfn-guard, `pip-audit` + `npm audit`, and the frontend build/tests. On `main`: deploy the WAF stack
(us-east-1) and the main stack to staging, publish the SPA with cache-busting + CloudFront invalidation, and smoke-test.
Production is **plan → manual approval → execute**: a change set is created and its resource changes printed to the job
summary (stateful resources must never show `Delete`), a reviewer approves the `production` environment, then the change
set executes with CodeDeploy canary traffic shifting and automatic rollback on the Lambda-errors alarm. Actions are
SHA-pinned; Dependabot keeps actions, npm and pip current.

---

## 10. Known constraints & decisions

- **Single Region.** af-south-1 only; the WAF web ACL is the sole us-east-1 resource (AWS requirement for CloudFront).
- **AI residency.** Global inference profiles may process prompts outside South Africa; prompts are minimised to
  aggregates + plates. Requires POPIA s72 sign-off or `AiEnabled=false`.
- **Lambda concurrency.** The account quota starts at 10; request an increase before production (alarm fires at 8).
- **Reference data.** Corridor distances/tolls are static and product-owned; the API labels them as unverified.
- **Not yet built.** No tenant-facing notifications (events are archived, not delivered); no per-user roles within a
  tenant (add Cognito groups if needed); the arm64 layer build and full pipeline haven't run end-to-end from a
  developer workstation (the first staging run is the real test).
