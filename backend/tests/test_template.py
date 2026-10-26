"""
Infrastructure regression guard. These assertions encode the Well-Architected fixes so a future edit cannot
silently reintroduce them (tenant spoofing, unmonitored stream failures, open CORS, unscoped Bedrock IAM, ...).
"""
import json

from conftest import load_template

T = load_template()
R = T["Resources"]


def of_type(kind):
    return {name: r for name, r in R.items() if r["Type"] == kind}


def test_all_data_tables_are_protected_and_retained():
    tables = of_type("AWS::DynamoDB::Table")
    assert len(tables) == 7
    for name, table in tables.items():
        props = table["Properties"]
        assert props["BillingMode"] == "PAY_PER_REQUEST", name
        assert props["SSESpecification"] == {"SSEEnabled": True, "SSEType": "KMS"}, name
        if name != "RateLimitTable":        # ephemeral counters expire via TTL
            assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True, name
            assert table["DeletionPolicy"] == "Retain" and table["UpdateReplacePolicy"] == "Retain", name
            assert "DeletionProtectionEnabled" in props, name
        assert "TableName" not in props, f"{name} must not use a fixed physical name"


def test_every_tenant_table_and_index_is_partitioned_by_tenant():
    for name, table in of_type("AWS::DynamoDB::Table").items():
        if name == "RateLimitTable":
            continue
        keys = {k["KeyType"]: k["AttributeName"] for k in table["Properties"]["KeySchema"]}
        assert keys["HASH"] == "tenantId", name
        for gsi in table["Properties"].get("GlobalSecondaryIndexes", []):
            hash_key = next(k["AttributeName"] for k in gsi["KeySchema"] if k["KeyType"] == "HASH")
            # vehicleKey is "<tenantId>#<vehicleId>", i.e. still tenant-scoped.
            assert hash_key in ("tenantId", "vehicleKey"), f"{name}.{gsi['IndexName']} is not tenant-scoped"


