# Bundesliga Scores Agent

A standalone AgentCore project, separate from `AgentCoreProject1/`, created with the
[AgentCore CLI](https://github.com/aws/agentcore-cli) (`agentcore create --skip-git`, so it lives in the workspace git
repo with no nested `.git`). The product spec is in `../canvas.md`.

## Bundesliga Scores Agent: web search via AgentCore Gateway

### What it does

A casual fan asks "How did my team do?" and gets their team's latest Bundesliga result first (opponent, score,
date), then a short list of the other results from that matchday, then the source links. Naming a team ("How did
Dortmund do?") overrides the profile team. The agent never invents a score: if search returns no clear, recent
result, it says it could not confirm the latest result. No memory, no UI, one tool.

### Architecture

```
AgentCore Runtime (BundesligaScoresAgent, Strands)
  └─ MCP over HTTPS, SigV4-signed (runtime execution role)
     └─ AgentCore Gateway "BundesligaGateway" (MCP, inbound auth AWS_IAM, semantic search off)
        └─ Target "WebSearch" (type connector, connectorId "web-search", us-west-2)
           └─ MCP tool WebSearch
```

### How the gateway and target were added

Run from this folder (no hand edits to `agentcore/agentcore.json`):

```bash
agentcore add gateway --name BundesligaGateway \
  --description "MCP gateway that fronts the built-in web search connector" \
  --protocol-type MCP --authorizer-type AWS_IAM --no-semantic-search --json
agentcore add gateway-target --name WebSearch --gateway BundesligaGateway \
  --type connector --connector web-search \
  --description "Built-in AgentCore web search connector for recent Bundesliga results" --json
agentcore validate
```

Semantic search is off because the gateway has a single tool. No connector version is pinned, so the default
`web-search` version applies, and no domain or date filters are set.

### How the agent connects

- On deploy, the CDK constructs set `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_URL` (and
  `AGENTCORE_GATEWAY_BUNDESLIGAGATEWAY_AUTH_TYPE=AWS_IAM`) on the Runtime. No URL is hardcoded.
  `agentcore dev` sets the same variables locally, but only after a first deploy.
- `app/BundesligaScoresAgent/mcp_client/client.py` reads that URL and builds a Strands `MCPClient` with
  `aws_iam_streamablehttp_client` from `mcp-proxy-for-aws`, which SigV4-signs requests for the `bedrock-agentcore`
  service.
- The CDK grants IAM automatically: the runtime role gets `bedrock-agentcore:InvokeGateway` on the gateway ARN, and
  the gateway service role gets `bedrock-agentcore:InvokeWebSearch`.
- If the URL is missing, the agent replies with a clear "Web search is not configured" message instead of answering
  from model memory.

### Profile team and citations

The only synthetic data is one line in `SYSTEM_PROMPT` in `app/BundesligaScoresAgent/main.py`:
`The user's favorite team is SC Freiburg.` Edit that line to change the profile team.

Every answer lists its source links. The Web Search Tool acceptable-use terms require showing the citations and
links of any search result used.

### Deploy and run the success test

```bash
agentcore deploy
agentcore invoke "How did Dortmund do?"
```

Expected: Borussia Dortmund's latest Bundesliga result first (opponent, score, date), then the other matches from
that matchday, then at least one source link. The Dortmund score should match bundesliga.com.

Deployment target: account `278581056849`, `us-west-2` (`agentcore/aws-targets.json`, same as `AgentCoreProject1`).
The deploy creates its own stack, `AgentCore-BundesligaScoresProject-default`.

### Check the deployment

```bash
agentcore status
aws cloudformation describe-stacks --stack-name AgentCore-BundesligaScoresProject-default \
  --query "Stacks[0].StackStatus" --output text --no-cli-pager --region us-west-2
```

A healthy deploy shows the stack as `CREATE_COMPLETE` (or `UPDATE_COMPLETE`), the runtime `BundesligaScoresAgent` as
`READY`, and `BundesligaGateway` with 1 web-search target. To check the gateway and target directly, take the gateway
ID from `agentcore status`:

```bash
aws bedrock-agentcore-control get-gateway --gateway-identifier <gateway-id> \
  --query "{status:status,auth:authorizerType}" --no-cli-pager --region us-west-2
aws bedrock-agentcore-control list-gateway-targets --gateway-identifier <gateway-id> \
  --query "items[].{name:name,status:status}" --no-cli-pager --region us-west-2
```

Expected: the gateway is `READY` with `AWS_IAM`, and the target `WebSearch` is `READY`. These checks cover the
infrastructure only. The success test above is what proves the agent can call web search end to end.

### Known limitations

- If the gateway URL is set but the call fails (IAM denied, gateway unreachable), the error comes back as a raw
  exception instead of a friendly message.
- No AgentCore Memory is attached, so nothing carries over between sessions. Within one runtime session the agent
  keeps the conversation history in process.
- Out of scope today (see `../canvas.md`, row 11): UI, real auth, memory, a `get_fan_profile` tool, other
  competitions, league tables, stats, predictions, domain/date filters, evals, cost tracking.

### Docs

- [Web Search Tool](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html)
- [Gateway target configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-api-target-config.html)
- [Connector versions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-versions.html)
- [Gateway inbound auth](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html)
- [Strands MCP client with SigV4 to a gateway](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-gateway-target.html)

## Project Structure

```
BundesligaScoresProject/
├── AGENTS.md               # AI coding assistant context
├── .agents/tasks/          # Plan, verification, and review notes from the build
├── agentcore/
│   ├── agentcore.json      # Runtime + BundesligaGateway with the WebSearch connector target
│   ├── aws-targets.json    # Deployment target (account + us-west-2)
│   ├── .env.local          # Secrets (gitignored; unused today)
│   ├── .llm-context/       # TypeScript type definitions for AI assistants
│   │   ├── agentcore.ts    # AgentCoreProjectSpec types
│   │   └── aws-targets.ts  # Deployment target types
│   └── cdk/                # CDK infrastructure (@aws/agentcore-cdk)
└── app/BundesligaScoresAgent/
    ├── main.py             # Entrypoint, system prompt (incl. synthetic favorite team)
    ├── mcp_client/client.py  # SigV4 MCP client for the gateway
    └── model/load.py       # Bedrock model (global.anthropic.claude-sonnet-4-5-20250929-v1:0)
```

## Getting Started

### Prerequisites

- **Node.js** 20.x or later (the AWS SDK warns that releases after early January 2027 need Node 22+)
- **Python 3.10+** and **uv** for Python agents ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **AWS credentials** configured (`aws configure` or environment variables)
- **Docker** (only for Container build agents)

### Development

Run your agent locally:

```bash
agentcore dev
```

### Validate Invocation Input

Validate runtime invocation payloads before forwarding them to an agent framework. Keep user prompts typed as strings
and pass only prompt text to the agent.

### Deployment

Deploy to AWS:

```bash
agentcore deploy
```

## Commands

| Command | Description |
| --- | --- |
| `agentcore create` | Create a new AgentCore project |
| `agentcore add` | Add resources (agent, memory, credential, gateway, evaluator, policy) |
| `agentcore remove` | Remove resources |
| `agentcore dev` | Run agent locally with hot-reload |
| `agentcore deploy` | Deploy to AWS via CDK |
| `agentcore status` | Show deployment status |
| `agentcore invoke` | Invoke agent (local or deployed) |
| `agentcore logs` | View agent logs |
| `agentcore traces` | View agent traces |
| `agentcore eval` | Run evaluations |
| `agentcore package` | Package agent artifacts |
| `agentcore validate` | Validate configuration |
| `agentcore pause` | Pause a deployed agent |
| `agentcore resume` | Resume a paused agent |
| `agentcore fetch` | Fetch remote resource definitions |
| `agentcore import` | Import existing resources |
| `agentcore update` | Check for CLI updates |

## Configuration

Edit the JSON files in `agentcore/` to configure your project. See `agentcore/.llm-context/` for type definitions and validation constraints.

The project uses a **flat resource model** — agents, memories, credentials, gateways, evaluators, and policies are top-level arrays in `agentcore.json`. Resources are independent; agents discover memories and credentials at runtime via environment variables or SDK calls.

## Resources

| Resource | Purpose |
| --- | --- |
| Agent (runtime) | HTTP, MCP, or A2A agent deployed to AgentCore Runtime |
| Memory | Persistent context storage with configurable strategies |
| Credential | API key or OAuth credential providers |
| Gateway | MCP gateway that routes tool calls to targets |
| Gateway Target | Tool implementation (Lambda, MCP server, OpenAPI, Smithy, API Gateway) |
| Evaluator | Custom LLM-as-a-Judge or code-based evaluation |
| Online Eval Config | Continuous evaluation pipeline for deployed agents |
| Policy | Cedar authorization policies for gateway tools |

### Agent Types

- **Template agents**: Created from framework templates (Strands, LangChain/LangGraph, GoogleADK, OpenAI Agents, Autogen)
- **BYO agents**: Bring your own code with `agentcore add agent --type byo`
- **Import agents**: Import existing Bedrock agents with `agentcore import`

### Build Types

- **CodeZip**: Python source packaged as a zip and deployed directly to AgentCore Runtime
- **Container**: Docker image built via CodeBuild (ARM64), pushed to ECR, and deployed to AgentCore Runtime

## Documentation

- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
