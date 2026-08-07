# Context7 MCP Server Integration Guide

## Method 1: Direct MCP Server Configuration

1. Edit your Agent Zero configuration file:
   ```yaml
   mcp_servers:
     context7:
       command: python
       args: ["/a0/usr/workdir/context7_mcp.py"]
       env:
         CONTEXT7_API_KEY: "ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"
   ```

2. Restart Agent Zero

## Method 2: Using MCP2CLI Plugin

If you have MCP2CLI installed:

```bash
# Configure MCP2CLI to use Context7
python -m a0.manage_plugin configure mcp2cli   --server context7   --command "python /a0/usr/workdir/context7_mcp.py"   --env CONTEXT7_API_KEY="ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"

# Enable the server
python -m a0.manage_plugin configure mcp2cli   --server context7   --enabled true
```

## Method 3: Manual Startup

Run the MCP server manually:
```bash
cd /a0/usr/workdir
CONTEXT7_API_KEY="ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07" python context7_mcp.py
```

## Available Tools

1. **context7_search_libraries**
   - Search for code libraries by name
   - Example: "Search for Next.js libraries about SSR"

2. **context7_get_documentation**
   - Get documentation and code snippets
   - Example: "Get documentation for Next.js about server-side rendering"

## Testing

Run the test suite:
```bash
cd /a0/usr/workdir
python test_context7_api.py
```
