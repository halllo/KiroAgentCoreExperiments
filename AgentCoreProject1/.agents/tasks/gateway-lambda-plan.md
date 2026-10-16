# Implementation Plan: AgentCore Gateway Lambda targets

Scope: create 4 files under `/home/workshop/ReturnsRefundsAgentProject/lambda_functions/` (directory does not exist yet) plus one throwaway verification script under `.agents/tasks/`. Do NOT touch anything else in `AgentCoreProject1/` (no `agentcore.json` edits, no deploy, no AWS resource creation, no commit). No worktree: use absolute paths.

## Docs consulted (cite in code comments)

- Gateway Lambda target contract: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html
  - `event` = flat map of inputSchema properties to values (no wrapper).
  - `context.client_context.custom` holds `bedrockAgentCoreMessageVersion`, `bedrockAgentCoreAwsRequestId`, `bedrockAgentCoreMcpMessageId`, `bedrockAgentCoreGatewayId`, `bedrockAgentCoreTargetId`, `bedrockAgentCoreToolName`.
  - Function must return a valid JSON response; meaningful error messages recommended.
  - The doc boilerplate assigns `toolName` but tests `tool_name` (bug) and uses `.index()` which raises when the delimiter is absent. Do not copy it.
- Tool naming (`${target_name}___${tool_name}`, three underscores): https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-tool-naming.html
- Retrieve API (request `retrievalQuery.text`, `retrievalConfiguration.vectorSearchConfiguration.numberOfResults`; response `retrievalResults[].content.text`, `.score`, `.location.s3Location.uri`): https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_Retrieve.html
- Environment facts: Python 3.10.12, installed boto3 `1.43.114` (also latest on PyPI per `pip index versions boto3`).

## Design decisions

1. Prefix stripping: shared-shape helper in each handler (duplicated, no shared module, since each Lambda is packaged on its own):
   ```python
   TOOL_NAME_DELIMITER = "___"
   def get_tool_name(context: Any) -> str:
       # client_context is None on direct/console invocations -> return "" (caller then falls back)
       custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
       full_name = custom.get("bedrockAgentCoreToolName", "")
       # Gateway sends "<target>___<tool>"; partition keeps the full name when the delimiter is absent.
       _, sep, tool = full_name.partition(TOOL_NAME_DELIMITER)
       return tool if sep else full_name
   ```
   Rationale: `str.partition` never raises and handles both the Gateway and local-test cases in one line.
2. Response shape: always a plain JSON-serializable dict. Success = tool-specific keys (below); failure = `{"error": "<message>"}`. Never raise out of `lambda_handler`; catch `botocore.exceptions.ClientError` / `BotoCoreError` and return `{"error": ...}` so the Gateway relays a readable message instead of a Lambda failure. Document the shape in each module docstring.
3. Input validation: required string fields must be non-empty `str`; otherwise `{"error": "customer_id is required (string)"}`, etc. (matches AGENTS.md invariant 5 spirit).
4. DynamoDB values are all strings in these tables, so `boto3.resource` items are JSON-safe (no `Decimal` handling needed; leave a one-line comment saying so).
5. Policy post-filter (decided): KB metadata filter on `x-amz-bedrock-kb-source-uri` returned zero results and generic queries skew to India chunks, so when `country_code` is given, over-fetch `numberOfResults=25` and keep results whose `source_uri` ends with `-us.pdf` / `-uk.pdf` / `-in.pdf`, then trim to `number_of_results`. Comment must explain why a KB filter isn't used.
6. KB ID cached in a module-level `_kb_id: Optional[str] = None`, loaded lazily from SSM on first call so warm invocations skip SSM and import never makes network calls.
7. Tool schemas: a module-level docstring section per handler with name/description/inputSchema JSON for each tool. No separate schema files.

## Plan

