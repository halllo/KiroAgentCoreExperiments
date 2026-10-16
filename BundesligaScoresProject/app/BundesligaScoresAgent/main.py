from typing import Any, AsyncIterator, Callable
from collections import OrderedDict
from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from mcp_client.client import GATEWAY_URL_ENV_VAR, get_bundesliga_gateway_mcp_client

app = BedrockAgentCoreApp()
log = app.logger

# The source-links rule is required by the Web Search Tool acceptable-use terms:
# https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html#gateway-target-connector-web-search-tool-acceptable-use
# The favorite-team line is the only synthetic data in this project; edit it to change the profile team.
SYSTEM_PROMPT = """
You are a friendly assistant for a casual Bundesliga fan who just wants a quick score.

The user's favorite team is SC Freiburg.

Focus team: if the user names a team (for example "How did Dortmund do?"), that team is the
focus team for this answer. Otherwise the focus team is the user's favorite team.

Always use the web search tool to find the focus team's latest men's Bundesliga (1. Bundesliga)
result. Do not answer from memory.

Answer in this order:
1. The focus team's latest result first: opponent, final score, and date.
2. A short list of the other results from that same matchday.
3. "Sources": the title and URL of each search result you used.

Never invent or guess a score. If the search does not return a clear, recent result, say that
you could not confirm the latest result, and still list the sources you checked.

Every answer that uses search results must show their source links.
Only cover Bundesliga results, and keep it brief.
"""

# Shown instead of an answer when the gateway URL is missing (e.g. before the first deploy).
GATEWAY_MISSING_MESSAGE = (
    f"Web search is not configured: {GATEWAY_URL_ENV_VAR} is not set. "
    "Deploy with `agentcore deploy` (or run `agentcore dev` after a deploy) "
    "so the agent can look up real results."
)

# Built once at import. An MCPClient can be passed straight into Agent(tools=[...]):
# Strands starts it and loads the gateway's tools (the WebSearch connector) for the model.
gateway_client = get_bundesliga_gateway_mcp_client()
tools = [gateway_client] if gateway_client else []


def _make_conversation_manager() -> NullConversationManager:
    # No AgentCore Memory is attached, so nothing persists across sessions. The cached Agent
    # still keeps in-process history within one runtime session; NullConversationManager never
    # trims it, which is fine for the short Q&A sessions this slice targets.
    return NullConversationManager()

# Reuses one Agent per session_id so each session keeps its own in-process
# conversation history (best-effort; resets on cold start). The cache is bounded
# to 128 sessions with LRU eviction (least-recently-used is dropped and its
# history reset) so a single process serving many sessions cannot leak history
# between them or grow without limit. For durable history, attach a session manager.
def agent_factory() -> Callable[[str], Agent]:
    cache: OrderedDict[str, Agent] = OrderedDict()
    def get_or_create_agent(session_id: str) -> Agent:
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[session_id] = Agent(
            model=load_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            conversation_manager=_make_conversation_manager(),
            hooks=[
            ],
        )
        return cache[session_id]
    return get_or_create_agent
get_or_create_agent = agent_factory()


def strip_trailing_tool_use(messages: Any) -> list[dict]:
    """Strip toolUse blocks from the tail until the last message has none."""
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")

    messages = list(messages)
    while messages:
        last = messages[-1]
        if not isinstance(last, dict):
            raise ValueError("each message must be an object")
        original_content = last.get("content", [])
        if not isinstance(original_content, list) or not all(isinstance(block, dict) for block in original_content):
            raise ValueError("each message content value must be a list of content blocks")

        content = [block for block in original_content if "toolUse" not in block]
        if len(content) == len(original_content):
            break
        if content:
            messages[-1] = {**last, "content": content}
            break
        messages.pop()

    return messages


def _extract_prompt(payload: dict) -> str | list[dict]:
    """Accept validated harness messages, tool results, or a plain prompt string."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if "messages" in payload:
        return strip_trailing_tool_use(payload["messages"])
    if "tool_results" in payload:
        tool_results = payload["tool_results"]
        if not isinstance(tool_results, list) or not all(
            isinstance(tool_result, dict) and isinstance(tool_result.get("toolUseId"), str)
            for tool_result in tool_results
        ):
            raise ValueError("tool_results must contain objects with a toolUseId string")
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in tool_results]}]
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    return prompt


@app.entrypoint
async def invoke(payload: dict, context: Any) -> AsyncIterator[Any]:
    log.info("Invoking Agent.....")

    # Without the gateway there is no web search, and answering from model memory
    # would risk invented scores. Reply with a clear message instead, using the same
    # Strands stream-event shape as normal output so clients render it as text.
    if gateway_client is None:
        log.error(GATEWAY_MISSING_MESSAGE)
        yield {"event": {"contentBlockDelta": {"delta": {"text": GATEWAY_MISSING_MESSAGE}}}}
        return

    session_id = getattr(context, 'session_id', 'default-session')
    agent = get_or_create_agent(session_id)

    prompt = _extract_prompt(payload)


    async for event in agent.stream_async(
        prompt,
    ):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
