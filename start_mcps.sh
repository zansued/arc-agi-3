#!/bin/bash
export PYTHONPATH=/a0/usr/workdir/mcp_servers:
pkill -f mcp_servers/ || true
sleep 1
setsid nohup /opt/venv-a0/bin/python /a0/usr/workdir/mcp_servers/knowledge_graph_mcp.py > /tmp/knowledge_graph_mcp.log 2>&1 < /dev/null &
setsid nohup /opt/venv-a0/bin/python /a0/usr/workdir/mcp_servers/rag_drive_mcp.py > /tmp/rag_drive_mcp.log 2>&1 < /dev/null &
setsid nohup /opt/venv-a0/bin/python /a0/usr/workdir/mcp_servers/paperclip_mcp.py > /tmp/paperclip_mcp.log 2>&1 < /dev/null &
setsid nohup /opt/venv-a0/bin/python /a0/usr/workdir/mcp_servers/dgm_agent_mcp_v2.py > /tmp/dgm_agent_mcp_v2.log 2>&1 < /dev/null &
setsid nohup /opt/venv-a0/bin/python /a0/usr/workdir/mcp_servers/spectral_mcp.py > /tmp/spectral_mcp.log 2>&1 < /dev/null &
echo All
