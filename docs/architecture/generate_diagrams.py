"""
SmartFleet architecture diagram suite.

Renders a set of AWS Solutions Architect-grade diagrams as PNGs using AWS-native icons
(the `diagrams` library + Graphviz). The suite is layered by audience:

  Non-technical / exec / compliance      -> context, security-isolation
  Technical / engineering / operations   -> system, request-lifecycle, cdc-flow, ai-agent, cicd

Requires:
  pip install diagrams
  Graphviz `dot` on PATH (Windows: winget install Graphviz.Graphviz, then add
  "C:\\Program Files\\Graphviz\\bin" to PATH)

Run:
  python docs/architecture/generate_diagrams.py

Outputs (this directory):
  smartfleet-context.png           business context (plain language)
  smartfleet-architecture.png      full system architecture
  smartfleet-request-lifecycle.png a single authenticated API request, end to end
  smartfleet-cdc-flow.png          change-data-capture and the no-silent-failure path
  smartfleet-ai-agent.png          the Bedrock / Strands agent data flow and guardrails
  smartfleet-security.png          identity, tenant isolation and data protection
  smartfleet-cicd.png              CI/CD: verify -> staging -> plan -> approve -> canary
"""
from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb, DynamodbTable
from diagrams.aws.devtools import Codebuild, Codedeploy, Codepipeline
from diagrams.aws.general import Client, InternetAlt1, User, Users
from diagrams.aws.integration import Eventbridge, SQS
from diagrams.aws.integration import SimpleNotificationServiceSnsTopic as SNS
from diagrams.aws.management import Cloudwatch, CloudwatchAlarm, CloudwatchLogs
from diagrams.aws.ml import Bedrock
from diagrams.aws.mobile import Amplify
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import KMS, WAF, Cognito, IAMRole, Shield
from diagrams.aws.storage import Backup, S3

# --- Shared visual language ------------------------------------------------------------------
# One consistent palette and edge vocabulary across every diagram so the suite reads as a set.
BLUE = "#2563eb"    # request / client traffic
GREEN = "#059669"   # data-plane writes/reads (trusted, in-Region)
RED = "#dc2626"     # failure / reliability path / streams
AMBER = "#d97706"   # AI / cross-border / caution
GREY = "#64748b"    # control plane, telemetry, supporting

GRAPH_ATTR = {
    "fontsize": "22",
    "fontname": "Helvetica",
    "labelloc": "t",
    "pad": "0.75",
    "splines": "spline",
    "nodesep": "0.65",
    "ranksep": "1.05",
    "bgcolor": "white",
}
NODE_ATTR = {"fontsize": "12", "fontname": "Helvetica"}
EDGE_ATTR = {"fontsize": "11", "fontname": "Helvetica"}
CLUSTER_REGION = {"bgcolor": "#eef6ff", "style": "rounded", "pencolor": "#2563eb", "fontcolor": "#1e3a8a"}
CLUSTER_EDGE = {"bgcolor": "#fff7ed", "style": "rounded", "pencolor": "#d97706", "fontcolor": "#7c2d12"}
CLUSTER_SEC = {"bgcolor": "#f5f3ff", "style": "rounded", "pencolor": "#7c3aed", "fontcolor": "#4c1d95"}
CLUSTER_OPS = {"bgcolor": "#f1f5f9", "style": "rounded", "pencolor": "#64748b", "fontcolor": "#334155"}


def _diagram(title: str, filename: str, direction: str = "LR") -> Diagram:
    return Diagram(
        title,
        filename=filename,
        outformat="png",
        show=False,
        direction=direction,
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    )


# =============================================================================================
# 1. BUSINESS CONTEXT — for non-technical stakeholders (what it is, who uses it, where data lives)
# =============================================================================================
def context_diagram() -> None:
    title = "SmartFleet - Business Context (what it does and where it runs)"
    with _diagram(title, "smartfleet-context"):
        owner = User("Fleet owner / controller\n(South African SME,\n2-50 vehicles)")

        with Cluster("SmartFleet - runs entirely on AWS (Cape Town, af-south-1)", graph_attr=CLUSTER_REGION):
            app = CloudFront("Secure web app\n(one sign-in, works\non phone & desktop)")

            with Cluster("What it keeps track of", graph_attr=CLUSTER_OPS):
                ops = Lambda("Vehicles, drivers, trips,\nfuel & maintenance")
                money = Dynamodb("The numbers you run on:\ncash flow, cost per km,\nfuel efficiency (ZAR)")

            with Cluster("Smart help", graph_attr=CLUSTER_EDGE):
                ai = Bedrock("AI assistant\n(reads your data,\nsuggests - never books)")

        with Cluster("Assurances", graph_attr=CLUSTER_SEC):
            isolation = Cognito("Each business sees\nonly its own data")
            cost = CloudwatchAlarm("Pay only for what\nyou use (scale-to-zero)")

        owner >> Edge(color=BLUE, label="signs in once (secure)") >> app
        app >> Edge(color=GREEN, label="runs the fleet") >> ops
        app >> Edge(color=GREEN, label="shows the money") >> money
        app >> Edge(color=AMBER, label="asks for advice") >> ai
        app >> Edge(color=GREY, style="dashed") >> isolation
        money >> Edge(color=GREY, style="dotted") >> cost


