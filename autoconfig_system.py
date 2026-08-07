#!/usr/bin/env python3
"""
Sistema de Autoconfiguração para Lead Agent com Autopoiese
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess

class AutoconfigSystem:
    def __init__(self):
        self.workdir = Path("/a0/usr/workdir")
        self.config_file = self.workdir / "autoconfig_state.json"
        self.load_config()
        
    def load_config(self):
        """Carrega configuração atual"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                self.config = json.load(f)
        else:
            self.config = {
                "version": 1,
                "created_at": datetime.now().isoformat(),
                "components": {
                    "lead_agent": {"status": "installed", "version": "1.0"},
                    "autopoiese": {"status": "active", "version": "1.0"},
                    "google_sheets": {"status": "quota_exceeded", "version": "1.0"},
                    "supabase": {"status": "not_configured", "version": "0.0"},
                    "osint_tools": {"status": "installed", "version": "1.0"},
                    "paperclip_zero": {"status": "installing", "version": "1.0.1"}
                },
                "metrics": {
                    "total_runs": 0,
                    "total_leads": 0,
                    "total_emails": 0,
                    "total_phones": 0,
                    "success_rate": 0.0
                },
                "optimizations": []
            }
    
    def save_config(self):
        """Salva configuração"""
        self.config["updated_at"] = datetime.now().isoformat()
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def analyze_system(self):
        """Analisa sistema atual e gera recomendações"""
        print("🔍 Analisando sistema...")
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "issues": [],
            "recommendations": [],
            "optimizations": []
        }
        
        # 1. Verificar Lead Agent
        lead_agent_path = self.workdir / "lead_agent_final.py"
        if lead_agent_path.exists():
            analysis["components"]["lead_agent"] = {"status": "ok", "path": str(lead_agent_path)}
        else:
            analysis["components"]["lead_agent"] = {"status": "missing", "path": "N/A"}
            analysis["issues"].append("Lead Agent script não encontrado")
        
        # 2. Verificar arquivos de autopoiese
        autopoiese_files = list(self.workdir.glob("autopoiese_*.json"))
        analysis["components"]["autopoiese"] = {
            "status": "ok" if autopoiese_files else "no_data",
            "files_count": len(autopoiese_files),
            "latest_file": str(autopoiese_files[-1]) if autopoiese_files else "N/A"
        }
        
        # 3. Verificar ferramentas OSINT
        osint_tools = [
            ("holehe", "/a0/usr/workdir/osint_tools_installed/holehe"),
            ("blackbird", "/a0/usr/workdir/osint_tools_installed/blackbird"),
            ("Phunter", "/a0/usr/workdir/osint_tools_installed/Phunter"),
            ("Telerecon", "/a0/usr/workdir/osint_tools_installed/Telerecon")
        ]
        
        osint_status = {}
        for name, path in osint_tools:
            if os.path.exists(path):
                osint_status[name] = {"status": "installed", "path": path}
            else:
                osint_status[name] = {"status": "missing", "path": path}
                analysis["issues"].append(f"Ferramenta OSINT {name} não encontrada")
        
        analysis["components"]["osint_tools"] = osint_status
        
        # 4. Verificar Google Sheets quota
        google_sheets_test = self.workdir / "test_google_sheets_fixed.py"
        if google_sheets_test.exists():
            # Executar teste rápido
            try:
                result = subprocess.run(
                    ["python3", str(google_sheets_test)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if "quota has been exceeded" in result.stdout or "quota has been exceeded" in result.stderr:
                    analysis["components"]["google_sheets"] = {"status": "quota_exceeded"}
                    analysis["recommendations"].append("Usar Supabase como alternativa ao Google Sheets")
                else:
                    analysis["components"]["google_sheets"] = {"status": "working"}
            except:
                analysis["components"]["google_sheets"] = {"status": "unknown"}
        
        # 5. Verificar Supabase
        supabase_mcp = Path("/a0/usr/workdir/mcp_servers/supabase_mcp.py")
        if supabase_mcp.exists():
            analysis["components"]["supabase"] = {"status": "available", "path": str(supabase_mcp)}
            analysis["recommendations"].append("Configurar armazenamento no Supabase")
        else:
            analysis["components"]["supabase"] = {"status": "not_available"}
        
        # 6. Verificar PaperClip Zero
        paperclip_path = Path("/a0/usr/plugins/paperclip_zero")
        if paperclip_path.exists():
            analysis["components"]["paperclip_zero"] = {
                "status": "installed",
                "path": str(paperclip_path),
                "api_responding": False  # Assumindo não responde
            }
            analysis["recommendations"].append("Ativar PaperClip Zero para gestão centralizada")
        
        # 7. Gerar otimizações baseadas em análise
        if len(autopoiese_files) >= 2:
            analysis["optimizations"].append("Sistema tem dados suficientes para aprendizado de máquina")
            analysis["optimizations"].append("Implementar otimização automática de parâmetros")
        
        if analysis["components"].get("osint_tools", {}).get("holehe", {}).get("status") == "installed":
            analysis["optimizations"].append("Integrar holehe para validação avançada de emails")
        
        # Salvar análise
        analysis_file = self.workdir / f"system_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(analysis_file, "w") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Análise salva em: {analysis_file}")
        
        return analysis
    
    def generate_autoconfig_script(self):
        """Gera script de autoconfiguração baseado na análise"""
        analysis = self.analyze_system()
        
        script_lines = [
            "#!/bin/bash",
            "# Script de autoconfiguração gerado automaticamente",
            f"# Gerado em: {datetime.now().isoformat()}",
            "",
            "echo '🚀 Iniciando autoconfiguração do sistema de leads'"
        ]
        
        # Adicionar comandos baseados nas recomendações
        for recommendation in analysis.get("recommendations", []):
            if "Supabase" in recommendation:
                script_lines.extend([
                    "",
                    "# Configurar Supabase",
                    "echo '📊 Configurando Supabase...'"
                ])
                # Adicionar comandos para configurar Supabase
                
            elif "PaperClip Zero" in recommendation:
                script_lines.extend([
                    "",
                    "# Ativar PaperClip Zero",
                    "echo '🔄 Ativando PaperClip Zero...'"
                ])
        
        # Adicionar otimizações
        for optimization in analysis.get("optimizations", []):
            if "holehe" in optimization.lower():
                script_lines.extend([
                    "",
                    "# Integrar holehe",
                    "echo '🔧 Integrando holehe...'"
                ])
        
        script_lines.extend([
            "",
            "# Executar Lead Agent para teste",
            "echo '🎯 Executando Lead Agent...'"
        ])
        
        script_content = "\n".join(script_lines)
        script_file = self.workdir / "autoconfig.sh"
        
        with open(script_file, "w") as f:
            f.write(script_content)
        
        os.chmod(script_file, 0o755)
        
        print(f"✅ Script de autoconfiguração gerado: {script_file}")
        return script_file
    
    def run_autoconfig(self):
        """Executa autoconfiguração"""
        print("🚀 INICIANDO AUTOCONFIGURAÇÃO")
        print("="*60)
        
        # 1. Analisar sistema
        analysis = self.analyze_system()
        
        # 2. Gerar relatório
        print("\n📊 RELATÓRIO DE ANÁLISE:")
        print(f"Componentes analisados: {len(analysis['components'])}")
        print(f"Problemas identificados: {len(analysis['issues'])}")
        print(f"Recomendações: {len(analysis['recommendations'])}")
        print(f"Otimizações possíveis: {len(analysis['optimizations'])}")
        
        # 3. Gerar script de autoconfiguração
        script_file = self.generate_autoconfig_script()
        
        # 4. Atualizar configuração
        self.config["last_analysis"] = analysis
        self.config["metrics"]["total_runs"] += 1
        self.save_config()
        
        print("\n✅ AUTOCONFIGURAÇÃO COMPLETA")
        print(f"Script gerado: {script_file}")
        print(f"Configuração salva: {self.config_file}")
        
        return {
            "status": "success",
            "analysis": analysis,
            "config_file": str(self.config_file),
            "script_file": str(script_file)
        }

if __name__ == "__main__":
    autoconfig = AutoconfigSystem()
    result = autoconfig.run_autoconfig()
    
    print("\n🎯 PRÓXIMOS PASSOS:")
    print("1. Executar autoconfig.sh")
    print("2. Configurar Supabase para armazenamento")
    print("3. Integrar holehe para validação de emails")
    print("4. Ativar PaperClip Zero quando disponível")
