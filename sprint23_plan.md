# Sprint 2+3 Implementation Plan
# awesome-deepseek-agent Absorption into BLACKGOV Ecosystem

**Date**: 2026-05-11
**Author**: Agent Zero 'Master Developer'
**Context**: Absorption of DeepSeek-TUI, Hermes Agent, Crush, and other awesome-deepseek-agent tools into existing BLACKGOV ecosystem

---

## Priority Order

1. **MCP Server Exposure** (highest impact, most immediately useful) — Implemented first
2. **Hermes Auto-Skilling** (extends existing skills system)
3. **HTTP Runtime API** (builds on existing A2A/status endpoints)
4. **Sandbox Tool Execution** (Landlock-based, Docker isolation)
5. **LSP Integration** (Language Server Protocol)
6. **RLM** (Recursive Language Model)

---

## Item 1: MCP Server Exposure

### Reference
DeepSeek-TUI is both an MCP client and an MCP server (`deepseek mcp serve`). It exposes agent capabilities to other MCP-compatible clients.

### Implementation
- **File**: `/a0/usr/workdir/github_hypados/deepclaude/mcp-server.js`
- **SDK**: `@modelcontextprotocol/sdk` (npm)
- **Transports**: stdio + HTTP
- **Tools exposed**:
  - `execute_tool` — Execute any Agent Zero tool (terminal, Python, Node.js)
  - `search_knowledge` — Query the Knowledge Graph in the BLACKGOV ecosystem
  - `list_skills` — List all available skills in /a0/usr/skills/
  - `call_mcp` — Call any MCP server tool (KG, RAG, DGM, Paperclip)
  - `analyze_code` — Analyze code via LSP or static analysis
  - `generate_text` — Generate text via DeepSeek API
  - `call_subordinate` — Delegate to a subordinate agent
  - `read_file` — Read files from the filesystem
  - `write_file` — Write files to the filesystem
  - `search_web` — Search the web

### Architecture
```
┌────────────────────────────────────────┐
│         MCP Client (IDE, CLI)          │
└────────────────┬───────────────────────┘
                 │
         MCP Protocol (JSON-RPC 2.0)
                 │
┌────────────────▼───────────────────────┐
│         MCP Server (mcp-server.js)      │
│  ┌──────────────────────────────────┐  │
│  │  Stdio Transport  │  HTTP Transp  │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │  Tool Registry                    │  │
│  │  ├─ execute_tool                 │  │
│  │  ├─ search_knowledge             │  │
│  │  ├─ list_skills                  │  │
│  │  ├─ call_mcp                     │  │
│  │  ├─ analyze_code                 │  │
│  │  ├─ generate_text                │  │
│  │  ├─ call_subordinate             │  │
│  │  ├─ read_file                    │  │
│  │  ├─ write_file                   │  │
│  │  └─ search_web                   │  │
│  └──────────────────────────────────┘  │
└────────────────┬───────────────────────┘
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
 ┌────────┐ ┌────────┐ ┌────────┐
 │ A2A    │ │ MCP    │ │ Agent  │
 │ Bridge │ │ Servers│ │ Zero   │
 │ :9999  │ │:8800-03│ │ Core   │
 └────────┘ └────────┘ └────────┘
```

### Launch Command
```bash
# stdio mode (for IDE integration):
node /a0/usr/workdir/github_hypados/deepclaude/mcp-server.js --stdio

# HTTP mode (for remote clients):
node /a0/usr/workdir/github_hypados/deepclaude/mcp-server.js --port 3100
```

---

## Item 2: Hermes Auto-Skilling

### Reference
Hermes Agent (Nous Research) has a built-in learning loop: creates skills from experience, improves them during use, persists knowledge, and builds an evolving model of preferences across sessions.

### Implementation
- **File**: `/a0/usr/workdir/auto_skilling/auto_skiller.py`
- **Trigger patterns**:
  - Successful tool execution sequences
  - Repeated usage of specific tools in patterns
  - User-saved solutions via memorization
  - Solution patterns in the dgm_lemoz/results/ archives
- **Output**: Auto-generated SKILL.md files in `/a0/usr/skills/<auto-name>/SKILL.md`
- **Watcher**: File watcher on /a0/usr/workdir/logs/ for pattern detection
- **Integration**: Coliseu evaluates auto-skills for quality before installation

### Architecture
```
┌──────────────────────────────────────────────┐
│              Auto-Skiller Watson              │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Log Watcher  │  │ Pattern Recognizer   │  │
│  │ (inotify)    │  │ (regex + frequency)  │  │
│  └──────┬───────┘  └─────────┬────────────┘  │
│         │                    │                │
│         ▼                    ▼                │
│  ┌──────────────────────────────────────┐    │
│  │ Skill Generator                      │    │
│  │ (reads pattern → drafts SKILL.md)    │    │
│  └──────────────┬───────────────────────┘    │
│                 │                             │
│                 ▼                             │
│  ┌──────────────────────────────────────┐    │
│  │ Coliseu Validator                    │    │
│  │ (scores skill quality before save)   │    │
│  └──────────────┬───────────────────────┘    │
│                 │                             │
│                 ▼                             │
│  ┌──────────────────────────────────────┐    │
│  │ /a0/usr/skills/<auto-name>/SKILL.md  │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

### Skill Schema (auto-generated)
```markdown
# Auto-Skill: <name>

## Trigger
Phrases or tool patterns that activate this skill

## Description
What this skill does, derived from observed patterns

## Tools Required
- tool1
- tool2

## Workflow
Step-by-step workflow derived from successful patterns

