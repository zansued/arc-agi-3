#!/usr/bin/env python3
"""
Wrapper para executar Lead Agent v4 sem problemas de event loop
"""

import subprocess
import sys
import os
from datetime import datetime

def run_lead_agent():
    """Executa o Lead Agent v4 e retorna resultado"""
    print(f"🚀 Iniciando Lead Agent v4 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Mudar para diretório correto
    os.chdir('/a0/usr/workdir')
    
    # Executar script
    try:
        result = subprocess.run(
            [sys.executable, 'lead_agent_v4_simple.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos timeout
        )
        
        print(f"📊 Resultado da execução:")
        print(f"   Exit code: {result.returncode}")
        print(f"   Stdout: {len(result.stdout)} caracteres")
        print(f"   Stderr: {len(result.stderr)} caracteres")
        
        # Mostrar saída
        if result.stdout:
            print("\n📋 Saída do Lead Agent:")
            print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
        
        if result.stderr:
            print("\n⚠️ Erros do Lead Agent:")
            print(result.stderr[:500] + "..." if len(result.stderr) > 500 else result.stderr)
        
        # Verificar se salvou no Supabase
        print("\n🔍 Verificando dados no Supabase...")
        check_supabase()
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        print("❌ Timeout: Lead Agent demorou mais de 5 minutos")
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        print(f"❌ Erro ao executar Lead Agent: {e}")
        return {'success': False, 'error': str(e)}

def check_supabase():
    """Verifica dados salvos no Supabase"""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            "postgresql://supabase_admin:Academia2026Supabase@supabase-db:5432/postgres"
        )
        cursor = conn.cursor()
        
        # Verificar total de leads
        cursor.execute("SELECT COUNT(*) FROM lead_agent_results")
        total_leads = cursor.fetchone()[0]
        
        # Verificar leads por nicho
        cursor.execute("SELECT nicho, COUNT(*) FROM lead_agent_results GROUP BY nicho")
        niches = cursor.fetchall()
        
        # Verificar última execução
        cursor.execute("SELECT MAX(created_at) FROM lead_agent_results")
        last_run = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print(f"✅ Supabase: {total_leads} leads totais")
        for niche, count in niches:
            print(f"   • {niche}: {count} leads")
        if last_run:
            print(f"   Última execução: {last_run}")
        
    except Exception as e:
        print(f"⚠️ Não consegui verificar Supabase: {e}")

def main():
    """Função principal"""
    print("=" * 60)
    print("📋 EXECUTANDO LEAD AGENT V4 (TAREFA AGENDADA)")
    print("=" * 60)
    
    # Executar Lead Agent
    result = run_lead_agent()
    
    print("\n" + "=" * 60)
    print("🎯 RESULTADO FINAL")
    print("=" * 60)
    
    if result.get('success'):
        print("✅ Lead Agent executado com sucesso!")
        
        # Salvar log
        with open('/a0/usr/workdir/lead_agent_scheduled_run.log', 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Execução: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Sucesso: Sim\n")
            f.write(f"Saída: {len(result.get('stdout', ''))} caracteres\n")
            
        print(f"📝 Log salvo em: /a0/usr/workdir/lead_agent_scheduled_run.log")
    else:
        print(f"❌ Lead Agent falhou: {result.get('error', 'Erro desconhecido')}")
        
        # Salvar log de erro
        with open('/a0/usr/workdir/lead_agent_error.log', 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Erro: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Detalhes: {result.get('error', 'Erro desconhecido')}\n")
            if result.get('stderr'):
                f.write(f"Stderr: {result.get('stderr')[:500]}\n")
        
        print(f"📝 Log de erro salvo em: /a0/usr/workdir/lead_agent_error.log")
    
    return 0 if result.get('success') else 1

if __name__ == "__main__":
    sys.exit(main())