# AgentCore Gateway Lambda targets for data lookup and policy retrieval

Two standalone Lambda handlers back the Returns & Refunds agent's Gateway. `data_lookup` serves `order_lookup`, `user_lookup` and `product_lookup` from the three `workshop-*` DynamoDB tables. `policy_retrieval` serves `retrieve_policy` against the Bedrock Knowledge Base, with the KB ID read from SSM. Both follow the Gateway Lambda contract: they strip the `<target>___` prefix from `bedrockAgentCoreToolName`, treat the event as a flat argument map, and always return a plain dict (tool-specific keys on success, `{"error": ...}` on failure). The coder's Verification section shows py_compile passing and 17/17 local invocations against live read-only AWS, with every output passed through `json.dumps`.

Watch for: JSON safety depends on every DynamoDB attribute being a string (likely to break if a numeric attribute is ever added). Raw AWS error text goes back to the agent (possible). The country post-filter can come back empty for generic queries (possible). None of these block shipping.

**Verdict**: APPROVED

## High-level view

Both handlers parse the tool name the same way. `str.partition("___")` keeps whatever follows the delimiter and falls back to the full name when there's no delimiter, so it never raises and doesn't carry over the doc boilerplate's `toolName`/`tool_name` mismatch or its `.index()` call. A missing `client_context` gives back an empty name, which `data_lookup` rejects as an unknown tool and `policy_retrieval` accepts as a direct test invocation.

`order_lookup` runs a partition-key Query with `LastEvaluatedKey` pagination, and a GetItem when `product_id` is supplied. It never scans. Both cases return the same `{"orders": [...], "count": N}` shape. Every lookup returns DynamoDB items without conversion, which only works because the current tables hold nothing but strings.

`policy_retrieval` caches the SSM-sourced KB ID in a module-level `_kb_id` and loads it lazily, so warm invocations skip SSM. When `country_code` is set, it fetches 25 results and keeps the ones whose source URI ends in `-us.pdf`, `-uk.pdf` or `-in.pdf`. A comment explains that the KB source-URI metadata filter returned zero results.

Error handling turns missing items, missing or invalid arguments, unknown tools, and `ClientError`/`BotoCoreError` (AccessDenied, missing SSM parameter) into readable `{"error": ...}` dicts. Each module docstring documents the response shape and the Gateway tool schemas. Both `requirements.txt` files pin `boto3==1.43.114` and note that the runtime already bundles boto3. Every boto3 client and resource sets `region_name="us-west-2"`, and every function has full type hints.

<details>
<summary>Issues (3)</summary>

1. **Decimal-unsafe DynamoDB passthrough** (likely, non-blocking): items go back raw. A future numeric attribute would come back as `Decimal`, and serializing the response would fail. If the schema might grow, convert with a small `json.loads(json.dumps(item, default=str))` step or similar.
2. **Raw AWS exception text returned to the agent** (possible, non-blocking): `f"DynamoDB error: {exc}"` and `f"Policy retrieval failed: {exc}"` can pass role ARNs and account IDs into the model's context. Consider returning the error code only (`exc.response["Error"]["Code"]`) and logging the full message.
3. **Country post-filter can go empty** (possible, non-blocking): if the top 25 chunks for a query all come from other countries' PDFs, the result is `count: 0` even though the requested country's policy exists. That's acceptable for the workshop. Mention it in the tool description or bump the over-fetch if it happens in practice.

</details>

<details>
<summary>Details</summary>

### Tool-name dispatch and the direct-invocation asymmetry

```
Gateway ──invoke(event={...args}, client_context.custom.bedrockAgentCoreToolName="Target___tool")──▶ Lambda
                                                     │
                              get_tool_name: partition("___") → "tool" (or full name if no "___")
```

The two handlers treat an empty tool name differently (confirmed). `data_lookup` returns `Unknown tool ''`, which it has to do because it serves three tools. `policy_retrieval` treats it as a direct call and runs the retrieve. That's deliberate and commented, but it means a console test event can only exercise `policy_retrieval`. Testing `data_lookup` without the Gateway needs a crafted `client_context`.

### DynamoDB item serialization

All three lookups return `Item`/`Items` from `boto3.resource` without conversion (confirmed: `return {"customer": item}`, `{"orders": items, ...}`). The comment says all attributes are strings, and the verification output bears that out. If anyone adds a numeric attribute such as a price or a quantity, the resource layer will return it as `Decimal` and the handler's return value will stop serializing, which surfaces as a Lambda failure instead of an `{"error": ...}` (likely, if the schema changes). Today it's an assumption, not a bug.

### Error surface sent to the model

Both `except (ClientError, BotoCoreError)` branches put `str(exc)` into the response (confirmed). For AccessDenied, botocore's message includes the caller's assumed-role ARN and the resource ARN, and the Gateway passes that straight into the agent's context and possibly to end users (possible). Returning just the error code keeps the message readable without exposing account details.

### Country post-filter

The over-fetch-then-filter approach is explained inline, and the US test only returned `-us.pdf` sources. The unfiltered run shows the skew it works around: 4 of 5 top results came from India. With a fixed over-fetch of 25, a generic enough query could still filter down to zero for a country whose chunks rank low (possible). The empty result is returned as a non-error `message`, so the agent can rephrase and try again.

### Test coverage

The verification covers every tool's happy path, not-found cases, missing required arguments, an unknown tool, the no-delimiter fallback, `client_context=None`, invalid `country_code`, out-of-range `number_of_results`, and KB-ID caching. Not tested: the `ClientError` path (no AccessDenied or missing-parameter simulation), multi-page Query pagination (C-01 fits on one page), and `product_id` sent as an empty string or non-string.

</details>

<details>
<summary>Files changed</summary>

- `lambda_functions/data_lookup/handler.py`: new. Gateway handler for order/user/product lookups (Query + GetItem), with tool schemas in the module docstring.
- `lambda_functions/data_lookup/requirements.txt`: new. `boto3==1.43.114` with a note that the runtime bundles boto3.
- `lambda_functions/policy_retrieval/handler.py`: new. Gateway handler for `retrieve_policy` (SSM-cached KB ID, Retrieve, country post-filter).
- `lambda_functions/policy_retrieval/requirements.txt`: new. Same boto3 pin.

Nothing under `AgentCoreProject1/` was modified apart from task artifacts in `.agents/tasks/`. There was no deploy and no commit, according to the coder's `git status` evidence. Full diff: `git -C /home/workshop/ReturnsRefundsAgentProject status --short lambda_functions/`.

</details>
