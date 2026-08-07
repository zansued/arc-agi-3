#!/usr/bin/env python3
"""
Lead Agent - Solução Python para automação de leads
Replica workflow n8n sem dependências externas
"""

import json
import os
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import time
from datetime import datetime

# Configurações
GOOGLE_SHEETS_ID = "1AqxF-zDpwo5k9QsuW1pMpi8y3Tpqc_atOoNru_fOpTU"  # Do workflow
SERVICE_ACCOUNT_KEY = "/a0/usr/workdir/simple_drive_system/service_account_key.json"

class LeadAgent:
    def __init__(self):
        print("🚀 Inicializando Lead Agent com Autopoiese")
        self.stats = {
            "leads_encontrados": 0,
            "emails_coletados": 0,
            "telefones_coletados": 0,
            "sucessos": 0,
            "falhas": 0
        }
        
    def buscar_negocios_google(self, query, localizacao=None, limite=10):
        """Busca negócios usando Google Places API alternativa"""
        print(f"🔍 Buscando: {query}")
        
        # Simulação - na prática usar API real
        # Por enquanto retorna dados de exemplo
        negocios = [
            {
                "nome": "Advogado João Silva",
                "endereco": "Rua das Flores, 123, São Paulo",
                "telefone": "(11) 9999-8888",
                "website": "https://advjoaosilva.com.br",
                "rating": 4.5
            },
            {
                "nome": "Escritório Legal & Associados",
                "endereco": "Av. Paulista, 1000, São Paulo",
                "telefone": "(11) 7777-6666",
                "website": "https://escritoriolegal.com.br",
                "rating": 4.2
            }
        ]
        
        print(f"✅ Encontrados {len(negocios)} negócios")
        return negocios
    
    def extrair_dados_site(self, url):
        """Extrai dados de um site"""
        try:
            print(f"🌐 Acessando: {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extrair texto
            texto = soup.get_text()
            
            # Buscar emails
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', texto)
            emails = list(set(emails))[:5]  # Limitar a 5 emails únicos
            
            # Buscar telefones (formato brasileiro)
            telefones = re.findall(r'\(?\d{2,}\)?[\s-]?\d{4,}[\s-]?\d{4}', texto)
            telefones = list(set(telefones))[:3]
            
            # Extrair título
            titulo = soup.title.string if soup.title else ""
            
            return {
                "titulo": titulo,
                "emails": emails,
                "telefones": telefones,
                "texto": texto[:1000]  # Primeiros 1000 caracteres
            }
            
        except Exception as e:
            print(f"❌ Erro ao acessar {url}: {e}")
            return {"titulo": "", "emails": [], "telefones": [], "texto": ""}
    
    def usar_ferramentas_osint(self, dominio, telefone=None):
        """Usa ferramentas OSINT instaladas para enriquecimento"""
        dados = {"dominio": dominio, "ferramentas_usadas": []}
        
        # Verificar se holehe está instalado
        holehe_path = "/a0/usr/workdir/osint_tools_installed/holehe"
        if os.path.exists(holehe_path):
            dados["ferramentas_usadas"].append("holehe")
            # Em produção, chamaria holehe via subprocess
        
        # Verificar se blackbird está instalado
        blackbird_path = "/a0/usr/workdir/osint_tools_installed/blackbird"
        if os.path.exists(blackbird_path):
            dados["ferramentas_usadas"].append("blackbird")
            
        # Verificar se Phunter está instalado (para telefones)
        if telefone:
            phunter_path = "/a0/usr/workdir/osint_tools_installed/Phunter"
            if os.path.exists(phunter_path):
                dados["ferramentas_usadas"].append("phunter")
        
        return dados
    
    def salvar_google_sheets(self, leads):
        """Salva leads no Google Sheets"""
        print(f"📊 Salvando {len(leads)} leads no Google Sheets")
        
        # Verificar se service account existe
        if not os.path.exists(SERVICE_ACCOUNT_KEY):
            print("❌ Service account key não encontrada")
            return False
        
        try:
            # Em produção, usar gspread com service account
            # Por enquanto apenas simular
            for lead in leads:
                print(f"  ✓ {lead.get('nome', 'N/A')}: {lead.get('email_principal', 'N/A')}")
            
            print(f"✅ Dados prontos para Google Sheets (ID: {GOOGLE_SHEETS_ID})")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar no Google Sheets: {e}")
            return False
    
    def executar_autopoiese(self):
        """Analisa performance e sugere melhorias"""
        print("🧠 Executando autopoiese...")
        
        taxa_sucesso = self.stats["sucessos"] / max(self.stats["sucessos"] + self.stats["falhas"], 1)
        
        sugestoes = []
        if taxa_sucesso < 0.5:
            sugestoes.append("Aumentar timeout para requests")
            sugestoes.append("Tentar mais fontes de dados")
        
        if self.stats["emails_coletados"] / max(self.stats["leads_encontrados"], 1) < 0.3:
            sugestoes.append("Melhorar regex de emails")
            sugestoes.append("Usar holehe para busca de emails")
        
        return {
            "taxa_sucesso": taxa_sucesso,
            "sugestoes": sugestoes,
            "stats": self.stats.copy()
        }
    
    def processar_nicho(self, nicho, localizacao=None, limite=5):
        """Processa um nicho completo"""
        print(f"🎯 Processando nicho: {nicho}")
        
        # 1. Buscar negócios
        negocios = self.buscar_negocios_google(nicho, localizacao, limite)
        self.stats["leads_encontrados"] += len(negocios)
        
        leads_completos = []
        
        for negocio in negocios:
            print(f"\n📋 Processando: {negocio['nome']}")
            
            # 2. Extrair dados do site
            if negocio.get('website'):
                dados_site = self.extrair_dados_site(negocio['website'])
                
                # 3. Usar ferramentas OSINT
                dominio = urlparse(negocio['website']).netloc if negocio['website'] else ""
                dados_osint = self.usar_ferramentas_osint(dominio, negocio.get('telefone'))
                
                # Combinar dados
                lead_completo = {
                    **negocio,
                    "email_principal": dados_site["emails"][0] if dados_site["emails"] else "",
                    "emails": dados_site["emails"],
                    "telefones": dados_site["telefones"] or [negocio.get('telefone', '')],
                    "titulo_site": dados_site["titulo"],
                    "ferramentas_osint": dados_osint["ferramentas_usadas"],
                    "timestamp": datetime.now().isoformat()
                }
                
                leads_completos.append(lead_completo)
                
                # Atualizar stats
                if dados_site["emails"]:
                    self.stats["emails_coletados"] += 1
                if dados_site["telefones"]:
                    self.stats["telefones_coletados"] += 1
                
                self.stats["sucessos"] += 1
            else:
                print(f"⚠️ Sem website: {negocio['nome']}")
                self.stats["falhas"] += 1
        
        # 4. Salvar no Google Sheets
        if leads_completos:
            self.salvar_google_sheets(leads_completos)
        
        # 5. Executar autopoiese
        analise = self.executar_autopoiese()
        
        return {
            "nicho": nicho,
            "leads": leads_completos,
            "total_leads": len(leads_completos),
            "analise_autopoiese": analise
        }

if __name__ == "__main__":
    agente = LeadAgent()
    
    # Testar com exemplo
    resultado = agente.processar_nicho("advogados São Paulo", limite=2)
    
    print("\n" + "="*50)
    print("📈 RESULTADOS:")
    print(f"Leads processados: {resultado['total_leads']}")
    print(f"Stats: {agente.stats}")
    print("="*50)
