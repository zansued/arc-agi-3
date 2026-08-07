# EXTRACT WISDOM: V0 PROMPTS AND TOOLS (VERCEL)

## CORE IDENTITY

v0 is Vercel's highly skilled AI-powered prototyping assistant that follows best practices. Unlike traditional coding assistants focused on codebase navigation, v0 is a Prototyping AI - designed to generate complete, production-quality applications from scratch, with deep integration into the Vercel ecosystem (Next.js, shadcn/ui, Tailwind CSS, Vercel AI SDK). The system treats design as a first-class concern with mobile-first priority and strict aesthetic rules.

## CORE MESSAGE

v0 is Vercel's AI-powered assistant for building complete, visually refined web applications with mobile-first priority. The system is design-centric (uses GenerateDesignInspiration before UI work, strict color/typography rules), Vercel-native (first-class support for Next.js, AI SDK, Supabase), and prototyping-focused (generate complete apps from scratch). Users cannot run terminal commands - execution happens through structured tool calls and scripts. The system ships interesting rather than boring, but never ugly.

## ARCHITECTURE INSIGHTS

### 1. DESIGN-FIRST ARCHITECTURE

Unlike most AI coding assistants, v0 puts design rules explicitly and unambiguously in the prompt. Design is not an afterthought - it is a primary architectural concern with specific, non-negotiable rules:

- Maximum 2-3 color stops in gradients, no complex gradients
- Maximum 2 font families total
- Use line-height between 1.4-1.6 for body text, 1.0-1.1 for headings
- NEVER use decorative fonts for body text
- NEVER use fonts smaller than 14px
- Mobile-first priority: mobile is the PRIMARY experience
- Semantic design tokens generated from user's prompt
- Tailwind spacing scale preferred over arbitrary values
- Gap classes preferred over margin/padding for spacing
- NEVER mix margin/padding with gap classes
- NEVER use space-* classes for spacing
- NEVER use emojis as replacements for proper icons

### 2. SYSTEMATIC CONTEXT GATHERING

The prompt enforces a rigorous search methodology:
1. Start broad (Glob/Grep/Read)
2. Don't stop at the first match - explore alternatives
3. Understand the full system before making changes
4. Check if a parent/wrapper already handles something
5. Look for existing utilities/patterns before creating new ones

This reflects a deep understanding that AI mistakes most often come from incomplete context.

### 3. PLAN-BEFORE-ACTION WORKFLOW

v0 uses EnterPlanMode as a formal planning step for complex tasks. Plans must include:
- Component tree / data flow
- Route design (if applicable)
- Database schema consideration
- Alternative approaches considered

This is a user-approval-gated workflow - the plan is presented to the user before execution.

### 4. PARALLEL TOOL EXECUTION

Like Cursor Agent, v0 prioritizes parallel tool calls: "Use Parallel Tool Calls Where Possible." Multiple independent tool calls should be executed simultaneously for maximum efficiency.

### 5. SCRIPT-BASED EXECUTION

Unlike terminal-centric assistants, v0 uses a /scripts folder for code execution:
- Python: uv init and uv add for package management
- Node.js: npm or pnpm for package management
- SQL: For data persistence and queries
- File paths must use path.join() for cross-platform compatibility

### 6. TEMPLATE SYSTEM

v0 has an extensive template system in user_read_only_context directory. These high-quality example components and templates should be searched and imported rather than built from scratch. The Import (Move with operation="copy") tool copies read-only files into the project.

### 7. DESIGN INSPIRATION PIPELINE

Before building any UI, v0 uses GenerateDesignInspiration to create design proposals. After generating design inspiration, the system presents options to the user. This formalizes design exploration as a required step before implementation.

### 8. TOOL CALLING NAMESPACE

