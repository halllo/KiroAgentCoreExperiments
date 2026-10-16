# Implementation Plan: Gateway + Web Search connector for BundesligaScoresAgent (first slice)

Scope: work directly in `/home/workshop/ReturnsRefundsAgentProject/BundesligaScoresProject` (absolute paths everywhere). Do NOT deploy, do NOT commit, do NOT touch anything under `/home/workshop/ReturnsRefundsAgentProject/AgentCoreProject1/`, and do NOT touch `agentcore/aws-targets.json` (it already has a staged user change). No nested `.git`.

Abbreviations: `PROJ=/home/workshop/ReturnsRefundsAgentProject/BundesligaScoresProject`, `AGENT=$PROJ/app/BundesligaScoresAgent`.

## Docs consulted (cite in code comments / README)

- Web Search Tool connector (tool discovery, input schema, response shape, us-west-2 availability, acceptable-use citation rule): https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html
- Target config / CLI example `agentcore add gateway-target --type connector --connector web-search`: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-api-target-config.html
- Connector versions (default `web-search` version is `1.1.0` when no version is pinned; the CLI schema has no version field, so we take the default): https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-versions.html
- IAM inbound auth (caller needs `bedrock-agentcore:InvokeGateway` scoped to the gateway ARN): https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html
- Strands + SigV4 to a Gateway via `mcp_proxy_for_aws.client.aws_iam_streamablehttp_client(endpoint=..., aws_region=..., aws_service="bedrock-agentcore")`: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-gateway-target.html (section "Invoke with Strands Agents")
- Strands `MCPClient(transport_callable, ..., prefix=None, ...)`: https://strandsagents.com/docs/api/python/strands.tools.mcp.mcp_client/index.md

## Findings from exploration (already verified, do not re-derive)

- CLI 1.0.0-preview.33 supports everything non-interactively. Trial run in a throwaway copy confirmed:
  - `agentcore add gateway --authorizer-type AWS_IAM --protocol-type MCP --no-semantic-search` writes `authorizerType: "AWS_IAM"`, `protocolType: "MCP"`, `enableSemanticSearch: false`. No Cognito is created.
  - `agentcore add gateway-target --type connector --connector web-search` writes `targetType: "connector"`, `connectorId: "web-search"`, plus a `configurations: [{ "name": "WebSearch", ... }]` entry. `agentcore validate` → `Valid`.
  - The CLI does NOT modify `app/` code when adding a gateway; the agent wiring is manual.
  - `agentcore deploy --dry-run --json` builds the CDK project and synthesizes CloudFormation (read-only AWS calls for bootstrap/stack status, no resources created, `.cli/deployed-state.json` unchanged). Output artifacts (`agentcore/cdk/cdk.out`, `agentcore/cdk/dist`, `agentcore/.cli/logs`) are gitignored.
- How the gateway URL reaches the agent (no hardcoding needed). From `agentcore/cdk/node_modules/@aws/agentcore-cdk/dist/cdk/constructs/l3/AgentCoreMcp.js` (`wireGatewayUrlsToAgents`) and the synthesized template:
  - Runtime env var `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL` = `Fn::GetAtt Gateway.GatewayUrl` (name = `AGENTCORE_GATEWAY_` + gateway name upper-cased, `-`→`_`, + `_URL`).
  - Runtime env var `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_AUTH_TYPE` = `AWS_IAM`.
  - Runtime execution role gets `bedrock-agentcore:InvokeGateway` on the gateway ARN only (least privilege, automatic).
  - Gateway service role gets `bedrock-agentcore:InvokeWebSearch` on `arn:aws:bedrock-agentcore:us-west-2:aws:tool/web-search.v1`; target uses `GATEWAY_IAM_ROLE` outbound credentials (automatic).
  - `agentcore dev` injects the same `AGENTCORE_GATEWAY_*_URL` env vars from `agentcore/.cli/deployed-state.json` once the project has been deployed. Before the first deploy the var is absent locally.
  - Therefore: do NOT add any `envVars` to `agentcore.json` and do NOT write a URL anywhere.
- The CLI's own Strands template (`/usr/lib/node_modules/@aws/agentcore/dist/assets/python/http/strands/base/mcp_client/client.py`, `hasGateway` + `AWS_IAM` branch) is the canonical pattern: read the env var, return `None` with a warning if missing, otherwise `MCPClient(lambda: aws_iam_streamablehttp_client(url, aws_service="bedrock-agentcore", aws_region=...))`, and add `mcp-proxy-for-aws` to `pyproject.toml`. We follow it.
- `mcp-proxy-for-aws` 1.7.0 installs cleanly into the project's Python 3.10 venv (trial-verified); signature `aws_iam_streamablehttp_client(endpoint, aws_service, aws_region=None, ...)`.
- `AgentCoreProject1` never actually wired a gateway in its agent (its `agentCoreGateways` is `[]` and its `mcp_client/client.py` is still the Exa template). It is only a style reference.
- `BedrockAgentCoreApp.entrypoint` returns the original function, so `main.invoke(payload, None)` can be driven directly from a test script; streamed values are SSE-serialized as-is.

