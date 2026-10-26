"""
Create a tenant user (administrators only). Self sign-up is disabled and custom:tenantId is immutable, so this is the
ONLY way a tenant identity is assigned. Run with credentials that hold cognito-idp:AdminCreateUser on the user pool.

Usage:
    python scripts/provision_tenant_user.py --user-pool-id af-south-1_XXXX --email dispatcher@fleet.co.za --tenant-id acme-logistics

The user receives a temporary password by email, must set a new password and enrol an authenticator app (MFA) at first sign-in.
"""
import argparse
import re
import sys

import boto3

TENANT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")  # keep in sync with backend/src/shared/auth.py


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--region", default="af-south-1")
    args = parser.parse_args()

    if not TENANT_ID.match(args.tenant_id):
        print("tenant-id must be 3-64 characters: letters, digits, '-' or '_' (starting with a letter or digit)", file=sys.stderr)
        return 2

    client = boto3.client("cognito-idp", region_name=args.region)
    response = client.admin_create_user(
        UserPoolId=args.user_pool_id,
        Username=args.email,
        UserAttributes=[
            {"Name": "email", "Value": args.email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "custom:tenantId", "Value": args.tenant_id},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )
    print(f"Created {response['User']['Username']} for tenant '{args.tenant_id}' (status {response['User']['UserStatus']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
