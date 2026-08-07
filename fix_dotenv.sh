#!/bin/bash
if grep -q "get_dotenv_file_path" /a0/helpers/secrets.py 2>/dev/null; then
    sed -i "s/dotenv\.get_dotenv_file_path()/dotenv.DEFAULT_DOTENV_PATH/g" /a0/helpers/secrets.py
    echo "$(date): Applied dotenv fix" >> /a0/usr/workdir/auto_fix.log
fi
