# Workshop User Inputs

This file collects every copy-paste input used across the workshop, grouped by lab and clearly separated by **type**:

- 🤖 **Kiro Vibe Prompt** — paste into the Kiro chat panel
- 💻 **Terminal Command** — run in the integrated terminal (bash on EC2/macOS/Linux)
- 💬 **Agent Test Prompt** — send to the running agent (via `agentcore dev`, `agentcore invoke`, or the Streamlit chat UI)

> Replace any `<placeholder>` values with the actual values from your environment before running.

---

## Lab 1 — Kiro & Its Features

### Lab 1 · Workshop Setup (Local install only)

💻 **Terminal Command** — Set AWS credentials from the workshop event page

```bash
export AWS_ACCESS_KEY_ID=<your-access-key>
export AWS_SECRET_ACCESS_KEY=<your-secret-key>
export AWS_SESSION_TOKEN=<your-session-token>
export AWS_DEFAULT_REGION=us-west-2
```

💻 **Terminal Command** — Verify credentials

```bash
aws sts get-caller-identity
```

💻 **Terminal Command** — Create the workshop project and open it in Kiro

```bash
mkdir -p ~/ReturnsRefundsAgentProject
cd ~/ReturnsRefundsAgentProject
kiro .
```

💻 **Terminal Command** — Create the MCP settings directory

```bash
mkdir -p .kiro/settings
```

📄 **Config File** — `.kiro/settings/mcp.json` (create this file with the content below)

```json
{
  "mcpServers": {
    "awslabs.aws-documentation-mcp-server": {
      "command": "uvx",
      "args": [
        "awslabs.aws-documentation-mcp-server@latest"
      ],
      "env": {
        "AWS_DOCUMENTATION_PARTITION": "aws",
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false,
      "autoApprove": [
        "search_documentation",
        "read_documentation"
      ]
    },
    "strands-agents": {
      "command": "uvx",
      "args": [
        "strands-agents-mcp-server"
      ],
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR"
      },
      "disabled": false,
      "autoApprove": [
        "search_docs",
        "fetch_doc"
      ]
    }
  }
}
```

### Lab 1 · Kiro Features and Capabilities

🤖 **Kiro Vibe Prompt** — Account identity check

```text
show me account details using aws caller identity
```

🤖 **Kiro Vibe Prompt** — MCP tool test

```text
What is time out limit for AWS Lambda. Explain a static website architecture hosted on s3 that uses AWS Lambda. Use MCP tool.
```

🤖 **Kiro Vibe Prompt** — Verify Strands MCP

```text
What is Strands Agents? use the available MCP tool
```

### Lab 1 · Hands-on: Set Up Steering

🤖 **Kiro Vibe Prompt** — Generate steering documents

```text
Generate steering documents for my project using Vibe mode. I am building Returns & Refunds assistant using Strands Agents SDK and the AgentCore CLI. The steering should ensure that:
- All code follows AWS best practices and official documentation
- Always look up the most up-to-date AWS and Strands documentation using MCP tools — do not rely on your own knowledge
- Python code uses type hints and educational inline comments
- Agent code uses the Strands @tool decorator pattern
- Search documents before writing python code regarding AgentCore or Strands Agents.
- All AWS operations target the us-west-2 region
- Code is minimal and focused on demonstrating core concepts
- When executing AWS CLI commands from a terminal, always include the --no-cli-pager option
```

---

## Lab 2 — Build & Deploy AI Agents with AgentCore CLI

### Part 1 · Your First Agent in 3 Commands

💻 **Terminal Command** — Scaffold the project (interactive wizard)

```bash
agentcore create
```

Wizard selections:
- Project name: `AgentCoreProject`
- What would you like to build: **Agent**
- Agent name: `CustomerAssistantAgent`
- Agent type: **Create new agent**
- Language: **Python**
- Build: **Direct Code Deploy**
- Protocol: **HTTP**
- Framework: **Strands Agents SDK**
- Model: **Amazon Bedrock**
- Memory: **None**
- Advanced options: **Select nothing**

💻 **Terminal Command** — Start the local dev server

```bash
cd AgentCoreProject
agentcore dev
```

💬 **Agent Test Prompt** — Basic LLM check

```text
What is the capital of France?
```

