# Documentation-First Rule (MCP)

**Always consult the most up-to-date official documentation via the MCP tools before writing or changing code. Do not rely on prior/internal knowledge for AWS, AgentCore, or Strands APIs — these move fast and training knowledge is often stale.**

## When this applies

Before writing or modifying any Python code, config, or CLI usage that touches:

- **AgentCore** (Runtime, Memory, Gateway, Targets, Harness, Identity, `agentcore.json`, `.env.local`)
- **Strands Agents SDK** (`Agent`, `@tool`, `strands_tools`, session managers, MCP client)
- **AWS APIs / boto3** (Bedrock, DynamoDB, Lambda, Cognito, SSM, IAM)

...first search and read the relevant docs.

## Which MCP tool to use

- **AWS services and APIs** → use the AWS Documentation MCP server
  - `search_documentation` to find the right page
  - `read_documentation` to read it
- **Strands Agents SDK** → use the Strands MCP server
  - `search_docs` to find the right page
  - `fetch_doc` to read it

## Workflow

1. **Search first.** Use `search_documentation` / `search_docs` with specific technical terms (e.g. "AgentCore Gateway Lambda target", "Strands AgentCore memory session manager").
2. **Read the source.** Fetch the actual page with `read_documentation` / `fetch_doc` and base the implementation on it.
3. **Cite it.** Reference the documentation URL you relied on in your explanation (and in a code comment when it clarifies a non-obvious pattern).
4. **Then write code.** Only after confirming the current API from docs.

## Non-negotiable

If you are about to write AgentCore or Strands Python code and have **not** looked up the current docs in this session for that API, **stop and search the docs first**. Guessing API shapes from memory is not acceptable in this project.
