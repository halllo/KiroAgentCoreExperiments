# Memory integration – verification

Memory ID: `AgentCoreProject1_CustomerAssistantMemory-mGsfj0Gqjg` (memory `CustomerAssistantMemory`, USER_PREFERENCE)
Env var: `MEMORY_CUSTOMERASSISTANTMEMORY_ID` (the CLI/CDK `MEMORY_<NAME>_ID` convention, see `AgentCoreMemory.getEnvVarName()` in `@aws/agentcore-cdk`)

## Memory ID lookup
- `agentcore status` → `CustomerAssistantMemory: Deployed (USER_PREFERENCE) (arn:...:memory/AgentCoreProject1_CustomerAssistantMemory-mGsfj0Gqjg)`
- `aws bedrock-agentcore-control list-memories --region us-west-2 --no-cli-pager` → one memory, id above, `ACTIVE`
- `aws bedrock-agentcore-control get-memory --memory-id <id> --region us-west-2 --no-cli-pager` → namespace `/users/{actorId}/preferences` (matches agentcore.json)

## Checks
- `agentcore validate` → `Valid`
- `.venv/bin/python -m py_compile main.py` → OK
- Import of `AgentCoreMemoryConfig`, `RetrievalConfig`, `AgentCoreMemorySessionManager` from the app venv (bedrock-agentcore 1.24.1, strands-agents 1.61.1) → OK
- `_make_session_manager("administrator", "verify-session-0001")` → `AgentCoreMemorySessionManager`, retrieval_config keys `['/users/administrator/preferences/']`, `top_k=5 relevance_score=0.3`
- End-to-end local call of `invoke({"prompt": ...}, context(session_id="verify-session-0001"))` → 24 events streamed, agent replied; then
  `aws bedrock-agentcore list-events --memory-id <id> --actor-id administrator --session-id verify-session-0001 --region us-west-2 --no-cli-pager` → 5 events stored
- `grep -c '${' agentcore/agentcore.json` → 0; envVars holds the literal ID; `agentcore/.env.local` holds the same ID
- No `{{` in main.py; namespace is `f"/users/{actor_id}/preferences/"` (trailing slash is AgentCore's normalized namespace form: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html)

## Not run
- `agentcore dev` (blocking) and `agentcore deploy` (user decides).
