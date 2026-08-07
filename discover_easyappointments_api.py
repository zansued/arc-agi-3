#!/usr/bin/env python3
"""
Descobrir URL correta da API Easy!Appointments
"""

import requests
import json
import time

BASE_URL = "https://cal.techstorebrasil.com"
TOKEN = "Easy!AppointmentsTokenSecretao"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_endpoint(endpoint):
    """Testa um endpoint específico"""
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        return {
            "endpoint": endpoint,
            "status": response.status_code,
            "size": len(response.text),
            "content_type": response.headers.get('Content-Type', ''),
            "success": response.status_code == 200 and len(response.text) > 0
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "status": "ERROR",
            "error": str(e),
            "success": False
        }

def discover_api_endpoints():
    """Descobre endpoints da API testando padrões comuns"""
    print("🔍 Descobrindo endpoints da API Easy!Appointments...")
    
    # Padrões comuns de endpoints da API Easy!Appointments
    patterns = [
        # Padrões REST API
        "/api/v1",
        "/api/v2",
        "/api",
        "/rest/api/v1",
        "/rest/api",
        "/index.php/api/v1",
        "/index.php/api",
        "/index.php/rest/api/v1",
        "/index.php/rest/api",
        
        # Endpoints específicos do Easy!Appointments
        "/index.php/api/v1/appointments",
        "/index.php/api/v1/customers",
        "/index.php/api/v1/services",
        "/index.php/api/v1/providers",
        "/index.php/api/v1/categories",
        
        # Endpoints de status/health
        "/status",
        "/health",
        "/api/status",
        "/api/health",
        
        # Documentação
        "/api-docs",
        "/swagger",
        "/swagger-ui",
        "/openapi.json",
        "/api.json",
        
        # Web interface
        "/index.php",
        "/dashboard",
        "/admin",
    ]
    
    results = []
    for pattern in patterns:
        result = test_endpoint(pattern)
        results.append(result)
        
        if result["success"]:
            print(f"✅ {pattern}: {result['status']} ({result['size']} bytes) - {result['content_type']}")
            
            # Se for JSON, mostrar um preview
            if 'application/json' in result['content_type']:
                try:
                    url = f"{BASE_URL}{pattern}"
                    response = requests.get(url, headers=headers, timeout=5)
                    data = response.json()
                    print(f"   Preview: {json.dumps(data)[:200]}...")
                except:
                    pass
        else:
            print(f"❌ {pattern}: {result.get('status', 'ERROR')} ({result.get('size', 0)} bytes)")
        
        time.sleep(0.1)  # Pequena pausa para não sobrecarregar
    
    return results

def test_authentication():
    """Testa diferentes métodos de autenticação"""
    print("\n🔐 Testando métodos de autenticação...")
    
    auth_methods = [
        {"name": "Bearer Token", "headers": {"Authorization": f"Bearer {TOKEN}"}},
        {"name": "Basic Auth", "headers": {"Authorization": f"Basic {TOKEN}"}},
        {"name": "Token", "headers": {"Authorization": f"Token {TOKEN}"}},
        {"name": "API Key", "headers": {"X-API-Key": TOKEN}},
        {"name": "API Token", "headers": {"X-API-Token": TOKEN}},
        {"name": "No Auth", "headers": {}},
    ]
    
    # Testar no endpoint raiz primeiro
    endpoint = "/"
    for method in auth_methods:
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=method["headers"], timeout=5)
            print(f"{method['name']}: {response.status_code} ({len(response.text)} bytes)")
        except Exception as e:
            print(f"{method['name']}: ERROR - {str(e)}")

def analyze_webpage():
    """Analisa a página web para encontrar referências à API"""
    print("\n🌐 Analisando página web...")
    
    try:
        response = requests.get(BASE_URL, timeout=5)
        html = response.text.lower()
        
        # Procurar por referências à API
        api_keywords = ["api", "rest", "swagger", "openapi", "endpoint", "json", "ajax"]
        for keyword in api_keywords:
            if keyword in html:
                print(f"✅ Encontrada referência a '{keyword}' na página")
                
        # Procurar por URLs de API em scripts
        import re
        api_patterns = [
            r'/api/[^"\']+',
            r'/index\.php/api/[^"\']+',
            r'https?://[^"\']+/api/[^"\']+',
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                print(f"✅ URLs encontradas com padrão {pattern}:")
                for match in matches[:5]:  # Limitar a 5 resultados
                    print(f"   - {match}")
    
    except Exception as e:
        print(f"❌ Erro ao analisar página: {e}")

def main():
    print("=" * 70)
    print("Descoberta da API Easy!Appointments")
    print("=" * 70)
    print(f"URL Base: {BASE_URL}")
    print(f"Token: {TOKEN[:15]}...{TOKEN[-5:] if len(TOKEN) > 20 else ''}")
    
    # Descobrir endpoints
    results = discover_api_endpoints()
    
    # Filtrar endpoints bem-sucedidos
    successful = [r for r in results if r["success"]]
    
    if successful:
        print("\n🎯 Endpoints bem-sucedidos:")
        for result in successful:
            print(f"  • {result['endpoint']} ({result['status']}, {result['size']} bytes)")
    else:
        print("\n❌ Nenhum endpoint da API encontrado")
    
    # Testar autenticação
    test_authentication()
    
    # Analisar página web
    analyze_webpage()
    
    # Recomendações
    print("\n💡 Recomendações:")
    if successful:
        print("1. Use um dos endpoints bem-sucedidos acima")
        print("2. Verifique a documentação em /api-docs ou /swagger")
        print("3. Teste operações CRUD (GET, POST, PUT, DELETE)")
    else:
        print("1. Verifique se a API está habilitada no Easy!Appointments")
        print("2. Consulte a documentação em https://easyappointments.org/docs.html")
        print("3. Teste acessando a interface administrativa")
        print("4. Verifique as configurações de CORS")
    
    print("=" * 70)

if __name__ == "__main__":
    main()