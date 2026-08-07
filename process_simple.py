import sqlite3
import os
import hashlib

print('=== PROCESSAMENTO SIMPLES SEM DUPLICADOS ===')

# Connect to database
db_path = '/a0/usr/uploads/BrazilianPeople.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables
print('\n1. Criando tabelas...')

# Telefones
cursor.execute('''CREATE TABLE IF NOT EXISTS telefones_processados (
    telefone TEXT PRIMARY KEY,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Contatos VCF
cursor.execute('''CREATE TABLE IF NOT EXISTS contatos_vcf_processados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    telefones TEXT,
    emails TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# Contatos Excel
cursor.execute('''CREATE TABLE IF NOT EXISTS contatos_excel_processados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dados TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()
print('✅ Tabelas criadas')

# Process Brazil.txt
print('\n2. Processando Brazil.txt...')
brazil_path = '/a0/usr/uploads/Brazil.txt'
if os.path.exists(brazil_path):
    inserted = 0
    skipped = 0
    batch = []
    
    with open(brazil_path, 'r', encoding='utf-8', errors='ignore') as f:
        # Skip header
        first_line = f.readline().strip()
        if 'phone' in first_line.lower():
            print('   Pulando cabeçalho...')
        else:
            f.seek(0)
        
        for line_num, line in enumerate(f, 1):
            phone = line.strip()
            
            if phone and len(phone) >= 10:
                # Check duplicate
                cursor.execute('SELECT 1 FROM telefones_processados WHERE telefone=?', (phone,))
                if not cursor.fetchone():
                    batch.append((phone, 'brazil.txt'))
                    inserted += 1
                else:
                    skipped += 1
            
            # Insert in batches
            if len(batch) >= 10000:
                cursor.executemany('INSERT OR IGNORE INTO telefones_processados (telefone, fonte) VALUES (?, ?)', batch)
                conn.commit()
                batch = []
                
            if line_num % 50000 == 0:
                print(f'   Linhas: {line_num:,} | Novos: {inserted:,} | Duplicados: {skipped:,}')
    
    # Insert remaining
    if batch:
        cursor.executemany('INSERT OR IGNORE INTO telefones_processados (telefone, fonte) VALUES (?, ?)', batch)
        conn.commit()
    
    print(f'✅ Brazil.txt: {inserted:,} novos | {skipped:,} duplicados')
else:
    print('❌ Brazil.txt não encontrado')

# Process VCF
print('\n3. Processando VCF...')
vcf_path = '/a0/usr/uploads/contatos 17280 2026-04-17.vcf'
if os.path.exists(vcf_path):
    try:
        import vobject
        
        with open(vcf_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        vcards = content.split('END:VCARD')
        inserted = 0
        skipped = 0
        
        print(f'   Total VCARDs: {len([v for v in vcards if "BEGIN:VCARD" in v]):,}')
        
        for i, vcard_text in enumerate(vcards, 1):
            if 'BEGIN:VCARD' not in vcard_text:
                continue
            
            try:
                vcard = vobject.readOne('BEGIN:VCARD\n' + vcard_text + 'END:VCARD')
                
                nome = vcard.fn.value if hasattr(vcard, 'fn') else ''
                
                telefones = []
                for tel in vcard.contents.get('tel', []):
                    if hasattr(tel, 'value'):
                        telefones.append(tel.value)
                
                emails = []
                for email in vcard.contents.get('email', []):
                    if hasattr(email, 'value'):
                        emails.append(email.value)
                
                # Create hash
                data_str = f"{nome}{''.join(telefones)}{''.join(emails)}"
                data_hash = hashlib.md5(data_str.encode()).hexdigest()
                
                # Check duplicate
                cursor.execute('SELECT 1 FROM contatos_vcf_processados WHERE hash=?', (data_hash,))
                if not cursor.fetchone():
                    cursor.execute('''INSERT INTO contatos_vcf_processados 
                                    (nome, telefones, emails, hash, fonte) 
                                    VALUES (?, ?, ?, ?, ?)''',
                                  (nome, ','.join(telefones), ','.join(emails), data_hash, 'vcf'))
                    inserted += 1
                else:
                    skipped += 1
                
                if i % 1000 == 0:
                    print(f'   Processados: {i:,} | Novos: {inserted:,} | Duplicados: {skipped:,}')
                    conn.commit()
                    
            except:
                skipped += 1
                continue
        
        conn.commit()
        print(f'✅ VCF: {inserted:,} novos | {skipped:,} duplicados/inválidos')
        
    except ImportError:
        print('⚠️ vobject não instalado, pulando VCF')
        print('   Execute: pip install vobject')
    except Exception as e:
        print(f'❌ Erro VCF: {e}')
else:
    print('❌ VCF não encontrado')

# Process Excel files
print('\n4. Processando arquivos Excel...')

excel_files = [
    '/a0/usr/uploads/Cópia de 12.733 contatos.xlsx',
    '/a0/usr/uploads/Cópia de 32 mil contatos.xlsx',
    '/a0/usr/uploads/Cópia de 5169 contatos.xlsx',
    '/a0/usr/uploads/Cópia de 7315 contatos.xlsx'
]

for excel_file in excel_files:
    if os.path.exists(excel_file):
        filename = os.path.basename(excel_file)
        print(f'   Processando: {filename}')
        
        try:
            import pandas as pd
            
            # Read Excel
            df = pd.read_excel(excel_file)
            print(f'     Registros: {len(df):,}')
            
            inserted = 0
            skipped = 0
            
            for _, row in df.iterrows():
                try:
                    row_json = row.to_json()
                    data_hash = hashlib.md5(row_json.encode()).hexdigest()
                    
                    cursor.execute('SELECT 1 FROM contatos_excel_processados WHERE hash=?', (data_hash,))
                    if not cursor.fetchone():
                        cursor.execute('''INSERT INTO contatos_excel_processados 
                                        (dados, hash, fonte) VALUES (?, ?, ?)''',
                                      (row_json, data_hash, filename))
                        inserted += 1
                    else:
                        skipped += 1
                except:
                    skipped += 1
            
            conn.commit()
            print(f'     ✅ {filename}: {inserted:,} novos | {skipped:,} duplicados')
            
        except ImportError:
            print('     ⚠️ pandas não instalado, pulando Excel')
            print('       Execute: pip install pandas openpyxl')
            break
        except Exception as e:
            print(f'     ❌ Erro {filename}: {e}')
    else:
        print(f'   ❌ {excel_file} não encontrado')

# Create indexes
print('\n5. Criando índices...')
try:
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_telefones ON telefones_processados(telefone)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vcf_hash ON contatos_vcf_processados(hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_excel_hash ON contatos_excel_processados(hash)')
    conn.commit()
    print('✅ Índices criados')
except Exception as e:
    print(f'⚠️ Erro índices: {e}')

# Final summary
print('\n' + '='*50)
print('📈 RESUMO FINAL:')
print('='*50)

# Count records
tables = ['telefones_processados', 'contatos_vcf_processados', 'contatos_excel_processados']
total_new = 0

for table in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'📊 {table}: {count:,} registros')
        total_new += count
    except:
        print(f'📊 {table}: 0 registros')

print(f'\n🎯 TOTAL NOVOS REGISTROS: {total_new:,}')
print(f'📈 TOTAL PESSOAS BRASILEIRAS: 9,145,152')
print(f'📈 TOTAL GERAL NO SISTEMA: {total_new + 9145152:,}')

conn.close()
print('\n' + '='*50)
print('🎯 PROCESSAMENTO CONCLUÍDO!') 
print('='*50)
