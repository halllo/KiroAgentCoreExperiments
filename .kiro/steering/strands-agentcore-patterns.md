# Strands & AgentCore Patterns

> Reminder: confirm the current API from the docs via MCP **before** writing code (see `documentation-first.md`). The patterns below are conventions for this project, not a substitute for the live docs.

## The `@tool` decorator pattern

Agent capabilities are exposed as tools using the Strands `@tool` decorator. This is the required pattern for all agent tools in this project.

```python
from strands import tool

@tool
def order_lookup(order_id: str) -> str:
    """Look up order details by order ID.

    Args:
        order_id: The order identifier, e.g. "ORD-001".

    Returns:
        A human-readable string describing the order.
    """
    # The model reads this docstring to decide when to call the tool,
    # so keep the description accurate and the arguments well named.
    ...
```

Rules for tools:

- One tool = one clear capability.
- Type-hint every parameter and the return value.
- The docstring is the model's instruction manual for the tool — make it count.
- Prefer returning a clean, formatted `str` the agent can relay to the user.
- Reuse Strands built-ins where they exist (e.g. `current_time` from `strands_tools`) instead of re-implementing them.

## Registering tools with the agent

Tools are passed to the `Agent` constructor. Keep the agent setup minimal and only add the `system_prompt` and `tools` the task requires.

## Search docs before coding AgentCore or Strands

Before writing any Python that uses AgentCore or Strands Agents (agents, tools, memory session managers, MCP gateway client, etc.):

1. `search_docs` / `search_documentation` for the specific feature.
2. `fetch_doc` / `read_documentation` on the matching page.
3. Implement against what the docs show, and cite the URL.

## AgentCore project files

- Treat `agentcore.json` and `agentcore/.env.local` as the source of truth for runtime config (memory ID, gateway URL, env vars, execution role, resource ARNs).
- Read values (IDs, ARNs, URLs) from these files or from `agentcore status` rather than hardcoding them.
- Keep changes to these files minimal and intentional.
