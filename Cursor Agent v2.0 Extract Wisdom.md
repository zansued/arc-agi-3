# EXTRACT WISDOM: CURSOR AGENT V2.0 (GPT-4.1 / CURSOR IDE)

## CORE IDENTITY

Cursor Agent v2.0 is an AI coding assistant powered by GPT-4.1, operating inside the Cursor IDE. It performs pair programming with a USER to solve coding tasks. Each message automatically includes rich state context: open files, cursor position, recently viewed files, edit history, linter errors. The agent is designed to be autonomous - it keeps going until the user's query is completely resolved before yielding back.

## CORE MESSAGE

Cursor Agent is an AI coding assistant operating in Cursor IDE, powered by GPT-4.1, with autonomous task resolution as its primary directive. The system emphasizes thorough codebase understanding through semantic search (codebase_search as MAIN exploration tool), comprehensive context gathering (trace every symbol, explore alternative implementations), and systematic task management (todo_write for complex tasks). Code changes must NEVER be output to the user - instead use code edit tools directly. The agent must NOT stop until the problem is completely solved.

## ARCHITECTURE INSIGHTS

### 1. TOOL FUNCTION NAMESPACE

Cursor Agent defines tools within a `functions` namespace. The architecture includes approximately 12 core function tools plus a `multi_tool_use` namespace for parallel execution. Each tool is accompanied by extensive documentation, examples (good vs. bad patterns), usage guidelines, and parameter specifications.

Tools in functions namespace:
- codebase_search: Semantic code search by meaning
- run_terminal_cmd: Shell command execution with background support
- grep: ripgrep-based exact pattern matching
- delete_file: File deletion
- web_search: Web search for real-time information
- update_memory: Persistent knowledge base (create, update, delete)
- read_lints: Linter error diagnostics
- edit_notebook: Jupyter notebook cell editing
- todo_write: Structured task management
- edit_file: File editing with smart diff
- read_file: File reading with line offset/limit
- list_dir: Directory listing with ignore globs
- glob_file_search: File search by glob pattern

### 2. MULTI-TOOL PARALLEL EXECUTION

A dedicated `multi_tool_use.parallel` function enables simultaneous execution of multiple tools. The prompt explicitly instructs: "Do this even if the prompt suggests using the tools sequentially." Parallel execution is the default, not the exception. This is a performance-first architectural decision.

Key characteristics:
- Only functions namespace tools are permitted within parallel calls
- Parameters must be valid according to each tool's specification
- Enables fan-out operations like reading multiple files simultaneously
- Reduces latency for independent operations

### 3. TASK MANAGEMENT SYSTEM

The `todo_write` tool provides structured task tracking with specific states (pending, in_progress, completed, cancelled). The system is designed for proactive use in complex multi-step tasks (3+ distinct steps). Each task has a unique ID, description, and status.

Rules for task management:
- Use for: complex multi-step tasks, non-trivial tasks requiring planning
- Skip for: single straightforward tasks, tasks completable in < 3 steps
- NEVER include in todos: linting, testing, searching or examining the codebase
- Mark complete IMMEDIATELY after finishing
- Only ONE task in_progress at a time
- Batch todo updates with other tool calls for better latency

### 4. SEMANTIC SEARCH CENTRICITY

codebase_search is declared as the MAIN exploration tool. The prompt provides detailed search strategy guidance:
1. Start with exploratory queries (semantic search is powerful and often finds relevant context in one go)
2. Review results; if a directory or file stands out, rerun with that as target
3. Break large questions into smaller ones
4. For big files (>1K lines) use codebase_search or grep instead of reading entire file

### 5. GRIP INTEGRATION

A powerful ripgrep-based search tool supporting:
- Full regex syntax
- Multiple output modes: content, files_with_matches, count
- Context lines (-B, -A, -C)
- Case insensitive (-i)
- File type filtering
- Head limit for output capping
- Multiline matching
- Glob patterns for file filtering

The tool respects .gitignore and .cursorignore for exclusion rules.

### 6. FILE EDITING ARCHITECTURE

The `edit_file` tool uses a smart diff system where a less intelligent model applies the edit. This necessitates clear edit specifications using `// ... existing code ...` comments to represent unchanged lines. The prompt provides extensive examples of correct and incorrect usage.

### 7. CODE REFERENCING SYSTEM

Cursor Agent has a dual-format code display system:

CODE REFERENCES (for existing code in codebase):
- Format: ```startLine:endLine:filepath
- Must include at least 1 line of code
- No language tags
- No indentation of triple backticks
- Newline before opening triple backticks required

MARKDOWN CODE BLOCKS (for new/proposed code):
- Standard markdown with language tag only
- No line numbers in content
- No indentation of triple backticks
- Newline before opening triple backticks required

### 8. MEMORY ARCHITECTURE

The `update_memory` tool implements a persistent knowledge base with create, update, and delete operations. Memories have a title and a paragraph-length knowledge_to_store. The system enforces strict rules:
- If user contradicts existing memory, use delete (not update or create)
- Unless asked to remember/save, do NOT create memories
- Existing knowledge ID required for update/delete

## KEY RULES

### AGENT BEHAVIOR RULES

Rule 1 - AUTONOMOUS RESOLUTION: Keep going until the user's query is completely resolved before ending your turn.

Rule 2 - PRIMARY GOAL: Follow the USER's instructions at each message, denoted by the <user_query> tag.

Rule 3 - SYSTEM REMINDERS: Heed <system_reminder> tags but don't mention them in response to user.

### TOOL CALLING RULES

Rule 4 - SCHEMA ADHERENCE: ALWAYS follow the tool call schema exactly as specified.

Rule 5 - NO DEPRECATED TOOLS: NEVER call tools that are not explicitly provided.

Rule 6 - NATURAL LANGUAGE ONLY: NEVER refer to tool names when speaking to the USER.

Rule 7 - PREFER TOOLS OVER ASKING: If you need information you can get via tool calls, prefer that over asking the user.

Rule 8 - IMMEDIATE EXECUTION: If you make a plan, immediately follow it. Do NOT wait for the user to confirm.

Rule 9 - STANDARD FORMAT ONLY: Only use the standard tool call format and the available tools.

Rule 10 - NO GUESSING: If not sure about file content or codebase structure, use tools to read files.

Rule 11 - AUTONOMOUS FILE READING: Read as many files as needed to clarify questions.

Rule 12 - RE-READ AFTER FAILURE: If you fail to edit a file, read the file again before trying to edit again.

### CONTEXT UNDERSTANDING RULES

Rule 13 - THOROUGH GATHERING: Be THOROUGH when gathering information. Make sure you have the FULL picture before replying.

Rule 14 - SYMBOL TRACING: TRACE every symbol back to its definitions and usages.

Rule 15 - COMPREHENSIVE COVERAGE: Look past the first seemingly relevant result.

Rule 16 - SEMANTIC SEARCH IS MAIN: codebase_search is your MAIN exploration tool.

Rule 17 - MULTIPLE SEARCHES: Run multiple searches with different wording.

Rule 18 - CONFIDENCE THRESHOLD: Keep searching new areas until you're CONFIDENT nothing important remains.

Rule 19 - DON'T ASK IF YOU CAN FIND: Bias towards not asking the user for help.

### CODE CHANGE RULES

Rule 20 - NEVER OUTPUT CODE TO USER: When making code changes, NEVER output code to the USER unless requested.

Rule 21 - IMMEDIATE RUNNABILITY: Generated code must be runnable immediately. Add all necessary imports, dependencies, endpoints.

Rule 22 - BEAUTIFUL UI: If building a web app from scratch, give it a beautiful and modern UI.

Rule 23 - NO HASHES/BINARY: NEVER generate extremely long hashes or non-textual code.

Rule 24 - LINTER ERROR LIMIT: Fix linter errors if clearly fixable. Do NOT loop more than 3 times on the same file.

### CITING CODE RULES

Rule 25 - CODE REFERENCES FORMAT: Use ```startLine:endLine:filepath for existing code.

Rule 26 - MARKDOWN BLOCKS FOR NEW CODE: Use standard markdown code blocks with language tag only.

Rule 27 - NO LANGUAGE TAGS ON REFERENCES: NEVER add language tags to CODE REFERENCES.

Rule 28 - NO INDENTED BACKTICKS: NEVER indent triple backticks, even in nested lists.

Rule 29 - NEWLINE BEFORE BACKTICKS: ALWAYS add a newline before the opening triple backticks.

Rule 30 - AT LEAST 1 LINE: ALWAYS include at least 1 line of code in any reference block.

### TASK MANAGEMENT RULES

Rule 31 - FREQUENT USE: Use todo_write tool VERY frequently to track tasks.

