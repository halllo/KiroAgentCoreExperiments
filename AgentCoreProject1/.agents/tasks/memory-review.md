# AgentCore Memory session manager for CustomerAssistantAgent

The change connects the `CustomerAssistantMemory` resource (USER_PREFERENCE strategy) to the Strands agent. Each cached `Agent` now gets an `AgentCoreMemorySessionManager` bound to one `(actor_id, session_id)` pair. Short-term events are written per session, and long-term preferences are retrieved from `/users/{actor_id}/preferences/` with `top_k=5` and `relevance_score=0.3`. The memory ID (`AgentCoreProject1_CustomerAssistantMemory-mGsfj0Gqjg`, an ID, not an ARN) is written as a literal into the runtime `envVars` and into `.env.local` under `MEMORY_CUSTOMERASSISTANTMEMORY_ID`, and `main.py` reads it from that variable. The coder's evidence covers `agentcore validate` (Valid), `py_compile` (OK), the SDK imports, and an end-to-end local invoke that stored 5 events in the deployed memory.

Watch for: caller-supplied `actor_id`/`session_id` are used without validation, so any caller can read another actor's memories (likely). Callers that send a full `messages` history will get duplicated context now that the session manager also restores history (likely). Neither is blocking for this workshop step.

**Verdict**: APPROVED

## High-level view

The integration follows the documented Strands pattern: build an `AgentCoreMemoryConfig` with `memory_id`, `session_id`, `actor_id`, and a `retrieval_config` map, then pass `AgentCoreMemorySessionManager(agentcore_memory_config=..., region_name="us-west-2")` to `Agent(session_manager=...)`. The system prompt, tools, MCP client, and conversation manager are unchanged. The agent cache key changed from `session_id` to `(actor_id, session_id)`, because a session manager is bound to a single actor.

Config wiring matches the user's instructions. The env var name follows the CLI's `MEMORY_<NAME>_ID` convention, `agentcore.json` has no `${` placeholders, and `envVars` uses the `{name, value}` array shape. The namespace copies the agentcore.json template `/users/{actorId}/preferences` (plural, as declared) and adds a trailing slash, filled with the real `actor_id`. It avoids the triple-brace mistake. If no memory ID is set, the agent logs a warning and runs without memory (fail-open). That suits local runs without `.env.local`, but a missing env var in the deployed runtime would only show up as a log line.

The new trust boundary is the payload. `actor_id` and `session_id` now come from the caller with no type or format checks. `actor_id` also directly selects which long-term memory namespace is read.

<details>
<summary>Issues (4)</summary>

1. **Caller-controlled actor_id selects memory namespace** — any invoker can pass another `actor_id` and get that actor's preferences back (likely). Before this assistant serves more than administrators, derive the actor from authenticated identity (e.g. Cognito claims in the later UI step) or restrict it.
2. **Unvalidated actor_id/session_id payload fields** — non-string or badly formatted values reach `AgentCoreMemoryConfig` and the memory APIs, where they fail with an opaque error mid-request (likely). Require them to be strings matching the memory ID pattern, as AGENTS.md invariant 5 asks for payloads.
3. **History duplication on the `messages` payload path** — the session manager restores stored history into the agent, and a caller-supplied full `messages` list is then appended on top of it (likely). Document that memory-backed sessions expect a `prompt`, or skip restoring when `messages` is supplied.
4. **Silent fail-open when memory ID is missing in the deployed runtime** — a missing env var only produces a warning, and the agent then quietly loses memory (confirmed). Consider failing fast when running inside the runtime, or at least logging once at import time instead of once per new agent.

</details>

<details>
<summary>Details</summary>

### Actor and session identity from the payload

```python
actor_id = payload.get("actor_id") or DEFAULT_ACTOR_ID
session_id = payload.get("session_id") or getattr(context, "session_id", None) or "default-session"
```

The payload override for `actor_id` is the only thing that picks the retrieval namespace `/users/{actor_id}/preferences/`, so it acts as an authorization decision made by the caller (likely). The deployed runtime sits behind IAM SigV4 by default, which limits who can call it. Once the Streamlit + Cognito step arrives, though, the actor should come from the verified identity and not from a free-form payload field.

Neither field is type-checked. `_extract_prompt` only confirms that `payload` is a dict. A numeric or object `actor_id` gets formatted into the namespace string and passed to the pydantic config, and values with `/` or spaces would build odd namespaces or be rejected by the Memory API partway through the request (likely). Preferring `payload["session_id"]` over the runtime session header also lets a caller write events into any session ID it chooses. This is consistent with the brief ("payload/runtime context"), but it widens the same trust gap. The `"default-session"` fallback predates this change. Inside the runtime the context header is always present, so the fallback only applies to local runs.

### Session manager and the `messages` input path

`AgentCoreMemorySessionManager` restores the session's stored conversation into `agent.messages` when the agent is created, and it appends every new message as an event. `_extract_prompt` still accepts a full `messages` history, which is passed straight to `stream_async`. For a memory-backed agent, that path now stacks the caller's history on top of the restored history (likely; not traced through the SDK). The workshop invokes with `prompt`, so this doesn't affect the current flow. It does affect harness-style callers.

### Fail-open without a memory ID

`_make_session_manager` returns `None` when `MEMORY_CUSTOMERASSISTANTMEMORY_ID` is unset (confirmed). The agent then runs statelessly and logs one warning for each new `(actor, session)`. Locally this is a deliberate convenience. In the deployed runtime, a missing env var would show up only as a log line while users quietly lose memory.

### Verification evidence and bundled changes

`agentcore dev` and `agentcore deploy` were not run, so the deployed runtime's IAM access to the memory has not been exercised. Not tested: the `actor_id`/`session_id` payload overrides, the `messages` input path with memory attached, and the no-memory-ID fallback.

The verification note `.agents/tasks/memory-verification.md` was committed with the code, and the work was committed straight to local `main` (one commit ahead of `origin/main`). Neither change was requested. Both are easy to move to a branch or drop before pushing.

</details>

<details>
<summary>File map</summary>

- `app/CustomerAssistantAgent/main.py`: memory imports, `MEMORY_ID`/region/default-actor constants, `_make_session_manager`, cache keyed by `(actor_id, session_id)`, actor/session resolution in `invoke`.
- `agentcore/agentcore.json`: runtime `envVars` with the literal `MEMORY_CUSTOMERASSISTANTMEMORY_ID`.
- `agentcore/.env.local` (gitignored, not in diff): same variable, same literal ID.
- `.agents/tasks/memory-verification.md`: coder's verification note.

Full diff: `git diff origin/main` from the repo root.

</details>
