from typing import Any
from collections import OrderedDict
from strands import Agent, tool
import asyncio
from datetime import date, timedelta
# Strands community tools package; current_time is a ready-made @tool.
from strands_tools import current_time
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from mcp_client.client import get_streamable_http_mcp_client

app = BedrockAgentCoreApp()
log = app.logger

# Define a Streamable HTTP MCP Client
mcp_clients = [get_streamable_http_mcp_client()]

# The system prompt sets the agent's role and behavior for every turn.
# Strands sends it to the model as the system message via Agent(system_prompt=...).
# Docs: https://strandsagents.com/docs/api/python/strands.agent.agent/
DEFAULT_SYSTEM_PROMPT = """
You are a Returns & Refunds Assistant. When greeting the user, introduce yourself
as the Returns & Refunds Assistant.

The user you are talking to is an administrator, not a customer. Administrators
can access customer data, orders, and return policies, and they act on behalf of
customers.

You help administrators:
- Check whether a customer's order is eligible for a return
- Calculate refund amounts
- Answer questions about return policies

Guidelines:
- Be helpful and concise.
- Use tools when appropriate to look up information rather than guessing.
- Always confirm the details (customer, order, items, and refund amount) with the
  administrator before processing any return or refund.
"""


# Define a collection of tools used by the model
tools = []

_INLINE_FUNCTION_NAMES = set()

# Define a simple function tool
@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a+b
tools.append(add_numbers)


# get_current_time: reuse the Strands built-in instead of re-implementing it.
# The model sees this tool under the name "current_time". It returns the current
# date/time in ISO 8601, which the agent needs to judge return windows.
# Note: deprecated in strands-agents-tools 0.8.x (still works, logs a warning).
# Docs: https://strandsagents.com/docs/user-guide/sdk/tools/community-tools-package/
tools.append(current_time)


# --- Mock data -------------------------------------------------------------
# Simple in-memory dicts stand in for real data sources (DynamoDB later on).

# Purchases are stored as "days ago" so the sample data stays valid whenever
# the workshop runs; order_lookup turns this into a concrete date.
ORDERS: dict[str, dict[str, Any]] = {
    "ORD-001": {"customer_id": "C-01", "product_id": "P-001", "product_name": "iPhone 15 Pro",
                "status": "DELIVERED", "purchase_days_ago": 5},
    "ORD-002": {"customer_id": "C-02", "product_id": "P-003", "product_name": "Kindle Paperwhite",
                "status": "DELIVERED", "purchase_days_ago": 45},
    # No purchase age was specified for this order, so it is left as None.
    "ORD-003": {"customer_id": "C-01", "product_id": "P-005", "product_name": "PlayStation 5",
                "status": "SHIPPED", "purchase_days_ago": None},
}

CUSTOMERS: dict[str, dict[str, str]] = {
    "C-01": {"name": "Rajesh Kumar", "country": "IN", "email": "rajesh@example.com"},
    "C-02": {"name": "Sarah Johnson", "country": "US", "email": "sarah@example.com"},
    "C-03": {"name": "James Wilson", "country": "UK", "email": "james@example.com"},
}

PRODUCTS: dict[str, dict[str, str]] = {
    "P-001": {"name": "iPhone 15 Pro", "brand": "Apple", "category": "phone"},
    "P-002": {"name": "Kindle Paperwhite", "brand": "Amazon", "category": "e-book"},
    "P-003": {"name": "iPad Air", "brand": "Apple", "category": "tablet"},
}

# Keyed by category so policy_retrieval can match on the category name.
POLICIES: dict[str, str] = {
    "electronics": "Electronics: 30-day return window. 100% refund if the item is unopened.",
    "clothing": "Clothing: 60-day return window. Full refund.",
    "books": "Books: 14-day return window. 50% refund.",
}


# --- Tools -------------------------------------------------------------------
# @tool turns each function into a tool the model can call by name. Strands
# builds the tool spec from the docstring (description + Args) and type hints,
# so the docstring is effectively the model's instructions for the tool.
# Docs: https://strandsagents.com/docs/user-guide/sdk/tools/custom-tools/