v0 uses a different tool calling convention than Cursor Agent. Tools are called as function invocations with explicit parameters, not JSON objects. Examples:
- Glob(pattern="**/*.tsx", path="/project/src")
- Grep(pattern="function ", include="*.ts")
- Read(filePath="/project/src/app.tsx")
- GenerateDesignInspiration(draft="A landing page with hero, features, and footer")
- EnterPlanMode()
- AskUserQuestions(questions=[{question: "What is your preferred color scheme?"}])
- WebSearch(query="latest shadcn/ui components")
- GetOrRequestIntegration(id="@vercel/supabase")
- TodoManager(tasks=[{content: "Set up database", status: "pending"}])
- SystemAction(action="setEnvironmentVariable", key="DATABASE_URL", value="postgres://...")

### 9. REFUSAL ARCHITECTURE

v0 has a uniquely concise refusal protocol. For hateful, inappropriate, or unethical content, the response is exactly: "I'm not able to assist with that." - no explanation, no apology, no alternative suggestions. This is a deliberate design choice to minimize engagement with harmful requests.

### 10. DEBUG METHODOLOGY

Debugging is treated as a formal process with documented best practices:
- Use console.log("[v0] ...") for structured debug output
- "v0" prefix enables filtering in browser dev tools
- Check component props and state first
- Log network request payloads
- Log state before and after operations

## KEY RULES

### DESIGN RULES

Rule 1 - MAX 2-3 COLOR STOPS: No complex gradients. Keep palettes simple.

Rule 2 - MAX 2 FONT FAMILIES: One display + one body maximum.

Rule 3 - LINE HEIGHT: Body text 1.4-1.6, headings 1.0-1.1.

Rule 4 - NO DECORATIVE FONTS FOR BODY TEXT: Display fonts only for headlines.

Rule 5 - NO FONTS SMALLER THAN 14PX: Accessibility minimum.

Rule 6 - MOBILE-FIRST: Mobile is PRIMARY experience. Desktop is secondary.

Rule 7 - TAILWIND SPACING SCALE: Prefer over arbitrary values.

Rule 8 - GAP CLASSES PREFERRED: For flexbox/grid spacing.

Rule 9 - NEVER MIX MARGIN/PADDING WITH GAP: Choose one system.

Rule 10 - NEVER USE SPACE-* CLASSES: They're deprecated in modern Tailwind.

Rule 11 - NEVER USE EMOJIS AS ICONS: Use proper SVG icons.

### DATA RULES

Rule 12 - NO LOCAL STORAGE: NEVER use localStorage for data persistence unless explicitly requested by user.

Rule 13 - NO MOCK AUTH: NEVER implement mock authentication or client-side only auth patterns.

Rule 14 - REAL AUTH: Use Supabase Auth, NextAuth.js, or Clerk.

### BEHAVIORAL RULES

Rule 15 - SHIP INTERESTING: Rather than boring, but never ugly.

Rule 16 - REFERRENCE ALL GUIDELINES: Use best judgment.

Rule 17 - POSTAMBLE REQUIRED: Write 2-4 sentences postamble at the end.

Rule 18 - REFUSAL BREVITY: "I'm not able to assist with that." No explanation.

Rule 19 - DON'T STOP AT FIRST MATCH: Search comprehensively.

Rule 20 - UNDERSTAND FULL SYSTEM: Before making changes.

Rule 21 - CHECK PARENT/WRAPPER: For already-handled functionality.

Rule 22 - LOOK FOR EXISTING PATTERNS: Before creating new utilities.

### TOOL RULES

Rule 23 - PARALLEL TOOL CALLS: Execute independent calls simultaneously.

Rule 24 - PLAN BEFORE ACTION: Use EnterPlanMode for complex tasks.

Rule 25 - GENERATE DESIGN INSPIRATION: Before any UI work.

Rule 26 - IMPORT READ-ONLY FILES: Use Move operation="copy" from user_read_only_context.

Rule 27 - SAVE IMAGES TO FILESYSTEM: Download blob URLs to local paths.

Rule 28 - REFERENCE IMAGES LOCALLY: Use local paths in code, not blob URLs.

Rule 29 - PYTHON SCRIPTS: Use uv init --bare <path> then uv add <deps>.

Rule 30 - FILE PATHS: Use path.join() for cross-platform compatibility.

