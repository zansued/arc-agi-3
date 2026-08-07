#!/bin/bash
# auto_prompt.sh - Lê next_prompt.txt e envia para Agent Zero
LOG=/a0/usr/workdir/auto_prompt_output.log
echo "Fri Jul 24 19:52:50     2026: auto_prompt.sh iniciado" >> 
cd /a0/usr/workdir
if [ -f next_prompt.txt ]; then
  /opt/venv/bin/python3 /a0/usr/workdir/auto_prompt.py /a0/usr/workdir/next_prompt.txt >>  2>&1
fi
echo "Fri Jul 24 19:52:50     2026: auto_prompt.sh finalizado (exit=0)" >> 
