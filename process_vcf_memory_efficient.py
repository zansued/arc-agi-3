#!/usr/bin/env python3
"""
MEMORY-EFFICIENT VCF CONTACTS PROCESSING
Processes 38 VCF files without consuming system memory
"""

import sqlite3
import os
import hashlib
import re
import sys
from datetime import datetime

print('='*70)
print('🤖 PROCESSAMENTO VCF SEM CONSUMO DE MEMÓRIA')
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

# Ensure vcf contacts table exists
print('📊 Verificando tabela contatos_vcf_processados...')
cursor.execute('''CREATE TABLE IF NOT EXISTS contatos_vcf_processados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    telefones TEXT,
    emails TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Create indexes BEFORE processing
print('⚡ Criando índices para performance...')
indexes = [
    'CREATE INDEX IF NOT EXISTS idx_vcf_hash ON contatos_vcf_processados(hash)',
    'CREATE INDEX IF NOT EXISTS idx_vcf_source ON contatos_vcf_processados(fonte)',
    'CREATE INDEX IF NOT EXISTS idx_vcf_name ON contatos_vcf_processados(nome)',
    'CREATE INDEX IF NOT EXISTS idx_vcf_phones ON contatos_vcf_processados(telefones)'
]

for idx_sql in indexes:
    try:
        cursor.execute(idx_sql)
    except Exception as e:
        print(f'   ⚠️ Erro no índice (continuando): {e}')

conn.commit()
print('✅ Tabela e índices configurados')
print()

def parse_vcf_line_by_line(filepath, fonte):
    """Parse VCF file line by line without loading in memory"""
    filename = os.path.basename(filepath)
    
    if not os.path.exists(filepath):
        print(f'❌ Arquivo não encontrado: {filename}')
        return 0, 0
    
    print(f'📁 Processando: {filename}')
    print(f'   Fonte: {fonte}')
    
    # Count lines first
    print('   Contando linhas...')
    total_lines = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
    
    print(f'   Total linhas: {total_lines:,}')
    print()
    
    # Start processing
    inserted = 0
    skipped = 0
    batch = []
    
    start_time = datetime.now()
    last_report = start_time
    
    current_contact = {
        'nome': '',
        'telefones': [],
        'emails': []
    }
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            if not line:
                continue
            
            # Start of new contact
            if line.startswith('BEGIN:VCARD'):
                current_contact = {'nome': '', 'telefones': [], 'emails': []}
            
            # End of contact - process it
            elif line.startswith('END:VCARD'):
                if current_contact['nome'] or current_contact['telefones']:
                    # Prepare data
                    nome = current_contact['nome'] or 'Sem nome'
                    telefones_str = ';'.join(current_contact['telefones']) if current_contact['telefones'] else ''
                    emails_str = ';'.join(current_contact['emails']) if current_contact['emails'] else ''
                    
                    # Create hash for duplicate detection
                    data_str = f"{nome}:{telefones_str}:{emails_str}"
                    data_hash = hashlib.md5(data_str.encode()).hexdigest()
                    
                    # Check if already exists
                    cursor.execute('SELECT 1 FROM contatos_vcf_processados WHERE hash=?', (data_hash,))
                    if not cursor.fetchone():
                        batch.append((
                            nome,
                            telefones_str,
                            emails_str,
                            data_hash,
                            fonte
                        ))
                        inserted += 1
                    else:
                        skipped += 1
                    
                    # Insert batch when full
                    if len(batch) >= 1000:
                        try:
                            cursor.executemany('''INSERT OR IGNORE INTO contatos_vcf_processados 
                                (nome, telefones, emails, hash, fonte)
                                VALUES (?, ?, ?, ?, ?)
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
                                      f'Novos: {inserted:,} | Duplicados: {skipped:,} | Velocidade: {speed:.0f} linhas/seg')
                                last_report = current_time
                        
                        except Exception as e:
                            print(f'   ⚠️ Erro no batch (continuando): {e}')
                            conn.rollback()
                            batch = []
                
                current_contact = {'nome': '', 'telefones': [], 'emails': []}
            
            # Parse contact fields
            elif line.startswith('FN:'):
                current_contact['nome'] = line[3:].strip()
            
            elif line.startswith('N:'):
                if not current_contact['nome']:
                    # Try to extract name from N field
                    name_parts = line[2:].strip().split(';')
                    if name_parts:
                        # Format: Last;First;Middle;Prefix;Suffix
                        if len(name_parts) >= 2:
                            current_contact['nome'] = f'{name_parts[1]} {name_parts[0]}'.strip()
                        elif name_parts[0]:
                            current_contact['nome'] = name_parts[0]
            
            elif line.startswith('TEL;') or line.startswith('TEL:'):
                # Extract phone number
                phone_match = re.search(r'[:;]([0-9+\-\(\)\s]+)', line)
                if phone_match:
                    phone = re.sub(r'[^0-9+]', '', phone_match.group(1))
                    if phone and len(phone) >= 8:
                        current_contact['telefones'].append(phone)
            
            elif line.startswith('EMAIL;') or line.startswith('EMAIL:'):
                # Extract email
                email_match = re.search(r'[:;]([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', line)
                if email_match:
                    current_contact['emails'].append(email_match.group(1))
            
            # Progress report every 5000 lines
            if line_num % 5000 == 0:
                current_time = datetime.now()
                if (current_time - last_report).total_seconds() >= 30:
                    elapsed = (current_time - start_time).total_seconds()
                    speed = line_num / elapsed if elapsed > 0 else 0
                    percent = (line_num / total_lines) * 100
                    
                    print(f'   Progresso: {line_num:,}/{total_lines:,} ({percent:.1f}%) | ' \
                          f'Novos: {inserted:,} | Duplicados: {skipped:,} | Velocidade: {speed:.0f} linhas/seg')
                    last_report = current_time
    
    # Insert final batch
    if batch:
        try:
            cursor.executemany('''INSERT OR IGNORE INTO contatos_vcf_processados 
                (nome, telefones, emails, hash, fonte)
                VALUES (?, ?, ?, ?, ?)
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
        print(f'   Contatos/seg: {inserted/elapsed:.0f}')
    
    print()
    
    return inserted, skipped

# Check current status
print('🔍 VERIFICANDO STATUS ATUAL DOS CONTATOS VCF...')
print()

try:
    cursor.execute('SELECT COUNT(*) FROM contatos_vcf_processados')
    current_count = cursor.fetchone()[0]
    print(f'📊 Registros atuais na tabela contatos_vcf_processados: {current_count:,}')
    
    cursor.execute('SELECT fonte, COUNT(*) FROM contatos_vcf_processados GROUP BY fonte')
    sources = cursor.fetchall()
    
    if sources:
        print('🔍 Distribuição por fonte:')
        for fonte, count in sources:
            print(f'   {fonte}: {count:,}')
    else:
        print('📭 Tabela contatos_vcf_processados está vazia')
    
    print()

except Exception as e:
    print(f'⚠️ Erro ao verificar status: {e}')
    print('   Continuando com tabela vazia...')
    print()

# Process VCF files
print('🚀 INICIANDO PROCESSAMENTO DOS ARQUIVOS VCF...')
print()

# Group VCF files by type
uploads_dir = '/a0/usr/uploads'
vcf_files = []

for filename in os.listdir(uploads_dir):
    if filename.endswith('.vcf'):
        filepath = os.path.join(uploads_dir, filename)
        
        # Determine source type
        if 'BRK VIEWS' in filename:
            fonte = 'brk_views'
        elif 'contatos' in filename.lower():
            fonte = 'contatos_geral'
        else:
            # Extract state from filename
            state_match = re.search(r'\((AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\)', filename)
            if state_match:
                fonte = f'estado_{state_match.group(1).lower()}'
            else:
                fonte = 'outros'
        
        vcf_files.append((filepath, fonte, filename))

print(f'📁 Total de arquivos VCF para processar: {len(vcf_files)}')
print()

# Process files
total_inserted = 0
total_skipped = 0

for filepath, fonte, filename in sorted(vcf_files):
    inserted, skipped = parse_vcf_line_by_line(filepath, fonte)
    total_inserted += inserted
    total_skipped += skipped

# Final summary
print('='*70)
print('📈 RESUMO FINAL DO PROCESSAMENTO VCF')
print('='*70)
print()

print(f'🎯 TOTAL NOVOS CONTATOS ADICIONADOS: {total_inserted:,}')
print(f'📊 TOTAL DUPLICADOS REMOVIDOS: {total_skipped:,}')
print(f'📈 TOTAL CONTATOS PROCESSADOS: {total_inserted + total_skipped:,}')
print()

# Check final count
cursor.execute('SELECT COUNT(*) FROM contatos_vcf_processados')
vcf_total = cursor.fetchone()[0]

cursor.execute('SELECT fonte, COUNT(*) FROM contatos_vcf_processados GROUP BY fonte ORDER BY COUNT(*) DESC')
print('🔍 DISTRIBUIÇÃO FINAL POR FONTE:')
for fonte, count in cursor.fetchall():
    print(f'   {fonte}: {count:,}')

print()
print(f'📊 TOTAL NA TABELA CONTATOS_VCF_PROCESSADOS: {vcf_total:,}')

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
print('✅ PROCESSAMENTO VCF CONCLUÍDO SEM CONSUMO DE MEMÓRIA!')
print('='*70)
print()
print('🎯 CONTATOS VCF PRONTOS PARA CONSULTA E CRUZAMENTO:')
print('   1. Consulta por nome ou telefone')
print('   2. Cruzamento com 9.15M brasileiros (CPF database)')
print('   3. Cruzamento com 16.1M perfis Facebook')
print('   4. Cruzamento com 8M telefones')
print('   5. Integração com JARVIS para multi-search')
print()
