import sqlite3
import os
import hashlib
import sys

print('=== PROCESSAMENTO EFICIENTE DE DADOS FACEBOOK ===')
print('')

# Connect to database
db_path = '/a0/usr/uploads/BrazilianPeople.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create table for Facebook data if not exists
print('1. Criando tabela para dados Facebook...')

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

# Create indexes for performance
cursor.execute('CREATE INDEX IF NOT EXISTS idx_facebook_telefone ON facebook_data(telefone)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_facebook_id ON facebook_data(facebook_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_facebook_hash ON facebook_data(hash)')

conn.commit()
print('✅ Tabela e índices criados')
print('')

# Function to process a file efficiently
def process_facebook_file(filepath, fonte):
    """Process Facebook data file efficiently"""
    filename = os.path.basename(filepath)
    print(f'📁 Processando: {filename}')
    print(f'   Fonte: {fonte}')
    
    if not os.path.exists(filepath):
        print(f'❌ Arquivo não encontrado')
        return 0, 0
    
    # First, count total lines
    print('   Contando linhas...')
    total_lines = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
    
    print(f'   Total linhas: {total_lines:,}')
    print('')
    
    # Now process
    inserted = 0
    skipped = 0
    batch = []
    batch_size = 10000
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            if not line:
                skipped += 1
                continue
            
            # Split by colon
            parts = line.split(':')
            
            if len(parts) < 4:  # Need at least phone, facebook_id, first_name, last_name
                skipped += 1
                continue
            
            try:
                # Extract fields
                telefone = parts[0].strip() if len(parts) > 0 else ''
                facebook_id = parts[1].strip() if len(parts) > 1 else ''
                nome = parts[2].strip() if len(parts) > 2 else ''
                sobrenome = parts[3].strip() if len(parts) > 3 else ''
                
                # Create full name
                nome_completo = f'{nome} {sobrenome}'.strip()
                
                # Extract other fields
                genero = parts[4].strip() if len(parts) > 4 else ''
                cidade = parts[5].strip() if len(parts) > 5 else ''
                estado = parts[6].strip() if len(parts) > 6 else ''
                relacionamento = parts[7].strip() if len(parts) > 7 else ''
                empresa = parts[8].strip() if len(parts) > 8 else ''
                data_cadastro = parts[9].strip() if len(parts) > 9 else ''
                data_nascimento = parts[10].strip() if len(parts) > 10 else ''
                email = parts[11].strip() if len(parts) > 11 else ''
                
                # Create hash for duplicate detection
                data_str = f"{telefone}:{facebook_id}:{nome}:{sobrenome}:{genero}:{cidade}:{estado}"
                data_hash = hashlib.md5(data_str.encode()).hexdigest()
                
                # Check if already exists
                cursor.execute('SELECT 1 FROM facebook_data WHERE hash=?', (data_hash,))
                if not cursor.fetchone():
                    # Also check if phone already exists
                    cursor.execute('SELECT 1 FROM facebook_data WHERE telefone=?', (telefone,))
                    if not cursor.fetchone():
                        batch.append((
                            telefone, facebook_id, nome, sobrenome, nome_completo,
                            genero, cidade, estado, relacionamento, empresa,
                            data_cadastro, data_nascimento, email, data_hash, fonte
                        ))
                        inserted += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
                
                # Insert in batches
                if len(batch) >= batch_size:
                    cursor.executemany('''INSERT INTO facebook_data 
                        (telefone, facebook_id, nome, sobrenome, nome_completo,
                         genero, cidade, estado, relacionamento, empresa,
                         data_cadastro, data_nascimento, email, hash, fonte)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch)
                    conn.commit()
                    batch = []
                
                # Progress every 100,000 lines
                if line_num % 100000 == 0:
                    print(f'   Processados: {line_num:,}/{total_lines:,} | Novos: {inserted:,} | Duplicados: {skipped:,}')
                    
            except Exception as e:
                skipped += 1
                continue
    
    # Insert remaining
    if batch:
        cursor.executemany('''INSERT INTO facebook_data 
            (telefone, facebook_id, nome, sobrenome, nome_completo,
             genero, cidade, estado, relacionamento, empresa,
             data_cadastro, data_nascimento, email, hash, fonte)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
        conn.commit()
    
    print(f'   ✅ {filename} processado:')
    print(f'      Novos registros: {inserted:,}')
    print(f'      Duplicados/pulados: {skipped:,}')
    print(f'      Total processado: {inserted + skipped:,}')
    print('')
    
    return inserted, skipped

# Process both files
print('2. Processando arquivos...')
print('')

total_inserted = 0
total_skipped = 0

# Process 1.txt
inserted1, skipped1 = process_facebook_file('/a0/usr/uploads/1.txt', 'facebook_1')
total_inserted += inserted1
total_skipped += skipped1

# Process 2.txt
inserted2, skipped2 = process_facebook_file('/a0/usr/uploads/2.txt', 'facebook_2')
total_inserted += inserted2
total_skipped += skipped2

# Final summary
print('='*60)
print('📈 RESUMO FINAL DO PROCESSAMENTO')
print('='*60)
print('')

print(f'🎯 TOTAL NOVOS REGISTROS: {total_inserted:,}')
print(f'📊 TOTAL DUPLICADOS/PULADOS: {total_skipped:,}')
print(f'📈 TOTAL LINHAS PROCESSADAS: {total_inserted + total_skipped:,}')
print('')

# Check final counts
cursor.execute('SELECT COUNT(*) FROM facebook_data')
facebook_count = cursor.fetchone()[0]

cursor.execute('SELECT fonte, COUNT(*) FROM facebook_data GROUP BY fonte')
print('🔍 DETALHAMENTO POR FONTE:')
for fonte, count in cursor.fetchall():
    print(f'   {fonte}: {count:,} registros')

print('')
print('📊 COMPARAÇÃO COM OUTRAS TABELAS:')

# Compare with other tables
tables = [
    ('facebook_data', '📱 Dados Facebook'),
    ('telefones_processados', '📞 Telefones'),
    ('contatos_excel_processados', '📊 Contatos Excel'),
    ('contatos_vcf_processados', '📇 Contatos VCF'),
    ('pessoas', '👥 Pessoas brasileiras')
]

for table_name, description in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'{description}: {count:,}')
    except:
        print(f'{description}: Tabela não existe')

# Calculate new total
cursor.execute('SELECT COUNT(*) FROM telefones_processados')
telefones_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM contatos_excel_processados')
excel_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM contatos_vcf_processados')
vcf_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM pessoas')
pessoas_count = cursor.fetchone()[0]

total_system = facebook_count + telefones_count + excel_count + vcf_count + pessoas_count

print('')
print(f'📈 TOTAL GERAL NO SISTEMA: {total_system:,}')
print('')

conn.close()
print('='*60)
print('🎯 PROCESSAMENTO CONCLUÍDO EFICIENTEMENTE!')
print('='*60)
