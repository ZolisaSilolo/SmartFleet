# SmartFleet Runbooks

Region: **af-south-1**. The CloudFront WAF web ACL is the only us-east-1 resource. Treat this document as confidential
(it describes security controls).

## 0. Before the first production deployment (one-time checklist)

| # | Task | Why / how |
|---|---|---|
| 1 | Confirm the project Region (AWS Settings > View all projects > Overview > Additional Info > Region) is af-south-1 and set `~/.aws/config` `region = af-south-1` | The CLI profile currently says us-east-1; deploying with the wrong default Region creates resources in the wrong place |
| 2 | **Bedrock model access**: the default model is Moonshot **Kimi K3** (`global.moonshotai.kimi-k3`), which this account can invoke today with **no model-access form**. Confirm with `aws bedrock-runtime converse --region af-south-1 --model-id global.moonshotai.kimi-k3 --messages '[{"role":"user","content":[{"text":"ok?"}]}]' --inference-config '{"maxTokens":64}'`. To switch to an Anthropic/Nova model later, submit its model-access form and set the `BedrockModelId`/`BedrockFoundationModelId`/`BedrockSupportsTemperature` stack parameters | Kimi is a reasoning model and rejects `temperature`, so `BedrockSupportsTemperature=false` (handled automatically). AI endpoints return `503 AI_UNAVAILABLE` only if the model is genuinely unavailable - there is no heuristic fallback |
| 3 | **POPIA s72 sign-off**: Bedrock in af-south-1 is reached through *global* inference profiles (Kimi K3 is global-only), so prompts can be processed outside South Africa. Prompts contain aggregates and vehicle plates only (no driver names, phones or licence numbers). Get legal sign-off and update your privacy notice, or deploy with `AiEnabled=false` | There is no in-Region model profile for af-south-1 |
| 4 | **Request a Lambda concurrency increase** (Service Quotas > Lambda > Concurrent executions; the account quota is 10) | With 9 functions plus bursts, 10 is too low for production; `smart-fleet-*-lambda-concurrency` alarms at 8 |
| 5 | Replace the IAM user access keys on this machine with `aws login`/IAM Identity Center sessions; delete the long-lived keys | Long-lived keys are the main credential-theft risk |
| 6 | Create the GitHub OIDC provider and **three roles**: staging deploy, production *plan* (read + create change set), production *deploy* (execute). Scope trust to `repo:<org>/<repo>:environment:<name>` | See "OIDC roles" below |
| 7 | GitHub repo settings: environments `staging`, `production-plan` (no reviewers), `production` (**required reviewers**); secrets `AWS_ROLE_ARN_STAGING`, `AWS_ROLE_ARN_PROD_PLAN`, `AWS_ROLE_ARN_PROD`; variable `ALERT_EMAIL` (and optionally `DOMAIN_NAME`, `CERTIFICATE_ARN`); branch protection on `main` (PR review + required checks) | The workspace was not a git repository - initialise and push first |
| 8 | Review and own the **corridor reference data** (`backend/src/shared/corridors.py`) against the Sanral tariff schedule | Static values; labelled "not live Sanral data" in responses |
| 9 | Confirm the alert mailbox subscription (SNS sends a confirmation email) | Alarms are useless until confirmed |

### OIDC roles (summary)
* Trust policy: `token.actions.githubusercontent.com`, `aud = sts.amazonaws.com`, `sub = repo:<org>/<repo>:environment:<env>`.
* Staging/prod deploy roles need CloudFormation, IAM (pass role for stack-created roles), Lambda, API Gateway, DynamoDB, S3, CloudFront, Cognito, Logs, SNS, SQS, KMS, Events, Backup, CodeDeploy and CloudWatch for `smart-fleet-*` resources; the plan role must not be able to execute change sets. Generate a baseline with the `aws-iam` skill and tighten it with IAM Access Analyzer policy generation after the first staging deploy.

## 1. First deployment (staging, then production)

