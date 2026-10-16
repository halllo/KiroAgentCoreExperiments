# Project Overview

This project is a **Returns & Refunds Assistant** built with the **Strands Agents SDK** and the **AgentCore CLI** (Amazon Bedrock AgentCore).

## What we are building

An AI agent that helps administrators:

- Check return eligibility for customer orders
- Calculate refund amounts
- Answer questions about return policies

The agent is backed by AgentCore Runtime, and over the course of the project gains persistent memory, a Gateway fronting real data sources (DynamoDB + a Bedrock Knowledge Base via Lambda), and a Streamlit chat UI with Cognito auth.

## Core technology stack

- **Strands Agents SDK** — agent definition, tools, model binding, memory session management
- **Amazon Bedrock AgentCore CLI** (`agentcore`) — scaffold, run locally (`agentcore dev`), deploy (`agentcore deploy`), and manage resources (Runtime, Memory, Gateway, Targets, Harness)
- **Amazon Bedrock** — model provider
- **Python** — implementation language
- **boto3** — AWS SDK for Lambda handlers and scripting

## Guiding principles

This is a **learning / workshop** project. Every piece of code should:

- Demonstrate one core concept clearly
- Stay minimal — avoid frameworks, abstractions, or options the task does not require
- Be readable by someone new to Strands and AgentCore

When a requirement is ambiguous, prefer the simplest implementation that satisfies the stated goal, and leave an inline comment explaining the choice.
