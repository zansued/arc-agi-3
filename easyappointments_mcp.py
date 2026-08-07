#!/usr/bin/env python3
"""
MCP Server for Easy!Appointments API
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional
import requests
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.shared as mcp

# Configuração da API
BASE_URL = "https://cal.techstorebrasil.com"
API_BASE = f"{BASE_URL}/index.php/api/v1"
TOKEN = os.environ.get("EASYAPPOINTMENTS_TOKEN", "Easy!AppointmentsTokenSecretao")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Inicializar servidor MCP
server = Server("easyappointments-mcp")

class EasyAppointmentsAPI:
    """Cliente para API Easy!Appointments"""
    
    @staticmethod
    def make_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Faz requisição para a API"""
        url = f"{API_BASE}{endpoint}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=10)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                return {"error": f"Método {method} não suportado"}
            
            # Tentar parsear JSON
            try:
                result = response.json()
            except:
                result = {"text": response.text, "status_code": response.status_code}
            
            return {
                "status_code": response.status_code,
                "data": result,
                "success": 200 <= response.status_code < 300
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Erro de conexão: {str(e)}",
                "success": False
            }
    
    @staticmethod
    def get_appointments() -> Dict:
        """Obtém todos os agendamentos"""
        return EasyAppointmentsAPI.make_request("GET", "/appointments")
    
    @staticmethod
    def get_appointment(appointment_id: int) -> Dict:
        """Obtém um agendamento específico"""
        return EasyAppointmentsAPI.make_request("GET", f"/appointments/{appointment_id}")
    
    @staticmethod
    def create_appointment(data: Dict) -> Dict:
        """Cria um novo agendamento"""
        return EasyAppointmentsAPI.make_request("POST", "/appointments", data)
    
    @staticmethod
    def update_appointment(appointment_id: int, data: Dict) -> Dict:
        """Atualiza um agendamento"""
        return EasyAppointmentsAPI.make_request("PUT", f"/appointments/{appointment_id}", data)
    
    @staticmethod
    def delete_appointment(appointment_id: int) -> Dict:
        """Exclui um agendamento"""
        return EasyAppointmentsAPI.make_request("DELETE", f"/appointments/{appointment_id}")
    
    @staticmethod
    def get_customers() -> Dict:
        """Obtém todos os clientes"""
        return EasyAppointmentsAPI.make_request("GET", "/customers")
    
    @staticmethod
    def get_customer(customer_id: int) -> Dict:
        """Obtém um cliente específico"""
        return EasyAppointmentsAPI.make_request("GET", f"/customers/{customer_id}")
    
    @staticmethod
    def create_customer(data: Dict) -> Dict:
        """Cria um novo cliente"""
        return EasyAppointmentsAPI.make_request("POST", "/customers", data)
    
    @staticmethod
    def get_services() -> Dict:
        """Obtém todos os serviços"""
        return EasyAppointmentsAPI.make_request("GET", "/services")
    
    @staticmethod
    def get_service(service_id: int) -> Dict:
        """Obtém um serviço específico"""
        return EasyAppointmentsAPI.make_request("GET", f"/services/{service_id}")
    
    @staticmethod
    def get_providers() -> Dict:
        """Obtém todos os provedores"""
        return EasyAppointmentsAPI.make_request("GET", "/providers")
    
    @staticmethod
    def get_provider(provider_id: int) -> Dict:
        """Obtém um provedor específico"""
        return EasyAppointmentsAPI.make_request("GET", f"/providers/{provider_id}")
    
    @staticmethod
    def get_availability(provider_id: int, service_id: int, date: str) -> Dict:
        """Obtém disponibilidade para agendamento"""
        params = f"?providerId={provider_id}&serviceId={service_id}&date={date}"
        return EasyAppointmentsAPI.make_request("GET", f"/availability{params}")

