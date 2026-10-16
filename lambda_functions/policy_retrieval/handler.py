"""Policy retrieval Lambda for an AgentCore Gateway target.

Serves one tool, retrieve_policy, which searches the return-policy Bedrock Knowledge Base.

Gateway Lambda contract (see
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html):
- `event` is a flat map of the tool's inputSchema properties, e.g. {"query": "..."}.
- `context.client_context.custom["bedrockAgentCoreToolName"]` holds the called tool as
  "<target_name>___<tool_name>" (see
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-tool-naming.html).
- The function must return valid JSON.

Retrieve API: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_Retrieve.html

Response shape (always a plain JSON-serializable dict):
- success    -> {"results": [{"text": str, "score": float, "source_uri": str}, ...], "count": N}
               (when nothing matches, also includes "message")
- any failure -> {"error": "<readable message>"}

Intended Gateway tool schema:

    {
      "name": "retrieve_policy",
      "description": "Retrieve return/refund policy excerpts from the knowledge base.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "What to search for, e.g. 'electronics return window'"},
          "country_code": {"type": "string", "description": "Optional policy country: US, UK or IN"},
          "number_of_results": {"type": "integer", "description": "Optional, 1-25, default 5"}
        },
        "required": ["query"]
      }
    }
"""

from typing import Any, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Created once at import time so warm Lambda invocations reuse the connections.
ssm = boto3.client("ssm", region_name="us-west-2")
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name="us-west-2")

KB_ID_PARAMETER = "/app/workshop/kb/knowledge-base-id"
TOOL_NAME = "retrieve_policy"
# Gateway prefixes every tool name with "<target_name>___" (three underscores).
TOOL_NAME_DELIMITER = "___"
DEFAULT_RESULTS = 5
MAX_RESULTS = 25
OVERFETCH_RESULTS = 25
# Each country's policy is a separate PDF, so the source URI suffix identifies the country.
COUNTRY_SUFFIXES = {"US": "-us.pdf", "UK": "-uk.pdf", "IN": "-in.pdf"}

# Cached KB ID: loaded from SSM on the first call, reused by warm invocations.
_kb_id: Optional[str] = None


def get_tool_name(context: Any) -> str:
    """Return the bare tool name from the Gateway context ('' if absent)."""
    # client_context is None on direct/console invocations, so read it defensively.
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    full_name = custom.get("bedrockAgentCoreToolName", "")
    # partition() never raises: with the delimiter we get the tool part, without it
    # (local tests) we keep the full name. The doc boilerplate uses .index(), which raises.
    _, sep, tool = full_name.partition(TOOL_NAME_DELIMITER)
    return tool if sep else full_name


def get_knowledge_base_id() -> str:
    """Return the KB ID from SSM, caching it for later invocations."""
    global _kb_id
    if _kb_id is None:
        # Read from SSM rather than hardcoding so the KB can change without a code deploy.
        _kb_id = ssm.get_parameter(Name=KB_ID_PARAMETER)["Parameter"]["Value"]
    return _kb_id


def retrieve_policy(query: str, number_of_results: int, country_code: Optional[str]) -> dict[str, Any]:
    """Search the KB and return the top policy excerpts, optionally for one country."""
    # Why post-filter instead of a KB metadata filter: a filter on the source URI
    # returns zero results on this KB, and generic queries skew towards one country's
    # chunks. So we over-fetch, then keep only the requested country's PDF.
    fetch_count = OVERFETCH_RESULTS if country_code else number_of_results
    response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=get_knowledge_base_id(),
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": fetch_count}},
    )

    results: list[dict[str, Any]] = [
        {
            "text": r.get("content", {}).get("text", ""),
            "score": r.get("score"),
            "source_uri": r.get("location", {}).get("s3Location", {}).get("uri", ""),
        }
        for r in response.get("retrievalResults", [])
    ]
    if country_code:
        suffix = COUNTRY_SUFFIXES[country_code]
        results = [r for r in results if r["source_uri"].lower().endswith(suffix)]
    results = results[:number_of_results]

    if not results:
        # No match is a valid answer, not an error.
        return {"results": [], "count": 0, "message": f"No policy excerpts found for '{query}'"}
    return {"results": results, "count": len(results)}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Entry point: validate the Gateway arguments and run retrieve_policy."""
    tool_name = get_tool_name(context)
    # An empty name means a direct (non-Gateway) invocation; allow it for local testing.
    if tool_name and tool_name != TOOL_NAME:
        return {"error": f"Unknown tool '{tool_name}'. Expected: {TOOL_NAME}"}

    # The Gateway sends the tool's arguments directly as the event (no wrapper object).
    event = event if isinstance(event, dict) else {}

    query = event.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"error": "query is required (string)"}

    number_of_results = event.get("number_of_results", DEFAULT_RESULTS)
    # bool is a subclass of int in Python, so reject it explicitly.
    if isinstance(number_of_results, bool) or not isinstance(number_of_results, int) \
            or not 1 <= number_of_results <= MAX_RESULTS:
        return {"error": f"number_of_results must be an integer between 1 and {MAX_RESULTS}"}

    country_code = event.get("country_code")
    if country_code is not None:
        country_code = str(country_code).strip().upper()
        if country_code not in COUNTRY_SUFFIXES:
            return {"error": f"country_code must be one of: {', '.join(COUNTRY_SUFFIXES)}"}

    try:
        return retrieve_policy(query.strip(), number_of_results, country_code)
    except (ClientError, BotoCoreError) as exc:
        # Return the AWS error (e.g. AccessDenied, missing SSM parameter) as data so the
        # Gateway relays a readable message to the agent instead of a Lambda failure.
        return {"error": f"Policy retrieval failed: {exc}"}
