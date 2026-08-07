#!/usr/bin/env python3
"""
Integração PaperClip Zero + Lead Agent
"""

import json
import requests
from datetime import datetime

class PaperClipLeadIntegration:
    def __init__(self, base_url="http://localhost:80"):
        self.base_url = base_url
        self.paperclip_api = f"{base_url}/api/paperclip_zero"
        
    def create_lead_work_item(self, nicho, localizacao, limite=10):
        """Cria um work item no PaperClip Zero para coleta de leads"""
        work_item = {
            "title": f"Coleta de Leads: {nicho} em {localizacao}",
            "description": f"Buscar leads de {nicho} em {localizacao}. Coletar nome, telefone, email, site.",
            "priority": "medium",
            "category": "lead_generation",
            "metadata": {
                "nicho": nicho,
                "localizacao": localizacao,
                "limite": limite,
                "agent": "lead_agent_final.py",
                "autopoiese": True
            },
            "assignee_employee_id": None,  # Auto-assign
            "estimated_duration_minutes": 30
        }
        
        try:
            response = requests.post(
                f"{self.paperclip_api}/work_item",
                json={
                    "action": "create",
                    "work_item": work_item
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print(f"✅ Work item criado: {result['work_item'].get('id')}")
                    return result["work_item"]
                else:
                    print(f"❌ Erro: {result.get('error')}")
            else:
                print(f"❌ Status code: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
            
        return None
    
    def execute_lead_agent_via_paperclip(self, nicho, localizacao="São Paulo", limite=5):
        """Executa Lead Agent através do PaperClip Zero"""
        print(f"🚀 Integrando PaperClip Zero + Lead Agent")
        print(f"Nicho: {nicho}, Localização: {localizacao}, Limite: {limite}")
        
        # 1. Criar work item
        work_item = self.create_lead_work_item(nicho, localizacao, limite)
        
        if not work_item:
            print("❌ Falha ao criar work item. Executando Lead Agent diretamente...")
            # Fallback: executar Lead Agent diretamente
            import subprocess
            result = subprocess.run(["python3", "/a0/usr/workdir/lead_agent_final.py"], 
                                  capture_output=True, text=True)
            print(result.stdout)
            return {"status": "fallback", "output": result.stdout}
        
        # 2. Disparar execução
        try:
            response = requests.post(
                f"{self.paperclip_api}/work_item",
                json={
                    "action": "dispatch",
                    "work_item_id": work_item["id"]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Work item disparado: {work_item['id']}")
                
                # 3. Aguardar conclusão (simulação)
                print("⏳ Aguardando execução... (simulação)")
                
                # Em produção, monitorar status via PaperClip Zero
                return {
                    "status": "dispatched",
                    "work_item_id": work_item["id"],
                    "work_item": work_item
                }
            
        except Exception as e:
            print(f"❌ Erro ao disparar work item: {e}")
        
        return {"status": "error"}
    
    def get_paperclip_status(self):
        """Verifica status do PaperClip Zero"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return {"status": "online", "code": response.status_code}
        except Exception as e:
            return {"status": "offline", "error": str(e)}

if __name__ == "__main__":
    integrator = PaperClipLeadIntegration()
    
    # Verificar status
    status = integrator.get_paperclip_status()
    print(f"📊 Status PaperClip Zero: {status['status']}")
    
    if status["status"] == "online":
        # Testar integração
        result = integrator.execute_lead_agent_via_paperclip("advogado", "São Paulo", 3)
        print(f"\n🎯 Resultado: {result}")
    else:
        print("❌ PaperClip Zero offline. Executando Lead Agent diretamente...")
        import subprocess
        result = subprocess.run(["python3", "/a0/usr/workdir/lead_agent_final.py"], 
                              capture_output=True, text=True)
        print(result.stdout)
