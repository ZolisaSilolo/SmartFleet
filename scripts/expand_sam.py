"""
Expand a SAM template into plain CloudFormation JSON so cfn-lint / cfn-guard can inspect real resources.
Runs fully offline (no AWS credentials): managed-policy ARNs that SAM resolves are supplied from a static map.

Usage: python scripts/expand_sam.py infrastructure/template.yaml out.json
"""
import json
import os
import sys

os.environ.setdefault("AWS_DEFAULT_REGION", "af-south-1")  # the translator needs a region for ARN partitions
from samtranslator.translator.transform import transform  # noqa: E402
from samtranslator.yaml_helper import yaml_parse

MANAGED = {
    "AWSLambdaBasicExecutionRole": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "AWSLambdaDynamoDBExecutionRole": "arn:aws:iam::aws:policy/service-role/AWSLambdaDynamoDBExecutionRole",
    "AWSXrayWriteOnlyAccess": "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess",
    "AWSCodeDeployRoleForLambda": "arn:aws:iam::aws:policy/service-role/AWSCodeDeployRoleForLambda",
    "AWSLambdaRole": "arn:aws:iam::aws:policy/service-role/AWSLambdaRole",
    "AWSLambdaVPCAccessExecutionRole": "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
}


class StaticPolicyLoader:
    def load(self):
        return dict(MANAGED)


def main(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as handle:
        template = yaml_parse(handle.read())
    for resource in template.get("Resources", {}).values():
        props = resource.setdefault("Properties", {})
        if resource.get("Type") == "AWS::Serverless::Function":
            props["CodeUri"] = "s3://placeholder/code.zip"
        elif resource.get("Type") == "AWS::Serverless::LayerVersion":
            props["ContentUri"] = "s3://placeholder/layer.zip"
    params = {"AlertEmail": "ops@example.invalid", "Stage": "prod", "AWS::Region": "af-south-1"}
    expanded = transform(template, params, StaticPolicyLoader())
    with open(dst, "w", encoding="utf-8") as out:
        json.dump(expanded, out, indent=2)
    print(f"expanded {len(expanded['Resources'])} resources -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
