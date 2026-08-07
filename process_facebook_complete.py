#!/usr/bin/env python3
"""
PROCESSAMENTO COMPLETO DOS DADOS FACEBOOK
Processa 1.txt e 2.txt sem consumir memória
"""

import sqlite3
import os
import hashlib
import re
import sys
from datetime import datetime

print('='*70)
print('🤖 PROCESSAMENTO COMPLETO FACEBOOK DATA')
print('='*70)
print()

# Configuração
db_path = '/a0/usr/uploads/BrazilianPeople.db'

# Verificar se database existe
if not os.path.exists(db_path):
    print(f'❌ Database não encontrado: {db_path}')
    sys.exit(1)

print(f'📊 Database: {db_path}')
print()

# Conectar ao database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Criar tabela se não existir
print('📊 Configurando tabela facebook_data...')
cursor.execute('''CREATE TABLE IF NOT EXISTS facebook_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefone TEXT,
    facebook_id TEXT,
    nome TEXT,
    sobrenome TEXT,
    nome_completo TEXT,
    genero TEXT,
    cidade TEXT,
    estado TEXT,
    relacionamento TEXT,
    empresa TEXT,
    data_cadastro TEXT,
    data_nascimento TEXT,
    email TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Criar índices para performance
print('⚡ Criando índices para busca rápida...')
indexes = [
    'CREATE INDEX IF NOT EXISTS idx_fb_phone ON facebook_data(telefone)',
    'CREATE INDEX IF NOT EXISTS idx_fb_hash ON facebook_data(hash)',
    'CREATE INDEX IF NOT EXISTS idx_fb_source ON facebook_data(fonte)',
    'CREATE INDEX IF NOT EXISTS idx_fb_name ON facebook_data(nome_completo)'
]

for idx_sql in indexes:
    try:
        cursor.execute(idx_sql)
    except Exception as e:
        print(f'   ⚠️ Erro no índice: {e}')

conn.commit()
print('✅ Tabela e índices configurados')
print()

def process_file_streaming(filepath, fonte, batch_size=50000):
    """Processa arquivo em streaming linha por linha"""
    filename = os.path.basename(filepath)
    
    if not os.path.exists(filepath):
        print(f'❌ Arquivo não encontrado: {filename}')
        return 0, 0, 0
    
    print(f'📁 PROCESSANDO: {filename}')
    print(f'   Fonte: {fonte}')
    print(f'   Batch size: {batch_size:,}')
    
    # Contar linhas primeiro (sem carregar na memória)
    print('   Contando linhas...')
    total_lines = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
    
    print(f'   Total linhas: {total_lines:,} ({total_lines/1000000:.2f}M)')
    print()
    
    # Iniciar processamento
    inserted = 0
    skipped = 0
    errors = 0
    batch = []
    
    start_time = datetime.now()
    last_report = start_time
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            if not line:
                skipped += 1
                continue
            
            try:
                # Dividir por ':'
                parts = line.split(':')
                
                # Extrair telefone (primeiro campo)
                telefone = parts[0].strip() if parts else ''
                
                # Verificar se é telefone válido
                digits = re.sub(r'[^0-9]', '', telefone)
                if not (8 <= len(digits) <= 15):
                    # Tentar encontrar telefone em outros campos
                    for part in parts:
                        digits = re.sub(r'[^0-9]', '', part)
                        if 8 <= len(digits) <= 15:
                            telefone = digits
                            break
                
                # Pular se não tem telefone
                if not telefone:
                    skipped += 1
                    continue
                
                # Extrair outros campos
                facebook_id = parts[1].strip() if len(parts) > 1 else ''
                nome = parts[2].strip() if len(parts) > 2 else ''
                sobrenome = parts[3].strip() if len(parts) > 3 else ''
                nome_completo = f'{nome} {sobrenome}'.strip()
                
                # Extrair campos adicionais se disponíveis
                genero = parts[4].strip() if len(parts) > 4 else ''
                cidade = parts[5].strip() if len(parts) > 5 else ''
                estado = parts[6].strip() if len(parts) > 6 else ''
                relacionamento = parts[7].strip() if len(parts) > 7 else ''
                empresa = parts[8].strip() if len(parts) > 8 else ''
                data_cadastro = parts[9].strip() if len(parts) > 9 else ''
                data_nascimento = parts[10].strip() if len(parts) > 10 else ''
                email = parts[11].strip() if len(parts) > 11 else ''
                
                # Criar hash para detecção de duplicados
                data_str = f"{telefone}:{facebook_id}:{nome}:{sobrenome}"
                data_hash = hashlib.md5(data_str.encode()).hexdigest()
                
                # Verificar se já existe
                cursor.execute('SELECT 1 FROM facebook_data WHERE hash=?', (data_hash,))
                if not cursor.fetchone():
                    # Adicionar ao batch
                    batch.append((
                        telefone, facebook_id, nome, sobrenome, nome_completo,
                        genero, cidade, estado, relacionamento, empresa,
                        data_cadastro, data_nascimento, email, data_hash, fonte
                    ))
                    inserted += 1
                else:
                    skipped += 1
                
                # Inserir em batch quando atingir o tamanho
                if len(batch) >= batch_size:
                    cursor.executemany('''INSERT OR IGNORE INTO facebook_data 
                        (telefone, facebook_id, nome, sobrenome, nome_completo,
                         genero, cidade, estado, relacionamento, empresa,
                         data_cadastro, data_nascimento, email, hash, fonte)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch)
                    conn.commit()
                    batch = []
                    
                    # Reportar progresso a cada 50,000 linhas
                    if line_num % 50000 == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        speed = line_num / elapsed if elapsed > 0 else 0
                        percent = (line_num / total_lines) * 100
                        
                        print(f'   Progresso: {line_num:,}/{total_lines:,} ({percent:.1f}%) | ' \
                              f'Novos: {inserted:,} | Velocidade: {speed:.0f} linhas/seg')
            
            except Exception as e:
                errors += 1
                continue
    
    # Inserir batch final
    if batch:
        cursor.executemany('''INSERT OR IGNORE INTO facebook_data 
            (telefone, facebook_id, nome, sobrenome, nome_completo,
             genero, cidade, estado, relacionamento, empresa,
             data_cadastro, data_nascimento, email, hash, fonte)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
        conn.commit()
    
    # Resultado final
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f'\n✅ {filename} PROCESSADO:')
    print(f'   Tempo total: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)')
    print(f'   Linhas processadas: {line_num:,}')
    print(f'   Novos registros: {inserted:,}')
    print(f'   Duplicados/pulados: {skipped:,}')
    print(f'   Erros: {errors:,}')
    
    if elapsed > 0:
        print(f'   Velocidade média: {line_num/elapsed:.0f} linhas/segundo')
        print(f'   Registros/segundo: {inserted/elapsed:.0f}')
    
    print()
    
    return inserted, skipped, errors

# Verificar status atual
print('🔍 VERIFICANDO STATUS ATUAL...')
print()

try:
    cursor.execute('SELECT COUNT(*) FROM facebook_data')
    current_count = cursor.fetchone()[0]
    print(f'📊 Registros atuais na tabela facebook_data: {current_count:,}')
    
    cursor.execute('SELECT fonte, COUNT(*) FROM facebook_data GROUP BY fonte')
    sources = cursor.fetchall()
    
    if sources:
        print('🔍 Distribuição por fonte:')
        for fonte, count in sources:
            print(f'   {fonte}: {count:,}')
    else:
        print('📱 Tabela facebook_data está vazia')
    
    print()

except Exception as e:
    print(f'⚠️ Erro ao verificar status: {e}')
    print('   Continuando com tabela vazia...')
    print()

# Processar arquivos
print('🚀 INICIANDO PROCESSAMENTO DOS ARQUIVOS...')
print()

files_to_process = [
    ('/a0/usr/uploads/1.txt', 'facebook_1'),
    ('/a0/usr/uploads/2.txt', 'facebook_2')
]

total_inserted = 0
total_skipped = 0
total_errors = 0

for filepath, fonte in files_to_process:
    if os.path.exists(filepath):
        inserted, skipped, errors = process_file_streaming(filepath, fonte, batch_size=50000)
        total_inserted += inserted
        total_skipped += skipped
        total_errors += errors
    else:
        print(f'❌ Arquivo não encontrado: {filepath}')
        print()

# Resumo final
print('='*70)
print('📈 RESUMO FINAL DO PROCESSAMENTO')
print('='*70)
print()

print(f'🎯 TOTAL NOVOS REGISTROS ADICIONADOS: {total_inserted:,}')
print(f'📊 TOTAL DUPLICADOS/PULADOS: {total_skipped:,}')
print(f'⚠️ TOTAL ERROS: {total_errors:,}')
print(f'📈 TOTAL LINHAS PROCESSADAS: {total_inserted + total_skipped + total_errors:,}')
print()

# Verificar contagem final
cursor.execute('SELECT COUNT(*) FROM facebook_data')
fb_total = cursor.fetchone()[0]

cursor.execute('SELECT fonte, COUNT(*) FROM facebook_data GROUP BY fonte')
print('🔍 DISTRIBUIÇÃO FINAL POR FONTE:')
for fonte, count in cursor.fetchall():
    print(f'   {fonte}: {count:,}')

print()
print(f'📊 TOTAL NA TABELA FACEBOOK_DATA: {fb_total:,}')

# Calcular total do sistema
print()
print('📈 TOTAL GERAL DO SISTEMA:')
print('-'*40)

tables = [
    ('facebook_data', '📱 Dados Facebook'),
    ('telefones_processados', '📞 Telefones'),
    ('contatos_excel_processados', '📊 Contatos Excel'),
    ('contatos_vcf_processados', '📇 Contatos VCF'),
    ('pessoas', '👥 Pessoas brasileiras')
]

system_total = 0

for table_name, description in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'{description}: {count:,}')
        system_total += count
    except Exception as e:
        print(f'{description}: Tabela não existe')

print(f'\n🎯 TOTAL GERAL NO SISTEMA: {system_total:,}')
print()

# Fechar conexão
conn.close()

print('='*70)
print('✅ PROCESSAMENTO COMPLETO CONCLUÍDO COM SUCESSO!')
print('='*70)
print()
print('🎯 OS DADOS FACEBOOK ESTÃO PRONTOS PARA:')
print('   1. Consulta por telefone ou nome')
print('   2. Cruzamento com outros sistemas')
print('   3. Integração com JARVIS para multi-search')
print()