# =============================================================================================
# 2. SYSTEM ARCHITECTURE — the full technical topology
# =============================================================================================
def system_diagram() -> None:
    title = "SmartFleet - Serverless Multi-Tenant Architecture (af-south-1)"
    with _diagram(title, "smartfleet-architecture"):
        user = User("Fleet operator\n(tenant user)")

        with Cluster("Global edge (CLOUDFRONT scope, us-east-1)", graph_attr=CLUSTER_EDGE):
            waf = WAF("AWS WAF web ACL\nmanaged rules +\nper-IP rate limits")
            cdn = CloudFront("CloudFront\nOAC - security headers\n/* -> SPA, /api/* -> API")

        with Cluster("Region: af-south-1 (Cape Town)", graph_attr=CLUSTER_REGION):
            with Cluster("Identity", graph_attr=CLUSTER_SEC):
                cognito = Cognito("Cognito user pool\ncustom:tenantId (immutable)\nTOTP MFA, admin-created")
            web_bucket = S3("Private S3\nReact SPA (Amplify auth)")

            with Cluster("API (JWT authorizer, throttled, access-logged)", graph_attr=CLUSTER_OPS):
                api = APIGateway("API Gateway\nHTTP API v2")

            with Cluster("Domain services (Lambda arm64 / Python 3.13 / Powertools)", graph_attr=CLUSTER_OPS):
                crud = Lambda("vehicles - drivers\nstations - trips\nfuel - maintenance")
                analytics = Lambda("analytics\n(read-only)")
                ai = Lambda("ai\n(Bedrock + Strands)")

            with Cluster("Data (tenantId partition key - PITR - KMS)", graph_attr=CLUSTER_OPS):
                tables = Dynamodb("7 DynamoDB tables\n(6 fleet + rate-limit TTL)")
                backup = Backup("AWS Backup\ndaily / 35-day")

            with Cluster("Change data capture", graph_attr=CLUSTER_OPS):
                proc = Lambda("stream processor\n(odometer, events)")
                bus = Eventbridge("Fleet event bus\n(+ 30-day archive)")
                dlq = SQS("Failure queue\n(on-failure dest)")

            kms = KMS("Customer-managed\nKMS key")

        bedrock = Bedrock("Amazon Bedrock\nglobal inference profile\n(Kimi K3 - no form)")

        with Cluster("Observability", graph_attr=CLUSTER_OPS):
            cw = Cloudwatch("Logs / metrics /\nX-Ray / dashboard")
            alarms = CloudwatchAlarm("Alarms -> SNS\n(errors, 5xx, DLQ,\niterator age, AI)")

        user >> Edge(color=BLUE, label="HTTPS") >> waf >> cdn
        cdn >> Edge(color=GREY, label="SPA") >> web_bucket
        user >> Edge(color=BLUE, style="dashed", label="sign-in (SRP + MFA)") >> cognito
        cdn >> Edge(color=BLUE, label="/api/* (ID token)") >> api
        api >> Edge(color=BLUE, label="JWT verified") >> [crud, analytics, ai]
        [crud, analytics, ai] >> Edge(color=GREEN) >> tables
        tables >> Edge(color=GREY, style="dotted", label="daily") >> backup
        ai >> Edge(color=AMBER, label="Converse / tool use") >> bedrock
        tables >> Edge(color=RED, label="streams") >> proc
        proc >> Edge(color=GREEN) >> tables
        proc >> Edge(color=GREY) >> bus
        proc >> Edge(color=RED, style="dashed", label="exhausted retries") >> dlq
        tables >> Edge(color=GREY, style="dotted") >> kms
        [crud, analytics, ai, proc] >> Edge(color=GREY, style="dotted") >> cw
        dlq >> Edge(color=RED, style="dotted") >> alarms
        cw >> Edge(color=GREY, style="dotted") >> alarms


