# Web-search Gateway wiring for the Bundesliga Scores agent

The change adds a CLI-scaffolded AgentCore Gateway (`BundesligaGateway`, MCP, AWS_IAM inbound auth, semantic search off) with one connector target (`WebSearch`, `connectorId: "web-search"`) to `agentcore.json`. The agent connects to it as a SigV4-signed MCP client by rewriting the template `mcp_client/client.py`, and `main.py` gets the canvas system prompt. When the gateway URL is missing, the agent sends back one clear text event instead of answering from model memory. Unused template pieces are removed (`add_numbers`, inline-function helpers, `skills/fetcher.py`, `model/mantle_compat.py`), and both READMEs document the setup. The recorded evidence covers `agentcore validate` (Valid), py_compile, the missing-URL path, a dry-run synth that shows the env-var/IAM/connector wiring, and a clean `git status` (nothing under `AgentCoreProject1/`, no nested `.git`).

Watch for: a misleading "each question stands alone" comment on top of a scaffold that keeps per-session in-process history (confirmed, non-blocking). A gateway connect or IAM failure after deploy still comes out as a raw exception (likely, acknowledged in the plan). The live success test has not been run yet; it needs a real deploy.

**Verdict**: APPROVED

## High-level view

The infrastructure is declarative and CLI-generated. The two `agentcore add` commands in the README match the ones recorded in the verification file. `agentcore.json` has no `${...}` placeholders and no runtime `envVars`. The gateway URL reaches the Runtime through the CDK's `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL` injection, and the synthesized template confirms it, along with least-privilege `InvokeGateway` and `InvokeWebSearch` grants in us-west-2.

The agent side follows the CLI's own Strands AWS_IAM template branch and the cited kb-gateway-target doc: `MCPClient(lambda: aws_iam_streamablehttp_client(endpoint, aws_service="bedrock-agentcore", aws_region=...))`, with region falling back to us-west-2. It stays minimal: a system prompt plus the gateway client as the only tool, with no memory, UI, or Cognito. The system prompt has every canvas requirement: the literal SC Freiburg line, the named-team override, the result → matchday → sources order, the never-invent rule with a "could not confirm" fallback, and the citation rule.

The missing-URL guard fails closed. It is the right call for the never-invent-a-score boundary. Failures after the URL is present (gateway unreachable, IAM denied) are not handled beyond the Strands default.

<details>
<summary>Issues (3)</summary>

1. **Misleading statelessness comment** (confirmed, non-blocking): `_make_conversation_manager` says "each question stands alone", but the scaffold's per-session Agent cache keeps in-process history, and `NullConversationManager` never trims it. Reword the comment to match what the code does. If true per-question statelessness is wanted, create the Agent per invoke instead.
2. **Raw exception on gateway connect failure** (likely, non-blocking): if the URL is set but the gateway rejects the SigV4 call or can't be reached, the error surfaces from Agent/MCPClient startup with no friendly message. This is acknowledged in the plan. Consider a follow-up that catches it in `invoke` and sends back a "could not reach web search" message.
3. **Success test not yet run** (confirmed, expected): canvas row 10 needs `agentcore deploy` + `agentcore invoke "How did Dortmund do?"`. The README documents both steps. Run them before calling the slice done.

</details>

<details>
<summary>Details</summary>

### Session history vs. "no memory"

Canvas row 7 says "Memory: None. Each question stands alone." No AgentCore Memory is attached, so the letter of the requirement holds. The new comment overstates it, though. `get_or_create_agent` caches one Agent per `session_id` (up to 128, LRU), so follow-up questions in the same runtime session do see earlier turns. `NullConversationManager` means that history is never trimmed, so a long session can eventually overflow the context window. The cache predates this change. The comment is new and is what's inaccurate (confirmed).

### Failure modes around the gateway

```
URL unset ──> client.py warns, returns None ──> invoke yields one text event (fail closed)
URL set, gateway OK ──> Strands opens SigV4 transport, lists WebSearch tool
URL set, gateway/IAM error ──> exception from Agent/MCPClient startup (unhandled)
```

The fail-closed path reuses the Strands `contentBlockDelta` event shape, so existing clients render it as text, and the recorded invoke script confirms one event with no traceback. The third path only appears after deploy (likely). One `MCPClient` instance is also shared across every cached Agent. That matches how Strands manages MCP tool providers, but nothing has exercised it yet because no live run has happened.

### Bundled cleanup

`skills/fetcher.py` and `model/mantle_compat.py` are deleted, and no remaining file references either one (grep confirmed). The staged `aws-targets.json` change (account + us-west-2) came before this task and is excluded from this review.

### Test coverage

Covered by recorded evidence: config validation, the dry-run synth wiring (env vars, connector ID, AWS_IAM authorizer, IAM scopes), module import with and without the URL, the tool count with the URL set, the missing-URL invoke path, and a check that the favorite-team line is in the prompt. Not tested: real tool discovery and the published tool name (likely `WebSearch___WebSearch`), an end-to-end answer format, citation output, the "could not confirm" behavior, and the named-team override. All of these need a deploy.

</details>

<details>
<summary>File map</summary>

- `agentcore/agentcore.json`: adds `BundesligaGateway` (MCP, AWS_IAM, semantic search off) with the `WebSearch` web-search connector target.
- `app/BundesligaScoresAgent/mcp_client/client.py`: replaces the Exa example with a SigV4 gateway MCP client read from `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL`.
- `app/BundesligaScoresAgent/main.py`: canvas system prompt, gateway-only tool list, missing-URL guard, type hints, template cleanup.
- `app/BundesligaScoresAgent/pyproject.toml`, `uv.lock`: adds `mcp-proxy-for-aws>=1.7.0,<2.0.0`.
- `app/BundesligaScoresAgent/README.md`: gateway env vars, new dev invoke example.
- `README.md`: new section with architecture, CLI commands, connection, IAM, profile line, citations, deploy + success test, doc links.
- Deleted: `app/BundesligaScoresAgent/skills/fetcher.py`, `app/BundesligaScoresAgent/model/mantle_compat.py`.

Full diff: `git diff HEAD -- BundesligaScoresProject`

</details>
