"""Zip and deploy the two Gateway Lambda targets with boto3 (region us-west-2).

Run from anywhere:  python3 lambda_functions/deploy.py

Re-running is safe: an existing function gets its code updated instead of
being created again.

Docs used:
- https://docs.aws.amazon.com/lambda/latest/dg/python-package.html
- https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html
"""

import io
import zipfile
from pathlib import Path

import boto3

REGION = "us-west-2"
ROLE_PARAM = "/app/workshop/lambda/execution-role-arn"
# Latest generally available Python runtime (Amazon Linux 2023).
RUNTIME = "python3.14"

# Function name -> source folder. Each folder holds a handler.py with lambda_handler.
FUNCTIONS: dict[str, str] = {
    "workshop-data-lookup": "data_lookup",
    "workshop-policy-retrieval": "policy_retrieval",
}

BASE_DIR = Path(__file__).resolve().parent

ssm = boto3.client("ssm", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)


def get_role_arn() -> str:
    """Read the pre-created Lambda execution role ARN from SSM (never hardcode it)."""
    return ssm.get_parameter(Name=ROLE_PARAM)["Parameter"]["Value"]


def build_zip(source_dir: Path) -> bytes:
    """Zip handler.py at the root of the archive, as Lambda expects.

    Only the handler is packaged: its sole dependency, boto3, is already
    included in the Lambda Python runtime, which keeps the zip tiny for the workshop.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_dir / "handler.py", arcname="handler.py")
    return buffer.getvalue()


def deploy_function(name: str, zip_bytes: bytes, role_arn: str) -> str:
    """Create the function, or update its code if it already exists. Returns the ARN."""
    try:
        response = lambda_client.create_function(
            FunctionName=name,
            Runtime=RUNTIME,
            Role=role_arn,
            # "<file>.<function>": handler.py -> lambda_handler()
            Handler="handler.lambda_handler",
            Code={"ZipFile": zip_bytes},
            # Retrieve calls to the Knowledge Base can take a few seconds; the 3s default is too tight.
            Timeout=30,
            MemorySize=256,
            Description="Returns & Refunds AgentCore Gateway target",
        )
    except lambda_client.exceptions.ResourceConflictException:
        # Already exists: push the new code instead.
        response = lambda_client.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        lambda_client.get_waiter("function_updated_v2").wait(FunctionName=name)
        return response["FunctionArn"]

    # A new function starts in "Pending"; wait until it can be invoked.
    lambda_client.get_waiter("function_active_v2").wait(FunctionName=name)
    return response["FunctionArn"]


def main() -> None:
    role_arn = get_role_arn()
    for name, folder in FUNCTIONS.items():
        arn = deploy_function(name, build_zip(BASE_DIR / folder), role_arn)
        print(f"{name}: {arn}")


if __name__ == "__main__":
    main()
