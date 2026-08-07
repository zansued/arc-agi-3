#!/usr/bin/env python3
"""
Teste da API do Easy!Appointments
"""

import requests
import json

# Configurações
BASE_URL = "https://cal.techstorebrasil.com/api/v1"
TOKEN = "Easy!AppointmentsTokenSecretao"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_connection():
    """Testa a conexão básica com a API"""
    print("🔍 Testando conexão com Easy!Appointments API...")
    
    try:
        # Endpoint de health/status (pode variar)
        response = requests.get(f"{BASE_URL}/appointments", headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Conexão bem-sucedida!")
            try:
                data = response.json()
                print(f"Resposta JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
            except:
                print(f"Resposta (texto): {response.text[:500]}")
        else:
            print(f"❌ Erro na conexão: {response.status_code}")
            print(f"Resposta: {response.text[:500]}")
            
            # Tentar endpoints alternativos
            test_alternative_endpoints()
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
        return False
    
    return response.status_code == 200

def test_alternative_endpoints():
    """Testa endpoints alternativos da API"""
    print("\n🔍 Testando endpoints alternativos...")
    
    endpoints = [
        "/",
        "/api",
        "/api/v1",
        "/api/v1/appointments",
        "/api/v1/customers",
        "/api/v1/services",
        "/api/v1/providers",
        "/api/v1/categories",
        "/status",
        "/health",
    ]
    
    for endpoint in endpoints:
        try:
            url = f"https://cal.techstorebrasil.com{endpoint}"
            response = requests.get(url, headers=headers, timeout=5)
            print(f"{endpoint}: {response.status_code} ({len(response.text)} bytes)")
            if response.status_code == 200 and len(response.text) > 0:
                print(f"  → Possível endpoint válido!")
        except:
            print(f"{endpoint}: Erro de conexão")

def get_api_structure():
    """Tenta descobrir a estrutura da API"""
    print("\n🔍 Descobrindo estrutura da API...")
    
    # Documentação da API (se disponível)
    try:
        response = requests.get("https://cal.techstorebrasil.com/api-docs", timeout=5)
        if response.status_code == 200:
            print("✅ Documentação da API encontrada em /api-docs")
    except:
        pass
    
    try:
        response = requests.get("https://cal.techstorebrasil.com/swagger", timeout=5)
        if response.status_code == 200:
            print("✅ Documentação Swagger encontrada em /swagger")
    except:
        pass
    
    try:
        response = requests.get("https://cal.techstorebrasil.com/openapi.json", timeout=5)
        if response.status_code == 200:
            print("✅ Especificação OpenAPI encontrada em /openapi.json")
    except:
        pass

def main():
    print("=" * 60)
    print("Teste da API Easy!Appointments")
    print("=" * 60)
    print(f"URL Base: {BASE_URL}")
    print(f"Token: {TOKEN[:10]}...{TOKEN[-10:] if len(TOKEN) > 20 else ''}")
    
    # Testar conexão
    if test_connection():
        print("\n✅ API Easy!Appointments está acessível!")
        
        # Descobrir estrutura
        get_api_structure()
        
        print("\n📋 Próximos passos:")
        print("1. Criar servidor MCP para Easy!Appointments")
        print("2. Implementar ferramentas para gerenciar agendamentos")
        print("3. Integrar com Agent Zero")
    else:
        print("\n❌ Não foi possível conectar à API Easy!Appointments")
        print("Verifique:")
        print("1. URL está correta: https://cal.techstorebrasil.com/")
        print("2. Token de autenticação está válido")
        print("3. API está acessível publicamente")
        print("4. CORS está configurado corretamente")
    
    print("=" * 60)

if __name__ == "__main__":
    main()