# =============================================================================================
# 3. REQUEST LIFECYCLE — one authenticated API call, edge to data
# =============================================================================================
def request_lifecycle_diagram() -> None:
    title = "SmartFleet - Authenticated Request Lifecycle (GET /api/vehicles)"
    with _diagram(title, "smartfleet-request-lifecycle"):
        browser = Client("Browser (SPA)\nAmplify holds the\nID token (sessionStorage)")
        cognito = Cognito("Cognito\nissues ID token\n(custom:tenantId)")

        with Cluster("Global edge", graph_attr=CLUSTER_EDGE):
            waf = WAF("1. WAF\nrules + rate limit")
            fn = CloudFront("2. CloudFront Fn\nstrip /api prefix")

        with Cluster("Region af-south-1", graph_attr=CLUSTER_REGION):
            api = APIGateway("3. HTTP API\nJWT authorizer\n(issuer + audience)")
            handler = Lambda("4. Lambda handler\nPowertools wrapper")

            with Cluster("In-process guards", graph_attr=CLUSTER_SEC):
                auth = IAMRole("5. shared/auth\ntoken_use == id\nread custom:tenantId")
                valid = IAMRole("6. Pydantic model\nextra=forbid")

            table = DynamodbTable("7. TenantRepo\nkey prefixed by tenantId\nattribute_exists guard")

        browser >> Edge(color=BLUE, style="dashed", label="sign-in once") >> cognito
        cognito >> Edge(color=BLUE, style="dashed", label="ID token") >> browser
        browser >> Edge(color=BLUE, label="Bearer ID token") >> waf >> fn >> api
        api >> Edge(color=BLUE) >> handler >> Edge(color=GREY) >> auth
        auth >> Edge(color=GREY) >> valid
        valid >> Edge(color=GREEN, label="tenant-scoped read") >> table
        table >> Edge(color=GREEN, style="dashed", label="items (no-store)") >> browser


# =============================================================================================
# 4. CDC & RELIABILITY — write path + the no-silent-failure path
# =============================================================================================
def cdc_diagram() -> None:
    title = "SmartFleet - CDC & Reliability Flow (no silent failures)"
    with _diagram(title, "smartfleet-cdc-flow"):
        with Cluster("Write path (single DynamoDB transaction)", graph_attr=CLUSTER_REGION):
            api = APIGateway("POST /trips/{id}/end")
            trips = DynamodbTable("TripsTable")
            veh = DynamodbTable("VehiclesTable")
            drv = DynamodbTable("DriversTable")
            api >> Edge(color=GREEN, label="transact:\ntrip + vehicle + driver") >> [trips, veh, drv]

        with Cluster("CDC worker", graph_attr=CLUSTER_OPS):
            proc = Lambda("stream processor\n(errors propagate)")
            bus = Eventbridge("event bus\nTripCompleted /\nFuelAnomalyDetected /\nFuelOffGeofence")

        with Cluster("Failure handling (reliability)", graph_attr=CLUSTER_OPS):
            dlq = SQS("failure queue\n14-day retention")
            alarm = CloudwatchAlarm("alarm -> SNS\n(DLQ depth +\niterator age)")

        trips >> Edge(color=RED, label="NEW + OLD images") >> proc
        proc >> Edge(color=GREEN, label="monotonic odometer\n(idempotent replay)") >> veh
        proc >> Edge(color=GREY, label="domain events") >> bus
        proc >> Edge(color=RED, style="dashed", label="retry x3 -> bisect ->\nexhausted") >> dlq
        dlq >> Edge(color=RED) >> alarm


# =============================================================================================
# 5. AI AGENT — Bedrock / Strands data flow and guardrails
# =============================================================================================
def ai_agent_diagram() -> None:
    title = "SmartFleet - AI Assistant (tenant-bound tools, propose-only, no fallback)"
    with _diagram(title, "smartfleet-ai-agent"):
        user = User("Tenant user")

        with Cluster("Region af-south-1", graph_attr=CLUSTER_REGION):
            api = APIGateway("POST /agent/chat\nPOST /analytics/ai-insights")

            with Cluster("Guardrails", graph_attr=CLUSTER_SEC):
                rate = DynamodbTable("rate limiter (TTL)\nfails CLOSED\nAiEnabled kill switch")

            with Cluster("ai Lambda (isolated IAM)", graph_attr=CLUSTER_OPS):
                agent = Lambda("Strands agent\nper-request tenant\nclosure (no shared state)")
                tools = Lambda("5 tools: KPIs, fuel-geofence\naudit, maintenance alerts,\ncorridor lookup, propose_service")

            data = Dynamodb("fleet data\n(aggregates + plates only)")

        bedrock = Bedrock("Amazon Bedrock\nglobal inference profile\n(Kimi K3)")

        user >> Edge(color=BLUE, label="question") >> api
        api >> Edge(color=GREY, label="check quota") >> rate
        api >> Edge(color=BLUE) >> agent
        agent >> Edge(color=AMBER, label="Converse + tool-use loop") >> bedrock
        bedrock >> Edge(color=AMBER, style="dashed", label="tool calls") >> agent
        agent >> Edge(color=GREEN) >> tools
        tools >> Edge(color=GREEN, label="tenant-scoped reads") >> data
        tools >> Edge(color=RED, style="dashed", label="write = PROPOSED only\n(human approves)") >> data


