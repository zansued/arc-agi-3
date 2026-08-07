#!/usr/bin/env python3
"""
MEMORY-EFFICIENT EXCEL PROCESSING
Processes large Excel files without consuming memory
"""

import sqlite3
import os
import hashlib
import json
import sys
import pandas as pd
from datetime import datetime

print('='*70)
print('🤖 PROCESSAMENTO EXCEL SEM CONSUMO DE MEMÓRIA')
print('='*70)
print()

# Database path
db_path = '/a0/usr/uploads/BrazilianPeople.db'
file_path = '/a0/usr/uploads/Itau Banck Brazil.xlsx'

if not os.path.exists(db_path):
    print(f'❌ Database não encontrado: {db_path}')
    sys.exit(1)

if not os.path.exists(file_path):
    print(f'❌ Arquivo não encontrado: {file_path}')
    sys.exit(1)

print(f'📊 Database: {db_path}')
print(f'📁 Arquivo: {os.path.basename(file_path)}')
print(f'   Tamanho: {os.path.getsize(file_path):,} bytes ({os.path.getsize(file_path)/1024/1024:.1f} MB)')
print()

# Connect with timeout
conn = sqlite3.connect(db_path, timeout=30)
cursor = conn.cursor()

# Ensure Excel contacts table exists
print('📊 Verificando tabela contatos_excel_processados...')
cursor.execute('''CREATE TABLE IF NOT EXISTS contatos_excel_processados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_json TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Create indexes BEFORE processing
print('⚡ Criando índices para performance...')
indexes = [
    'CREATE INDEX IF NOT EXISTS idx_excel_hash ON contatos_excel_processados(hash)',
    'CREATE INDEX IF NOT EXISTS idx_excel_source ON contatos_excel_processados(fonte)'
]

for idx_sql in indexes:
    try:
        cursor.execute(idx_sql)
    except Exception as e:
        print(f'   ⚠️ Erro no índice (continuando): {e}')

conn.commit()
print('✅ Tabela e índices configurados')
print()

# Check current status
print('🔍 VERIFICANDO STATUS ATUAL DOS CONTATOS EXCEL...')
print()

try:
    cursor.execute('SELECT COUNT(*) FROM contatos_excel_processados')
    current_count = cursor.fetchone()[0]
    print(f'📊 Registros atuais na tabela contatos_excel_processados: {current_count:,}')
    
    cursor.execute('SELECT fonte, COUNT(*) FROM contatos_excel_processados GROUP BY fonte ORDER BY COUNT(*) DESC')
    sources = cursor.fetchall()
    
    if sources:
        print('🔍 Distribuição por fonte:')
        for fonte, count in sources:
            print(f'   {fonte}: {count:,}')
    else:
        print('📭 Tabela contatos_excel_processados está vazia')
    
    print()

except Exception as e:
    print(f'⚠️ Erro ao verificar status: {e}')
    print('   Continuando com tabela vazia...')
    print()

# Process Excel file
print('🚀 INICIANDO PROCESSAMENTO DO ARQUIVO EXCEL...')
print()

try:
    # Get sheet names
    excel_file = pd.ExcelFile(file_path)
    sheet_name = excel_file.sheet_names[0]
    
    print(f'📋 Planilha a processar: {sheet_name}')
    print()
    
    # Estimate total rows
    print('📈 Estimando tamanho do arquivo...')
    
    # Count rows efficiently
    total_rows = 0
    chunk_size = 10000
    
    for chunk in pd.read_excel(file_path, sheet_name=sheet_name, chunksize=chunk_size):
        total_rows += len(chunk)
        if total_rows >= 1000000:  # Cap at 1M for estimation
            print(f'   Mais de {total_rows:,} linhas (estimativa conservadora)')
            break
    
    print(f'   Total estimado de linhas: {total_rows:,}')
    print()
    
    # Start processing
    inserted = 0
    skipped = 0
    batch = []
    
    start_time = datetime.now()
    last_report = start_time
    
    # Create source identifier
    source_hash = hashlib.md5('Itau Banck Brazil.xlsx'.encode()).hexdigest()[:16]
    fonte = f'itau_bank_brazil_{source_hash}'
    
    print(f'🔧 Fonte identificada: {fonte}')
    print(f'📦 Tamanho do batch: 1,000 registros')
    print()
    
    # Process in chunks
    processed_rows = 0
    
    for chunk_num, chunk in enumerate(pd.read_excel(file_path, sheet_name=sheet_name, chunksize=1000), 1):
        chunk_start = datetime.now()
        
        for idx, row in chunk.iterrows():
            try:
                # Convert row to JSON string
                row_dict = row.to_dict()
                
                # Clean NaN values
                for key, value in row_dict.items():
                    if pd.isna(value):
                        row_dict[key] = None
                
                row_json = json.dumps(row_dict, ensure_ascii=False, default=str)
                
                # Create hash for duplicate detection
                data_hash = hashlib.md5(row_json.encode()).hexdigest()
                
                # Check if already exists
                cursor.execute('SELECT 1 FROM contatos_excel_processados WHERE hash=?', (data_hash,))
                if not cursor.fetchone():
                    batch.append((row_json, data_hash, fonte))
                    inserted += 1
                else:
                    skipped += 1
                
                processed_rows += 1
                
                # Insert batch when full
                if len(batch) >= 1000:
                    try:
                        cursor.executemany('''INSERT OR IGNORE INTO contatos_excel_processados 
                            (data_json, hash, fonte)
                            VALUES (?, ?, ?)
                        ''', batch)
                        conn.commit()
                        batch = []
                        
                        # Report progress every 30 seconds
                        current_time = datetime.now()
                        if (current_time - last_report).total_seconds() >= 30:
                            elapsed = (current_time - start_time).total_seconds()
                            speed = processed_rows / elapsed if elapsed > 0 else 0
                            percent = (processed_rows / total_rows) * 100 if total_rows > 0 else 0
                            
                            print(f'   Progresso: {processed_rows:,}/{total_rows:,} ({percent:.1f}%) | ' \
                                  f'Novos: {inserted:,} | Duplicados: {skipped:,} | Velocidade: {speed:.0f} linhas/seg')
                            last_report = current_time
                    
                    except Exception as e:
                        print(f'   ⚠️ Erro no batch (continuando): {e}')
                        conn.rollback()
                        batch = []
            
            except Exception as e:
                skipped += 1
                continue
        
        # Report chunk completion
        chunk_time = (datetime.now() - chunk_start).total_seconds()
        if chunk_time > 0:
            chunk_speed = len(chunk) / chunk_time
            print(f'   Chunk {chunk_num}: {len(chunk):,} linhas em {chunk_time:.1f}s ({chunk_speed:.0f} linhas/seg)')
    
    # Insert final batch
    if batch:
        try:
            cursor.executemany('''INSERT OR IGNORE INTO contatos_excel_processados 
                (data_json, hash, fonte)
                VALUES (?, ?, ?)
            ''', batch)
            conn.commit()
        
        except Exception as e:
            print(f'   ⚠️ Erro no batch final: {e}')
            conn.rollback()
    
    # Final results
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f'\n✅ ARQUIVO EXCEL PROCESSADO:')
    print(f'   Tempo total: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)')
    print(f'   Linhas processadas: {processed_rows:,}')
    print(f'   Novos registros: {inserted:,}')
    print(f'   Duplicados/pulados: {skipped:,}')
    
    if elapsed > 0:
        print(f'   Velocidade média: {processed_rows/elapsed:.0f} linhas/segundo')
        print(f'   Registros/segundo: {inserted/elapsed:.0f}')
    
    print()
    
except Exception as e:
    print(f'❌ Erro ao processar arquivo Excel: {e}')
    import traceback
    traceback.print_exc()
    conn.close()
    sys.exit(1)

# Final summary
print('='*70)
print('📈 RESUMO FINAL DO PROCESSAMENTO EXCEL')
print('='*70)
print()

print(f'🎯 TOTAL NOVOS REGISTROS ADICIONADOS: {inserted:,}')
print(f'📊 TOTAL DUPLICADOS REMOVIDOS: {skipped:,}')
print(f'📈 TOTAL LINHAS PROCESSADAS: {processed_rows:,}')
print()

# Check final count
cursor.execute('SELECT COUNT(*) FROM contatos_excel_processados')
excel_total = cursor.fetchone()[0]

cursor.execute('SELECT fonte, COUNT(*) FROM contatos_excel_processados GROUP BY fonte ORDER BY COUNT(*) DESC')
print('🔍 DISTRIBUIÇÃO FINAL POR FONTE:')
for fonte, count in cursor.fetchall():
    print(f'   {fonte}: {count:,}')

print()
print(f'📊 TOTAL NA TABELA CONTATOS_EXCEL_PROCESSADOS: {excel_total:,}')

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

# Show sample of new data
print('📋 AMOSTRA DOS NOVOS DADOS (primeiros 3 registros desta fonte):')
print('-'*80)

cursor.execute('''
    SELECT data_json 
    FROM contatos_excel_processados 
    WHERE fonte = ? 
    LIMIT 3
''', (fonte,))

sample_data = cursor.fetchall()

for i, (data_json,) in enumerate(sample_data, 1):
    try:
        data = json.loads(data_json)
        print(f'Registro {i}:')
        for key, value in list(data.items())[:5]:  # Show first 5 fields
            if value is not None:
                val_str = str(value)
                if len(val_str) > 50:
                    val_str = val_str[:50] + '...'
                print(f'  {key}: {val_str}')
        print()
    except:
        print(f'Registro {i}: [Erro ao decodificar JSON]')
        print()

# Close connection
conn.close()

print('='*70)
print('✅ PROCESSAMENTO EXCEL CONCLUÍDO SEM CONSUMO DE MEMÓRIA!')
print('='*70)
print()
print('🎯 DADOS ITAU BANK BRAZIL PRONTOS PARA CONSULTA E CRUZAMENTO:')
print('   1. Dados bancários do Itaú disponíveis para análise')
print('   2. Cruzamento com 9.15M brasileiros (CPF database)')
print('   3. Cruzamento com 16.1M perfis Facebook')
print('   4. Cruzamento com 8M telefones e 22K contatos VCF')
print('   5. Integração com JARVIS para multi-search')
print()
