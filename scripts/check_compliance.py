"""
Run the AWS IaC MCP server's cfn-guard security rule set against CloudFormation templates and fail on any
violation that is not an explicitly documented waiver.

Usage: python scripts/check_compliance.py <template.(json|yaml)> [...]
Requires: awslabs.aws-iac-mcp-server (see CI workflow for the pinned version).
"""
import sys

from awslabs.aws_iac_mcp_server.tools import cloudformation_compliance_checker as checker

# SAM generates one scoped inline policy per function role from the policy templates in template.yaml;
# that is the intended least-privilege shape, so this rule is waived project-wide.
WAIVED = {"IAM_NO_INLINE_POLICY_CHECK"}


def main(paths: list[str]) -> int:
    checker.initialize_guard_rules()
    failed = False
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            result = checker.check_compliance(handle.read())
        violations = [v for v in result["violations"] if v["rule_id"] not in WAIVED]
        waived = sorted({v["rule_id"] for v in result["violations"] if v["rule_id"] in WAIVED})
        print(f"{path}: {'FAIL' if violations else 'PASS'} (waived: {waived or 'none'})")
        for violation in violations:
            failed = True
            print(f"  - {violation['rule_id']}: {violation['remediation']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
