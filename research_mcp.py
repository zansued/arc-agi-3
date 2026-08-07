#!/usr/bin/env python3
"""
Research MCP Server — Unifies ArXiv + WolframAlpha

Exposes tools:
  - arxiv_search(query, max_results=5, categories=None)
  - wolfram_query(input_query, format="plaintext")
  - unified_research(topic, max_papers=3)

Transport: stdio (FastMCP)

Environment:
  WOLFRAMALPHA_APP_ID - WolframAlpha App ID (87WY7VE4WV)
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from mcp.server.fastmcp import FastMCP

# ── WolframAlpha ──────────────────────────────────────────────

WOLFRAM_APP_ID = os.environ.get("WOLFRAMALPHA_APP_ID", "87WY7VE4WV")
WOLFRAM_URL = "https://api.wolframalpha.com/v2/query"


def wolfram_query(input_query: str, format: str = "plaintext") -> dict:
    """Query WolframAlpha Full Results API."""
    params = urllib.parse.urlencode({
        "appid": WOLFRAM_APP_ID,
        "input": input_query,
        "format": format
    })
    url = f"{WOLFRAM_URL}?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            root = ET.fromstring(body)
            success = root.get("success", "false")
            error = root.get("error", "false")
            pods = []
            for pod in root.findall(".//pod"):
                title = pod.get("title", "")
                texts = []
                for sub in pod.findall(".//subpod/plaintext"):
                    if sub.text:
                        texts.append(sub.text)
                pods.append({"title": title, "texts": texts})
            return {
                "success": success == "true",
                "error": error == "true",
                "numpods": len(pods),
                "pods": pods,
                "input": input_query
            }
    except Exception as e:
        return {"success": False, "error": True, "message": str(e), "input": input_query}


# ── ArXiv ─────────────────────────────────────────────────────


def arxiv_search(query: str, max_results: int = 5, categories: str | None = None) -> dict:
    """Search ArXiv academic papers."""
    try:
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        papers = []
        for r in client.results(search):
            papers.append({
                "title": r.title,
                "authors": [a.name for a in r.authors],
                "published": str(r.published.date()),
                "summary": r.summary[:500] + "..." if len(r.summary) > 500 else r.summary,
                "url": r.entry_id,
                "pdf_url": r.pdf_url,
                "categories": list(r.categories)
            })
        return {
            "success": True,
            "query": query,
            "total": len(papers),
            "papers": papers
        }
    except Exception as e:
        return {"success": False, "error": str(e), "query": query}


# ── MCP Server ────────────────────────────────────────────────

mcp = FastMCP(
    "research-mcp"
)


@mcp.tool()
def arxiv_search_tool(query: str, max_results: int = 5) -> str:
    """Search ArXiv for academic papers matching the query.

    Args:
        query: Search query (e.g. 'quantum computing', 'deep learning optimization')
        max_results: Maximum number of results (1-50, default 5)
    Returns:
        JSON string with paper titles, authors, publication dates, summaries, and URLs
    """
    result = arxiv_search(query, min(max_results, 50))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def wolfram_query_tool(input_query: str) -> str:
    """Query WolframAlpha computational knowledge engine.

    Args:
        input_query: Natural language query (e.g. 'gravitational constant',
                     'population of Brazil', 'solve x^2 - 4x + 3 = 0')
    Returns:
        JSON string with pods containing results
    """
    result = wolfram_query(input_query)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def unified_research_tool(topic: str, max_papers: int = 3) -> str:
    """Perform unified research on a topic: get computational knowledge + recent papers.

    Args:
        topic: Research topic or question
        max_papers: Maximum number of ArXiv papers to include (1-10, default 3)
    Returns:
        JSON string with WolframAlpha knowledge + ArXiv paper results
    """
    wolfram = wolfram_query(topic)
    papers = arxiv_search(topic, min(max_papers, 10))
    return json.dumps({
        "topic": topic,
        "wolframalpha": wolfram,
        "arxiv": papers,
        "summary": (
            f"WolframAlpha: {wolfram.get('numpods', 0)} pods, "
            f"ArXiv: {papers.get('total', 0)} papers"
        )
    }, ensure_ascii=False, indent=2)


# ── Main ──────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