## Origin
- Discovered: <date>
- Source: <conversation pattern / dgm solution>
- Confidence: <0-1>
```

---

## Item 3: HTTP Runtime API

### Reference
DeepSeek-TUI's `deepseek serve --http` exposes a `/v1/*` runtime API for embedding in IDEs and web UIs (sessions, threads, turns, tasks, automations, MCP, skills).

### Implementation
- **File**: `/a0/usr/workdir/github_hypados/deepclaude/runtime-api.js`
- **Port**: 3101
- **Endpoints**:
  - `GET /v1/health` — Health check
  - `POST /v1/chat/completions` — OpenAI-compatible chat completions (like DeepClaude proxy)
  - `POST /v1/tasks` — Submit a task to the agent
  - `GET /v1/tasks/:id` — Get task status
  - `POST /v1/tools/:name` — Execute a specific tool
  - `GET /v1/skills` — List skills
  - `GET /v1/mcp/servers` — List MCP servers
  - `POST /v1/mcp/call` — Call an MCP server tool
  - `GET /v1/agents` — List available agents
  - `GET /v1/sessions` — List sessions
  - `GET /v1/sessions/:id` — Get session context
  - `DELETE /v1/sessions/:id` — Clear session

### Architecture
```
┌─────────────────────────────────────────────┐
│          HTTP Runtime API (:3101)            │
│  Fastify/Express with OpenAI-compatible      │
│  /v1/* endpoints                             │
├─────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌───────────────┐ │
│  │ /v1/chat│ │ /v1/tasks│ │ /v1/tools/*   │ │
│  └────┬────┘ └────┬─────┘ └──────┬────────┘ │
│       │           │              │           │
│       ▼           ▼              ▼           │
│  ┌────────────────────────────────────┐      │
│  │ A2A Bridge (:9999) / MCP / Agent   │      │
│  └────────────────────────────────────┘      │
└─────────────────────────────────────────────┘
```

---

## Item 4: Sandbox Tool Execution

### Reference
DeepSeek-TUI ships sandboxed tool execution on macOS (Seatbelt), Linux (Landlock), and Windows.

### Implementation (In-Process)
- We're already in Docker, which provides container-level isolation
- Add explicit sandbox policy:
  - **File**: `/a0/usr/workdir/github_hypados/deepclaude/sandbox_policy.json`
  - **Mechanism**: Node.js `child_process` with Landlock seccomp-bpf via `seccomp` npm package
  - **Restrictions**:
    - No network access (or limited to specific hosts)
    - Read-only filesystem (or limited to specific paths)
    - No syscalls: `execve`, `fork`, `clone`, `ptrace`
    - CPU/memory limits via `cgroups`

### Python Fallback
- If seccomp not available, use `nsjail` or `bubblewrap` as sandbox
- Already installed in Kali: check `nsjail`, `bubblewrap`, or `firejail`

---

## Item 5: LSP Integration

### Reference
Crush (charmbracelet/crush) has LSP integration for code analysis. Uses `__debugger__` hook and supports multiple language servers.

### Implementation
- **File**: `/a0/usr/workdir/lsp_integration/lsp_client.js`
- **SDK**: `vscode-languageserver-protocol` (npm) or `langserver`
- **Language Servers**:
  - Python: `pylsp` / `pyright`
  - JavaScript/TypeScript: `typescript-language-server`
  - Go: `gopls`
  - Rust: `rust-analyzer`
- **Features**:
  - Diagnostics (errors, warnings)
  - Code completion
  - Go to definition
  - Find references
  - Hover information

---

## Item 6: RLM (Recursive Language Model)

### Reference
DeepSeek-TUI has a built-in recursive-LM tool that processes oversized inputs in a sandboxed Python REPL without polluting the parent context.

### Implementation
- **File**: `/a0/usr/workdir/rlm_processor/rlm_agent.py`
- **Mechanism**:
  - Offloads large context processing to a sandboxed Python REPL
  - Communicates via stdin/stdout JSON-RPC
  - Results are summarized and returned to the parent context
- **Use cases**:
  - Processing large files (>100K tokens)
  - Batch analysis of datasets
  - Recursive code generation
  - Document summarization

---

## Implementation Timeline

| Day | Items |
|-----|-------|
| 1   | MCP Server Exposure (implemented now) |
| 1-2 | Hermes Auto-Skilling + testing |
| 2-3 | HTTP Runtime API + integration testing |
| 3-4 | Sandbox Tool Execution |
| 4-5 | LSP Integration |
| 5-6 | RLM Processor |

---

## Dependencies

```bash
# For MCP Server
npm install @modelcontextprotocol/sdk

# For Hermes Auto-Skilling
pip install watchdog          # file watcher
pip install pyyaml            # YAML parsing

# For HTTP Runtime API
npm install fastify
npm install @fastify/cors

# For Sandbox
apt-get install bubblewrap   # Linux sandboxing
npm install seccomp          # (if available)

# For LSP
npm install vscode-languageserver-protocol
pip install python-lsp-server   # Python LSP

# For RLM
# (uses existing Python environment, no additional deps)
```

---

## Success Criteria

1. **MCP Server**: MCP client can discover and call all 10 tools; both stdio and HTTP transports work
2. **Auto-Skilling**: Skills auto-generated from observed patterns; validated by Coliseu before installation
3. **HTTP Runtime**: All /v1/* endpoints respond correctly; OpenAI-compatible /chat/completions works
4. **Sandbox**: Untrusted code execution is restricted via Landlock/namespace
5. **LSP**: Code diagnostics, completion, and navigation work for Python and JavaScript
6. **RLM**: Oversized inputs are processed in sandboxed REPL; results returned without context pollution