1. `pytest`, `ruff check backend scripts`, `cd frontend && npm ci && npm test && npm run build` - all green locally.
2. Push to `main`. CI deploys the WAF stack (us-east-1), builds the arm64 layer and deploys staging, publishes the SPA, invalidates CloudFront and runs `scripts/smoke_test.py`.
3. **Staging acceptance (manual, once):**
   * Create two users in two tenants: `python scripts/provision_tenant_user.py --user-pool-id <id> --email a@x.co.za --tenant-id staging-a` (and `staging-b`).
   * Sign in to each (temporary password -> new password -> authenticator enrolment).
   * As tenant A create a vehicle and driver; dispatch and complete a trip; log two full-tank fill-ups; confirm the odometer updates and L/100km appears.
   * As tenant B confirm none of A's data is visible and that A's ids return 404.
   * Try changing your own tenant: `aws cognito-idp update-user-attributes` with tenant B's id using tenant A's access token must be rejected (attribute is immutable/not writable).
   * Add an authorised station; log a fill-up outside it; confirm the Fuel anomaly/geofence results.
   * Ask the assistant a question (needs Bedrock access, task 0.2) and approve a proposed maintenance job.
   * Force a poison record (e.g. temporarily set `TRIPS_TABLE` to a wrong name on the processor) and confirm it lands in the failure queue and the `failed-stream-records` alarm fires; restore the setting.
4. Merge approved -> CI creates the **production change set**. Open the job summary, read every `Replace`/`Delete` row (stateful resources are `Retain` and must never show Delete), then approve the `production` environment.
5. Post-deploy: CodeDeploy shifts 10% of traffic for 5 minutes with automatic rollback on the `lambda-errors` alarm. Watch the `SmartFleet-prod` CloudWatch dashboard.

## 2. Onboard a tenant / user
`python scripts/provision_tenant_user.py --user-pool-id <id> --email <email> --tenant-id <slug>` (admin credentials). The tenant id is permanent (immutable attribute); to move a user to a different tenant delete and recreate the user. Offboarding: `aws cognito-idp admin-disable-user`, then export/erase tenant data per your POPIA process (query each table by `tenantId`).

## 3. Roll back
* **Automatic:** failed CloudFormation updates roll back; canary alarms roll back Lambda traffic.
* **Manual Lambda rollback:** `aws deploy stop-deployment --auto-rollback-enabled ...` during a canary, or re-run the previous commit's pipeline.
* **Frontend:** S3 versioning keeps previous assets - re-run the previous commit, or restore `index.html` from a prior version and invalidate `/index.html`.
* **Data:** see "Restore".

## 4. Failed stream records (SQS on-failure destination)
1. Alarm `...-failed-stream-records` fires. Inspect: `aws sqs receive-message --queue-url <FailedRecordsQueueUrl> --max-number-of-messages 10` (messages hold the shard/sequence range and the failure reason, not the record body).
2. Fix the root cause (see processor logs in `/smartfleet/<stage>/app`; filter `level=ERROR`).
3. Derived data is idempotent: re-save the affected trip/fuel item (e.g. a no-op `update_item` on `updatedAt`) or re-drive the range with `aws dynamodbstreams get-records` and invoke the processor with that event. Odometer updates are monotonic and safe to replay; EventBridge events are at-least-once.
4. Purge handled messages: `aws sqs purge-queue ...` only after the data is verified.

## 5. Restore (DynamoDB)
* Point-in-time: `aws dynamodb restore-table-to-point-in-time --source-table-name <name> --target-table-name <name>-restore --restore-date-time <ts>`; validate the data, then repoint (update the stack to the restored table via import) or copy items back.
* AWS Backup: daily recovery points (35 days) in vault `smart-fleet-vault-<stage>`.
* **Run a restore drill once per quarter** and record the elapsed time. Target RPO: 5 minutes (PITR); target RTO: 4 hours - confirm these with the business, they are not yet agreed.

## 6. Incident response
| Severity | Examples | First actions |
|---|---|---|
| SEV1 | Cross-tenant data exposure, credential compromise, total outage | Disable the app: set CloudFront distribution to disabled or attach a WAF block-all rule; revoke sessions (`aws cognito-idp admin-user-global-sign-out`); preserve CloudTrail + API access logs; notify the Information Officer - POPIA s22 requires notifying the Regulator and affected data subjects as soon as reasonably possible |
| SEV2 | Sustained 5xx, stream lag, AI outage | Check the dashboard and alarms, recent deployments (roll back), Bedrock status, DynamoDB throttles |
| SEV3 | Single feature degraded | Ticket and fix forward |

AI-specific levers: set `AiEnabled=false` (stack parameter, instant kill switch); tighten `AiRateLimitPerMinute/Day`; throttle the API with `ApiThrottleRate/Burst`.

## 7. Quarterly checks
* Reference data review (corridors, tolls) - owner: product.
* IAM Access Analyzer findings and unused-access report; rotate/delete stale users.
* `pip-audit` / `npm audit` / Dependabot PRs merged; Lambda runtime still supported.
* Cost review (Cost Explorer by tag `Stage`), Bedrock spend, and CloudWatch log volume.
* Restore drill (section 5) and this runbook's accuracy.
