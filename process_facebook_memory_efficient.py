#!/usr/bin/env python3
"""
MEMORY-EFFICIENT FACEBOOK DATA PROCESSING
Processes 1.txt and 2.txt without consuming system memory
"""

import sqlite3
import os
import hashlib
import re
import sys
from datetime import datetime

print('='*70)
print('🤖 PROCESSAMENTO FACEBOOK SEM CONSUMO DE MEMÓRIA')
print('='*70)
print()

# Database path
db_path = '/a0/usr/uploads/BrazilianPeople.db'

if not os.path.exists(db_path):
    print(f'❌ Database não encontrado: {db_path}')
    sys.exit(1)

print(f'📊 Database: {db_path}')
print()

# Connect with timeout
conn = sqlite3.connect(db_path, timeout=30)
cursor = conn.cursor()

# Create facebook_data table if not exists
print('📊 Criando tabela facebook_data...')
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

# Create indexes BEFORE processing
print('⚡ Criando índices para performance...')
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
        print(f'   ⚠️ Erro no índice (continuando): {e}')

conn.commit()
print('✅ Tabela e índices configurados')
print()

def process_file_streaming(filepath, fonte, batch_size=50000):
    """Processa arquivo em streaming linha por linha"""
    filename = os.path.basename(filepath)
    
    if not os.path.exists(filepath):
        print(f'❌ Arquivo não encontrado: {filename}')
        return 0, 0
    
    print(f'📁 Processando: {filename}')
    print(f'   Fonte: {fonte}')
    print(f'   Batch size: {batch_size:,}')
    
    # Count lines first
    print('   Contando linhas...')
    total_lines = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
    
    print(f'   Total linhas: {total_lines:,} ({total_lines/1000000:.2f}M)')
    print()
    
    # Start processing
    inserted = 0
    skipped = 0
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
                # Split by ':'
                parts = line.split(':')
                
                # Extract phone (first field)
                telefone = parts[0].strip() if parts else ''
                
                # Validate phone (8-15 digits)
                digits = re.sub(r'[^0-9]', '', telefone)
                if not (8 <= len(digits) <= 15):
                    # Try to find phone in other fields
                    for part in parts:
                        digits = re.sub(r'[^0-9]', '', part)
                        if 8 <= len(digits) <= 15:
                            telefone = digits
                            break
                
                # Skip if no valid phone
                if not telefone:
                    skipped += 1
                    continue
                
                # Extract other fields
                facebook_id = parts[1].strip() if len(parts) > 1 else ''
                nome = parts[2].strip() if len(parts) > 2 else ''
                sobrenome = parts[3].strip() if len(parts) > 3 else ''
                nome_completo = f'{nome} {sobrenome}'.strip()
                
                # Extract additional fields if available
                genero = parts[4].strip() if len(parts) > 4 else ''
                cidade = parts[5].strip() if len(parts) > 5 else ''
                estado = parts[6].strip() if len(parts) > 6 else ''
                relacionamento = parts[7].strip() if len(parts) > 7 else ''
                empresa = parts[8].strip() if len(parts) > 8 else ''
                data_cadastro = parts[9].strip() if len(parts) > 9 else ''
                data_nascimento = parts[10].strip() if len(parts) > 10 else ''
                email = parts[11].strip() if len(parts) > 11 else ''
                
                # Create hash for duplicate detection
                data_str = f"{telefone}:{facebook_id}:{nome}:{sobrenome}"
                data_hash = hashlib.md5(data_str.encode()).hexdigest()
                
                # Check if already exists
                cursor.execute('SELECT 1 FROM facebook_data WHERE hash=?', (data_hash,))
                if not cursor.fetchone():
                    batch.append((
                        telefone, facebook_id, nome, sobrenome, nome_completo,
                        genero, cidade, estado, relacionamento, empresa,
                        data_cadastro, data_nascimento, email, data_hash, fonte
                    ))
                    inserted += 1
                else:
                    skipped += 1
                
                # Insert batch when full
                if len(batch) >= batch_size:
                    try:
                        cursor.executemany('''INSERT OR IGNORE INTO facebook_data 
                            (telefone, facebook_id, nome, sobrenome, nome_completo,
                             genero, cidade, estado, relacionamento, empresa,
                             data_cadastro, data_nascimento, email, hash, fonte)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', batch)
                        conn.commit()
                        batch = []
                        
                        # Report progress every 30 seconds
                        current_time = datetime.now()
                        if (current_time - last_report).total_seconds() >= 30:
                            elapsed = (current_time - start_time).total_seconds()
                            speed = line_num / elapsed if elapsed > 0 else 0
                            percent = (line_num / total_lines) * 100
                            
                            print(f'   Progresso: {line_num:,}/{total_lines:,} ({percent:.1f}%) | ' \
                                  f'Novos: {inserted:,} | Velocidade: {speed:.0f} linhas/seg')
                            last_report = current_time
                    
                    except Exception as e:
                        print(f'   ⚠️ Erro no batch (continuando): {e}')
                        conn.rollback()
                        batch = []
            
            except Exception as e:
                skipped += 1
                continue
    
    # Insert final batch
    if batch:
        try:
            cursor.executemany('''INSERT OR IGNORE INTO facebook_data 
                (telefone, facebook_id, nome, sobrenome, nome_completo,
                 genero, cidade, estado, relacionamento, empresa,
                 data_cadastro, data_nascimento, email, hash, fonte)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)
            conn.commit()
        
        except Exception as e:
            print(f'   ⚠️ Erro no batch final: {e}')
            conn.rollback()
    
    # Final results
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f'\n✅ {filename} PROCESSADO:')
    print(f'   Tempo: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)')
    print(f'   Linhas: {line_num:,}')
    print(f'   Novos: {inserted:,}')
    print(f'   Duplicados: {skipped:,}')
    
    if elapsed > 0:
        print(f'   Velocidade: {line_num/elapsed:.0f} linhas/seg')
        print(f'   Registros/seg: {inserted/elapsed:.0f}')
    
    print()
    
    return inserted, skipped