- [ ] 1. Create the data_lookup Lambda.
      Files: `/home/workshop/ReturnsRefundsAgentProject/lambda_functions/data_lookup/handler.py`
      Contents:
      - Module docstring: purpose, Gateway contract summary + URLs above, response shape, and tool schemas:
        - `order_lookup`: "Look up a customer's orders (optionally one product's order)". props `customer_id` (string, e.g. "C-01"), `product_id` (string, optional, e.g. "P-001"); required `["customer_id"]`.
        - `user_lookup`: "Look up customer profile (name, country_code)". props `customer_id`; required `["customer_id"]`.
        - `product_lookup`: "Look up product details (name, category, provider)". props `product_id`; required `["product_id"]`.
      - `dynamodb = boto3.resource("dynamodb", region_name="us-west-2")` at module scope (reused across warm invocations).
      - Constants: `ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "workshop-orders")`, `CUSTOMERS_TABLE` (`workshop-customers`), `PRODUCTS_TABLE` (`workshop-products`).
      - `get_tool_name(context: Any) -> str` per decision 1.
      - `order_lookup(customer_id: str, product_id: Optional[str]) -> dict[str, Any]`: if product_id -> `get_item(Key={"customer_id":..., "product_id":...})`, return `{"orders": [item], "count": 1}` or `{"error": "No order found for customer C-01 and product P-009"}`; else `query(KeyConditionExpression=Key("customer_id").eq(customer_id))` looping while `LastEvaluatedKey` (pass `ExclusiveStartKey`), return `{"orders": items, "count": len(items)}`; empty -> `{"error": "No orders found for customer ..."}`. Comment: table has no `order_id`; orders are keyed by (customer_id, product_id); Query not Scan.
      - `user_lookup(customer_id: str) -> dict[str, Any]` -> `{"customer": item}` or not-found error.
      - `product_lookup(product_id: str) -> dict[str, Any]` -> `{"product": item}` or not-found error.
      - `lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]`: strip tool name, dispatch via `if/elif` on the three names, validate required string inputs (`product_id` optional but if present must be a non-empty string), unknown tool -> `{"error": "Unknown tool '<name>'. Expected one of: order_lookup, user_lookup, product_lookup"}`; wrap AWS calls in `try/except (ClientError, BotoCoreError)` -> `{"error": f"DynamoDB error: {exc}"}`.
      - Full type hints, short WHY comments (Gateway prefix, flat event, client_context).
      Verify: `python3 -m py_compile /home/workshop/ReturnsRefundsAgentProject/lambda_functions/data_lookup/handler.py` exits 0.

- [ ] 2. Create the policy_retrieval Lambda.
      Files: `/home/workshop/ReturnsRefundsAgentProject/lambda_functions/policy_retrieval/handler.py`
      Contents:
      - Module docstring: purpose, contract + URLs, response shape, tool schema:
        - `retrieve_policy`: "Retrieve return/refund policy excerpts from the knowledge base". props `query` (string), `country_code` (string, optional, one of US/UK/IN; matches workshop-customers.country_code), `number_of_results` (integer, optional, default 5); required `["query"]`.
      - Module-scope clients: `ssm = boto3.client("ssm", region_name="us-west-2")`, `bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name="us-west-2")`.
      - Constants: `KB_ID_PARAMETER = "/app/workshop/kb/knowledge-base-id"`, `TOOL_NAME = "retrieve_policy"`, `DEFAULT_RESULTS = 5`, `MAX_RESULTS = 25`, `OVERFETCH_RESULTS = 25`, `COUNTRY_SUFFIXES = {"US": "-us.pdf", "UK": "-uk.pdf", "IN": "-in.pdf"}`.
      - `get_tool_name(context: Any) -> str` per decision 1.
      - `get_knowledge_base_id() -> str`: module-level cache `_kb_id`; `ssm.get_parameter(Name=KB_ID_PARAMETER)["Parameter"]["Value"]`. Never hardcode the ID.
      - `retrieve_policy(query: str, number_of_results: int, country_code: Optional[str]) -> dict[str, Any]`: fetch count = `OVERFETCH_RESULTS` if country_code else `number_of_results`; call `bedrock_agent_runtime.retrieve(knowledgeBaseId=..., retrievalQuery={"text": query}, retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": n}})`; map each result to `{"text": r["content"].get("text", ""), "score": r.get("score"), "source_uri": r.get("location", {}).get("s3Location", {}).get("uri", "")}`; if country_code, keep only `source_uri.lower().endswith(suffix)` (decision 5 comment); trim to `number_of_results`; return `{"results": [...], "count": n}`; empty -> `{"results": [], "count": 0, "message": "No policy excerpts found ..."}` (not an error).
      - `lambda_handler(event, context) -> dict[str, Any]`: strip name; if non-empty and != `retrieve_policy` -> unknown-tool error (empty name allowed for direct tests); validate `query` non-empty str; `number_of_results` must be int (reject bool) in 1..MAX_RESULTS, default 5; `country_code` optional, `.upper()`, must be in `COUNTRY_SUFFIXES` else error listing valid codes; catch `(ClientError, BotoCoreError)` -> `{"error": f"Policy retrieval failed: {exc}"}`.
      Verify: `python3 -m py_compile /home/workshop/ReturnsRefundsAgentProject/lambda_functions/policy_retrieval/handler.py` exits 0.

