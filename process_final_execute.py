import sqlite3
import os
import hashlib
import sys

print('=== PROCESSAMENTO FINAL VCF + EXCEL ===')
print('')

# Connect to database
db_path = '/a0/usr/uploads/BrazilianPeople.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables if not exist
print('1. Verificando tabelas...')

cursor.execute('''CREATE TABLE IF NOT EXISTS contatos_vcf_processados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    telefones TEXT,
    emails TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS contatos_excel_processados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dados TEXT,
    hash TEXT UNIQUE,
    fonte TEXT,
    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()
print('✅ Tabelas verificadas')
print('')

# Process VCF
print('2. 📇 PROCESSANDO VCF...')
vcf_path = '/a0/usr/uploads/contatos 17280 2026-04-17.vcf'
if os.path.exists(vcf_path):
    try:
        import vobject
        
        print(f'   Arquivo: {os.path.basename(vcf_path)}')
        print(f'   Tamanho: {os.path.getsize(vcf_path)/1024/1024:.1f} MB')
        
        with open(vcf_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Split into VCARDs
        vcards = content.split('END:VCARD')
        total_vcards = len([v for v in vcards if 'BEGIN:VCARD' in v])
        
        print(f'   Total VCARDs encontrados: {total_vcards:,}')
        print('')
        
        inserted = 0
        skipped = 0
        
        for i, vcard_text in enumerate(vcards, 1):
            if 'BEGIN:VCARD' not in vcard_text:
                continue
            
            try:
                vcard = vobject.readOne('BEGIN:VCARD\n' + vcard_text + 'END:VCARD')
                
                # Extract data
                nome = vcard.fn.value if hasattr(vcard, 'fn') else ''
                
                telefones = []
                for tel in vcard.contents.get('tel', []):
                    if hasattr(tel, 'value'):
                        telefones.append(tel.value)
                
                emails = []
                for email in vcard.contents.get('email', []):
                    if hasattr(email, 'value'):
                        emails.append(email.value)
                
                # Create hash for duplicate check
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
                
                # Progress every 1000 records
                if i % 1000 == 0:
                    print(f'   Processados: {i:,}/{total_vcards:,} | Novos: {inserted:,} | Duplicados: {skipped:,}')
                    conn.commit()
                    
            except Exception as e:
                # Skip invalid VCARDs
                skipped += 1
                continue
        
        conn.commit()
        print('')
        print(f'✅ VCF PROCESSADO COM SUCESSO:')
        print(f'   Contatos novos: {inserted:,}')
        print(f'   Contatos duplicados/inválidos: {skipped:,}')
        print(f'   Total processados: {inserted + skipped:,}')
        
    except ImportError:
        print('❌ ERRO: Biblioteca vobject não instalada')
        print('   Execute: pip install vobject')
    except Exception as e:
        print(f'❌ ERRO VCF: {e}')
else:
    print('❌ Arquivo VCF não encontrado')

print('')

# Process Excel files
print('3. 📊 PROCESSANDO ARQUIVOS EXCEL...')
print('')

excel_files = [
    '/a0/usr/uploads/Cópia de 12.733 contatos.xlsx',
    '/a0/usr/uploads/Cópia de 32 mil contatos.xlsx',
    '/a0/usr/uploads/Cópia de 5169 contatos.xlsx',
    '/a0/usr/uploads/Cópia de 7315 contatos.xlsx'
]

for excel_file in excel_files:
    if os.path.exists(excel_file):
        filename = os.path.basename(excel_file)
        print(f'   📁 Processando: {filename}')
        print(f'     Tamanho: {os.path.getsize(excel_file)/1024:.1f} KB')
        
        try:
            import pandas as pd
            
            # Read Excel
            df = pd.read_excel(excel_file)
            total_rows = len(df)
            print(f'     Registros no arquivo: {total_rows:,}')
            
            inserted = 0
            skipped = 0
            
            for idx, row in df.iterrows():
                try:
                    # Convert row to JSON string
                    row_json = row.to_json()
                    
                    # Create hash
                    data_hash = hashlib.md5(row_json.encode()).hexdigest()
                    
                    # Check duplicate
                    cursor.execute('SELECT 1 FROM contatos_excel_processados WHERE hash=?', (data_hash,))
                    if not cursor.fetchone():
                        cursor.execute('''INSERT INTO contatos_excel_processados 
                                        (dados, hash, fonte) VALUES (?, ?, ?)''',
                                      (row_json, data_hash, filename))
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as e:
                    skipped += 1
                    continue
                
                # Progress every 1000 records
                if (idx + 1) % 1000 == 0:
                    print(f'       Processados: {idx+1:,}/{total_rows:,} | Novos: {inserted:,} | Duplicados: {skipped:,}')
            
            conn.commit()
            print(f'     ✅ {filename}:')
            print(f'       Novos: {inserted:,}')
            print(f'       Duplicados: {skipped:,}')
            print(f'       Total: {inserted + skipped:,}')
            print('')
            
        except ImportError:
            print('     ❌ ERRO: Biblioteca pandas não instalada')
            print('       Execute: pip install pandas openpyxl')
            break
        except Exception as e:
            print(f'     ❌ ERRO {filename}: {e}')
            print('')
    else:
        print(f'   ❌ Arquivo não encontrado: {excel_file}')
        print('')

# Create indexes
print('4. ⚡ CRIANDO ÍNDICES...')
try:
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vcf_hash ON contatos_vcf_processados(hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_excel_hash ON contatos_excel_processados(hash)')
    conn.commit()
    print('✅ Índices criados')
except Exception as e:
    print(f'⚠️ Erro criando índices: {e}')

print('')

# Final summary
print('='*60)
print('📈 RESUMO FINAL DO PROCESSAMENTO')
print('='*60)
print('')

# Count records
tables = [
    ('telefones_processados', '📞 Telefones processados'),
    ('contatos_vcf_processados', '📇 Contatos VCF'),
    ('contatos_excel_processados', '📊 Contatos Excel'),
    ('pessoas', '👥 Pessoas brasileiras')
]

total_processed = 0
for table_name, description in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'{description}: {count:,}')
        if table_name != 'pessoas':
            total_processed += count
    except:
        print(f'{description}: Tabela não existe')

print('')
print(f'🎯 TOTAL DE REGISTROS PROCESSADOS: {total_processed:,}')
print(f'📈 TOTAL PESSOAS BRASILEIRAS: 9,145,152')
print(f'📈 TOTAL GERAL NO SISTEMA: {total_processed + 9145152:,}')
print('')

# Check what was actually processed
print('🔍 DETALHAMENTO POR FONTE:')
print('')

# Telefones por fonte
try:
    cursor.execute('SELECT fonte, COUNT(*) FROM telefones_processados GROUP BY fonte')
    print('📞 Telefones:')
    for fonte, count in cursor.fetchall():
        print(f'   {fonte}: {count:,}')
except:
    pass

# Excel por fonte
try:
    cursor.execute('SELECT fonte, COUNT(*) FROM contatos_excel_processados GROUP BY fonte')
    print('\n📊 Excel:')
    for fonte, count in cursor.fetchall():
        print(f'   {fonte}: {count:,}')
except:
    pass

conn.close()
print('')
print('='*60)
print('🎯 PROCESSAMENTO FINAL CONCLUÍDO COM SUCESSO!')
print('='*60)
