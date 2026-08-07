#!/usr/bin/env python3
"""
Setup script for Context7 MCP Server integration with Agent Zero.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Configuration
CONTEXT7_API_KEY = "ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"
WORKDIR = Path("/a0/usr/workdir")

def run_command(cmd, description):
    """Run a shell command and print status."""
    print(f"\n🔧 {description}...")
    print(f"   Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=WORKDIR,
        )
        
        if result.returncode == 0:
            print(f"   ✅ Success")
            if result.stdout.strip():
                print(f"   Output: {result.stdout[:200]}...")
            return True
        else:
            print(f"   ❌ Failed with code {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        return False

def check_python_dependencies():
    """Check if required Python packages are installed."""
    print("\n📦 Checking Python dependencies...")
    
    required_packages = ["httpx", "mcp"]
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"   ❌ {package} (missing)")
    
    return missing

def install_dependencies():
    """Install required dependencies."""
    print("\n📦 Installing dependencies...")
    
    # Check if requirements file exists
    req_file = WORKDIR / "requirements_context7.txt"
    if not req_file.exists():
        print(f"   ❌ Requirements file not found: {req_file}")
        return False
    
    # Install from requirements file
    cmd = f"pip install -r {req_file}"
    return run_command(cmd, "Installing dependencies from requirements.txt")

def test_context7_api():
    """Test the Context7 API connection."""
    print("\n🔍 Testing Context7 API connection...")
    
    test_script = WORKDIR / "test_context7_api.py"
    if not test_script.exists():
        print(f"   ❌ Test script not found: {test_script}")
        return False
    
    cmd = f"python {test_script}"
    return run_command(cmd, "Running API tests")

def create_mcp_config():
    """Create MCP configuration for Agent Zero."""
    print("\n⚙️  Creating MCP configuration...")
    
    config = {
        "mcp_servers": {
            "context7": {
                "command": "python",
                "args": [str(WORKDIR / "context7_mcp.py")],
                "env": {
                    "CONTEXT7_API_KEY": CONTEXT7_API_KEY
                }
            }
        }
    }
    
    config_file = WORKDIR / "context7_mcp_config.json"
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"   ✅ Configuration saved to: {config_file}")
        return True
    except Exception as e:
        print(f"   ❌ Failed to save config: {str(e)}")
        return False

def create_agent_zero_integration_guide():
    """Create integration guide for Agent Zero."""
    print("\n📋 Creating integration guide...")
    
    guide = """# Context7 MCP Server Integration Guide

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
python -m a0.manage_plugin configure mcp2cli \
  --server context7 \
  --command "python /a0/usr/workdir/context7_mcp.py" \
  --env CONTEXT7_API_KEY="ctx7sk-795674f5-4964-453b-a05c-b14d36cafc07"

# Enable the server
python -m a0.manage_plugin configure mcp2cli \
  --server context7 \
  --enabled true
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
"""
    
    guide_file = WORKDIR / "INTEGRATION_GUIDE.md"
    try:
        with open(guide_file, "w") as f:
            f.write(guide)
        print(f"   ✅ Guide saved to: {guide_file}")
        return True
    except Exception as e:
        print(f"   ❌ Failed to save guide: {str(e)}")
        return False

def main():
    """Main setup function."""
    print("🚀 Context7 MCP Server Setup\n")
    print("=" * 60)
    
    # Check current directory
    print(f"📁 Working directory: {WORKDIR}")
    if not WORKDIR.exists():
        print(f"❌ Working directory does not exist")
        return False
    
    # Step 1: Check dependencies
    missing = check_python_dependencies()
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        if not install_dependencies():
            print("❌ Failed to install dependencies")
            return False
    else:
        print("\n✅ All dependencies are installed")
    
    # Step 2: Test API
    if not test_context7_api():
        print("\n⚠️  API test failed. Continuing anyway...")
    else:
        print("\n✅ API tests passed")
    
    # Step 3: Create configuration
    if not create_mcp_config():
        print("\n⚠️  Failed to create configuration")
    
    # Step 4: Create integration guide
    if not create_agent_zero_integration_guide():
        print("\n⚠️  Failed to create integration guide")
    
    print("\n" + "=" * 60)
    print("🎉 Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Review the integration guide: /a0/usr/workdir/INTEGRATION_GUIDE.md")
    print("2. Configure Agent Zero to use the Context7 MCP server")
    print("3. Restart Agent Zero")
    print("4. Test the tools in Agent Zero")
    print("\n🔧 Files created:")
    print(f"   - {WORKDIR}/context7_mcp_config.json")
    print(f"   - {WORKDIR}/INTEGRATION_GUIDE.md")
    print(f"   - {WORKDIR}/README_CONTEXT7.md")
    print("\n💡 Usage examples:")
    print("   • Search for Next.js libraries about SSR")
    print("   • Get documentation for React about state management")
    print("   • Find Python libraries for web scraping")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)