# Context7 MCP Server for Agent Zero

A Model Context Protocol (MCP) server that integrates Context7 API with Agent Zero for intelligent code documentation search.

## Features

- **Search Libraries**: Find code libraries by name and query
- **Get Documentation**: Retrieve code snippets and documentation for specific libraries
- **Intelligent Context**: Get relevant documentation based on your development queries
- **MCP Integration**: Native integration with Agent Zero's tool system

## API Overview

Context7 provides intelligent code documentation search with two main endpoints:

### 1. Search Libraries
```bash
GET /api/v2/libs/search?libraryName=next.js&query=setup+ssr
Authorization: Bearer YOUR_API_KEY
```

### 2. Get Context/Documentation
```bash
GET /api/v2/context?libraryId=/vercel/next.js&query=setup+ssr&type=json
Authorization: Bearer YOUR_API_KEY
```

## Installation

### Prerequisites
- Python 3.8+
- Agent Zero installed and running
- Context7 API Key (provided: `ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07`)

### Step 1: Install Dependencies
```bash
cd /a0/usr/workdir
pip install -r requirements_context7.txt
```

### Step 2: Test the API Connection
```bash
python test_context7_api.py
```

Expected output:
```
✅ API key is valid! Status: 200
✅ Search successful! Status: 200
✅ Documentation retrieval successful! Status: 200
```

### Step 3: Run the MCP Server
```bash
python context7_mcp.py
```

The server will start in stdio mode, ready to accept connections from Agent Zero.

## Integration with Agent Zero

### Method 1: Direct MCP Server Integration

1. **Configure Agent Zero to use the MCP server:**
   - Edit Agent Zero configuration
   - Add the Context7 MCP server to the MCP servers list

2. **Example configuration:**
```yaml
mcp_servers:
  context7:
    command: python
    args: ["/a0/usr/workdir/context7_mcp.py"]
    env:
      CONTEXT7_API_KEY: "ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"
```

### Method 2: Using MCP2CLI Plugin

If you have the MCP2CLI plugin installed:

1. **Configure MCP2CLI to use Context7:**
```bash
# Configure MCP2CLI settings
python -m a0.manage_plugin configure mcp2cli \
  --server context7 \
  --command "python /a0/usr/workdir/context7_mcp.py" \
  --env CONTEXT7_API_KEY="ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"
```

2. **Enable the server in MCP2CLI:**
```bash
python -m a0.manage_plugin configure mcp2cli \
  --server context7 \
  --enabled true
```

## Available Tools

### 1. `context7_search_libraries`
Search for code libraries on Context7 by name and query.

**Parameters:**
- `library_name` (required): Name of the library to search for (e.g., 'next.js', 'react', 'django')
- `query` (optional): Search query to rank results by relevance (e.g., 'setup ssr', 'authentication', 'state management')

**Example usage in Agent Zero:**
```
Search for Next.js libraries about SSR
```

### 2. `context7_get_documentation`
Get documentation and code snippets for a specific library from Context7.

**Parameters:**
- `library_id` (required): Library ID from search results (e.g., '/vercel/next.js')
- `query` (required): Question or task to get documentation for (e.g., 'setup ssr', 'authentication', 'state management')
- `response_type` (optional): Response format ('txt' or 'json', default: 'json')

**Example usage in Agent Zero:**
```
Get documentation for Next.js about server-side rendering
```

## Usage Examples

### Example 1: Search for React Libraries
```
Use context7_search_libraries to find React libraries about state management
```

### Example 2: Get Documentation for Django
```
First search for Django libraries, then use context7_get_documentation with the library ID to get authentication documentation
```

### Example 3: Complete Development Workflow
```
1. Search for 'next.js' libraries
2. Get the library ID from results
3. Get documentation for 'setup ssr'
4. Use the code snippets in your project
```

## Testing

### Run Complete Test Suite
```bash
python test_context7_api.py
```

### Test Individual Components
```bash
# Test API key only
python -c "
import httpx
import asyncio

async def test():
    headers = {'Authorization': 'Bearer ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07'}
    async with httpx.AsyncClient() as client:
        response = await client.get('https://context7.com/api/v2/libs/search?libraryName=react', headers=headers)
        print(f'Status: {response.status_code}')
        print(f'Valid: {response.status_code == 200}')

asyncio.run(test())
"
```

## Troubleshooting

### Common Issues

1. **API Key Invalid**
   - Error: `401 Unauthorized`
   - Solution: Verify your API key is correct

2. **Server Not Starting**
   - Error: `ModuleNotFoundError: No module named 'mcp'`
   - Solution: Install dependencies: `pip install -r requirements_context7.txt`

3. **Connection Timeout**
   - Error: `TimeoutError`
   - Solution: Check internet connection and Context7 API status

4. **Agent Zero Not Recognizing Tools**
   - Error: Tools not appearing in Agent Zero
   - Solution: Ensure MCP server is properly configured in Agent Zero settings

### Debug Mode

Enable debug logging:
```bash
CONTEXT7_DEBUG=1 python context7_mcp.py
```

## Performance Tips

1. **Cache Results**: The MCP server doesn't cache by default. Consider implementing caching for frequent queries.
2. **Batch Searches**: Combine multiple related queries into single searches when possible.
3. **Use Specific Queries**: More specific queries yield better results.

## Security Considerations

1. **API Key Protection**:
   - Store API key in environment variables
   - Never commit API keys to version control
   - Use Agent Zero's secure configuration system

2. **Network Security**:
   - The MCP server runs locally
   - All API calls are encrypted (HTTPS)
   - No sensitive data is stored locally

## Development

### Project Structure
```
/a0/usr/workdir/
├── context7_mcp.py          # Main MCP server
├── test_context7_api.py     # API test suite
├── requirements_context7.txt # Dependencies
├── README_CONTEXT7.md       # This file
└── config_example.yaml      # Example configuration
```

### Extending the Server

To add new tools or modify existing ones:

1. Edit `context7_mcp.py`
2. Add new tool definitions in `handle_list_tools()`
3. Implement tool logic in `handle_call_tool()`
4. Test with `python test_context7_api.py`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## License

This MCP server is provided under the MIT License.

## Support

- **Context7 API Documentation**: https://context7.com/api/v2/docs
- **Agent Zero Documentation**: https://www.agent-zero.ai/docs
- **MCP Specification**: https://spec.modelcontextprotocol.io

## Acknowledgments

- Context7 for providing the excellent code documentation API
- The Model Context Protocol team for the MCP specification
- Agent Zero community for integration support