💻 **Terminal Command** — Deploy to AgentCore Runtime

```bash
# Make sure you are in AgentCoreProject folder
agentcore deploy
```

💻 **Terminal Command** — Invoke the deployed agent

```bash
agentcore invoke
```

💬 **Agent Test Prompt** — Deployed agent smoke test

```text
Hi there! Tell me something interesting.
```

🤖 **Kiro Vibe Prompt** — Update steering with AgentCore-specific rules

```text
Update the steering documents to add the following rules:
- ALWAYS run `agentcore validate` after editing agentcore.json
- In agentcore.json, runtime envVars are arrays like:
  "envVars": [{ "name": "KEY", "value": "VALUE" }]
```

### Part 2 · Build the Returns & Refunds Agent

🤖 **Kiro Vibe Prompt** — Add the domain system prompt

```text
Update AgentCoreProject/app/CustomerAssistantAgent/main.py
to add a system prompt for a returns and refunds assistant:
- The agent should introduce itself as a Returns & Refunds Assistant
- The user is an administrator who can access customer data, orders, and return policies
- It helps administrators check return eligibility, calculate refund amounts, and answer questions about return policies on behalf of customers
- The system prompt should instruct the agent to be helpful, concise, and always confirm details before processing any return or refund
- Keep the existing agent setup and just add the system_prompt parameter to the Agent constructor
```

🤖 **Kiro Vibe Prompt** — Add five tools (one built-in, four mock)

```text
Update AgentCoreProject/app/CustomerAssistantAgent/main.py to add the following tools:

1. get_current_time()
   - Use the Strands built-in current_time tool from strands_tools
   - Returns the current date and time

2. order_lookup(order_id: str)
   - A dummy @tool that looks up order details by order ID
   - Use mock data with sample orders:
     - "ORD-001": customer C-01, product P-001 (iPhone 15 Pro), status DELIVERED, purchased 5 days ago
     - "ORD-002": customer C-02, product P-003 (Kindle Paperwhite), status DELIVERED, purchased 45 days ago
     - "ORD-003": customer C-01, product P-005 (PlayStation 5), status SHIPPED
   - Return order details as a formatted string

3. user_lookup(user_id: str)
   - A dummy @tool that retrieves customer information by user ID
   - Use mock data:
     - "C-01": Rajesh Kumar, country IN, email rajesh@example.com
     - "C-02": Sarah Johnson, country US, email sarah@example.com
     - "C-03": James Wilson, country UK, email james@example.com
   - Return customer details as a formatted string

4. product_lookup(product_id: str)
   - A dummy @tool that retrieves product information by product ID
   - Use mock data:
     - "P-001": iPhone 15 Pro, Apple, phone
     - "P-002": Kindle Paperwhite, Amazon, e-book
     - "P-003": iPad Air, Apple, tablet
   - Return product details as a formatted string

5. policy_retrieval(query: str)
   - A dummy @tool that retrieves return policy information
   - Use mock data with policies for categories: "electronics" (30-day return, 100% refund if unopened), "clothing" (60-day return, full refund), "books" (14-day return, 50% refund)
   - Return the policy details as a string

Make sure to update dependencies in pyproject.toml.
```

🤖 **Kiro Vibe Prompt** — Create a dependency sync hook

```text
Create an agent hook that watches for changes to pyproject.toml.
When the file is edited, it should automatically run "uv sync" to install any new or updated dependencies.
Invoke the hook for initial sync up.
```

💻 **Terminal Command** — Run locally

```bash
agentcore dev
```

💬 **Agent Test Prompt** — Order lookup

```text
Look up order ORD-001
```

💬 **Agent Test Prompt** — Policy retrieval

```text
What's the return policy for electronics?
```

💬 **Agent Test Prompt** — Customer lookup

```text
Get info for customer C-02
```

💻 **Terminal Command** — Redeploy

```bash
agentcore deploy
```

💻 **Terminal Command** — Invoke the deployed agent

```bash
agentcore invoke
```

💬 **Agent Test Prompt** — Status check on deployed agent

```text
Look up order ORD-003 and tell me its status
```

💬 **Agent Test Prompt** — Combined tools

```text
Look up customer C-01 and check the return policy for their electronics order.
```

### Part 3 · Add Persistent Memory

💻 **Terminal Command** — Add a memory resource (interactive)