# Check current status
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

# Process files
print('🚀 INICIANDO PROCESSAMENTO DOS ARQUIVOS FACEBOOK...')
print()

files_to_process = [
    ('/a0/usr/uploads/1.txt', 'facebook_1'),
    ('/a0/usr/uploads/2.txt', 'facebook_2')
]

total_inserted = 0
total_skipped = 0

for filepath, fonte in files_to_process:
    if os.path.exists(filepath):
        inserted, skipped = process_file_streaming(filepath, fonte, batch_size=50000)
        total_inserted += inserted
        total_skipped += skipped
    else:
        print(f'❌ Arquivo não encontrado: {filepath}')
        print()

# Final summary
print('='*70)
print('📈 RESUMO FINAL DO PROCESSAMENTO')
print('='*70)
print()

print(f'🎯 TOTAL NOVOS REGISTROS: {total_inserted:,}')
print(f'📊 TOTAL DUPLICADOS: {total_skipped:,}')
print(f'📈 TOTAL LINHAS: {total_inserted + total_skipped:,}')
print()

# Check final count
cursor.execute('SELECT COUNT(*) FROM facebook_data')
fb_total = cursor.fetchone()[0]

cursor.execute('SELECT fonte, COUNT(*) FROM facebook_data GROUP BY fonte')
print('🔍 DISTRIBUIÇÃO FINAL:')
for fonte, count in cursor.fetchall():
    print(f'   {fonte}: {count:,}')

print()
print(f'📊 TOTAL NA TABELA FACEBOOK_DATA: {fb_total:,}')

# Calculate system total
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

# Close connection
conn.close()

print('='*70)
print('✅ PROCESSAMENTO CONCLUÍDO SEM CONSUMO DE MEMÓRIA!')
print('='*70)
print()
print('🎯 DADOS FACEBOOK PRONTOS PARA CONSULTA E CRUZAMENTO:')
print('   1. Consulta por telefone ou nome')
print('   2. Cruzamento com 9.15M brasileiros (CPF database)')
print('   3. Cruzamento com 8M telefones (Brazil.txt)')
print('   4. Integração com JARVIS para multi-search')
print()