## Design decisions

1. Gateway `BundesligaGateway`, protocol MCP, inbound auth `AWS_IAM` (decided upstream). Semantic search is disabled (`--no-semantic-search`) because there is exactly one tool; leaving it on would add the extra `x_amz_bedrock_agentcore_search` tool, and the canvas says "one tool".
2. Target `WebSearch`, `--type connector --connector web-search`, no `--exclude-domains` (out of scope today), no version pin (CLI schema has no version field; default 1.1.0 is fine).
3. No `prefix` on the `MCPClient`. With a single gateway the tool names the gateway publishes (target `WebSearch` + tool `WebSearch`) are already unambiguous; the system prompt refers to "the web search tool" rather than an exact name so it works regardless of the gateway's `<target>___<tool>` naming.
4. Missing gateway URL: `mcp_client/client.py` returns `None` and logs a warning (template behavior). `main.py` then refuses to answer from model memory: `invoke` logs an error and yields one text event with a clear message (e.g. "Web search is not configured: AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL is not set. Deploy with `agentcore deploy` (or run `agentcore dev` after a deploy) so the agent can look up real results.") and returns, without building an Agent. Rationale: answering without the tool would risk invented scores, which the boundary forbids. The yielded event uses the Strands stream shape `{"event": {"contentBlockDelta": {"delta": {"text": msg}}}}` so the same clients that render normal agent output render this message.
5. Region for SigV4: `os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-west-2"))` (Runtime sets `AWS_REGION`; fallback follows the project's us-west-2 rule).
6. Dependency pin: `mcp-proxy-for-aws>=1.7.0,<2.0.0` (bounded range, same style as the existing `mcp >= 1.28.1, < 2.0.0`), added with `uv add` so `uv.lock` and `.venv` stay in sync.
7. Template cleanup: remove the `add_numbers` sample tool and the unused `skills/` package (`skills/fetcher.py` is not imported anywhere). Also remove `model/mantle_compat.py` (unused OpenAI/Mantle shim; not imported). Keep the rest of the entrypoint plumbing (`strip_trailing_tool_use`, `_extract_prompt`, session cache, `NullConversationManager`) so `invoke` behaves exactly as scaffolded. Remove the now-dead `_INLINE_FUNCTION_NAMES`, `_has_inline_function_call`, `_is_inline_function_call` (no inline function tools remain). Keep `model/load.py` unchanged (model ID already matches canvas row 8).

## Steps

- [ ] 1. Add the gateway and the web search connector target with the CLI, then validate.
      Run from `$PROJ`:
      ```bash
      cd /home/workshop/ReturnsRefundsAgentProject/BundesligaScoresProject
      agentcore add gateway --name BundesligaGateway \
        --description "MCP gateway that fronts the built-in web search connector" \
        --protocol-type MCP --authorizer-type AWS_IAM --no-semantic-search --json
      agentcore add gateway-target --name WebSearch --gateway BundesligaGateway \
        --type connector --connector web-search \
        --description "Built-in AgentCore web search connector for recent Bundesliga results" --json
      agentcore validate
      ```
      No hand edits to `agentcore.json` are expected. If a command fails, run `agentcore remove gateway --name BundesligaGateway -y` and retry rather than hand-editing; if hand edits become unavoidable, follow `agentcore/.llm-context/agentcore.ts` and never add `${...}` placeholders.
      Files: `$PROJ/agentcore/agentcore.json`
      Verify: both commands print `{"success":true,...}`; `agentcore validate` prints `Valid`; `agentCoreGateways[0]` has `name: "BundesligaGateway"`, `protocolType: "MCP"`, `authorizerType: "AWS_IAM"`, `enableSemanticSearch: false`, and one target with `targetType: "connector"`, `connectorId: "web-search"`, `name: "WebSearch"`. `runtimes[0]` has no `envVars` added.

- [ ] 2. Add the SigV4 MCP transport dependency.
      Run from `$AGENT`: `uv add "mcp-proxy-for-aws>=1.7.0,<2.0.0"`.
      Files: `$AGENT/pyproject.toml`, `$AGENT/uv.lock` (and the gitignored `.venv`)
      Verify: `cd $AGENT && uv run python -c "from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client; print('ok')"` prints `ok`.

- [ ] 3. Rewrite `mcp_client/client.py` for the gateway (replace the Exa example).
      Implement `get_bundesliga_gateway_mcp_client() -> MCPClient | None` following the CLI template's AWS_IAM branch: constant `GATEWAY_URL_ENV_VAR = "AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL"`; read it with `os.environ.get`; if empty, `logger.warning(...)` and return `None`; otherwise return `MCPClient(lambda: aws_iam_streamablehttp_client(endpoint=url, aws_service="bedrock-agentcore", aws_region=<decision 5>))` with no prefix. Drop the unused `streamablehttp_client` import. Type hints on everything; educational comments explaining: where the env var comes from (CDK wiring at deploy, `agentcore dev` after deploy), why SigV4 (`AWS_IAM` inbound auth, runtime role has `InvokeGateway`), and why the lambda (MCPClient opens the transport lazily). Cite the kb-gateway-target and gateway-inbound-auth doc URLs in a comment.
      Files: `$AGENT/mcp_client/client.py`
      Verify: `cd $AGENT && uv run python -m py_compile mcp_client/client.py` exits 0; `env -u AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL uv run python -c "from mcp_client.client import get_bundesliga_gateway_mcp_client as g; print(g())"` prints `None` (plus the warning) with no traceback; `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL=https://example.invalid/mcp uv run python -c "from mcp_client.client import get_bundesliga_gateway_mcp_client as g; print(type(g()).__name__)"` prints `MCPClient` (no network call happens at construction).

- [ ] 4. Update `main.py`: system prompt, tool wiring, missing-gateway guard, template cleanup.
      Depends on step 3.
      - Import `get_bundesliga_gateway_mcp_client`; build `gateway_client = get_bundesliga_gateway_mcp_client()` once at module load; `tools = [gateway_client] if gateway_client else []`. Remove `add_numbers`, the `@tool`/`tool` import if unused, `_INLINE_FUNCTION_NAMES`, `_has_inline_function_call`, `_is_inline_function_call`, and the old `mcp_clients` loop.
      - Replace `DEFAULT_SYSTEM_PROMPT` with a short `SYSTEM_PROMPT` containing exactly these rules (wording may be tightened, meaning must not change):
        - Role: friendly assistant for a casual Bundesliga fan who wants a quick score.
        - The literal line: `The user's favorite team is SC Freiburg.`
        - If the user names a team (e.g. "How did Dortmund do?"), that team is the focus team for this answer; otherwise the focus team is the favorite team.
        - Always use the web search tool to find the focus team's latest men's Bundesliga (1. Bundesliga) result; do not answer from memory.
        - Output order: (1) focus team's latest result first: opponent, final score, date; (2) a short list of the other results from that same matchday; (3) a "Sources" list with the URLs (and titles) of the search results used.
        - Never invent or guess a score. If search does not return a clear, recent result, say you could not confirm the latest result (still list any sources consulted).
        - Every answer that uses search results must include their source links (required by the Web Search Tool acceptable-use terms; add a code comment citing https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html#gateway-target-connector-web-search-tool-acceptable-use).
        - Stay on Bundesliga results only; keep it brief.
      - In `invoke`, before `get_or_create_agent`, if `gateway_client is None`: `log.error(...)`, `yield {"event": {"contentBlockDelta": {"delta": {"text": GATEWAY_MISSING_MESSAGE}}}}` and `return` (decision 4). Keep the rest of `invoke` and the helpers as scaffolded.
      - Add type hints to any function you touch/keep where missing (`invoke(payload: dict, context: Any) -> AsyncIterator[Any]`, `agent_factory`, etc.) and short educational comments (why the tool list holds an MCPClient, why no memory/NullConversationManager, why we refuse without the gateway).
      Files: `$AGENT/main.py`
      Verify (from `$AGENT`):
      - `uv run python -m py_compile main.py mcp_client/client.py model/load.py` exits 0.
      - `env -u AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL uv run python -c "import main; print('import ok')"` prints `import ok`.
      - Missing-URL behavior, no traceback, exit code 0:
        ```bash
        env -u AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL uv run python -c "
        import asyncio, main
        async def run():
            return [e async for e in main.invoke({'prompt': 'How did Dortmund do?'}, None)]
        events = asyncio.run(run())
        print(events)
        assert len(events) == 1 and 'AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL' in events[0]['event']['contentBlockDelta']['delta']['text']
        "
        ```
      - `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL=https://example.invalid/mcp uv run python -c "import main; print(len(main.tools))"` prints `1`.
      - `uv run python -c "import main; assert \"The user's favorite team is SC Freiburg.\" in main.SYSTEM_PROMPT; print('prompt ok')"` prints `prompt ok`.

- [ ] 5. Remove unused template files.
      Delete `$AGENT/skills/fetcher.py` (and the now-empty `$AGENT/skills/` dir) and `$AGENT/model/mantle_compat.py`. Do not delete anything else.
      Files: `$AGENT/skills/fetcher.py`, `$AGENT/model/mantle_compat.py`
      Verify: rerun all step 4 verify commands; all still pass. `uv run python -c "import main"` with no `ModuleNotFoundError`.

- [ ] 6. Document the setup in the READMEs.
      - `$PROJ/README.md`: keep the generated content, add a section near the top, "Bundesliga Scores Agent: web search via AgentCore Gateway", covering: what the agent does (canvas rows 2-4, 9, short); architecture (Runtime → SigV4 → `BundesligaGateway` (AWS_IAM, MCP, semantic search off) → `WebSearch` connector target, `connectorId: web-search`, us-west-2); the exact two `agentcore add ...` commands from step 1 plus `agentcore validate`; how the agent finds the gateway (`AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL` and `_AUTH_TYPE` injected at deploy, `agentcore dev` picks them up only after a deploy; no URL is hardcoded); IAM that the CDK creates automatically (runtime role `bedrock-agentcore:InvokeGateway` on the gateway ARN; gateway role `bedrock-agentcore:InvokeWebSearch`); the citation requirement and the never-invent-a-score rule; the synthetic profile line; how to deploy and run the success test (`agentcore deploy`, then `agentcore invoke "How did Dortmund do?"`, expected output per canvas row 10); what happens if the gateway URL is missing; out of scope today (memory, UI, auth, domain/date filters, other tools). Link the doc URLs listed above.
      - `$AGENT/README.md`: add `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL` (set by deploy / `agentcore dev` after deploy; required for answers) and `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_AUTH_TYPE` (`AWS_IAM`, informational) to the env var table; mention the `mcp-proxy-for-aws` dependency; remove any mention of skills if present.
      Files: `$PROJ/README.md`, `$AGENT/README.md`
      Verify: commands in the README match the ones actually run in step 1 (copy them from your shell history); every doc URL in the README is one of the URLs in "Docs consulted".

- [ ] 7. Full verification checklist (run all, record results in your step output).
      1. `cd $PROJ && agentcore validate` → `Valid`; `python3 -c "import json;g=json.load(open('agentcore/agentcore.json'))['agentCoreGateways'];print(g)"` shows `BundesligaGateway` with `authorizerType: AWS_IAM` and target `WebSearch` with `targetType: connector`, `connectorId: web-search`. `grep -n '\${' agentcore/agentcore.json` finds nothing.
      2. `cd $AGENT && uv run python -m py_compile main.py mcp_client/client.py model/load.py` exits 0, and the step 4 missing-URL script prints the clear message and exits 0 with no traceback.
      3. `cd $PROJ && agentcore deploy --dry-run --json` → `"success":true` (synth only; it does NOT create resources). Then confirm the synthesized template wires things up:
         ```bash
         python3 - <<'EOF'
         import json, glob
         t = json.load(open(glob.glob("/home/workshop/ReturnsRefundsAgentProject/BundesligaScoresProject/agentcore/cdk/cdk.out/*.template.json")[0]))
         r = t["Resources"]
         rt = [v for v in r.values() if v["Type"] == "AWS::BedrockAgentCore::Runtime"][0]
         print(sorted(rt["Properties"]["EnvironmentVariables"]))
         print([v["Properties"]["TargetConfiguration"] for v in r.values() if v["Type"] == "AWS::BedrockAgentCore::GatewayTarget"])
         print([v["Properties"]["AuthorizerType"] for v in r.values() if v["Type"] == "AWS::BedrockAgentCore::Gateway"])
         EOF
         ```
         Expected: env vars include `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL` and `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_AUTH_TYPE`; target config has `Connector.Source.ConnectorId == "web-search"`; authorizer `AWS_IAM`. Never run `agentcore deploy` without `--dry-run`.
      4. `git -C /home/workshop/ReturnsRefundsAgentProject status --short` shows changes only under `BundesligaScoresProject/` (plus the pre-existing staged `BundesligaScoresProject/agentcore/aws-targets.json`), nothing under `AgentCoreProject1/`; `find $PROJ -name .git` prints nothing; `agentcore/.cli/deployed-state.json` is unchanged (`git diff --quiet -- BundesligaScoresProject/agentcore/.cli/deployed-state.json`).
      5. No commit, no push, no real deploy.

## Gaps / assumptions

- The live success test (canvas row 10) needs a real deploy, which is out of scope for this slice; the README documents how to run it.
- The exact MCP tool name the gateway publishes (likely `WebSearch___WebSearch`) can only be observed after deploy; the code and prompt do not depend on it.
- If the gateway is reachable but fails at connect time (after deploy), Strands raises when the Agent starts the MCP client; handling that beyond the default error event is out of scope for this slice.
