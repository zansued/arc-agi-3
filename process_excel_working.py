#!/usr/bin/env python3
"""
Processador funcional de Excel Itau Bank Brazil
Baseado em padrões comprovados do sistema
"""

import pandas as pd
import sqlite3
import hashlib
import json
import os
import time

# Configurações
db_path = '/a0/usr/uploads/BrazilianPeople.db'
file_path = '/a0/usr/uploads/Itau Banck Brazil.xlsx'

print('='*70)
print('🚀 PROCESSADOR FUNCIONAL EXCEL - PADRÕES COMPROVADOS')
print('='*70)
print()

# Verificar arquivo
if not os.path.exists(file_path):
    print(f'❌ Arquivo não encontrado: {file_path}')
    exit(1)

file_size = os.path.getsize(file_path)
print(f'📁 Arquivo: {os.path.basename(file_path)}')
print(f'   Tamanho: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)')
print()

# Conectar ao database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar/ajustar estrutura da tabela
print('🔧 VERIFICANDO ESTRUTURA DA TABELA...')

# Verificar colunas existentes
cursor.execute('PRAGMA table_info(contatos_excel_processados)')
columns = [col[1] for col in cursor.fetchall()]
print(f'Colunas existentes: {columns}')

# Adicionar colunas se não existirem
required_columns = ['hash', 'fonte', 'dados_json', 'nome', 'telefones', 'emails']
for col in required_columns:
    if col not in columns:
        print(f'⚠️ Adicionando coluna {col}...')
        if col == 'hash':
            cursor.execute(f'ALTER TABLE contatos_excel_processados ADD COLUMN {col} TEXT UNIQUE')
        else:
            cursor.execute(f'ALTER TABLE contatos_excel_processados ADD COLUMN {col} TEXT')
        print(f'✅ Coluna {col} adicionada')

conn.commit()
print('✅ Estrutura da tabela verificada/ajustada')
print()

# Verificar registros atuais
cursor.execute('SELECT COUNT(*) FROM contatos_excel_processados')
total_atual = cursor.fetchone()[0]
print(f'📊 Registros Excel atuais: {total_atual:,}')
print()

# ABORDAGEM SIMPLES E DIRETA
print('🚀 INICIANDO PROCESSAMENTO DIRETO...')
print('-'*70)

start_time = time.time()