- [ ] 3. Create both requirements.txt files (same content).
      Files: `/home/workshop/ReturnsRefundsAgentProject/lambda_functions/data_lookup/requirements.txt`, `/home/workshop/ReturnsRefundsAgentProject/lambda_functions/policy_retrieval/requirements.txt`
      Contents:
      ```
      # The AWS Lambda Python runtime already bundles boto3; pinning here keeps local testing
      # and any packaged deployment on a known version that includes bedrock-agent-runtime.
      boto3==1.43.114
      ```
      Verify: `pip install --dry-run -r <file>` resolves (or `pip index versions boto3` lists 1.43.114).

- [ ] 4. Write and run the local verification script (read-only AWS calls only: Query, GetItem, GetParameter, Retrieve).
      Files: `/home/workshop/ReturnsRefundsAgentProject/AgentCoreProject1/.agents/tasks/gateway-lambda-verify.py` (lives with task artifacts, not in `lambda_functions/`, so no extra deliverable is added).
      Approach: load each handler with `importlib.util.spec_from_file_location` (both are named `handler.py`), build a fake context `SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "DataLookup___order_lookup", ...other keys...}))`, call `lambda_handler`, `json.dumps` every result (proves JSON-serializable), and assert:
      - data_lookup: `order_lookup {"customer_id":"C-01"}` -> count 5, product_ids {P-001,P-002,P-005,P-006,P-007}; `order_lookup {"customer_id":"C-01","product_id":"P-001"}` -> count 1; `user_lookup C-03` -> name "Michael Smith", country_code "US"; `product_lookup P-001` -> has product_name; `user_lookup C-99` -> "error"; missing customer_id -> "error"; unknown tool `X___bogus` -> "error"; context with `client_context=None` and no delimiter (`custom={"bedrockAgentCoreToolName":"user_lookup"}`) still works.
      - policy_retrieval: `PolicyTarget___retrieve_policy {"query":"electronics return policy","country_code":"US","number_of_results":3}` -> 1..3 results, all `source_uri` end with `-us.pdf`; no country_code -> results list returned; `country_code "FR"` -> error; missing query -> error; wrong tool name -> error; second call does not re-hit SSM (assert module `_kb_id` is set after first call).
      Verify: `AWS_DEFAULT_REGION=us-west-2 python3 /home/workshop/ReturnsRefundsAgentProject/AgentCoreProject1/.agents/tasks/gateway-lambda-verify.py` prints all checks passed and exits 0. Paste output summary into the step report. If AWS credentials are unavailable, state that and fall back to a stubbed run (monkeypatch module clients with fakes) for dispatch/validation logic.