# =============================================================================================
# 6. SECURITY & TENANT ISOLATION — the zero-leakage / POPIA story
# =============================================================================================
def security_diagram() -> None:
    title = "SmartFleet - Identity, Tenant Isolation & Data Protection"
    with _diagram(title, "smartfleet-security", direction="TB"):
        users = Users("Tenant A users /\nTenant B users")

        with Cluster("Edge protection", graph_attr=CLUSTER_EDGE):
            shield = Shield("AWS Shield\n(standard)")
            waf = WAF("WAF managed rules\n+ per-IP rate limits")

        with Cluster("Verified identity", graph_attr=CLUSTER_SEC):
            cognito = Cognito("Cognito user pool\nSRP + mandatory TOTP\nadmin-created users")
            amplify = Amplify("Amplify auth client\nID token in sessionStorage\n(no localStorage)")
            jwt = APIGateway("HTTP API JWT authorizer\ntoken_use == id\nissuer + audience")

        with Cluster("Isolation boundary (every key prefixed by tenantId)", graph_attr=CLUSTER_REGION):
            a = DynamodbTable("Tenant A partition")
            b = DynamodbTable("Tenant B partition")

        with Cluster("Data protection", graph_attr=CLUSTER_OPS):
            kms = KMS("Customer-managed KMS\n(SNS, SQS, logs)")
            logs = CloudwatchLogs("Retained, encrypted\nlogs (no PII)")

        users >> Edge(color=BLUE) >> shield >> waf >> cognito
        cognito >> Edge(color=BLUE, style="dashed", label="ID token") >> amplify
        amplify >> Edge(color=BLUE, label="Bearer token") >> jwt
        jwt >> Edge(color=GREEN, label="tenant A -> A only") >> a
        jwt >> Edge(color=GREEN, label="tenant B -> B only") >> b
        a >> Edge(color=RED, style="dashed", label="cross-tenant = 404\n(attribute_exists guard)") >> b
        [a, b] >> Edge(color=GREY, style="dotted") >> kms
        kms >> Edge(color=GREY, style="dotted") >> logs


# =============================================================================================
# 7. CI/CD — verify -> staging -> plan -> approve -> canary
# =============================================================================================
def pipeline_diagram() -> None:
    title = "SmartFleet - CI/CD (verify -> staging -> plan -> approve -> canary)"
    with _diagram(title, "smartfleet-cicd"):
        dev = User("Engineer\n(push / PR)")
        oidc = IAMRole("GitHub OIDC roles\nstaging / prod-plan / prod\n(no long-lived keys)")

        with Cluster("GitHub Actions", graph_attr=CLUSTER_OPS):
            verify = Codebuild("verify\nruff - pytest (85%)\ncfn-lint - cfn-guard\npip-audit - npm audit")
            staging = Codepipeline("deploy staging\n(automatic on main)")
            plan = Codepipeline("plan prod\n(change set, no execute)")
            approve = Codepipeline("manual approval\n(production env reviewers)")
            prod = Codedeploy("deploy prod\ncanary + auto rollback\non Lambda-errors alarm")

        with Cluster("AWS (af-south-1 + us-east-1 WAF)", graph_attr=CLUSTER_REGION):
            waf = WAF("WAF stack\n(us-east-1)")
            stack = CloudFront("SAM stack\n(af-south-1)")

        dev >> Edge(color=BLUE) >> verify >> staging >> plan >> approve >> prod
        oidc >> Edge(color=GREY, style="dotted") >> [staging, plan, prod]
        prod >> Edge(color=GREEN) >> waf
        prod >> Edge(color=GREEN) >> stack


if __name__ == "__main__":
    import os

    # Render into this script's directory regardless of the caller's working directory
    # (the `diagrams` library writes `<filename>.png` relative to CWD).
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    context_diagram()
    system_diagram()
    request_lifecycle_diagram()
    cdc_diagram()
    ai_agent_diagram()
    security_diagram()
    pipeline_diagram()
    print(
        "Generated 7 diagrams:\n"
        "  smartfleet-context.png\n"
        "  smartfleet-architecture.png\n"
        "  smartfleet-request-lifecycle.png\n"
        "  smartfleet-cdc-flow.png\n"
        "  smartfleet-ai-agent.png\n"
        "  smartfleet-security.png\n"
        "  smartfleet-cicd.png"
    )
