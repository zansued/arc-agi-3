#!/usr/bin/env python3
"""
Test script for Context7 API integration.
"""

import os
import sys
import json
import asyncio
import httpx

# API Configuration
CONTEXT7_API_KEY = "ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"
CONTEXT7_API_BASE = "https://context7.com/api/v2"

headers = {
    "Authorization": f"Bearer {CONTEXT7_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

async def test_search_libraries():
    """Test the libraries search endpoint."""
    print("🔍 Testing Context7 library search...")
    
    params = {
        "libraryName": "next.js",
        "query": "setup ssr",
    }
    
    url = f"{CONTEXT7_API_BASE}/libs/search"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ Search successful! Status: {response.status_code}")
            print(f"📊 Found {len(data.get('results', []))} libraries")
            
            if data.get("results"):
                for i, lib in enumerate(data["results"][:3], 1):
                    print(f"\n{i}. {lib.get('title', 'Unknown')}")
                    print(f"   ID: {lib.get('id', 'N/A')}")
                    print(f"   Description: {lib.get('description', 'No description')[:100]}...")
                    print(f"   Stars: {lib.get('stars', 0):,}")
                    print(f"   Trust Score: {lib.get('trustScore', 0)}/10")
            
            return True, data
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
        return False, None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False, None

async def test_get_context():
    """Test the context/documentation endpoint."""
    print("\n📚 Testing Context7 documentation retrieval...")
    
    # First, search for a library to get its ID
    search_success, search_data = await test_search_libraries()
    
    if not search_success or not search_data.get("results"):
        print("⚠️  Using fallback library ID for testing")
        library_id = "/vercel/next.js"
    else:
        library_id = search_data["results"][0].get("id", "/vercel/next.js")
    
    params = {
        "libraryId": library_id,
        "query": "setup ssr",
        "type": "json",
    }
    
    url = f"{CONTEXT7_API_BASE}/context"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ Documentation retrieval successful! Status: {response.status_code}")
            
            code_snippets = data.get("codeSnippets", [])
            info_snippets = data.get("infoSnippets", [])
            
            print(f"📝 Found {len(code_snippets)} code snippets and {len(info_snippets)} info snippets")
            
            if code_snippets:
                print("\n📋 Sample code snippet:")
                snippet = code_snippets[0]
                print(f"   Title: {snippet.get('codeTitle', 'Untitled')}")
                print(f"   Description: {snippet.get('codeDescription', '')[:100]}...")
                
                code_list = snippet.get("codeList", [])
                if code_list:
                    code_item = code_list[0]
                    language = code_item.get("language", "text")
                    code = code_item.get("code", "")
                    print(f"   Language: {language}")
                    print(f"   Code preview: {code[:100]}...")
            
            return True, data
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
        return False, None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False, None

async def test_api_key():
    """Test if the API key is valid."""
    print("🔑 Testing Context7 API key validity...")
    
    # Simple test with minimal parameters
    params = {
        "libraryName": "react",
        "query": "",
    }
    
    url = f"{CONTEXT7_API_BASE}/libs/search"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=10.0,
            )
            
            if response.status_code == 200:
                print(f"✅ API key is valid! Status: {response.status_code}")
                return True
            elif response.status_code == 401:
                print("❌ API key is invalid (401 Unauthorized)")
                return False
            else:
                print(f"⚠️  Unexpected status: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print(f"❌ Error testing API key: {str(e)}")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting Context7 API tests\n")
    
    # Test 1: API Key validity
    api_key_valid = await test_api_key()
    if not api_key_valid:
        print("\n❌ API key test failed. Exiting.")
        return False
    
    # Test 2: Library search
    search_success, search_data = await test_search_libraries()
    
    # Test 3: Documentation retrieval
    if search_success:
        doc_success, doc_data = await test_get_context()
    
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    print(f"✅ API Key: {'Valid' if api_key_valid else 'Invalid'}")
    print(f"✅ Library Search: {'Success' if search_success else 'Failed'}")
    
    if search_success:
        print(f"✅ Documentation Retrieval: {'Success' if doc_success else 'Failed'}")
    
    print("\n🎯 Next steps:")
    print("1. Install dependencies: pip install -r requirements_context7.txt")
    print("2. Run MCP server: python context7_mcp.py")
    print("3. Configure Agent Zero to use the MCP server")
    
    return api_key_valid and search_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)