```bash
agentcore add
```

Wizard selections:
- Resource: **Memory**
- Memory name: `CustomerAssistantMemory`
- Expiry: **7 days**
- Memory record streaming: **No**
- Strategies: **User preference** (only)
- **Confirm**

💻 **Terminal Command** — Deploy the memory resource

```bash
agentcore deploy
```

🤖 **Kiro Vibe Prompt** — Integrate memory into the agent

```text
I have added a new memory using AgentCore CLI.
Update app/CustomerAssistantAgent/main.py to integrate it.
Refer to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/strands-sdk-memory.html
Find the new memory ID (not ARN) using CLI and update agentcore/.env.local.
Add memory ID to envVars of the runtime in agentcore/agentcore.json.
Specify the region as us-west-2.
Default the actor_id to "administrator".
Read agentcore.json to find the memory namespaces and use them for the retrieval config. Use low relevance_score as 0.3 for testing.
Do not make a common mistake: f"/users/{{{actor_id}}}/preference". Correct one is f"/users/{actor_id}/preference/"
Refer to https://strandsagents.com/docs/community/session-managers/agentcore-memory/ for the correct Strands memory integration pattern.
```

💻 **Terminal Command** — Run locally to seed memory

```bash
agentcore dev
```

💬 **Agent Test Prompt** — Seed customer preference

```text
Customer C-01, Rajesh Kumar, prefers email communication and his favorite product category is electronics.
```

💻 **Terminal Command** — Start a new local session to test recall

```bash
agentcore dev
```

💬 **Agent Test Prompt** — Recall preferences

```text
What are the communication preferences for customer C-01?
```

💻 **Terminal Command** — Redeploy with memory

```bash
agentcore deploy
```

🤖 **Kiro Vibe Prompt** — Patch the runtime role for memory namespacePath

