"""
Generate SmartFleet architecture diagrams as PNGs using AWS-native icons (the `diagrams` library).

Requires: pip install diagrams, and the Graphviz `dot` binary on PATH.
Run: python docs/architecture/generate_diagrams.py
Outputs (in this directory): smartfleet-architecture.png, smartfleet-cdc-flow.png
"""
from diagrams import Cluster, Diagram, Edge
from diagrams.aws.security import Cognito, WAF, KMS
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb, DynamodbTable
from diagrams.aws.storage import S3
from diagrams.aws.integration import Eventbridge, SQS
from diagrams.aws.ml import Bedrock
from diagrams.aws.management import Cloudwatch, CloudwatchAlarm
from diagrams.aws.devtools import Codepipeline
from diagrams.aws.general import User
from diagrams.aws.security import IAMRole

GRAPH_ATTR = {"fontsize": "20", "labelloc": "t", "pad": "0.6", "splines": "spline", "nodesep": "0.6", "ranksep": "1.0"}
BLUE = "#2563eb"
GREEN = "#059669"
RED = "#dc2626"
GREY = "#64748b"


def system_diagram() -> None:
    title = "SmartFleet - Serverless Multi-Tenant Architecture (af-south-1)"
    with Diagram(title, filename="smartfleet-architecture", outformat="png", show=False, direction="LR", graph_attr=GRAPH_ATTR):
        user = User("Fleet operator\n(tenant user)")

        with Cluster("Global edge (us-east-1 scope)"):
            waf = WAF("WAF web ACL\nmanaged rules +\nper-IP rate limits")
            cdn = CloudFront("CloudFront\nOAC, security headers,\n/* -> SPA, /api/* -> API")

        with Cluster("Region: af-south-1"):
            cognito = Cognito("Cognito user pool\ncustom:tenantId (immutable)\nMFA, admin-created users")
            web_bucket = S3("Private S3\nReact SPA")

            with Cluster("HTTP API (JWT authorizer, throttled, access-logged)"):
                api = APIGateway("API Gateway\nHTTP API v2")

            with Cluster("Domain services (Lambda arm64, Python 3.13, Powertools)"):
                crud = Lambda("vehicles / drivers /\nstations / trips /\nfuel / maintenance")
                analytics = Lambda("analytics\n(read-only)")
                ai = Lambda("ai\n(Bedrock + Strands agent)")

            with Cluster("Data (tenantId partition key, PITR, KMS, AWS Backup)"):
                tables = Dynamodb("6 fleet tables\n+ rate-limit (TTL)")

            with Cluster("Change data capture"):
                proc = Lambda("stream processor\n(odometer, events)")
                bus = Eventbridge("Fleet event bus\n(+ archive)")
                dlq = SQS("Failure queue\n(on-failure dest)")

            kms = KMS("Customer-managed\nKMS key")

        bedrock = Bedrock("Bedrock\nglobal inference profile\n(Kimi K3 - no form)")

        with Cluster("Observability"):
            cw = Cloudwatch("Logs / metrics /\nX-Ray / dashboard")
            alarms = CloudwatchAlarm("Alarms -> SNS\n(errors, 5xx, DLQ,\niterator age, AI)")

        user >> Edge(color=BLUE, label="HTTPS") >> waf >> cdn
        cdn >> Edge(color=GREY, label="SPA") >> web_bucket
        user >> Edge(color=BLUE, style="dashed", label="sign-in (SRP+MFA)") >> cognito
        cdn >> Edge(color=BLUE, label="/api/* (ID token)") >> api
        api >> Edge(color=BLUE, label="JWT verified") >> [crud, analytics, ai]
        [crud, analytics, ai] >> Edge(color=GREEN) >> tables
        ai >> Edge(color=GREEN, label="Converse / tool use") >> bedrock
        tables >> Edge(color=RED, label="streams") >> proc
        proc >> Edge(color=GREEN) >> tables
        proc >> Edge(color=GREY) >> bus
        proc >> Edge(color=RED, style="dashed", label="exhausted retries") >> dlq
        tables >> Edge(color=GREY, style="dotted") >> kms
        [crud, analytics, ai, proc] >> Edge(color=GREY, style="dotted") >> cw
        dlq >> Edge(color=RED, style="dotted") >> alarms
        cw >> Edge(color=GREY, style="dotted") >> alarms


def cdc_diagram() -> None:
    title = "SmartFleet - CDC & Reliability Flow (no silent failures)"
    with Diagram(title, filename="smartfleet-cdc-flow", outformat="png", show=False, direction="LR", graph_attr=GRAPH_ATTR):
        with Cluster("Write path (single transaction)"):
            api = APIGateway("POST /trips/{id}/end")
            trips = DynamodbTable("TripsTable")
            veh = DynamodbTable("VehiclesTable")
            drv = DynamodbTable("DriversTable")
            api >> Edge(color=GREEN, label="transact:\ntrip+vehicle+driver") >> [trips, veh, drv]

        with Cluster("CDC worker"):
            proc = Lambda("stream processor\nerrors propagate")
            bus = Eventbridge("event bus\nTripCompleted,\nFuelAnomaly,\nFuelOffGeofence")

        with Cluster("Failure handling"):
            retry = Lambda("retry x3\n+ bisect batch")
            dlq = SQS("failure queue\n14-day retention")
            alarm = CloudwatchAlarm("alarm -> SNS\n(DLQ + iterator age)")

        trips >> Edge(color=RED, label="NEW+OLD images") >> proc
        proc >> Edge(color=GREEN, label="monotonic odometer\n(idempotent)") >> veh
        proc >> Edge(color=GREY) >> bus
        proc >> Edge(color=RED, style="dashed", label="on failure") >> retry
        retry >> Edge(color=RED) >> dlq >> Edge(color=RED) >> alarm


def pipeline_diagram() -> None:
    title = "SmartFleet - CI/CD (plan -> approve -> canary)"
    with Diagram(title, filename="smartfleet-cicd", outformat="png", show=False, direction="LR", graph_attr=GRAPH_ATTR):
        oidc = IAMRole("GitHub OIDC roles\nstaging / prod-plan / prod")
        with Cluster("GitHub Actions"):
            verify = Codepipeline("verify\n(tests, cfn-lint,\ncfn-guard, audits)")
            staging = Codepipeline("deploy staging\n(auto)")
            plan = Codepipeline("plan prod\n(change set)")
            approve = Codepipeline("manual approval")
            prod = Codepipeline("deploy prod\n(canary + rollback)")
        verify >> staging >> plan >> approve >> prod
        oidc >> Edge(style="dotted", color=GREY) >> [staging, plan, prod]


if __name__ == "__main__":
    system_diagram()
    cdc_diagram()
    pipeline_diagram()
    print("Generated: smartfleet-architecture.png, smartfleet-cdc-flow.png, smartfleet-cicd.png")