# Passo 1: Ler apenas as primeiras linhas para estrutura
try:
    print('📖 Lendo estrutura do arquivo...')
    df_sample = pd.read_excel(file_path, nrows=10)
    print(f'✅ Arquivo pode ser lido')
    print(f'📊 Colunas: {len(df_sample.columns)}')
    print(f'   Exemplo: {list(df_sample.columns[:5])}...')
    print()
    
    # Mostrar amostra
    print('🔍 AMOSTRA DE DADOS:')
    print('-'*40)
    for i in range(min(3, len(df_sample))):
        row = df_sample.iloc[i]
        print(f'Linha {i+1}:')
        
        # Mostrar CPF e Nome
        if 'CPF' in df_sample.columns:
            cpf = row['CPF']
            print(f'  CPF: {cpf}')
        
        if 'Nome' in df_sample.columns:
            nome = row['Nome']
            print(f'  Nome: {nome[:30]}...' if len(str(nome)) > 30 else f'  Nome: {nome}')
        
        print()
    
    # Passo 2: Processar em chunks pequenos
    print('🚀 PROCESSANDO EM CHUNKS PEQUENOS...')
    print('-'*70)
    
    chunk_size = 1000  # Chunks pequenos para melhor controle
    total_processed = 0
    total_added = 0
    total_duplicates = 0
    
    for chunk_num in range(0, 1000):  # Máximo 1,000 chunks (1,000,000 linhas)
        skip_rows = chunk_num * chunk_size
        
        print(f'📦 Chunk {chunk_num+1} (linhas {skip_rows+1}-{skip_rows+chunk_size})...')
        
        try:
            # Ler chunk
            df_chunk = pd.read_excel(
                file_path,
                skiprows=skip_rows,
                nrows=chunk_size,
                header=None if skip_rows > 0 else 0
            )
            
            if df_chunk.empty:
                print(f'✅ Fim do arquivo alcançado')
                break
            
            # Se pulamos linhas, usar nomes das colunas
            if skip_rows > 0:
                df_chunk.columns = df_sample.columns
            
            # Processar chunk
            batch = []
            for idx, row in df_chunk.iterrows():
                total_processed += 1
                
                # Converter para dict
                row_dict = row.to_dict()
                
                # Criar hash único
                row_json = json.dumps(row_dict, sort_keys=True, default=str)
                row_hash = hashlib.md5(row_json.encode()).hexdigest()
                
                # Extrair campos básicos
                nome = str(row_dict.get('Nome', '')) if 'Nome' in row_dict else ''
                
                # Preparar para inserção
                fonte = f'itau_bank_brazil_{row_hash[:8]}'
                
                batch.append((
                    row_hash,
                    fonte,
                    row_json,
                    nome[:200] if nome else '',
                    '',  # telefones (podemos extrair depois)
                    ''   # emails (podemos extrair depois)
                ))
                
                # Inserir em lotes de 100
                if len(batch) >= 100:
                    try:
                        cursor.executemany('''
                            INSERT OR IGNORE INTO contatos_excel_processados 
                            (hash, fonte, dados_json, nome, telefones, emails)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', batch)
                        
                        added = cursor.rowcount
                        total_added += added
                        total_duplicates += len(batch) - added
                        
                        conn.commit()
                        batch = []
                        
                        # Progresso
                        if total_processed % 1000 == 0:
                            elapsed = time.time() - start_time
                            speed = total_processed / elapsed if elapsed > 0 else 0
                            
                            print(f'   📈 {total_processed:,} linhas')
                            print(f'   ⚡ {speed:.0f} linhas/segundo')
                            print(f'   ✅ {total_added:,} novos, {total_duplicates:,} duplicados')
                            
                    except Exception as e:
                        print(f'   ⚠️ Erro no batch: {e}')
                        conn.rollback()
                        batch = []
            
            # Inserir batch final do chunk
            if batch:
                try:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO contatos_excel_processados 
                        (hash, fonte, dados_json, nome, telefones, emails)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', batch)
                    
                    added = cursor.rowcount
                    total_added += added
                    total_duplicates += len(batch) - added
                    
                    conn.commit()
                    print(f'   ✅ Chunk {chunk_num+1}: {len(df_chunk)} linhas')
                    
                except Exception as e:
                    print(f'   ⚠️ Erro no batch final: {e}')
            
        except Exception as e:
            print(f'   ⚠️ Erro no chunk {chunk_num+1}: {e}')
            continue
    
    # Resultados
    elapsed = time.time() - start_time
    print()
    print('='*70)
    print('🎯 PROCESSAMENTO CONCLUÍDO!')
    print('='*70)
    print()
    
    print(f'📊 RESULTADOS:')
    print(f'   Linhas processadas: {total_processed:,}')
    print(f'   Novos registros: {total_added:,}')
    print(f'   Duplicados ignorados: {total_duplicates:,}')
    print(f'   Tempo total: {elapsed:.1f} segundos ({elapsed/60:.1f} minutos)')
    print(f'   Velocidade: {total_processed/elapsed:.0f} linhas/segundo')
    print()
    
    # Verificar total
    cursor.execute('SELECT COUNT(*) FROM contatos_excel_processados')
    total_final = cursor.fetchone()[0]
    print(f'📈 TOTAL NO SISTEMA:')
    print(f'   Antes: {total_atual:,}')
    print(f'   Depois: {total_final:,}')
    print(f'   Crescimento: {total_final - total_atual:,}')
    print()
    
    # Verificar Itau
    cursor.execute('''
        SELECT COUNT(*) 
        FROM contatos_excel_processados 
        WHERE fonte LIKE 'itau_bank_brazil%'
    ''')
    
    itau_count = cursor.fetchone()[0]
    print(f'🎯 REGISTROS ITAU: {itau_count:,}')
    
    if itau_count > 0:
        print('✅ DADOS ITAU ADICIONADOS COM SUCESSO!')
        print('   Prontos para consulta e cruzamento.')
        
        # Amostra
        cursor.execute('''
            SELECT nome, dados_json
            FROM contatos_excel_processados 
            WHERE fonte LIKE 'itau_bank_brazil%'
            LIMIT 2
        ''')
        
        print('\n🔍 AMOSTRA:')
        print('-'*40)
        for nome, dados_json in cursor.fetchall():
            print(f'Nome: {nome[:30]}...' if nome and len(nome) > 30 else f'Nome: {nome or "N/A"}')
            # Extrair CPF do JSON
            try:
                dados = json.loads(dados_json)
                if 'CPF' in dados:
                    print(f'  CPF: {dados["CPF"]}')
            except:
                pass
            print()
    else:
        print('⚠️ Nenhum registro Itau foi adicionado')
    
    print()
    
except Exception as e:
    print(f'❌ ERRO CRÍTICO: {e}')
    import traceback
    traceback.print_exc()

finally:
    conn.close()
    print('='*70)

