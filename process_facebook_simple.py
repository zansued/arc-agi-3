#!/usr/bin/env python3
"""
PROCESSAMENTO SIMPLES E EFICIENTE DOS DADOS FACEBOOK
"""

import sqlite3
import os
import hashlib
import re
import sys
from datetime import datetime

print('='*60)
print('PROCESSAMENTO FACEBOOK DATA')
print('='*60)
print()

# Configuração
db_path = '/a0/usr/uploads/BrazilianPeople.db'

if not os.path.exists(db_path):
    print(f'❌ Database não encontrado: {db_path}')
    sys.exit(1)

print(f'📊 Database: {db_path}')
print()

# Conectar ao database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Criar tabela se não existir
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

# Criar índices
print('⚡ Criando índices...')
try:
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_phone ON facebook_data(telefone)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_hash ON facebook_data(hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_source ON facebook_data(fonte)')
except:
    pass

conn.commit()
print('✅ Tabela e índices prontos')
print()

def process_file(filepath, fonte):
    """Processa arquivo em streaming"""
    filename = os.path.basename(filepath)
    
    if not os.path.exists(filepath):
        print(f'❌ Arquivo não encontrado: {filename}')
        return 0, 0
    
    print(f'📁 Processando: {filename}')
    print(f'   Fonte: {fonte}')
    
    # Contar linhas
    print('   Contando linhas...')
    total_lines = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
    
    print(f'   Total linhas: {total_lines:,}')
    print()
    
    # Processar
    inserted = 0
    skipped = 0
    batch = []
    batch_size = 100000
    
    start_time = datetime.now()
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            if not line:
                skipped += 1
                continue
            
            try:
                parts = line.split(':')
                
                # Extrair telefone
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
                
                if not telefone:
                    skipped += 1
                    continue
                
                # Extrair outros campos
                facebook_id = parts[1].strip() if len(parts) > 1 else ''
                nome = parts[2].strip() if len(parts) > 2 else ''
                sobrenome = parts[3].strip() if len(parts) > 3 else ''
                nome_completo = f'{nome} {sobrenome}'.strip()
                
                genero = parts[4].strip() if len(parts) > 4 else ''
                cidade = parts[5].strip() if len(parts) > 5 else ''
                estado = parts[6].strip() if len(parts) > 6 else ''
                relacionamento = parts[7].strip() if len(parts) > 7 else ''
                empresa = parts[8].strip() if len(parts) > 8 else ''
                data_cadastro = parts[9].strip() if len(parts) > 9 else ''
                data_nascimento = parts[10].strip() if len(parts) > 10 else ''
                email = parts[11].strip() if len(parts) > 11 else ''
                
                # Criar hash para duplicados
                data_str = f"{telefone}:{facebook_id}:{nome}:{sobrenome}"
                data_hash = hashlib.md5(data_str.encode()).hexdigest()
                
                # Verificar duplicado
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
                
                # Inserir em batch
                if len(batch) >= batch_size:
                    cursor.executemany('''INSERT OR IGNORE INTO facebook_data 
                        (telefone, facebook_id, nome, sobrenome, nome_completo,
                         genero, cidade, estado, relacionamento, empresa,
                         data_cadastro, data_nascimento, email, hash, fonte)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch)
                    conn.commit()
                    batch = []
                    
                    # Progresso
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = line_num / elapsed if elapsed > 0 else 0
                    percent = (line_num / total_lines) * 100
                    
                    print(f'   Progresso: {line_num:,}/{total_lines:,} ({percent:.1f}%) | ' \
                          f'Novos: {inserted:,} | Velocidade: {speed:.0f} linhas/seg')
            
            except Exception as e:
                skipped += 1
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
    
    # Resultado
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f'\n✅ {filename} processado:')
    print(f'   Tempo: {elapsed:.1f} segundos')
    print(f'   Linhas: {line_num:,}')
    print(f'   Novos: {inserted:,}')
    print(f'   Duplicados: {skipped:,}')
    if elapsed > 0:
        print(f'   Velocidade: {line_num/elapsed:.0f} linhas/seg')
    print()
    
    return inserted, skipped

# Verificar status atual
print('🔍 Verificando status atual...')
print()

try:
    cursor.execute('SELECT COUNT(*) FROM facebook_data')
    current = cursor.fetchone()[0]
    print(f'📊 Registros atuais: {current:,}')
    
    cursor.execute('SELECT fonte, COUNT(*) FROM facebook_data GROUP BY fonte')
    sources = cursor.fetchall()
    
    if sources:
        print('🔍 Por fonte:')
        for fonte, count in sources:
            print(f'   {fonte}: {count:,}')
    else:
        print('📱 Tabela vazia')
    
    print()
except:
    print('📱 Tabela não existe ainda')
    print()

# Processar arquivos
print('🚀 Iniciando processamento...')
print()

total_inserted = 0
total_skipped = 0

# Processar 1.txt
if os.path.exists('/a0/usr/uploads/1.txt'):
    inserted1, skipped1 = process_file('/a0/usr/uploads/1.txt', 'facebook_1')
    total_inserted += inserted1
    total_skipped += skipped1
else:
    print('❌ 1.txt não encontrado')
    print()

# Processar 2.txt
if os.path.exists('/a0/usr/uploads/2.txt'):
    inserted2, skipped2 = process_file('/a0/usr/uploads/2.txt', 'facebook_2')
    total_inserted += inserted2
    total_skipped += skipped2
else:
    print('❌ 2.txt não encontrado')
    print()

# Resumo final
print('='*60)
print('📈 RESUMO FINAL')
print('='*60)
print()

print(f'🎯 Novos registros: {total_inserted:,}')
print(f'📊 Duplicados: {total_skipped:,}')
print(f'📈 Total processado: {total_inserted + total_skipped:,}')
print()

# Verificar contagem final
cursor.execute('SELECT COUNT(*) FROM facebook_data')
fb_total = cursor.fetchone()[0]

cursor.execute('SELECT fonte, COUNT(*) FROM facebook_data GROUP BY fonte')
print('🔍 Distribuição final:')
for fonte, count in cursor.fetchall():
    print(f'   {fonte}: {count:,}')

print()
print(f'📊 Total facebook_data: {fb_total:,}')

# Calcular total do sistema
print()
print('📈 TOTAL DO SISTEMA:')
print('-'*40)

tables = [
    ('facebook_data', '📱 Facebook'),
    ('telefones_processados', '📞 Telefones'),
    ('contatos_excel_processados', '📊 Excel'),
    ('contatos_vcf_processados', '📇 VCF'),
    ('pessoas', '👥 Pessoas')
]

system_total = 0

for table_name, description in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'{description}: {count:,}')
        system_total += count
    except:
        print(f'{description}: Tabela não existe')

print(f'\n🎯 TOTAL GERAL: {system_total:,}')
print()

conn.close()

print('='*60)
print('✅ PROCESSAMENTO CONCLUÍDO!')
print('='*60)
