# AWS Conventions

## Region: always us-west-2

**Every AWS operation in this project targets `us-west-2`.** No exceptions unless the user explicitly says otherwise.

- boto3 clients/resources: pass `region_name="us-west-2"`.
  ```python
  import boto3
  dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
  ```
- AWS CLI: rely on `AWS_DEFAULT_REGION=us-west-2` and/or pass `--region us-west-2` explicitly.
- AgentCore config and resource ARNs: use the `us-west-2` region.

## AWS CLI: always use `--no-cli-pager`

When running **any** AWS CLI command from the terminal, include `--no-cli-pager` so output is printed directly and does not block on an interactive pager.

```bash
aws sts get-caller-identity --no-cli-pager --region us-west-2
aws dynamodb scan --table-name workshop-orders --no-cli-pager --region us-west-2
```

## Follow AWS best practices

- Base all AWS usage on current official AWS documentation (look it up via the AWS Documentation MCP server first — see `documentation-first.md`).
- Use least-privilege IAM: scope policies to specific resources and actions required by the task.
- Read configuration (KB IDs, role ARNs, memory IDs) from the documented sources — SSM parameters, `agentcore.json`, `.env.local`, or `agentcore status` — instead of hardcoding.
- Prefer parameterized, non-interactive CLI invocations so commands run cleanly in automation.
- Do not echo secret values (client secrets, tokens, keys) back in responses; reference them by name.

## boto3 defaults

- Always set the region explicitly on clients and resources.
- Handle expected errors (missing item, access denied, timeout) with clear messages rather than silent failures.