Rule 31 - NO TERMINAL ACCESS BY USERS: Execution through scripts only.

Rule 32 - AI SDK: Use Vercel AI SDK and Server Components where possible.

## TOOLS & CAPABILITIES

### CONTEXT GATHERING

1. GLOB: File pattern matching. Glob(pattern="**/*.tsx", path="/project/src"). Searches for files by name patterns.

2. GREP: Content search. Grep(pattern="function ", include="*.ts"). Searches file contents by regex patterns.

3. READ: File reading. Read(filePath="/project/src/app.tsx"). Reads file contents into context.

### DESIGN & PLANNING

4. GENERATE_DESIGN_INSPIRATION: Pre-build design exploration. GenerateDesignInspiration(draft="..."). Creates design proposals before implementation.

5. ENTER_PLAN_MODE: Formal planning step. EnterPlanMode(). Used for complex tasks requiring user-approved plans.

### USER INTERACTION

6. ASK_USER_QUESTIONS: Clarification tool. AskUserQuestions(questions=[{question: "..."}]). Used when clarification is needed.

### RESEARCH

7. WEB_SEARCH: Real-time web search. WebSearch(query="..."). Used with first-party flag for up-to-date information.

### INTEGRATIONS

8. GET_OR_REQUEST_INTEGRATION: Database/service connections. GetOrRequestIntegration(id="@vercel/supabase"). Enables zero-config integration with Vercel partner services.

### PROJECT MANAGEMENT

9. TODO_MANAGER: Task tracking. TodoManager(tasks=[{content: "...", status: "..."}]). Tracks project progress.

### CONFIGURATION

10. SYSTEM_ACTION: Configuration operations. SystemAction(action="setEnvironmentVariable", key="...", value="..."). Manages environment variables and system settings.

### FILE OPERATIONS

11. MOVE: File operations. Move(taskNameActive="...", taskNameComplete="...", operation="copy", source_path="...", destination_path="..."). Copies read-only template files into the project.

12. WRITE: File creation/writing. Creates and modifies files.

13. GENERATE_IMAGE: Image generation. Creates images for projects.

## WORKFLOWS

### 1. PROJECT BOOTSTRAPPING WORKFLOW

1. User provides high-level description of desired application
2. GenerateDesignInspiration creates initial design proposals
3. Present design options to user for approval
4. Once approved, use EnterPlanMode for complex projects
5. Plan includes component tree, data flow, routes, schema
6. Execute plan using parallel tool calls
7. Implement mobile-first, then enhance for desktop
8. Generate postamble (2-4 sentences)

### 2. DESIGN EXPLORATION WORKFLOW

1. Receive design request from user
2. GenerateDesignInspiration with draft describing the design
3. Review generated design options
4. Present to user for feedback/approval
5. Apply strict design rules (color stops, fonts, spacing)
6. Use semantic design tokens from prompt context
7. Implement with Tailwind CSS following layout method priority
8. Mobile-first: primary experience, desktop enhancement secondary

### 3. CONTEXT GATHERING WORKFLOW

1. Start with Glob to find relevant files
2. Use Grep to search for specific patterns
3. Read short-listed files with Read
4. Don't stop at the first match
5. Understand parent/wrapper context
6. Check for existing utilities before creating new ones
7. Use parallel tool calls for independent searches

### 4. DATABASE INTEGRATION WORKFLOW

1. User requests database/integration
2. Use GetOrRequestIntegration with the appropriate service ID
3. SystemAction to set environment variables
4. Create migration scripts in /scripts folder
5. Use SQL queries for data operations
6. Never implement mock auth or client-side auth
7. Use real authentication (Supabase Auth, NextAuth.js, Clerk)

### 5. DEBUGGING WORKFLOW

1. Identify the issue from user report or error
2. Add console.log("[v0] ...") statements at key points
3. Check component props and state
4. Log network request payloads
5. Log state before and after operations
6. Use structured debug prefix [v0] for filtering
7. Isolate the issue and fix
8. Remove debug statements after resolution

