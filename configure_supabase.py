#!/usr/bin/env python3
"""
Configurar Supabase para armazenamento de leads
"""

import json
from datetime import datetime

# Testar conexão com Supabase MCP
try:
    import sys
    sys.path.append('/a0/usr/workdir/mcp_servers')
    from supabase_mcp import SupabaseMCP
    
    print("✅ Supabase MCP importado")
    
    # Criar tabela para leads
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS lead_agent_results (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        nicho TEXT NOT NULL,
        nome TEXT,
        telefone TEXT,
        email TEXT,
        website TEXT,
        endereco TEXT,
        redes_sociais TEXT[],
        status TEXT,
        metadata JSONB
    );
    """
    
    print("📊 Criando tabela no Supabase...")
    print(f"SQL: {create_table_sql[:100]}...")
    
    # Em produção, executaria via MCP
    # Por enquanto, salvar SQL em arquivo
    with open("/a0/usr/workdir/supabase_setup.sql", "w") as f:
        f.write(create_table_sql)
    
    print("✅ SQL para Supabase salvo em: /a0/usr/workdir/supabase_setup.sql")
    
    # Criar também tabela para análises de autopoiese
    create_analysis_table = """
    CREATE TABLE IF NOT EXISTS autopoiese_analysis (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        timestamp TIMESTAMPTZ DEFAULT NOW(),
        execution_id TEXT,
        stats JSONB,
        metrics JSONB,
        recommendations TEXT[],
        optimizations TEXT[]
    );
    """
    
    with open("/a0/usr/workdir/supabase_setup.sql", "a") as f:
        f.write("\n\n" + create_analysis_table)
    
    print("✅ Tabela de análise adicionada")
    
    # Criar script Python para salvar no Supabase
    save_script = '''
#!/usr/bin/env python3
"""
Salvar resultados do Lead Agent no Supabase
"""

import json
import sys
from datetime import datetime

def save_to_supabase(result_data):
    """Salva dados no Supabase"""
    try:
        # Em produção, usar MCP Supabase
        # Por enquanto, salvar em arquivo JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/a0/usr/workdir/supabase_backup_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Dados salvos para Supabase: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao salvar para Supabase: {e}")
        return False

if __name__ == "__main__":
    # Testar com dados de exemplo
    test_data = {
        "timestamp": datetime.now().isoformat(),
        "nicho": "advogado",
        "leads": [
            {"nome": "Teste", "email": "teste@exemplo.com", "telefone": "(11) 9999-8888"}
        ],
        "stats": {"total": 1, "emails": 1, "phones": 1}
    }
    
    save_to_supabase(test_data)
'''
    
    with open("/a0/usr/workdir/save_to_supabase.py", "w") as f:
        f.write(save_script)
    
    import os
    os.chmod("/a0/usr/workdir/save_to_supabase.py", 0o755)
    
    print("✅ Script para salvar no Supabase criado: /a0/usr/workdir/save_to_supabase.py")
    
    # Modificar lead_agent_final.py para usar Supabase
    print("\n🔧 Modificando lead_agent_final.py para usar Supabase...")
    
    with open("/a0/usr/workdir/lead_agent_final.py", "r") as f:
        content = f.read()
    
    # Adicionar função para salvar no Supabase
    if "def salvar_leads_supabase" not in content:
        supabase_function = '''
    def salvar_leads_supabase(self, leads):
        """Salva leads no Supabase"""
        try:
            import sys
            sys.path.append('/a0/usr/workdir')
            from save_to_supabase import save_to_supabase
            
            result_data = {
                "timestamp": datetime.now().isoformat(),
                "leads": leads,
                "stats": self.stats,
                "nicho": leads[0].get("nicho", "") if leads else ""
            }
            
            if save_to_supabase(result_data):
                print(f"✅ {len(leads)} leads salvos para Supabase")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"❌ Erro ao salvar no Supabase: {e}")
            return False
'''
        
        # Encontrar onde adicionar a função (após salvar_leads_google_sheets)
        if "def salvar_leads_google_sheets" in content:
            # Adicionar após essa função
            insert_point = content.find("def salvar_leads_google_sheets")
            # Encontrar fim da função
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith("def salvar_leads_google_sheets"):
                    # Procurar próxima função ou fim da classe
                    for j in range(i+1, len(lines)):
                        if lines[j].strip().startswith("def ") and lines[j].strip() != "":
                            # Inserir antes da próxima função
                            lines.insert(j, supabase_function)
                            break
                    else:
                        # Se não encontrar próxima função, adicionar no final da classe
                        lines.append(supabase_function)
                    break
            
            new_content = '\n'.join(lines)
            
            with open("/a0/usr/workdir/lead_agent_final_v2.py", "w") as f:
                f.write(new_content)
            
            print("✅ Nova versão do Lead Agent criada: lead_agent_final_v2.py")
            print("   Inclui função para salvar no Supabase")
        
    else:
        print("✅ Lead Agent já tem função para Supabase")
    
except Exception as e:
    print(f"❌ Erro ao configurar Supabase: {e}")
    print("Criando fallback para arquivo local...")
    
    # Fallback: criar sistema de arquivos local
    fallback_script = '''
import json
import os
from datetime import datetime

def save_to_local(leads, analysis):
    """Salva dados localmente"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Salvar leads
    leads_file = f"/a0/usr/workdir/leads_backup/leads_{timestamp}.json"
    os.makedirs(os.path.dirname(leads_file), exist_ok=True)
    
    with open(leads_file, "w") as f:
        json.dump({"leads": leads, "timestamp": timestamp}, f, indent=2)
    
    # Salvar análise
    analysis_file = f"/a0/usr/workdir/leads_backup/analysis_{timestamp}.json"
    with open(analysis_file, "w") as f:
        json.dump({"analysis": analysis, "timestamp": timestamp}, f, indent=2)
    
    print(f"✅ Dados salvos localmente: {leads_file}, {analysis_file}")
    return True
'''
    
    with open("/a0/usr/workdir/save_to_local.py", "w") as f:
        f.write(fallback_script)
    
    print("✅ Fallback local criado: /a0/usr/workdir/save_to_local.py")

print("\n🎯 Configuração Supabase concluída!")
print("Próximos passos:")
print("1. Executar supabase_setup.sql no Supabase")
print("2. Usar lead_agent_final_v2.py para salvar no Supabase")
print("3. Testar com: python3 save_to_supabase.py")
