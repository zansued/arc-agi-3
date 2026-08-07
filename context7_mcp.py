#!/usr/bin/env python3
"""
Context7 MCP Server for Agent Zero

This MCP server provides integration with Context7 API for code documentation search.
API Documentation: https://context7.com/api/v2/docs
"""

import os
import sys
import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    GetPromptResult,
    ListPromptsResult,
    Prompt,
    PromptArgument,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("context7-mcp")

# Context7 API configuration
CONTEXT7_API_BASE = "https://context7.com/api/v2"
CONTEXT7_API_KEY = os.environ.get("CONTEXT7_API_KEY", "ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07")

class Context7Client:
    """Client for Context7 API."""
    
    def __init__(self, api_key: str = CONTEXT7_API_KEY):
        self.api_key = api_key
        self.base_url = CONTEXT7_API_BASE
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    async def search_libraries(self, library_name: str, query: str = "") -> Dict[str, Any]:
        """Search for libraries by name and query."""
        params = {
            "libraryName": library_name,
            "query": query,
        }
        
        url = f"{self.base_url}/libs/search"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_context(self, library_id: str, query: str, response_type: str = "json") -> Dict[str, Any]:
        """Get documentation/context for a specific library."""
        params = {
            "libraryId": library_id,
            "query": query,
            "type": response_type,
        }
        
        url = f"{self.base_url}/context"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

async def main():
    """Main function to run the MCP server."""
    
    # Initialize MCP server
    server = Server("context7-mcp")
    context7_client = Context7Client()
    
    @server.list_tools()
    async def handle_list_tools() -> List[Tool]:
        """List available tools."""
        return [
            Tool(
                name="context7_search_libraries",
                description="Search for code libraries on Context7 by name and query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "library_name": {
                            "type": "string",
                            "description": "Name of the library to search for (e.g., 'next.js', 'react', 'django')",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query to rank results by relevance (e.g., 'setup ssr', 'authentication', 'state management')",
                        },
                    },
                    "required": ["library_name"],
                },
            ),
            Tool(
                name="context7_get_documentation",
                description="Get documentation and code snippets for a specific library from Context7",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "library_id": {
                            "type": "string",
                            "description": "Library ID from search results (e.g., '/vercel/next.js')",
                        },
                        "query": {
                            "type": "string",
                            "description": "Question or task to get documentation for (e.g., 'setup ssr', 'authentication', 'state management')",
                        },
                        "response_type": {
                            "type": "string",
                            "enum": ["txt", "json"],
                            "default": "json",
                            "description": "Response format (txt or json)",
                        },
                    },
                    "required": ["library_id", "query"],
                },
            ),
        ]
    
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls."""
        try:
            if name == "context7_search_libraries":
                library_name = arguments.get("library_name", "")
                query = arguments.get("query", "")
                
                if not library_name:
                    raise ValueError("library_name is required")
                
                logger.info(f"Searching libraries: {library_name}, query: {query}")
                result = await context7_client.search_libraries(library_name, query)
                
                # Format the response
                formatted_result = _format_search_results(result)
                return [
                    TextContent(
                        type="text",
                        text=formatted_result,
                    )
                ]
                
            elif name == "context7_get_documentation":
                library_id = arguments.get("library_id", "")
                query = arguments.get("query", "")
                response_type = arguments.get("response_type", "json")
                
                if not library_id or not query:
                    raise ValueError("library_id and query are required")
                
                logger.info(f"Getting documentation: {library_id}, query: {query}")
                result = await context7_client.get_context(library_id, query, response_type)
                
                # Format the response
                formatted_result = _format_documentation_results(result, library_id, query)
                return [
                    TextContent(
                        type="text",
                        text=formatted_result,
                    )
                ]
            
            else:
                raise ValueError(f"Unknown tool: {name}")
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            return [
                TextContent(
                    type="text",
                    text=f"Error: {error_msg}",
                )
            ]
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            return [
                TextContent(
                    type="text",
                    text=f"Error: {error_msg}",
                )
            ]
    
    def _format_search_results(self, result: Dict[str, Any]) -> str:
        """Format search results for display."""
        if not result.get("results"):
            return "No libraries found."
        
        formatted = "## Context7 Library Search Results\n\n"
        
        for i, lib in enumerate(result["results"], 1):
            formatted += f"### {i}. {lib.get('title', 'Unknown')}\n"
            formatted += f"- **ID**: `{lib.get('id', 'N/A')}`\n"
            formatted += f"- **Description**: {lib.get('description', 'No description')}\n"
            formatted += f"- **Branch**: {lib.get('branch', 'N/A')}\n"
            formatted += f"- **Last Update**: {lib.get('lastUpdateDate', 'N/A')}\n"
            formatted += f"- **State**: {lib.get('state', 'N/A')}\n"
            formatted += f"- **Total Tokens**: {lib.get('totalTokens', 0):,}\n"
            formatted += f"- **Total Snippets**: {lib.get('totalSnippets', 0):,}\n"
            formatted += f"- **Stars**: {lib.get('stars', 0):,}\n"
            formatted += f"- **Trust Score**: {lib.get('trustScore', 0)}/10\n"
            formatted += f"- **Benchmark Score**: {lib.get('benchmarkScore', 0)}%\n"
            
            versions = lib.get("versions", [])
            if versions:
                formatted += f"- **Versions**: {', '.join(versions[:3])}"
                if len(versions) > 3:
                    formatted += f" (+{len(versions)-3} more)"
                formatted += "\n"
            
            formatted += "\n"
        
        return formatted
    
    def _format_documentation_results(self, result: Dict[str, Any], library_id: str, query: str) -> str:
        """Format documentation results for display."""
        formatted = f"## Context7 Documentation for `{library_id}`\n"
        formatted += f"**Query**: {query}\n\n"
        
        code_snippets = result.get("codeSnippets", [])
        info_snippets = result.get("infoSnippets", [])
        
        if not code_snippets and not info_snippets:
            formatted += "No documentation found for this query.\n"
            return formatted
        
        # Format code snippets
        if code_snippets:
            formatted += "### Code Snippets\n\n"
            for i, snippet in enumerate(code_snippets, 1):
                formatted += f"#### {i}. {snippet.get('codeTitle', 'Untitled')}\n"
                formatted += f"{snippet.get('codeDescription', '')}\n\n"
                
                code_list = snippet.get("codeList", [])
                for code_item in code_list:
                    language = code_item.get("language", "text")
                    code = code_item.get("code", "")
                    
                    formatted += f"```{language}\n{code}\n```\n\n"
                
                formatted += f"*Page: {snippet.get('pageTitle', 'Unknown')}*\n"
                formatted += f"*ID: {snippet.get('codeId', 'N/A')}*\n\n"
        
        # Format info snippets
        if info_snippets:
            formatted += "### Information Snippets\n\n"
            for i, info in enumerate(info_snippets, 1):
                formatted += f"#### {i}. {info.get('breadcrumb', 'Information')}\n"
                formatted += f"{info.get('content', '')}\n\n"
                formatted += f"*Page ID: {info.get('pageId', 'N/A')}*\n\n"
        
        return formatted
    
    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="context7-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())