# Ferramentas MCP
@server.list_tools()
async def handle_list_tools() -> List[mcp.Tool]:
    """Lista todas as ferramentas disponíveis"""
    return [
        mcp.Tool(
            name="easyappointments_get_appointments",
            description="Get all appointments from Easy!Appointments",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        mcp.Tool(
            name="easyappointments_get_appointment",
            description="Get a specific appointment by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "Appointment ID"
                    }
                },
                "required": ["appointment_id"]
            }
        ),
        mcp.Tool(
            name="easyappointments_create_appointment",
            description="Create a new appointment",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "integer",
                        "description": "Service ID"
                    },
                    "provider_id": {
                        "type": "integer",
                        "description": "Provider ID"
                    },
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID"
                    },
                    "start_datetime": {
                        "type": "string",
                        "description": "Start datetime (YYYY-MM-DD HH:MM:SS)"
                    },
                    "end_datetime": {
                        "type": "string",
                        "description": "End datetime (YYYY-MM-DD HH:MM:SS)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Appointment notes",
                        "optional": True
                    }
                },
                "required": ["service_id", "provider_id", "customer_id", "start_datetime", "end_datetime"]
            }
        ),
        mcp.Tool(
            name="easyappointments_get_customers",
            description="Get all customers",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        mcp.Tool(
            name="easyappointments_get_services",
            description="Get all services",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        mcp.Tool(
            name="easyappointments_get_providers",
            description="Get all providers",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        mcp.Tool(
            name="easyappointments_get_availability",
            description="Get availability for scheduling",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider_id": {
                        "type": "integer",
                        "description": "Provider ID"
                    },
                    "service_id": {
                        "type": "integer",
                        "description": "Service ID"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date (YYYY-MM-DD)"
                    }
                },
                "required": ["provider_id", "service_id", "date"]
            }
        ),
        mcp.Tool(
            name="easyappointments_test_connection",
            description="Test connection to Easy!Appointments API",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Dict[str, Any]
) -> List[mcp.TextContent]:
    """Executa ferramentas"""
    
    if name == "easyappointments_test_connection":
        result = EasyAppointmentsAPI.make_request("GET", "/services")
        if result.get("success"):
            return [mcp.TextContent(
                type="text",
                text=f"✅ Conexão bem-sucedida!\nStatus: {result['status_code']}\nServiços encontrados: {len(result['data']) if isinstance(result['data'], list) else 'N/A'}"
            )]
        else:
            return [mcp.TextContent(
                type="text",
                text=f"❌ Falha na conexão: {result.get('error', 'Unknown error')}"
            )]
    
    elif name == "easyappointments_get_appointments":
        result = EasyAppointmentsAPI.get_appointments()
        return format_result(result, "Appointments")
    
    elif name == "easyappointments_get_appointment":
        appointment_id = arguments.get("appointment_id")
        result = EasyAppointmentsAPI.get_appointment(appointment_id)
        return format_result(result, f"Appointment {appointment_id}")
    
    elif name == "easyappointments_create_appointment":
        data = {
            "serviceId": arguments.get("service_id"),
            "providerId": arguments.get("provider_id"),
            "customerId": arguments.get("customer_id"),
            "start": arguments.get("start_datetime"),
            "end": arguments.get("end_datetime"),
            "notes": arguments.get("notes", "")
        }
        result = EasyAppointmentsAPI.create_appointment(data)
        return format_result(result, "Created Appointment")
    
    elif name == "easyappointments_get_customers":
        result = EasyAppointmentsAPI.get_customers()
        return format_result(result, "Customers")
    
    elif name == "easyappointments_get_services":
        result = EasyAppointmentsAPI.get_services()
        return format_result(result, "Services")
    
    elif name == "easyappointments_get_providers":
        result = EasyAppointmentsAPI.get_providers()
        return format_result(result, "Providers")
    
    elif name == "easyappointments_get_availability":
        provider_id = arguments.get("provider_id")
        service_id = arguments.get("service_id")
        date = arguments.get("date")
        result = EasyAppointmentsAPI.get_availability(provider_id, service_id, date)
        return format_result(result, f"Availability for provider {provider_id}, service {service_id} on {date}")
    
    else:
        return [mcp.TextContent(
            type="text",
            text=f"Ferramenta '{name}' não encontrada"
        )]

def format_result(result: Dict, title: str) -> List[mcp.TextContent]:
    """Formata resultado para resposta MCP"""
    if result.get("success"):
        data = result.get("data", {})
        if isinstance(data, list):
            count = len(data)
            preview = json.dumps(data[:3], indent=2, ensure_ascii=False) if data else "[]"
            if count > 3:
                preview += f"\n... and {count - 3} more items"
            text = f"✅ {title}\nCount: {count}\nData: {preview}"
        else:
            text = f"✅ {title}\nData: {json.dumps(data, indent=2, ensure_ascii=False)}"
    else:
        error = result.get("error", "Unknown error")
        status = result.get("status_code", "N/A")
        text = f"❌ {title}\nError: {error}\nStatus: {status}"
    
    return [mcp.TextContent(type="text", text=text)]

async def main():
    """Função principal"""
    # Inicializar servidor
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="easyappointments-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    
    # Verificar token
    if not TOKEN:
        print("❌ Erro: Variável de ambiente EASYAPPOINTMENTS_TOKEN não definida", file=sys.stderr)
        print(f"Usando token padrão: {TOKEN[:10]}...", file=sys.stderr)
    
    # Testar conexão inicial
    print("🔍 Testando conexão com Easy!Appointments API...", file=sys.stderr)
    test_result = EasyAppointmentsAPI.make_request("GET", "/services")
    
    if test_result.get("success"):
        print(f"✅ Conexão bem-sucedida! Status: {test_result['status_code']}", file=sys.stderr)
        data = test_result.get("data", [])
        if isinstance(data, list):
            print(f"✅ {len(data)} serviços encontrados", file=sys.stderr)
            for service in data[:3]:  # Mostrar primeiros 3 serviços
                print(f"   • {service.get('name', 'Unknown')} (ID: {service.get('id', 'N/A')})", file=sys.stderr)
        else:
            print(f"✅ Dados: {json.dumps(data, indent=2, ensure_ascii=False)[:200]}...", file=sys.stderr)
    else:
        print(f"❌ Falha na conexão: {test_result.get('error', 'Unknown error')}", file=sys.stderr)
        print(f"Status: {test_result.get('status_code', 'N/A')}", file=sys.stderr)
    
    # Executar servidor MCP
    print("🚀 Iniciando servidor MCP Easy!Appointments...", file=sys.stderr)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Servidor MCP encerrado", file=sys.stderr)
    except Exception as e:
        print(f"❌ Erro no servidor MCP: {e}", file=sys.stderr)
        sys.exit(1)
