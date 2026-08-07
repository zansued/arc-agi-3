# Agent2Agent (A2A) Protocol

**An open protocol enabling communication and interoperability between opaque agentic applications.**

The Agent2Agent (A2A) protocol addresses a critical challenge in the AI landscape: enabling gen AI agents, built on diverse frameworks by different companies running on separate servers, to communicate and collaborate effectively - as agents, not just as tools. A2A aims to provide a common language for agents, fostering a more interconnected, powerful, and innovative AI ecosystem.

With A2A, agents can:

- Discover each other's capabilities.
- Negotiate interaction modalities (text, forms, media).
- Securely collaborate on long-running tasks.
- Operate without exposing their internal state, memory, or tools.

Why A2A?

- Break Down Silos: Connect agents across different ecosystems.
- Enable Complex Collaboration: Allow specialized agents to work together on tasks that a single agent cannot handle alone.
- Promote Open Standards: Foster a community-driven approach to agent communication, encouraging innovation and broad adoption.
- Preserve Opacity: Allow agents to collaborate without needing to share internal memory, proprietary logic, or specific tool implementations, enhancing security and protecting intellectual property.

Key Features:

- Standardized Communication: JSON-RPC 2.0 over HTTP(S).
- Agent Discovery: Via Agent Cards detailing capabilities and connection info.
- Flexible Interaction: Supports synchronous request/response, streaming (SSE), and asynchronous push notifications.
- Rich Data Exchange: Handles text, files, and structured JSON data.
- Enterprise-Ready: Designed with security, authentication, and observability in mind.

Getting Started:
- A2A Python SDK: pip install a2a-sdk
- A2A Go SDK: go get github.com/a2aproject/a2a-go
- A2A JS SDK: npm install @a2a-js/sdk
- A2A Java SDK: using maven
- A2A .NET SDK: dotnet add package A2A

What is next:
- Formalize AgentDiscovery authorization schemes
- QuerySkill() method for dynamic capability checking
- Dynamic UX negotiation within tasks
- Client-initiated methods beyond task management

The A2A Protocol is an open source project under the Linux Foundation, contributed by Google. Licensed under Apache License 2.0.
