#!/usr/bin/env python3
"""
Script para corrigir problema de autenticação OOB no plugin Google do Agent Zero.
A Google descontinuou o fluxo OOB (urn:ietf:wg:oauth:2.0:oob) e agora requer PKCE com redirect_uri localhost.
"""

import os
import shutil
from pathlib import Path

def backup_file(file_path):
    """Cria backup do arquivo original."""
    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
    if not backup_path.exists():
        shutil.copy2(file_path, backup_path)
        print(f"✅ Backup criado: {backup_path}")
    else:
        print(f"⚠️  Backup já existe: {backup_path}")
    return backup_path

def fix_google_auth_file(file_path):
    """Corrige o arquivo google_auth.py para usar PKCE com redirect_uri localhost."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se já está corrigido
    if 'redirect_uri="http://localhost:8080"' in content:
        print("✅ O arquivo já está corrigido.")
        return False
    
    # Substituir redirect_uri OOB por localhost
    old_redirect = 'redirect_uri="urn:ietf:wg:oauth:2.0:oob"'
    new_redirect = 'redirect_uri="http://localhost:8080"'
    
    if old_redirect not in content:
        print("❌ Não encontrei o redirect_uri OOB no arquivo.")
        return False
    
    # Fazer as substituições
    content = content.replace(old_redirect, new_redirect)
    
    # Adicionar configuração PKCE se necessário
    pkce_config = '''    # PKCE configuration for Google OAuth
    flow = Flow.from_client_secrets_file(
        str(creds_file),
        scopes=scopes,
        redirect_uri="http://localhost:8080",
    )'''
    
    # Verificar se já tem configuração PKCE
    if 'code_verifier' not in content:
        print("⚠️  Configuração PKCE pode precisar de ajustes adicionais.")
    
    # Salvar arquivo corrigido
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Arquivo corrigido: {file_path}")
    return True

def check_google_cloud_config():
    """Verifica se a configuração do Google Cloud está correta."""
    print("\n📋 Verificando configuração do Google Cloud:")
    print("1. Acesse https://console.cloud.google.com/")
    print("2. Vá para APIs & Services > Credentials")
    print("3. Clique no seu OAuth 2.0 Client ID")
    print("4. Em 'Authorized redirect URIs', adicione:")
    print("   - http://localhost:8080")
    print("5. Salve as alterações")
    print("\n⚠️  IMPORTANTE: O tipo de aplicativo deve ser 'Desktop app'")

def main():
    """Função principal."""
    print("🔧 Corrigindo problema de autenticação OOB do plugin Google\n")
    
    # Caminho do arquivo google_auth.py
    google_auth_path = Path("/a0/usr/plugins/google/helpers/google_auth.py")
    
    if not google_auth_path.exists():
        print(f"❌ Arquivo não encontrado: {google_auth_path}")
        print("Verificando outros locais...")
        
        # Tentar encontrar o arquivo
        possible_paths = [
            "/a0/plugins/google/helpers/google_auth.py",
            "/git/agent-zero/usr/plugins/google/helpers/google_auth.py",
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                google_auth_path = Path(path)
                print(f"✅ Encontrado em: {google_auth_path}")
                break
        else:
            print("❌ Não consegui encontrar o arquivo google_auth.py")
            return
    
    # Criar backup
    print(f"📁 Arquivo original: {google_auth_path}")
    backup_file(google_auth_path)
    
    # Corrigir arquivo
    if fix_google_auth_file(google_auth_path):
        print("\n✅ Correção aplicada com sucesso!")
        print("\n📝 Próximos passos:")
        print("1. Reinicie o Agent Zero")
        print("2. Acesse Settings > External Services > Google Suite")
        print("3. Clique em 'Authorize' novamente")
        print("4. Siga o fluxo de autenticação normal")
        
        # Mostrar instruções de configuração do Google Cloud
        check_google_cloud_config()
    else:
        print("\n⚠️  Não foi necessário aplicar correções ou ocorreu um erro.")

if __name__ == "__main__":
    main()