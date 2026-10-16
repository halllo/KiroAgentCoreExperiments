"""Data lookup Lambda for an AgentCore Gateway target.

Serves three tools from DynamoDB (us-west-2): order_lookup, user_lookup, product_lookup.

Gateway Lambda contract (see
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html):
- `event` is a flat map of the tool's inputSchema properties, e.g. {"customer_id": "C-01"}.
- `context.client_context.custom["bedrockAgentCoreToolName"]` holds the called tool as
  "<target_name>___<tool_name>" (see
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-tool-naming.html).
- The function must return valid JSON.

Response shape (always a plain JSON-serializable dict):
- order_lookup   -> {"orders": [ {customer_id, product_id, purchased_date, status}, ... ], "count": N}
- user_lookup    -> {"customer": {customer_id, name, country_code}}
- product_lookup -> {"product": {product_id, product_name, product_category, provider}}
- any failure    -> {"error": "<readable message>"}

Intended Gateway tool schemas:

    {
      "name": "order_lookup",
      "description": "Look up a customer's orders, or one specific order when product_id is given.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "customer_id": {"type": "string", "description": "Customer ID, e.g. C-01"},
          "product_id": {"type": "string", "description": "Optional product ID, e.g. P-001"}
        },
        "required": ["customer_id"]
      }
    }
    {
      "name": "user_lookup",
      "description": "Look up a customer profile (name, country_code).",
      "inputSchema": {
        "type": "object",
        "properties": {
          "customer_id": {"type": "string", "description": "Customer ID, e.g. C-01"}
        },
        "required": ["customer_id"]
      }
    }
    {
      "name": "product_lookup",
      "description": "Look up product details (name, category, provider).",
      "inputSchema": {
        "type": "object",
        "properties": {
          "product_id": {"type": "string", "description": "Product ID, e.g. P-001"}
        },
        "required": ["product_id"]
      }
    }
"""

import os
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

# Created once at import time so warm Lambda invocations reuse the same connection.
dynamodb = boto3.resource("dynamodb", region_name="us-west-2")

# Env-overridable so the same code can point at other tables without edits.
ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "workshop-orders")
CUSTOMERS_TABLE = os.environ.get("CUSTOMERS_TABLE", "workshop-customers")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "workshop-products")

# Gateway prefixes every tool name with "<target_name>___" (three underscores).
TOOL_NAME_DELIMITER = "___"
TOOLS = ("order_lookup", "user_lookup", "product_lookup")


def get_tool_name(context: Any) -> str:
    """Return the bare tool name from the Gateway context ('' if absent)."""
    # client_context is None on direct/console invocations, so read it defensively.
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    full_name = custom.get("bedrockAgentCoreToolName", "")
    # partition() never raises: with the delimiter we get the tool part, without it
    # (local tests) we keep the full name. The doc boilerplate uses .index(), which raises.
    _, sep, tool = full_name.partition(TOOL_NAME_DELIMITER)
    return tool if sep else full_name


def order_lookup(customer_id: str, product_id: Optional[str]) -> dict[str, Any]:
    """Return one order (customer_id + product_id) or all orders for a customer."""
    table = dynamodb.Table(ORDERS_TABLE)
    # The orders table has no order_id: each order is keyed by (customer_id, product_id).
    if product_id:
        item = table.get_item(Key={"customer_id": customer_id, "product_id": product_id}).get("Item")
        if not item:
            return {"error": f"No order found for customer {customer_id} and product {product_id}"}
        return {"orders": [item], "count": 1}

    # Query on the partition key reads only this customer's items (a Scan would read the whole table).
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"KeyConditionExpression": Key("customer_id").eq(customer_id)}
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        # Query returns at most 1 MB per page; LastEvaluatedKey means there is more.
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    if not items:
        return {"error": f"No orders found for customer {customer_id}"}
    # All attributes in these tables are strings, so items are JSON-safe (no Decimal values).
    return {"orders": items, "count": len(items)}


def user_lookup(customer_id: str) -> dict[str, Any]:
    """Return the customer profile for customer_id."""
    item = dynamodb.Table(CUSTOMERS_TABLE).get_item(Key={"customer_id": customer_id}).get("Item")
    if not item:
        return {"error": f"No customer found with ID {customer_id}"}
    return {"customer": item}


def product_lookup(product_id: str) -> dict[str, Any]:
    """Return the product details for product_id."""
    item = dynamodb.Table(PRODUCTS_TABLE).get_item(Key={"product_id": product_id}).get("Item")
    if not item:
        return {"error": f"No product found with ID {product_id}"}
    return {"product": item}


def _required_str(event: dict[str, Any], name: str) -> Optional[str]:
    """Return event[name] if it is a non-empty string, else None."""
    value = event.get(name)
    return value.strip() if isinstance(value, str) and value.strip() else None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Entry point: dispatch to the tool named in the Gateway context."""
    tool_name = get_tool_name(context)
    # The Gateway sends the tool's arguments directly as the event (no wrapper object).
    event = event if isinstance(event, dict) else {}

    try:
        if tool_name == "order_lookup":
            customer_id = _required_str(event, "customer_id")
            if not customer_id:
                return {"error": "customer_id is required (string)"}
            # product_id is optional, but if the model sends it, it must be usable.
            product_id = _required_str(event, "product_id")
            if "product_id" in event and event["product_id"] is not None and not product_id:
                return {"error": "product_id must be a non-empty string when provided"}
            return order_lookup(customer_id, product_id)

        if tool_name == "user_lookup":
            customer_id = _required_str(event, "customer_id")
            if not customer_id:
                return {"error": "customer_id is required (string)"}
            return user_lookup(customer_id)

        if tool_name == "product_lookup":
            product_id = _required_str(event, "product_id")
            if not product_id:
                return {"error": "product_id is required (string)"}
            return product_lookup(product_id)

        return {"error": f"Unknown tool '{tool_name}'. Expected one of: {', '.join(TOOLS)}"}
    except (ClientError, BotoCoreError) as exc:
        # Return the AWS error (e.g. AccessDenied) as data so the Gateway relays a
        # readable message to the agent instead of a generic Lambda failure.
        return {"error": f"DynamoDB error: {exc}"}