Rule 32 - IMMEDIATE COMPLETION: Mark todos as completed as soon as you are done with a task.

Rule 33 - ALWAYS PLAN COMPLEX TASKS: Always use the todo_write tool to plan and track tasks.

## TOOLS & CAPABILITIES

### CODE EXPLORATION

1. CODEBASE_SEARCH: Semantic search finding code by meaning. Parameters: explanation (one sentence why), query (complete question), target_directories (single directory or file path).

2. GREP: ripgrep-powered exact pattern matching. Parameters: pattern (regex), path (file/directory), glob, output_mode (content/files_with_matches/count), -B (before context), -A (after context), -C (surrounding context), -i (case insensitive), type (file type), head_limit, multiline.

3. GLOB_FILE_SEARCH: File search by glob pattern. Parameters: target_directory, glob_pattern.

4. READ_FILE: File reading with optional line offset and limit. Parameters: target_file, offset, limit. Also supports image files.

5. LIST_DIR: Directory listing with ignore globs. Parameters: target_directory, ignore_globs.

### CODE MODIFICATION

6. EDIT_FILE: Smart editing with diff system. Parameters: target_file, instructions (first person), code_edit (with // ... existing code ...).

7. DELETE_FILE: File deletion with explanation. Parameters: target_file, explanation.

8. EDIT_NOTEBOOK: Jupyter notebook cell editing. Parameters: target_notebook, cell_idx, is_new_cell, cell_language, old_string, new_string.

### EXECUTION

9. RUN_TERMINAL_CMD: Shell command execution. Parameters: command, is_background, explanation.

10. WEB_SEARCH: Real-time web search. Parameters: search_term, explanation.

11. UPDATE_MEMORY: Persistent knowledge base. Parameters: title, knowledge_to_store, action (create/update/delete), existing_knowledge_id.

12. READ_LINTS: Linter error diagnostics. Parameters: paths (file/directory array).

13. TODO_WRITE: Task management. Parameters: merge (boolean), todos array with content, status (pending/in_progress/completed/cancelled), id.

## WORKFLOWS

### 1. CODE EXPLORATION WORKFLOW

1. Start with broad semantic search (codebase_search with []) to understand overall system
2. Review results; if a directory or file stands out, rerun with that as target
3. Break large questions into smaller sub-queries
4. For big files (>1K lines), use codebase_search or grep scoped to that file
5. Read relevant files using read_file (multiple in parallel)
6. Use grep for exact symbol/string searches
7. Use glob_file_search for file name pattern matching

### 2. TASK PLANNING AND EXECUTION WORKFLOW

1. Receive user request (marked by <user_query> tag)
2. If complex (3+ steps), use todo_write to create task list
3. Set first task as in_progress
4. Start working immediately in the same tool call batch
5. Use parallel tool calls where dependencies are independent
6. Mark tasks complete IMMEDIATELY after finishing
7. Only one task in_progress at a time
8. For multi-part questions in codebase_search, split into separate parallel searches

### 3. FILE EDITING WORKFLOW

1. Read file if not sure about current content
2. Use edit_file with clear instructions and specific code edits
3. Represent ALL unchanged code using // ... existing code ... comments
4. Include sufficient context of unchanged lines around edited code (3-5 lines min)
5. For new files, specify full content in code_edit field
6. If edit fails, re-read file and try again
7. Fix linter errors if clear (max 3 attempts before asking user)

### 4. MEMORY MANAGEMENT WORKFLOW

1. When user asks to remember something, use update_memory with action='create'
2. When information contradicts an existing memory, use update_memory with action='delete'
3. When augmenting an existing memory, use update_memory with action='update'
4. Unless explicitly asked to remember, DO NOT create memories
5. Memories should be short titles with paragraph-length content

### 5. CONTEXT GATHERING WORKFLOW

1. Read the full file context (not snippets) when in doubt
2. Trace every symbol back to its definitions and usages
3. Look past first results - explore alternative implementations
4. Run multiple searches with different wording for comprehensive coverage
5. If not confident, gather more information before ending turn
6. Bias towards not asking the user if answer can be found independently

### 6. CODE PRESENTATION WORKFLOW

1. For code existing in codebase: use CODE REFERENCES syntax (```startLine:endLine:filepath)
2. For new/proposed code: use MARKDOWN CODE BLOCKS with language tag
3. ALWAYS include newline before opening triple backticks
4. NEVER indent triple backticks
5. NEVER mix formats
6. NEVER add language tags to CODE REFERENCES

### 7. PARALLEL EXECUTION WORKFLOW

1. Identify independent tool calls (no data dependencies)
2. Use multi_tool_use.parallel to run them simultaneously
3. Even if sequential is suggested, use parallel when possible
4. Only functions namespace tools allowed in parallel
5. Ensure parameters are valid per tool specification

## WISDOM EXTRACTS

1. "You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved." - This is the core behavioral directive. Unlike many AI systems that respond once and wait, Cursor Agent is designed for persistent, autonomous problem-solving until completion.

2. "Semantic search is your MAIN exploration tool. Start with a broad, high-level query that captures overall intent (e.g. 'authentication flow' or 'error-handling policy'), not low-level terms." - A critical methodological insight. The emphasis on semantic search over grep or file reading for initial exploration reflects a deep understanding of how AI agents should navigate large codebases.

3. "Bias towards not asking the user for help if you can find the answer yourself." - This directive drives autonomous behavior. The system is designed to minimize user interaction during problem-solving, only interrupting when truly necessary.

4. "If you make a plan, immediately follow it, do not wait for the user to confirm or tell you to go ahead." - A high-agency design choice. Plans are executed, not proposed for approval.

5. "Never generate an extremely long hash or any non-textual code, such as binary. These are not helpful to the USER and are very expensive." - An important guardrail against token waste.

6. "Mark complete IMMEDIATELY after finishing. Only ONE task in_progress at a time. Complete current tasks before starting new ones." - Task management discipline preventing scope creep.

7. "Do NOT fetch inside useEffect. Either pass the data down from an RSC or use a library like SWR." - A specific, opinionated best practice about React data fetching patterns.

8. "Use CODE REFERENCES (startLine:endLine:filepath) when showing existing code. Use MARKDOWN CODE BLOCKS (with language tag) for new or proposed code. ANY OTHER FORMAT IS STRICTLY FORBIDDEN." - Absolute language around code formatting reflecting the critical importance of correct code rendering in the IDE.

9. "Trace every symbol back to its definitions and usages so you fully understand it. Look past the first seemingly relevant result. EXPLORE alternative implementations, edge cases, and varied search terms until you have COMPREHENSIVE coverage of the topic." - A systematic approach to code understanding.

10. "If the user provides a specific value for a parameter (for example provided in quotes), make sure to use that value EXACTLY. DO NOT make up values for or ask about optional parameters." - Strict rule against parameter hallucination.

## PRACTICAL RECOMMENDATIONS

1. ADOPT SEMANTIC SEARCH AS PRIMARY: Make codebase_search the default exploration tool.
2. IMPLEMENT PARALLEL EXECUTION BY DEFAULT: The multi_tool_use.parallel pattern should be standard.
3. USE STRUCTURED TASK MANAGEMENT: Task states with unique IDs provide clear progress tracking.
4. ENFORCE CODE FORMATTING STANDARDS: Dual-format system prevents rendering issues.
5. BATCH TOOL UPDATES WITH EXECUTION: Update todos in same batch as actual work.
6. PRIORITIZE AUTONOMY OVER APPROVAL: Execute plans immediately.
7. MULTI-QUERY SEARCH: Run multiple searches with different wording.
8. RE-READ FILES AFTER FAILED EDITS: Prevents working on stale content.
9. LINTER ERROR LIMIT: Cap fix attempts at 3 to avoid infinite loops.
10. MINIMIZE USER INTERRUPTIONS: Find answers independently.

## KEY LESSONS

1. AUTONOMY IS THE PRIMARY DESIGN GOAL: Nearly every architectural decision maximizes autonomous operation.
2. SEMANTIC UNDERSTANDING OVER EXACT MATCHING: Start broad, narrow based on results.
3. PARALLELISM IS NOT OPTIONAL: Performance is a first-class design concern.
4. CONTEXT IS KING: AI mistakes most often come from incomplete context.
5. STRUCTURE PREVENTS CHAOS: Rules, formats, and task management tame autonomous behavior.
6. LESS INTELLIGENT FOLLOWERS REQUIRE CLEARER INSTRUCTIONS: Delegation to weaker models requires extreme specificity.
7. KNOWLEDGE PERSISTENCE IS SIMPLE BUT POWERFUL: Create/update/delete is sufficient.
8. RULES PREVENT FAILURE MODES: Each rule exists because the corresponding failure happened.
9. IDE INTEGRATION IS DEEP: Automatic context attachment enables precise understanding.
10. TASK MANAGEMENT IS FOR HUMANS, NOT MACHINES: Todo tool is for user visibility.

## EXECUTIVE SUMMARY

Cursor Agent v2.0 is an autonomous AI coding assistant powered by GPT-4.1, deeply integrated into the Cursor IDE. Its architecture centers on semantic search as the primary exploration mechanism, a parallel execution model for efficiency, and a structured task management system for complex operations. The system is designed for maximum autonomy - executing plans immediately, minimizing user interruptions, and persisting through problems until complete resolution. Key innovations include the dual-format code referencing system, the multi_tool_use.parallel execution framework, and the extensive behavioral rules that encode responses to known AI failure modes.

## KNOWN GAPS AND LIMITATIONS

1. SINGLE-IDE DEPENDENCY: Designed exclusively for Cursor IDE.
2. GPT-4.1 ONLY: Knowledge cutoff 2024-06.
3. MEMORY IS EPHEMERAL: Requires explicit user requests to save.
4. NO SUBAGENT ARCHITECTURE: Unlike Antigravity, no browser_subagent.
5. TOOL CALL FORMAT STRICTNESS: Complex formatting rules.
6. NO WORKFLOW SYSTEM: No executable workflow engine.
7. LINTER FIX LOOP LIMIT: 3-attempt limit could leave issues unresolved.

## CROSS-REFERENCE CONNECTIONS

1. RELATED TO ANTIGRAVITY: Both are pair programming AI coding assistants. Antigravity has superior knowledge persistence (KI system), while Cursor Agent emphasizes autonomous task resolution.
2. CONTRAST WITH V0: v0 is a Prototyping AI focused on Vercel's ecosystem; Cursor Agent is a Development AI focused on codebase navigation.
3. INDUSTRY POSITION: Cursor Agent represents the mainstream AI coding assistant paradigm.

## WISDOM DENSITY ANALYSIS

The Cursor Agent v2.0 system prompt has a wisdom density of approximately 12% (moderately concentrated). Key high-density sections: Tool Calling rules (25%), Context Understanding (30%), Code Citing rules (35%), Task Management (20%).

## IMPLEMENTATION PATTERNS

1. SEMANTIC SEARCH FIRST: Begin with broad semantic queries, narrow based on results.
2. PARALLEL EXECUTION: Run all independent tool calls simultaneously.
3. TASK DECOMPOSITION: Break complex tasks into tracked subtasks.
4. CODE REFERENCING DUALITY: Different formats for existing vs. new code.
5. FAILURE RECOVERY: After failed edit, re-read file. After 3 linter attempts, ask user.
6. MEMORY DISCIPLINE: Only create memories when explicitly asked.

## RECOMMENDED EXTENSIONS

1. ADD KNOWLEDGE PERSISTENCE: KI-like system for automatic knowledge accumulation.
2. ADD WORKFLOW ENGINE: Support executable workflow files.
3. ADD BROWSER SUBAGENT: Browser automation capabilities.
4. IMPROVE CROSS-FILE REFACTORING: Better support for systematic refactoring.
5. ADD ERROR RECOVERY PROTOCOLS: Explicit retry strategies for common failures.

## META-ANALYSIS

Cursor Agent v2.0 represents a mature, practical design for AI coding assistants. Its most significant contribution is the careful balance between autonomy and structure. The system gives the agent unprecedented freedom to explore, plan, and execute while simultaneously imposing rigorous formatting standards, task management discipline, and failure recovery procedures.

The extensive use of examples (good vs. bad) throughout the tool definitions is a notable pedagogical approach. Each tool's documentation teaches correct usage through comparison, making the system prompt simultaneously a reference and a training document.

The dual-format code referencing system is a deceptively simple innovation with profound implications. By requiring different formats for existing vs. new code, the system prevents a class of rendering and context ambiguity issues that plague other AI coding assistants.

The edit_file architecture reveals a key insight: when delegating code changes to a less intelligent model, instructions must be extremely explicit, with all unchanged code clearly marked using `// ... existing code ...` placeholders.

Overall, Cursor Agent v2.0 is the most production-ready of the three analyzed systems. Its design philosophy reflects a deep understanding that AI agents need structure (rules, formats, task management) to balance autonomy with reliability. Every rule exists because the corresponding failure mode was observed in practice, making this a system hardened by real-world usage.