@tool
def order_lookup(order_id: str) -> str:
    """Look up order details by order ID.

    Args:
        order_id: The order identifier, e.g. "ORD-001".

    Returns:
        A formatted string with the customer ID, product, status, and purchase
        date of the order, or a not-found message.
    """
    order = ORDERS.get(order_id.strip().upper())
    if order is None:
        return f"No order found with ID {order_id}."

    # Convert "days ago" into a real date so the agent can compare it with
    # the current time when checking a return window.
    days_ago = order["purchase_days_ago"]
    if days_ago is None:
        purchased = "Not specified"
    else:
        purchase_date = date.today() - timedelta(days=days_ago)
        purchased = f"{purchase_date.isoformat()} ({days_ago} days ago)"

    return (
        f"Order {order_id.strip().upper()}\n"
        f"- Customer ID: {order['customer_id']}\n"
        f"- Product: {order['product_name']} ({order['product_id']})\n"
        f"- Status: {order['status']}\n"
        f"- Purchase date: {purchased}"
    )
tools.append(order_lookup)


@tool
def user_lookup(user_id: str) -> str:
    """Retrieve customer information by user ID.

    Args:
        user_id: The customer identifier, e.g. "C-01".

    Returns:
        A formatted string with the customer's name, country, and email,
        or a not-found message.
    """
    customer = CUSTOMERS.get(user_id.strip().upper())
    if customer is None:
        return f"No customer found with ID {user_id}."
    return (
        f"Customer {user_id.strip().upper()}\n"
        f"- Name: {customer['name']}\n"
        f"- Country: {customer['country']}\n"
        f"- Email: {customer['email']}"
    )
tools.append(user_lookup)


@tool
def product_lookup(product_id: str) -> str:
    """Retrieve product information by product ID.

    Args:
        product_id: The product identifier, e.g. "P-001".

    Returns:
        A formatted string with the product's name, brand, and category,
        or a not-found message.
    """
    product = PRODUCTS.get(product_id.strip().upper())
    if product is None:
        return f"No product found with ID {product_id}."
    return (
        f"Product {product_id.strip().upper()}\n"
        f"- Name: {product['name']}\n"
        f"- Brand: {product['brand']}\n"
        f"- Category: {product['category']}"
    )
tools.append(product_lookup)


@tool
def policy_retrieval(query: str) -> str:
    """Retrieve return policy information for product categories.

    Known categories: electronics, clothing, books.

    Args:
        query: A question or keywords about return policies, e.g.
            "electronics return window".

    Returns:
        The matching return policy details. If no category is mentioned in
        the query, all policies are returned.
    """
    query_lower = query.lower()
    matches = [policy for category, policy in POLICIES.items() if category in query_lower]
    # Simple keyword matching keeps the demo easy to follow. When nothing
    # matches, return every policy and let the model pick the relevant one.
    if not matches:
        matches = list(POLICIES.values())
    return "\n".join(matches)
tools.append(policy_retrieval)



# Add MCP client to tools if available
for mcp_client in mcp_clients:
    if mcp_client:
        tools.append(mcp_client)


def _make_conversation_manager():
    return NullConversationManager()

# Reuses one Agent per session_id so each session keeps its own in-process
# conversation history (best-effort; resets on cold start). The cache is bounded
# to 128 sessions with LRU eviction (least-recently-used is dropped and its
# history reset) so a single process serving many sessions cannot leak history
# between them or grow without limit. For durable history, attach a session manager.
def agent_factory():
    cache = OrderedDict()
    def get_or_create_agent(session_id):
        if session_id in cache:
            cache.move_to_end(session_id)
            return cache[session_id]
        if len(cache) >= 128:
            cache.popitem(last=False)
        cache[session_id] = Agent(
            model=load_model(),
            system_prompt=DEFAULT_SYSTEM_PROMPT,
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


def _extract_prompt(payload: dict):
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


def _has_inline_function_call(messages) -> bool:
    """Return True if messages contains an assistant toolUse for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES:
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    """Check if a contentBlockStart event is for an inline function tool."""
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES



@app.entrypoint
async def invoke(payload, context):
    log.info("Invoking Agent.....")


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
