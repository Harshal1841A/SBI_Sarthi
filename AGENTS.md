# Sarthi Agent Topology

Sarthi is powered by a hierarchical multi-agent state graph orchestrated via LangGraph.

## Core Topology
1. **Supervisor (`supervisor.py`)**: Central router that analyzes user queries, assesses intent, and delegates tasks to domain sub-agents.
2. **Shield (`shield.py`)**: Security pre-filter responsible for prompt injection classification and PII guardrails before processing.
3. **Domain Agents**:
   - **Acquisition (`acquisition.py`)**: Handles onboarding, KYC workflows, and initial customer discovery.
   - **Adoption (`adoption.py`)**: Guides users through product features and usage patterns.
   - **Assist (`assist.py`)**: Answers customer support queries, transaction inquiries, and FAQs.
   - **Engagement (`engagement.py`)**: Manages notifications, proactive alerts, and follow-ups.
   - **Compensation (`compensation.py`)**: Manages redressal, refund requests, and financial dispute resolution.
4. **HITL (`hitl.py`)**: Human-In-The-Loop interrupt point that pauses state execution for supervisor approval on high-risk actions.

All agents operate asynchronously and store durable state checkpoints in Redis and Postgres.