- [ ] 5. Final checks.
      - `git -C /home/workshop/ReturnsRefundsAgentProject status --short` shows only new `lambda_functions/` files and `.agents/tasks/` artifacts (pre-existing `deployed-state.json` modification is not ours; leave it). No commit.
      - Remove `__pycache__` dirs created under `lambda_functions/` by py_compile/imports.
      - Confirm every function in both handlers has full type hints and both handlers cite the Gateway doc URL.

## Gaps / assumptions

- Target names used in tests (`DataLookup`, `PolicyTarget`) are placeholders; real names are chosen at gateway-target registration (out of scope).
- `number_of_results` capped at 25 to match the over-fetch size; Retrieve itself allows more, but the cap keeps post-filter semantics simple.
- IAM for the eventual Lambda roles (dynamodb:Query/GetItem on the 3 tables; ssm:GetParameter on the one parameter; bedrock:Retrieve on the KB) is not created here; mention it in the final report only.

## Verification

Iteration 1 (no gateway-lambda-review.json existed). Docs re-read via AWS Documentation MCP: gateway-add-target-lambda.html, gateway-tool-naming.html (search hit), API_agent-runtime_Retrieve.html. Env: Python 3.10.12, boto3 1.43.114, account 278581056849, us-west-2.

Commands run (from /home/workshop/ReturnsRefundsAgentProject):

```
python3 -m py_compile lambda_functions/data_lookup/handler.py
python3 -m py_compile lambda_functions/policy_retrieval/handler.py
AWS_DEFAULT_REGION=us-west-2 python3 AgentCoreProject1/.agents/tasks/gateway-lambda-verify.py
```

py_compile: both OK (exit 0). Verify script: 17/17 PASS, exit 0. Every output passed through `json.dumps`. Fake context = `SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "DataLookupTarget___<tool>"}))` (policy: `PolicyTarget___retrieve_policy`).

| Test | Output (abridged) |
| --- | --- |
| order_lookup C-01 | count 5; product_ids {P-001,P-002,P-005,P-006,P-007} |
| order_lookup C-01 + P-002 | `{"orders":[{"customer_id":"C-01","purchased_date":"2024-02-20","status":"OPENED","product_id":"P-002"}],"count":1}` |
| user_lookup C-03 | `{"customer":{"customer_id":"C-03","name":"Michael Smith","country_code":"US"}}` |
| product_lookup P-003 | `{"product":{"provider":"Apple","product_name":"iPad Air","product_category":"tablet","product_id":"P-003"}}` |
| user_lookup C-99 | `{"error":"No customer found with ID C-99"}` |
| order_lookup C-99 | `{"error":"No orders found for customer C-99"}` |
| unknown tool `DataLookupTarget___bogus` | `{"error":"Unknown tool 'bogus'. Expected one of: order_lookup, user_lookup, product_lookup"}` |
| order_lookup missing customer_id | `{"error":"customer_id is required (string)"}` |
| no delimiter, tool name `user_lookup` | `{"customer":{"customer_id":"C-01","name":"Rajesh Kumar","country_code":"IN"}}` |
| client_context=None | `{"error":"Unknown tool ''. Expected one of: ..."}` (no exception) |
| retrieve_policy "electronics return window", country_code US | results >= 1, all sources = `s3://278581056849-us-west-2-kiro-ws-kb-a150a020/Amazon-return-policy-us.pdf`; first excerpt "It can take up to 30 days for us to receive and process your return..." |
| retrieve_policy same query, no country_code | 5 results; sources in, in, in, in, us |
| second call (query "refund") | results returned; module `_kb_id` cached (SSM not re-read) |
| country_code FR | `{"error":"country_code must be one of: US, UK, IN"}` |
| missing query | `{"error":"query is required (string)"}` |
| wrong tool `PolicyTarget___other` | `{"error":"Unknown tool 'other'. Expected: retrieve_policy"}` |
| number_of_results 0 | `{"error":"number_of_results must be an integer between 1 and 25"}` |

Cleanup: verify script deleted; `__pycache__` removed from both lambda dirs. `git status`: only `lambda_functions/` and this plan file are new; `deployed-state.json` modification pre-existed. No commit, no deploy, no AWS writes.
