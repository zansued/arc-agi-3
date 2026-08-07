import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

key_path = "/a0/usr/workdir/simple_drive_system/service_account_key.json"
spreadsheet_id = "1AqxF-zDpwo5k9QsuW1pMpi8y3Tpqc_atOoNru_fOpTU"

print(f"Testando conexão com Google Sheets...")
print(f"Service account: {key_path}")
print(f"Spreadsheet ID: {spreadsheet_id}")

try:
    # Autenticar
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
    client = gspread.authorize(creds)
    
    print("✅ Autenticação bem-sucedida")
    
    # Tentar abrir a planilha
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"✅ Planilha encontrada: {spreadsheet.title}")
        
        # Listar worksheets
        worksheets = spreadsheet.worksheets()
        print(f"Worksheets disponíveis: {[ws.title for ws in worksheets]}")
        
    except Exception as e:
        print(f"⚠️ Não consegui abrir a planilha: {e}")
        print("Criando nova planilha de teste...")
        
        # Criar nova planilha de teste
        spreadsheet = client.create("Test Lead Agent")
        worksheet = spreadsheet.sheet1
        worksheet.update([[\"Nome\", \"Email\", \"Telefone\"]]) 
        print(f"✅ Nova planilha criada: {spreadsheet.id}")
        
except Exception as e:
    print(f"❌ Erro geral: {e}")

print("Teste concluído")