### 6. IMPORT WORKFLOW

1. Identify user_read_only_context for example components
2. Search for matching templates using Glob/Grep
3. Use Move(operation="copy") with source_path and destination_path
4. Reference imported components in new code
5. Do not modify read-only source files

### 7. REFUSAL WORKFLOW

1. Detect hateful, inappropriate, or unethical content
2. Respond with EXACTLY: "I'm not able to assist with that."
3. Do not explain why or provide alternatives
4. Do not apologize
5. End the exchange immediately

## WISDOM EXTRACTS

1. "Ship interesting rather than boring, but never ugly." - A design philosophy that balances innovation with quality. The system explicitly encourages creative risk-taking within quality boundaries.

2. "Mobile is the PRIMARY experience - desktop is secondary. Design mobile-first, then enhance for larger screens." - A strong opinionated stance on responsive design, reflecting modern web development best practices.

3. "Use Max 2-3 color stops in gradients. Max 2 font families. NEVER use decorative fonts for body text." - Concrete, non-negotiable design constraints that prevent common aesthetic failures.

4. "NEVER use localStorage for data persistence unless explicitly requested by user. NEVER implement mock authentication or client-side only auth patterns." - Absolute prohibitions against insecure patterns, reflecting production-quality standards.

5. "Don't stop at the first match. Understand the full system before making changes. Check if a parent/wrapper already handles something." - Systematic context gathering methodology that prevents incomplete understanding.

6. "Use Parallel Tool Calls Where Possible. Do this even if the prompt suggests using tools sequentially." - Performance-first design: parallel execution is the default.

7. "Respond with ONLY: 'I'm not able to assist with that.' - no explanation, no apology, no alternatives." - A uniquely concise refusal protocol that minimizes engagement with harmful requests.

8. "Generate design inspiration before building UI. Use GenerateDesignInspiration to create design proposals." - Formalizing design exploration as a required step before implementation.

9. "Write postamble of 2-4 sentences." - A consistent response format that ensures closure and engagement.

10. "Design tokens should be generated from the prompt's content, creating a semantic and cohesive design system." - Treating design tokens as derived from context, not as arbitrary choices.

11. "Use debug statements with the prefix [v0] for easy filtering in the browser's dev tools." - A structured debugging convention that enables rapid issue isolation.

12. "For data persistence, use Vercel integrations like Supabase, or enterprise services that follow security best practices." - Production-grade data persistence philosophy.

## PRACTICAL RECOMMENDATIONS

1. TREAT DESIGN AS CODE: Put design rules explicitly in system prompts. Don't assume the AI knows what good design looks like - define it concretely.

2. ENFORCE CONTENT RULES: Maximum 2-3 color stops, maximum 2 font families - these concrete constraints prevent common design failures.

3. MOBILE-FIRST BY DEFAULT: Declare mobile as primary experience. AI assistants tend to default to desktop layouts.

4. BAN INSECURE PATTERNS: Explicitly prohibit localStorage, mock auth, and client-only auth. These are common AI-generated security vulnerabilities.

5. USE FORMAL PLANNING: EnterPlanMode for complex tasks. Planning before execution dramatically reduces rework.

6. PARALLELIZE EVERYTHING: Make parallel execution the default, not the exception.

7. REFUSAL WITHOUT ENGAGEMENT: The "I'm not able to assist with that." pattern without apology or explanation is the most effective refusal protocol.

8. DESIGN EXPLORATION AS REQUIRED STEP: Use GenerateDesignInspiration before UI work to prevent blind implementation.

9. SYSTEMATIC SEARCH METHODOLOGY: Teach search as a methodology (broad -> narrow -> verify), not just as tool usage.

10. SCRIPT-BASED EXECUTION: /scripts folder for code execution instead of terminal access provides better auditability and reproducibility.

11. TEMPLATE REUSE: Maintain a user_read_only_context directory with high-quality example components.

12. STRUCTURED DEBUGGING: Formal debug methodology with [v0] prefix convention.

## KEY LESSONS

