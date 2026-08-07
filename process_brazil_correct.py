import sqlite3
import os
import re

print('=== PROCESSAMENTO CORRETO DO Brazil.txt ===')

# Connect to database
db_path = '/a0/usr/uploads/BrazilianPeople.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create table if not exists
cursor.execute('''CREATE TABLE IF NOT EXISTS telefones_processados (
    telefone TEXT PRIMARY KEY,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()

# Process Brazil.txt
filepath = '/a0/usr/uploads/Brazil.txt'
if not os.path.exists(filepath):
    print('❌ Brazil.txt não encontrado')
    exit(1)

print(f'📞 Processando {filepath}...')

# First, analyze file
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    first_line = f.readline().strip()
    
    # Check if first line is header
    has_header = 'phone' in first_line.lower()
    
    # Rewind
    f.seek(0)
    
    if has_header:
        print('   Pulando cabeçalho...')
        f.readline()  # Skip header
    
    # Count total lines
    print('   Contando linhas...')
    total_lines = 0
    for line in f:
        total_lines += 1
    
    print(f'   Total linhas: {total_lines:,}')

# Now process
inserted = 0
skipped = 0
batch = []
batch_size = 10000

with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    if has_header:
        f.readline()  # Skip header
    
    for line_num, line in enumerate(f, 1):
        line = line.strip()
        
        if not line:
            continue
        
        # Extract phone numbers from line
        # Remove all non-digit characters
        digits = re.sub(r'[^0-9]', '', line)
        
        # Check if this looks like a phone number
        if 8 <= len(digits) <= 15:
            phone = digits
            
            # Check duplicate
            cursor.execute('SELECT 1 FROM telefones_processados WHERE telefone=?', (phone,))
            if not cursor.fetchone():
                batch.append((phone, 'brazil.txt'))
                inserted += 1
            else:
                skipped += 1
        else:
            # Try to split by common separators
            parts = re.split(r'[\s,;|]+', line)
            for part in parts:
                part_digits = re.sub(r'[^0-9]', '', part)
                if 8 <= len(part_digits) <= 15:
                    phone = part_digits
                    
                    cursor.execute('SELECT 1 FROM telefones_processados WHERE telefone=?', (phone,))
                    if not cursor.fetchone():
                        batch.append((phone, 'brazil.txt'))
                        inserted += 1
                    else:
                        skipped += 1
        
        # Insert in batches
        if len(batch) >= batch_size:
            cursor.executemany('INSERT OR IGNORE INTO telefones_processados (telefone, fonte) VALUES (?, ?)', batch)
            conn.commit()
            batch = []
            
        if line_num % 100000 == 0:
            print(f'   Processados: {line_num:,}/{total_lines:,} | Novos: {inserted:,} | Duplicados: {skipped:,}')

# Insert remaining
if batch:
    cursor.executemany('INSERT OR IGNORE INTO telefones_processados (telefone, fonte) VALUES (?, ?)', batch)
    conn.commit()

print(f'\n✅ Brazil.txt processado:')
print(f'   Linhas processadas: {line_num:,}')
print(f'   Telefones novos: {inserted:,}')
print(f'   Telefones duplicados: {skipped:,}')

# Create index
print('\n⚡ Criando índice...')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_telefones ON telefones_processados(telefone)')
conn.commit()

# Final count
cursor.execute('SELECT COUNT(*) FROM telefones_processados')
total_phones = cursor.fetchone()[0]
print(f'📊 Total telefones na tabela: {total_phones:,}')

conn.close()
print('\n🎯 Processamento concluído!')
