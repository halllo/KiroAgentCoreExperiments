import os
import logging
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# The AgentCore CDK constructs inject this env var into the Runtime at deploy time
# (name = "AGENTCORE_GATEWAY_" + gateway name upper-cased + "_URL"). `agentcore dev`
# sets the same var locally, but only after the project has been deployed once.
# Reading it here means no gateway URL is ever hardcoded.
GATEWAY_URL_ENV_VAR = "AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL"


def get_bundesliga_gateway_mcp_client() -> MCPClient | None:
    """Return an MCP client for the BundesligaGateway, or None if its URL is not set."""
    url = os.environ.get(GATEWAY_URL_ENV_VAR)
    if not url:
        logger.warning("%s not set; BundesligaGateway tools unavailable", GATEWAY_URL_ENV_VAR)
        return None

    # The gateway uses AWS_IAM inbound auth, so every MCP request must be SigV4-signed
    # for the "bedrock-agentcore" service. The Runtime execution role already has
    # bedrock-agentcore:InvokeGateway on this gateway (granted by the CDK at deploy).
    # Pattern from https://docs.aws.amazon.com/bedrock/latest/userguide/kb-gateway-target.html
    # ("Invoke with Strands Agents") and
    # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))

    # MCPClient takes a factory (the lambda) rather than an open connection: Strands
    # opens the transport itself when the Agent starts using the tools, and tool
    # discovery (tools/list) then finds the gateway's WebSearch tool automatically.
    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=url,
            aws_service="bedrock-agentcore",
            aws_region=region,
        )
    )