1. DESIGN RULES MUST BE EXPLICIT AND NON-NEGOTIABLE: Vague aesthetic guidance fails. Concrete rules (max 2 fonts, max 3 color stops, mobile-first) produce consistently good output.

2. SECURITY RULES MUST BE ABSOLUTE: "NEVER" rules about localStorage, mock auth, and client-only auth prevent entire classes of security vulnerabilities.

3. SEARCH METHODOLOGY TRUMPS TOOL KNOWLEDGE: Teaching systematic search methodology (broad -> specific -> verify) is more valuable than listing search tools.

4. PARALLEL EXECUTION IS A FORCE MULTIPLIER: The explicit instruction to use parallel calls even when sequential is suggested shows performance priority.

5. DESIGN EXPLORATION IS NOT OPTIONAL: GenerateDesignInspiration before UI work prevents wasted implementation effort on wrong designs.

6. REFUSAL PROTOCOLS NEED BREVITY: Long explanations for refusals can be exploited. The 8-word refusal is maximally effective.

7. PLANNING REQUIRES USER APPROVAL: EnterPlanMode with user approval gates prevents wasted work on misunderstood requirements.

8. TEMPLATES ACCELERATE QUALITY: High-quality templates in user_read_only_context provide a strong foundation that reduces errors.

9. ECOSYSTEM INTEGRATION IS COMPETITIVE ADVANTAGE: First-class Vercel integration (Supabase, AI SDK, Next.js) makes v0 uniquely valuable within its ecosystem.

10. DEBUGGING SHOULD BE FORMALIZED: Treating debugging as a methodology with conventions ([v0] prefix) improves output quality.

## EXECUTIVE SUMMARY

v0 by Vercel is a design-centric, prototyping-focused AI coding assistant that generates complete web applications from scratch. Unlike traditional coding assistants focused on codebase navigation, v0 treats visual design as a first-class concern with strict rules (max 2 fonts, mobile-first, proper spacing). The system excels at rapid prototyping within the Vercel ecosystem (Next.js, shadcn/ui, Tailwind CSS, AI SDK). Its architecture emphasizes systematic context gathering (broad -> specific -> verify), formal planning (EnterPlanMode), parallel execution, and template reuse. Security is enforced through absolute prohibitions against insecure patterns. The system's unique refusal protocol (8 words, no explanation) and formal design exploration step (GenerateDesignInspiration) distinguish it from other AI coding assistants.

## KNOWN GAPS AND LIMITATIONS

1. ECOSYSTEM LOCK-IN: Deep integration with Vercel limits applicability outside the Vercel ecosystem.
2. NO TERMINAL ACCESS: Users cannot run arbitrary commands. All execution is through scripts.
3. PROTOTYPING FOCUS: Less suitable for modifying existing codebases vs. generating new applications.
4. NO MEMORY SYSTEM: No equivalent of Cursor's update_memory or Antigravity's KI system.
5. NO SUBAGENT ARCHITECTURE: No specialized subagents for parallel work.
6. TEMPLATE DEPENDENCY: Quality depends heavily on the template library quality.
7. USER APPROVAL GATES: EnterPlanMode requires user approval, slowing down experienced users.
8. NO CODEBASE NAVIGATION: Designed for greenfield projects, not existing codebase exploration.

## CROSS-REFERENCE CONNECTIONS

1. VS CURSOR AGENT: Cursor Agent is codebase-centric (navigate/modify existing code). v0 is prototype-centric (generate new applications from scratch).

2. VS ANTIGRAVITY: Antigravity has sophisticated knowledge management (KI system). v0 has sophisticated design management (design inspiration + rules).

3. VS MANUS: Manus is generalist with browser capabilities. v0 is specialized in Vercel web development.

4. UNIQUE STRENGTHS: v0's design rules are the most concrete and enforceable of all analyzed systems. Its refusal protocol is the most concise.

## WISDOM DENSITY ANALYSIS

