#!/usr/bin/env python3
import requests
import json
from datetime import datetime

# URLs para testar
urls = [
    "http://localhost:80/api/paperclip_zero/health",
    "http://localhost:8000/api/paperclip_zero/health",
    "http://localhost:8080/api/paperclip_zero/health",
    "http://127.0.0.1:80/api/paperclip_zero/health",
    "http://127.0.0.1:8000/api/paperclip_zero/health"
]

print("🔍 Testando acesso ao PaperClip Zero...")

for url in urls:
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            print(f"✅ {url} - ONLINE (Status: {response.status_code})")
            print(f"   Response: {response.text[:100]}")
            
            # Testar criação de work item
            test_work_item = {
                "type": "lead_generation",
                "data": {
                    "nicho": "advogado",
                    "localizacao": "São Paulo",
                    "limite": 2
                },
                "priority": "normal",
                "metadata": {
                    "source": "lead_agent_v4",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Tentar criar work item
            create_url = url.replace("/health", "/work_items")
            try:
                create_response = requests.post(create_url, json=test_work_item, timeout=5)
                if create_response.status_code in [200, 201]:
                    print(f"✅ Work item criado com sucesso!")
                    print(f"   Response: {create_response.json()}")
                else:
                    print(f"⚠️ Não consegui criar work item (Status: {create_response.status_code})")
            except Exception as e:
                print(f"⚠️ Erro ao criar work item: {e}")
            
            break
        else:
            print(f"⚠️ {url} - Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ {url} - Erro: {type(e).__name__}")
    except Exception as e:
        print(f"❌ {url} - Erro inesperado: {e}")

# Se nenhuma URL funcionar, verificar configuração
print("\n📋 Verificando configuração do PaperClip Zero...")
import os
paperclip_path = "/a0/usr/plugins/paperclip_zero"
if os.path.exists(paperclip_path):
    print(f"✅ PaperClip Zero instalado em: {paperclip_path}")
    
    # Verificar arquivos de configuração
    config_files = [
        "config.json",
        "settings.py",
        "config.py",
        "paperclip_zero.py"
    ]
    
    for config_file in config_files:
        config_path = os.path.join(paperclip_path, config_file)
        if os.path.exists(config_path):
            print(f"   ✅ {config_file} encontrado")
            # Ler primeira linha
            try:
                with open(config_path, 'r') as f:
                    first_line = f.readline().strip()
                    print(f"      Primeira linha: {first_line[:50]}...")
            except:
                pass
        else:
            print(f"   ❌ {config_file} não encontrado")
else:
    print(f"❌ PaperClip Zero não encontrado em {paperclip_path}")

print("\n🎯 Próximos passos:")
print("1. Verificar se PaperClip Zero está rodando como serviço")
print("2. Verificar logs do PaperClip Zero")
print("3. Configurar integração com Lead Agent")
