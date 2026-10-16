# Verification: websearch gateway first slice (iteration 1)

No review file existed, so this was the first iteration. No deploy, no commit. Nothing under `AgentCoreProject1/` was touched.

## Docs consulted (via MCP)
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html (connectorId, us-west-2 availability, acceptable-use citation rule)
- https://docs.aws.amazon.com/bedrock/latest/userguide/kb-gateway-target.html ("Invoke with Strands Agents": `aws_iam_streamablehttp_client(endpoint, aws_region, aws_service="bedrock-agentcore")`)
- https://strandsagents.com/docs/api/python/strands.tools.mcp.mcp_client/index.md (MCPClient)
- CLI template `/usr/lib/node_modules/@aws/agentcore/dist/assets/python/http/strands/base/mcp_client/client.py` (AWS_IAM gateway branch)

## Commands run (from `BundesligaScoresProject/`) and results
```
agentcore add gateway --name BundesligaGateway --description "MCP gateway that fronts the built-in web search connector" --protocol-type MCP --authorizer-type AWS_IAM --no-semantic-search --json
  -> {"success":true,"gatewayName":"BundesligaGateway"}
agentcore add gateway-target --name WebSearch --gateway BundesligaGateway --type connector --connector web-search --description "Built-in AgentCore web search connector for recent Bundesliga results" --json
  -> {"success":true,"toolName":"WebSearch"}
agentcore validate                       -> Valid (run again at the end: Valid)
grep -c '\${' agentcore/agentcore.json  -> 0
```
`agentCoreGateways[0]`: name BundesligaGateway, protocolType MCP, authorizerType AWS_IAM, enableSemanticSearch false, one target `WebSearch` with targetType connector, connectorId web-search. `runtimes[0]` has no envVars.

## Agent (from `app/BundesligaScoresAgent/`), all exit 0
- `uv add "mcp-proxy-for-aws>=1.7.0,<2.0.0"` -> installed; signature `aws_iam_streamablehttp_client(endpoint, aws_service, aws_region=None, ...)`
- `uv run python -m py_compile main.py mcp_client/client.py model/load.py` -> rc=0
- `env -u AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL uv run python -c "...get_bundesliga_gateway_mcp_client()"` -> warning + `None`, no traceback
- With `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL=https://example.invalid/mcp` -> `MCPClient`; `len(main.tools)` -> `1`
- `env -u ... uv run python -c "import main"` -> `import ok`
- Missing-URL invoke script (plan step 4) -> one event `{'event': {'contentBlockDelta': {'delta': {'text': 'Web search is not configured: AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL is not set. Deploy with `agentcore deploy` (or run `agentcore dev` after a deploy) so the agent can look up real results.'}}}}`, assertion passed, no traceback
- Prompt check -> `prompt ok` (contains "The user's favorite team is SC Freiburg.")
- Removed unused `skills/fetcher.py` (+ empty `skills/`), `model/mantle_compat.py`, `add_numbers`, inline-function helpers. Re-ran all checks after removal: pass.

## Synth only (no resources created)
`agentcore deploy --dry-run --json` -> `{"success":true,"stackName":"AgentCore-BundesligaScoresProject-default",...}`, exit 0.
Synthesized template:
- Runtime env vars: `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_AUTH_TYPE`, `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL`
- GatewayTarget: `{'Mcp': {'Connector': {'Source': {'ConnectorId': 'web-search'}, 'Enabled': ['WebSearch'], ...}}}`
- Gateway AuthorizerType: `AWS_IAM`
- IAM: `bedrock-agentcore:InvokeGateway` on the gateway ARN (GetAtt); `bedrock-agentcore:InvokeWebSearch` on `arn:aws:bedrock-agentcore:us-west-2:aws:tool/web-search.v1`
- `agentcore/.cli/deployed-state.json` byte-identical before/after (`cmp`).

## Git
`git -C /home/workshop/ReturnsRefundsAgentProject status --short`: changes only under `BundesligaScoresProject/` (README.md, agentcore/agentcore.json, app/BundesligaScoresAgent/{README.md, main.py, mcp_client/client.py, pyproject.toml, uv.lock}, deletions of model/mantle_compat.py and skills/fetcher.py, untracked .agents/, plus the pre-existing staged aws-targets.json). Nothing under `AgentCoreProject1/`. `find BundesligaScoresProject -name .git` (excluding node_modules) -> nothing.

## Not verified
The live success test (`agentcore invoke "How did Dortmund do?"`) needs a real deploy, which is out of scope here. The exact published tool name (likely `WebSearch___WebSearch`) is only visible after deploy; code and prompt do not depend on it.