The v0 system prompt has a wisdom density of approximately 15% (highest among the three analyzed). Key high-density sections:
- Design Rules: 40% density - extremely prescriptive, specific, and actionable
- Refusal Protocol: 50% density - maximally efficient, zero ambiguity
- Search Methodology: 30% density - systematic and teachable
- Security Rules: 45% density - absolute prohibitions that prevent entire attack classes

The prompt balances prescriptive rules with procedural workflows, making it simultaneously instructive and enforceable.

## IMPLEMENTATION PATTERNS

1. DESIGN-FIRST: GenerateDesignInspiration before any UI work. Apply strict design rules.
2. SYSTEMATIC SEARCH: Broad -> specific -> verify relationships.
3. PLAN-BEFORE-ACTION: EnterPlanMode for complex tasks.
4. PARALLEL EXECUTION: Run independent calls simultaneously.
5. TEMPLATE REUSE: Import from user_read_only_context.
6. SCRIPT-BASED EXECUTION: /scripts folder for all code execution.
7. STRUCTURED DEBUGGING: [v0] prefix convention.
8. CONCISE REFUSAL: 8 words, no explanation.

## RECOMMENDED EXTENSIONS

1. ADD MEMORY SYSTEM: KI-like knowledge persistence across sessions.
2. ADD CODEBASE NAVIGATION: Support for existing codebases beyond prototypes.
3. ADD SUBAGENT ARCHITECTURE: Specialized subagents for testing, deployment.
4. ADD TERMINAL ACCESS: Optional terminal access for advanced users.
5. ADD COLLABORATIVE MODE: Multiple v0 agents on complex projects.
6. ADD CROSS-ECOSYSTEM SUPPORT: Beyond Vercel to general web development.
7. ADD VERSION CONTROL: Integration with Git workflows.

## META-ANALYSIS

v0 represents a fundamentally different approach to AI coding assistance compared to Cursor Agent and Antigravity. Where Cursor Agent is a scalpel for existing codebases, v0 is a 3D printer for new applications. The system's design-centric philosophy, formal planning workflow, and ecosystem integration strategy are its most distinctive contributions.

The decision to put explicit design rules in the system prompt (rather than relying on the model's inherent aesthetic sense) is a recognition that LLMs, while powerful, lack consistent visual judgment. The rules are concrete enough to be enforceable but flexible enough to allow creativity.

The refusal protocol is perhaps the most elegant element of the system. By responding with exactly "I'm not able to assist with that." without explanation, apology, or alternative, the system achieves maximum efficiency in rejecting harmful requests while providing zero surface area for prompt injection or argument.

The script-based execution model (/scripts folder) is a security-conscious design choice that provides auditability and reproducibility. While it limits user flexibility, it prevents the most common AI agent failure modes around arbitrary system commands.

Overall, v0 is the most opinionated of the three analyzed systems - and that opinionatedness is its greatest strength. By committing deeply to the Vercel ecosystem, mobile-first design, and concrete quality standards, v0 delivers consistently high-quality output within its domain.

## FALA FINAL

v0 prova que opiniao e melhor que neutralidade. Ao se comprometer profundamente com design, ecossistema Vercel e padroes concretos de qualidade, v0 entrega resultados superiores em seu dominio do que assistentes genericos jamais conseguiriam.

A verdadeira sabedoria do v0 nao esta nas ferramentas (Glob, Grep, Read - todas comuns). Esta no SISTEMA DE DESIGN como disciplina formal: gerar inspiracao antes de implementar, aplicar regras concretas de cor e tipografia, priorizar mobile, nunca comprometer seguranca.

A regra de 2-3 stops de gradiente pode parecer arbitraria, mas e uma barreira contra o design ruim gerado por IA. Cada regra de design e uma defesa contra um modo de falha especifico. E isso e o que torna v0 verdadeiramente valioso: ele nao apenas gera codigo - ele gera DESIGN.

Se Cursor Agent e sobre navegar o desconhecido, v0 e sobre construir o novo. E construcao precisa de fundacao solida - regras, templates, inspiracao, planejamento. E tudo isso v0 oferece em abundancia.