```text
Find the AgentCore Runtime execution role created during `agentcore deploy`. You can locate it by running `agentcore status` and reading the role ARN from the output, or by reading the executionRole field from agentcore/agentcore.json.

Attach an inline IAM policy named "MemoryNamespacePathFix" to that role that allows the deployed agent to call memory operations on our memory resource using the corrected condition key:

- Use `bedrock-agentcore:namespacePath` with the `StringLike` operator
- The pattern should match `/users/*/preferences`
- Cover these actions: RetrieveMemoryRecords, CreateEvent, GetEvent, ListEvents, BatchCreateMemoryRecords, BatchUpdateMemoryRecords, BatchDeleteMemoryRecords
- Scope the Resource to our memory ARN (read it from agentcore/agentcore.json or agentcore/.env.local; the format is arn:aws:bedrock-agentcore:<region>:<account>:memory/<memory_id>)

Use AWS CLI in the workshop region. Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html
```

💻 **Terminal Command** — Invoke the deployed agent

```bash
agentcore invoke
```

💬 **Agent Test Prompt** — Seed on deployed agent

```text
Customer C-02, Sarah Johnson, prefers phone calls and mostly buys books.
```

💻 **Terminal Command** — Open a new deployed session

```bash
agentcore invoke
```

💬 **Agent Test Prompt** — Cross-session recall on deployed agent

```text
What do you know about customer C-02?
```

### Part 4 · Connect to Real Data — DynamoDB & Knowledge Base

🤖 **Kiro Vibe Prompt** — Explore DynamoDB seed data

```text
Query the DynamoDB `workshop-orders` table to find all orders for customer C-01 using CLI.
Use the AWS region us-west-2.
```

🤖 **Kiro Vibe Prompt** — Explore the Knowledge Base

```text
Query the Bedrock Knowledge Base to retrieve the return policy for electronics in the US.
Use AWS CLI for each step.
The Knowledge Base ID is stored in SSM parameter `/app/workshop/kb/knowledge-base-id`.
Use the AWS region us-west-2.
Show me the relevant policy excerpts.
```

🤖 **Kiro Vibe Prompt** — Create the two Lambda functions

```text
First, describe the DynamoDB tables (workshop-customers, workshop-orders, workshop-products) to understand their key structure and attributes.

Then create two Lambda functions in a `/lambda_functions/` directory inside my root project:

1. `/lambda_functions/data_lookup/handler.py` -- A Lambda function that handles order, customer, and product lookups from DynamoDB.
   It should support three tools: `order_lookup`, `user_lookup`, and `product_lookup`.
   Use the `bedrockAgentCoreToolName` from the Lambda context to determine which tool was called.
   Use boto3 in region us-west-2.

2. `/lambda_functions/policy_retrieval/handler.py` -- A Lambda function that retrieves return policies from the Bedrock Knowledge Base.
   Read the Knowledge Base ID from SSM parameter `/app/workshop/kb/knowledge-base-id`.
   Use the Bedrock Agent Runtime `retrieve` API.
   Use region us-west-2.

For each Lambda, create a `requirements.txt` with dependencies.

Follow the Lambda function input/output format for AgentCore Gateway targets as described in:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html
```

🤖 **Kiro Vibe Prompt** — Deploy Lambda functions

```text
Deploy both Lambda functions to AWS in region us-west-2.
Zip each function's code, create the Lambda functions using boto3, Use the pre-created Lambda execution role ARN from SSM parameter `/app/workshop/lambda/execution-role-arn`.
Print the Lambda ARNs after deployment.
```

🤖 **Kiro Vibe Prompt** — Test the Lambda functions directly

```text
Test the two Lambda functions we just deployed:
1. Invoke the data lookup Lambda with customer_id "C-01" to test order lookup and show the response
2. Invoke the policy retrieval Lambda with query "What is the return policy for electronics in the US?" and show the response
Use AWS CLI in region us-west-2.
```

🤖 **Kiro Vibe Prompt** — Create tool specifications

```text
Create tool specification JSON files for the AgentCore Gateway in `AgentCoreProject/tool_specs/` directory.
File names: data_lookup.json and policy_retrieval.json
Use the Lambda functions we created as the targets.
Make sure you are using the AgentCore Gateway Lambda tool spec format.
Look up the latest AWS documentation for the correct format.
Make each JSON as an array.
Do NOT include outputSchema — only name, description, and inputSchema are needed.
```

🤖 **Kiro Vibe Prompt** — Create Cognito User Pool for gateway auth

```text
Create a Cognito User Pool for the workshop gateway authentication:
- User Pool name: workshop-gateway-auth
- Create a domain prefix for OAuth endpoints
- Create a resource server with a custom scope for gateway invocation
- Create an app client configured for machine-to-machine (client_credentials) flow
- Save all credentials (user_pool_id, domain, client_id, client_secret, token_endpoint, discovery_url) to a config file - cognito_config.json
- Use the IDP-based discovery URL format: https://cognito-idp.us-west-2.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
- Region: us-west-2
```

💻 **Terminal Command** — Add the Gateway (interactive)

```bash
agentcore add
```

Wizard selections (Gateway):
- Resource: **Gateway**
- Gateway name: `workshop-gateway`
- Authorizer type: **Custom JWT**
- Discovery URL: paste `discovery_url` from `cognito_config.json`
- Client ID: paste `client_id` from `cognito_config.json`
- Configure Custom JWT Authorizer (OAuth creds): press **Enter to skip**
- Advanced config: **Semantic Search** only
- **Confirm**

🤖 **Kiro Vibe Prompt** — Show Lambda ARNs for the targets step

```text
Show me the lambda ARNs.
```

💻 **Terminal Command** — Add the first Gateway Target (interactive)

```bash
agentcore add
```

Wizard selections (data-lookup target):
- Resource: **Gateway Target**
- Name: `data-lookup`
- Target type: **Lambda function**
- Lambda ARN: paste the Data Lookup Lambda ARN
- Tool schema file path: `./tool_specs/data_lookup.json`
- Gateway: select the gateway created above
- **Confirm**

💻 **Terminal Command** — Add the second Gateway Target (interactive)

```bash
agentcore add
```

Wizard selections (policy-retrieval target):
- Resource: **Gateway Target**
- Name: `policy-retrieval`
- Target type: **Lambda function**
- Lambda ARN: paste the Policy Retrieval Lambda ARN
- Tool schema file path: `./tool_specs/policy_retrieval.json`
- Gateway: select the gateway created above
- **Confirm**

💻 **Terminal Command** — Deploy the updated project

```bash
agentcore deploy
```

🤖 **Kiro Vibe Prompt** — Test the Gateway MCP endpoint

```text
Test the AgentCore Gateway MCP endpoint.
Get the gateway URL from the agentcore configuration.
Use the Cognito credentials from cognito_config.json to obtain a JWT token, then call the gateway's /mcp endpoint to list available tools.
Show me the tools that the gateway exposes.
```

🤖 **Kiro Vibe Prompt** — Integrate gateway tools into the agent

```text
Update app/CustomerAssistantAgent/main.py to replace the dummy order_lookup, user_lookup, product_lookup, and policy_retrieval tools with real gateway tools.

The agent should connect to the AgentCore Gateway as an MCP client to discover and call the data_lookup and policy_retrieval Lambda functions.
The data_lookup Lambda handles order_lookup, user_lookup, and product_lookup calls.
Remove the dummy mock data functions.

The agent must handle OAuth token management for gateway authentication:
- Read GATEWAY_CLIENT_ID, GATEWAY_CLIENT_SECRET, GATEWAY_TOKEN_ENDPOINT, and GATEWAY_SCOPE from environment variables
- Obtain a JWT access token from Cognito using the client_credentials grant type
- Pass the token as an Authorization Bearer header when making MCP calls to the gateway URL
- Cache and auto-refresh the token before expiry

Keep the get_current_time tool and the memory integration intact.
Update agentcore.json and .env.local with the gateway endpoint URL and the Cognito credentials (client_id, client_secret, token_endpoint, scope).
Look up the latest AgentCore Gateway integration documentation for the correct MCP client pattern.
Refer to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-agent-integration.html for the Strands MCP client integration.
```

🤖 **Kiro Vibe Prompt** — Local integration tests (Kiro will run `agentcore dev` for each)

```text
Test the gateway integration locally by running these commands one by one and showing me the results:
1. `agentcore dev "Look up orders for customer C-01"`
2. `agentcore dev "What is the return policy for electronics in India?"`
3. `agentcore dev "Can I return the PlayStation 5 I ordered? What's the policy for gaming consoles in India?"`
```

💻 **Terminal Command** — Redeploy

```bash
agentcore deploy
```

💻 **Terminal Command** — Invoke the deployed agent

```bash
agentcore invoke
```

💬 **Agent Test Prompt** — Combined gateway + KB

```text
Look up orders for customer C-02 and tell me about the UK return policy
```

### Part 5 · Build a Web Chat UI with Streamlit and Cognito

🤖 **Kiro Vibe Prompt** — Create a test Cognito user for the UI

```text
Using the existing Cognito User Pool configuration, create a test user for the Streamlit UI:
- Find the Cognito User Pool ID from the project's configuration files
- Create a user with email "administrator@example.com" and a temporary password "Workshop1!"
- Enable the user and set email as verified
- Use region us-west-2
```

🤖 **Kiro Vibe Prompt** — Build the Streamlit app

```text
Create a Streamlit chat application in a file called `streamlit_app.py` in /streamlit-ui/ folder under root.
The app should:

1. **Authentication with Cognito:**
   - Read the Cognito User Pool ID and App Client ID from the existing Cognito configuration files in the project
   - Show a login form with email and password fields when the user is not authenticated
     (For convinience during the workshop , use the Cognito user name and password as the default values)
   - Handle the Cognito USER_PASSWORD_AUTH flow using boto3 cognito-idp client
   - Handle the NEW_PASSWORD_REQUIRED challenge for first-time login (show a "Set New Password" form)
   - Store the authentication tokens in Streamlit session state
   - Show a logout button in the sidebar when authenticated

2. **Chat Interface:**
   - Display a chat history using `st.chat_message` components
   - Provide a chat input box at the bottom for user messages
   - When the user sends a message, invoke the deployed agent using the AgentCore Runtime API
   - Read the agent endpoint URL from the agentcore configuration
   - Display the agent's response in the chat
   - Maintain chat history in Streamlit session state

3. **AgentCore Runtime Integration:**
   - Refer to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html
   - Use AgentCore Runtime ARN from the previous steps.
   - Use the user name (part before @) as actor_id.
   - Pass a consistent session_id per user session so the agent's memory works across messages
   - Include proper error handling for connection failures and timeouts

4. **UI Layout:**
   - Page title: "Returns & Refunds Assistant"
   - Sidebar showing: user email, session ID, and a logout button
   - Render streaming response properly. Tries to parse each chunk as JSON first. If successful, yields the parsed value (without the extra quotes) If not JSON, yields the chunk as-is
   - Welcome message when chat starts: "Hello! I'm your Returns & Refunds Assistant. I can help you look up orders, check return eligibility, calculate refunds and answer policy questions. How can I help you today?"

Use region us-west-2 for all AWS service calls.
```

💻 **Terminal Command** — Install Streamlit dependencies

```bash
pip install streamlit boto3
```

💻 **Terminal Command** — Run the Streamlit app

```bash
cd streamlit-ui
streamlit run streamlit_app.py --server.port 8501
```

💬 **Agent Test Prompt** — Memory recall (via Streamlit)

```text
What do you know about customer C-01?
```

💬 **Agent Test Prompt** — Order/product lookup

```text
What is product P-006
```

💬 **Agent Test Prompt** — UK return policy

```text
What is the return policy for electronics in the UK?
```

💬 **Agent Test Prompt** — Combined capabilities

```text
Can customer C-03 return their iPad Air? What's the US return policy for tablets?
```

### Part 6 · Explore Observability

💻 **Terminal Command** — Stream runtime logs

```bash
agentcore logs
```

💻 **Terminal Command** — Past logs with filters

```bash
agentcore logs --since 30m --limit 100
```

```bash
agentcore logs --since 1h --level error
```

```bash
agentcore logs --since 30m --query "gateway"
```

💻 **Terminal Command** — List traces

```bash
agentcore traces list
```

💻 **Terminal Command** — Download a specific trace

```bash
agentcore traces get <traceId>
```

💻 **Terminal Command** — Browse local CLI logs

```bash
ls agentcore/.cli/logs/
```

```bash
ls -lt agentcore/.cli/logs/dev/ | head -5
```

### Part 7 · Make It Yours — Open-Ended Enhancements

🤖 **Kiro Vibe Prompt** — Add more Cognito users (example)

```text
Add two more Cognito users to the Streamlit app:
- admin2@example.com with password "Workshop2!"
- admin3@example.com with password "Workshop3!"
Each user should have their own memory session so the agent remembers interactions per user.
```

🤖 **Kiro Vibe Prompt** — Add a new gateway tool (example)

```text
Add a new Lambda tool called "find_returned_products" to the data_lookup Lambda.
It should query the workshop-orders table for all orders with status "RETURNED", enrich with product names from workshop-products, and return the results.
Update the tool spec, redeploy the Lambda, and update the gateway target.
```

🤖 **Kiro Vibe Prompt** — Add a refund-processing tool (example)

```text
Add a "process_refund" tool to the data_lookup Lambda.
It should accept an order_id, look up the order in workshop-orders, update its status to "REFUNDED", and return the refund confirmation with the product details.
Update the tool spec and redeploy.
```

### Part 8 · Try the AgentCore Harness (Preview)

💻 **Terminal Command** — Move to the project directory

```bash
cd ~/ReturnsRefundsAgentProject/AgentCoreProject
```

💻 **Terminal Command** — Add a harness via the interactive wizard

```bash
agentcore add
```

Wizard selections:
- Resource: **Harness**
- Harness name: `CustAssistantHarness`
- Model provider: **Amazon Bedrock**
- Model: same Claude inference profile you used for the runtime agent
- System prompt: same Returns & Refunds Assistant prompt as the runtime agent (see Part 2)
- Custom environment: **Default Environment**
- Memory: **Enabled**
- Advanced settings: **Tools selected** → **AgentCore Browser**, **AgentCore Code Interpreter**, **AgentCore Gateway**
- Gateway ARN: paste the value Kiro returns (see prompt below)
- Gateway outbound auth: **OAuth**
- Credential provider ARN: paste the value Kiro returns (see prompt below)
- OAuth scopes: paste the `scope` value from `cognito_config.json` (a URL like `https://gateway.workshop.local/invoke`, not `workshop-gateway/invoke`)
- **Confirm**

🤖 **Kiro Vibe Prompt** — Get the workshop-gateway ARN

```text
Get me the ARN of the workshop-gateway we created in Part 4.
Run `agentcore status` and look for the gateway entry, or read the gateway ARN from the agentcore project config files. Print just the ARN.
```

🤖 **Kiro Vibe Prompt** — Create the OAuth2 credential provider

```text
Create an OAuth2 credential provider in AgentCore Identity that the harness can use to authenticate against the workshop-gateway.

Steps:
1. Read Cognito credentials from cognito_config.json in the project root: client_id, client_secret, token_endpoint, and the scope value (the scope is a Cognito resource-server identifier like https://gateway.workshop.local/invoke — use the exact value from the file).
2. Use the AWS CLI (bedrock-agentcore-control) or the AgentCore SDK to create a credential provider named "workshop-gateway-cognito" with grant type client_credentials, the Cognito token endpoint, and the scope from cognito_config.json.
3. Print the resulting credential provider ARN — I'll paste it into the agentcore add wizard.

Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-outbound-credential-provider.html
```

💻 **Terminal Command** — Deploy the harness alongside the runtime agent

```bash
agentcore deploy
```

💻 **Terminal Command** — Confirm both resources exist

```bash
agentcore status
```

💻 **Terminal Command** — Invoke the harness interactively

```bash
agentcore invoke --harness CustAssistantHarness --session-id "$(uuidgen)"
```

💬 **Agent Test Prompt** — Customer + order lookup via gateway

```text
Look up customer C-01 and list their orders.
```

💬 **Agent Test Prompt** — Policy retrieval via gateway + Knowledge Base

```text
What is the return policy for electronics in India?
```

💬 **Agent Test Prompt** — Browser verifies internal KB against amazon.com

```text
Visit amazon.com's official US returns policy page and quote the standard return window for electronics. Then compare it against what our internal knowledge base says (use the policy_retrieval tool). Tell me whether they agree.
```

💬 **Agent Test Prompt** — Code interpreter computes refund line items

```text
Compute the refund for an order with these details: subtotal $349.99, shipping $19.99, sales tax 10%, the customer is requesting return on day 8 of a 30-day return window, restocking fee 15% per our policy. Show every line item and the final refund amount.
```

💬 **Agent Test Prompt** — Combined: all three tools in one workflow

```text
Customer C-02 is asking about returning order ORD-002.

1. Use the gateway to look up the order details and the customer's country.
2. Use the gateway to fetch the return policy for that product category in the customer's country.
3. Use the browser to verify the return window against amazon.com's published policy for the same country.
4. Use code_interpreter to compute the refund: assume subtotal is the order price, shipping was $9.99, sales tax 8%, and apply any restocking fee from the policy if applicable.

Give me a final summary with the refund amount and whether the request is within the return window.
```

💻 **Terminal Command** — Override the model for one invocation

```bash
agentcore invoke --harness CustAssistantHarness \
  --session-id "$(uuidgen)" \
  --model-id us.anthropic.claude-opus-4-5-20251101-v1:0 \
  "Look up customer C-03 and the US return policy for tablets."
```

💻 **Terminal Command** — Restrict to gateway only for a regulated query

```bash
agentcore invoke --harness CustAssistantHarness \
  --session-id "$(uuidgen)" \
  --tools workshop-gateway \
  "List all returnable orders for customer C-01 with their refund amounts."
```

💻 **Terminal Command** — Override the system prompt for one invocation

```bash
agentcore invoke --harness CustAssistantHarness \
  --session-id "$(uuidgen)" \
  --system-prompt "You are a terse policy lookup tool. Answer in one sentence." \
  "What's the return policy for electronics in India?"
```

💻 **Terminal Command** — Local development with the agent inspector

```bash
agentcore dev --harness CustAssistantHarness
```

### Clean Up

💻 **Terminal Command** — Move to the project directory

```bash
cd ~/ReturnsAndRefundsAgentProject/AgentCoreProject
```

💻 **Terminal Command** — Remove resources via the TUI (select `remove`, then pick agent, harness, memory, gateway, targets)

```bash
agentcore
```

💻 **Terminal Command** — Tear down AWS resources

```bash
agentcore deploy
```

🤖 **Kiro Vibe Prompt** — Clean up Lambda + Cognito

```text
Delete all the Lambda functions and IAM roles we created during this workshop.
Also delete the Cognito User Pool we created for gateway authentication.
Use the configuration files in the project to find the resource IDs.
Handle missing resources gracefully.
```
