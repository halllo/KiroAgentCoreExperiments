# Agent Canvas: Bundesliga Scores Agent

| # | Row | Decision |
|---|-----|----------|
| 1 | Problem | Checking recent Bundesliga results means going through apps and websites full of ads, news, and clutter, when a casual fan only wants a quick score. |
| 2 | User and trigger | One casual fan with one favorite team (synthetic profile: SC Freiburg). Trigger: after a matchday the fan asks, "How did my team do?" |
| 3 | Goal | Give a casual fan their favorite team's latest Bundesliga result first, followed by a short list of the other results from the same matchday. |
| 4 | Inputs and outputs | **Input:** a natural question ("scores?"). It can name a team ("How did Dortmund do?"), which overrides the profile team. **Output:** the focus team's latest result first (opponent, score, date), then the other matches from that matchday, then the source links. The Web Search Tool terms require these citations. |
| 5 | Tools and data | One tool: the AgentCore Gateway Web Search Tool connector (`connectorId: "web-search"`, exposed to the agent as MCP tool `WebSearch`, available in `us-west-2`). It returns **real** snippets, URLs, titles, and publication dates. **Synthetic data:** only the user profile, written as one line in the system prompt: "The user's favorite team is SC Freiburg." Docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-web-search-tool.html |
| 6 | Knowledge | None beyond what search returns. The system prompt only sets tone and output format. |
| 7 | Memory | None. Each question stands alone. |
| 8 | Model | Project default: `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (from `AgentCoreProject1/app/CustomerAssistantAgent/model/load.py`). |
| 9 | Boundaries | Never invent a score. If search does not return a clear, recent result, the agent says it could not confirm the latest result instead of guessing. |
| 10 | Success test | **Input:** "How did Dortmund do?" **Expected:** the headline is Borussia Dortmund's latest Bundesliga result (opponent, score, date), followed by the other matches from that matchday and at least one source link. The Dortmund score matches bundesliga.com. |
| 11 | Out of scope today | No UI. No real authentication. No memory. No `get_fan_profile` tool. No live push alerts. No other leagues or competitions (2. Bundesliga, DFB-Pokal, Champions League). No league table. No player stats or goalscorers. No match previews or predictions. No domain or date filters on the web-search target. No evaluation suite. No billing or cost tracking. |

## Starter pattern

**Customer support.** The fan asks a question and the agent answers it with one lookup tool, grounded and cited. It is not onboarding (no guided steps), not data analysis (no aggregation or charts), and not workflow automation (no multi-step actions or side effects).

## Project structure

A new, standalone AgentCore project in its own folder, `BundesligaScoresProject/`, next to `AgentCoreProject1/`. It has its own `agentcore.json`, its own Runtime, and its own Gateway. Nothing in `AgentCoreProject1/` is reused or changed. Only the default model ID is copied over.

## First slice

Build **one tool first: the AgentCore Gateway Web Search Tool connector (`WebSearch`)**. Create a Gateway, add the `web-search` connector target, connect the agent to the Gateway as an MCP client, and put the synthetic favorite team in the system prompt. Deploy, then run the success test from row 10.

Next, after the first deploy: `get_fan_profile` (synthetic profile tool).
