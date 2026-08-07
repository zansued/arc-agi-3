import json
import os
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

print('Searching Google Drive contact databases for Amanda Baran Santana...')

# Authenticate
creds_path = 'simple_drive_system/service_account_key.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
credentials = service_account.Credentials.from_service_account_file(
    creds_path, scopes=SCOPES)
service = build('drive', 'v3', credentials=credentials)

# Search for Excel files with 'contatos' in name
query = "name contains 'contatos' and (mimeType contains 'spreadsheet' or mimeType contains 'excel')"
results = service.files().list(q=query, pageSize=10, fields='files(id, name, mimeType, size)').execute()
files = results.get('files', [])

print(f'Found {len(files)} contact Excel files:')
for file in files:
    print(f'  - {file["name"]} ({file.get("size", "N/A")} bytes)')

# Download and search each Excel file
for file in files:
    print(f'\nSearching in {file["name"]}...')
    try:
        # Download file
        request = service.files().get_media(fileId=file['id'])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        # Read Excel
        fh.seek(0)
        df = pd.read_excel(fh, nrows=1000)  # Read first 1000 rows for speed
        
        # Search for Amanda Baran Santana
        matches = df.apply(lambda row: row.astype(str).str.contains('amanda.*baran.*santana', case=False, na=False).any(), axis=1)
        if matches.any():
            print(f'  ✓ Found {matches.sum()} matches!')
            matching_rows = df[matches]
            for idx, row in matching_rows.head(3).iterrows():
                print(f'    Row {idx}: {row.to_dict()}')
        else:
            print('  ✗ No matches found in first 1000 rows')
            
        # Also search for CPF 07638048946
        cpf_matches = df.apply(lambda row: row.astype(str).str.contains('07638048946', na=False).any(), axis=1)
        if cpf_matches.any():
            print(f'  ✓ Found CPF 07638048946!')
            
    except Exception as e:
        print(f'  ✗ Error processing {file["name"]}: {e}')

print('\n✓ Google Drive contact search completed')
