# Python Coding Standards

All Python in this project is written for **learning**, so clarity beats cleverness.

## Type hints

- **Every function uses type hints** on all parameters and the return value.
- Use precise types (`str`, `int`, `dict[str, Any]`, `list[str]`, `Optional[...]`) rather than bare `Any` when the shape is known.
- Import from `typing` only when needed; prefer built-in generics (`list`, `dict`) on modern Python.

```python
def order_lookup(order_id: str) -> str:
    """Look up order details by order ID and return a formatted string."""
    ...
```

## Educational inline comments

- Add short inline comments that explain **why**, not just what — the reader is learning the concepts.
- Comment the parts that are specific to Strands or AgentCore (e.g. why a tool is decorated, what a session manager does, why a namespace is formatted a certain way).
- Keep comments accurate and concise. Remove stale comments when code changes.

```python
# @tool registers this function with the agent so the LLM can call it by name.
# The docstring is what the model reads to decide when to use the tool.
@tool
def product_lookup(product_id: str) -> str:
    ...
```

## Keep it minimal and focused

- Implement exactly what the task asks. No speculative configuration, no extra abstraction layers.
- Prefer a single clear module over splitting logic across many files unless the task calls for it.
- Mock/sample data (orders, customers, products, policies) should be simple literals that make the concept obvious.

## Docstrings matter for tools

For Strands `@tool` functions, the **docstring is a functional contract** — the model uses it to decide when and how to call the tool. Write a clear one-line summary plus a note on inputs and what is returned.