def test_cognito_makes_tenant_identity_unspoofable():
    pool, client = R["UserPool"]["Properties"], R["UserPoolClient"]["Properties"]
    tenant_attr = next(a for a in pool["Schema"] if a["Name"] == "tenantId")
    assert tenant_attr["Mutable"] is False
    assert pool["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is True     # no self sign-up
    assert pool["MfaConfiguration"] == "ON" and pool["DeletionProtection"] == "ACTIVE"
    assert pool["Policies"]["PasswordPolicy"]["MinimumLength"] >= 12
    assert "custom:tenantId" not in client["WriteAttributes"]                    # clients can never write the tenant
    assert "custom:tenantId" in client["ReadAttributes"]
    assert "ALLOW_USER_PASSWORD_AUTH" not in client["ExplicitAuthFlows"]
    assert client["GenerateSecret"] is False and client["EnableTokenRevocation"] is True
    assert R["UserPool"]["DeletionPolicy"] == "Retain"


def test_http_api_is_authorised_throttled_logged_and_has_no_cors():
    api = R["FleetHttpApi"]["Properties"]
    assert api["Auth"]["DefaultAuthorizer"] == "CognitoJwtAuthorizer" and "CorsConfiguration" not in api
    assert "ThrottlingRateLimit" in api["DefaultRouteSettings"] and "AccessLogSettings" in api
    for name, fn in of_type("AWS::Serverless::Function").items():
        for event_name, event in fn["Properties"].get("Events", {}).items():
            if event["Type"] == "HttpApi":
                assert "Auth" not in event["Properties"], f"{name}.{event_name} must not override the default authorizer"


def test_stream_worker_has_a_real_failure_path():
    fn = R["FleetEventProcessorFunction"]["Properties"]
    assert "DeadLetterQueue" not in fn          # async-only setting; useless for stream event sources
    for name in ("TripsStream", "FuelStream"):
        props = fn["Events"][name]["Properties"]
        assert props["DestinationConfig"]["OnFailure"]["Type"] == "SQS"
        assert props["BisectBatchOnFunctionError"] is True and props["MaximumRetryAttempts"] == 3
        assert "ReportBatchItemFailures" in props["FunctionResponseTypes"]
        assert "FilterCriteria" in props
    assert "StreamSpecification" not in R["MaintenanceTable"]["Properties"]       # no consumer => no stream
    for alarm in ("EventDLQAlarm", "StreamIteratorAgeAlarm", "LambdaErrorsAlarm", "HttpApi5xxAlarm", "AiFailuresAlarm"):
        assert R[alarm]["Properties"]["AlarmActions"], f"{alarm} must notify someone"


def test_bedrock_iam_is_scoped_to_one_profile_and_model():
    statements = [s for p in R["AiFunction"]["Properties"]["Policies"] if isinstance(p, dict) and "Statement" in p for s in p["Statement"]]
    assert len(statements) == 3
    for s in statements:
        assert "*" not in json.dumps(s["Resource"]).replace("${", "")  # no wildcard resources
        assert set(s["Action"]) == {"bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"}
    other = [name for name, fn in of_type("AWS::Serverless::Function").items() if name != "AiFunction" and "bedrock" in json.dumps(fn["Properties"].get("Policies", []))]
    assert other == []                                                          # only the AI function can call Bedrock


def test_least_privilege_per_function():
    fns = of_type("AWS::Serverless::Function")
    assert len(fns) == 9
    for name, fn in fns.items():
        dumped = json.dumps(fn["Properties"].get("Policies", []))
        assert "Resource': '*'" not in dumped and '"Resource": "*"' not in dumped, name
    analytics = json.dumps(fns["AnalyticsFunction"]["Properties"]["Policies"])
    assert "DynamoDBCrudPolicy" not in analytics                                # analytics is read-only
    assert "PutEvents" not in json.dumps(fns["VehiclesFunction"]["Properties"]["Policies"])


def test_runtime_observability_and_safe_deploys():
    g = T["Globals"]["Function"]
    assert g["Runtime"] == "python3.13" and g["Architectures"] == ["arm64"] and g["Tracing"] == "Active"
    assert g["LoggingConfig"]["LogFormat"] == "JSON" and g["AutoPublishAlias"] == "live"
    assert g["DeploymentPreference"]["Alarms"]
    for log_group in of_type("AWS::Logs::LogGroup").values():
        assert "RetentionInDays" in log_group["Properties"]


def test_edge_is_hardened():
    dist = R["FrontendDistribution"]["Properties"]["DistributionConfig"]
    assert dist["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "redirect-to-https"
    assert dist["Logging"] and "WebACLId" in dist and dist["PriceClass"] == "PriceClass_200"
    assert "CustomErrorResponses" not in dist       # would turn API 403/404 into index.html with status 200
    headers = R["SecurityHeadersPolicy"]["Properties"]["ResponseHeadersPolicyConfig"]["SecurityHeadersConfig"]
    assert {"StrictTransportSecurity", "ContentSecurityPolicy", "FrameOptions", "ContentTypeOptions", "ReferrerPolicy"} <= set(headers)
    for name in ("FrontendBucket", "AccessLogsBucket"):
        props = R[name]["Properties"]
        assert all(props["PublicAccessBlockConfiguration"].values()) and R[name]["DeletionPolicy"] == "Retain"
    for policy in ("FrontendBucketPolicy", "AccessLogsBucketPolicy"):
        assert "aws:SecureTransport" in json.dumps(R[policy]["Properties"]["PolicyDocument"])


def test_no_unbounded_or_dead_resources():
    assert "DocumentsBucket" not in R and "DeadLetterQueue" not in json.dumps(R)
    assert not [r for r in R.values() if r["Type"] == "AWS::Location::GeofenceCollection"]
    params = T["Parameters"]
    assert "AlertEmail" in params and "Default" not in params["AlertEmail"]    # must be supplied per environment
