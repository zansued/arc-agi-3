import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

print('Testing Google Drive API access...')

# Check credentials file
creds_path = 'simple_drive_system/service_account_key.json'
if not os.path.exists(creds_path):
    print(f'ERROR: Credentials file not found at {creds_path}')
    exit(1)

print(f'✓ Credentials file found: {creds_path}')

# Load credentials
with open(creds_path, 'r') as f:
    creds_data = json.load(f)

print(f'✓ Service Account: {creds_data["client_email"]}')

# Authenticate
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
try:
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=credentials)
    print('✓ Google Drive API authentication successful')
    
    # Test by listing some files
    print('\nTesting file listing...')
    results = service.files().list(pageSize=5, fields='files(id, name, mimeType)').execute()
    files = results.get('files', [])
    
    if not files:
        print('No files found. Service Account may not have access to any shared folders.')
    else:
        print(f'Found {len(files)} files accessible to Service Account:')
        for file in files:
            print(f'  - {file["name"]} ({file["mimeType"]})')
    
    # Search for Amanda Baran Santana
    print('\nSearching for "Amanda Baran Santana"...')
    query = "name contains 'Amanda' or name contains 'Baran' or name contains 'Santana' or fullText contains 'Amanda Baran Santana'"
    search_results = service.files().list(
        q=query,
        pageSize=10,
        fields='files(id, name, mimeType, modifiedTime, size)'
    ).execute()
    search_files = search_results.get('files', [])
    
    if not search_files:
        print('No files found containing search terms.')
    else:
        print(f'Found {len(search_files)} files matching search:')
        for file in search_files:
            size_str = f"{file.get('size', 'N/A')} bytes" if 'size' in file else 'N/A'
            print(f'  - {file["name"]} ({file["mimeType"]}, {size_str})')
    
    # Also search in file content
    print('\nSearching in file content (this may take longer)...')
    content_query = "fullText contains 'Amanda Baran Santana'"
    content_results = service.files().list(
        q=content_query,
        pageSize=5,
        fields='files(id, name, mimeType)'
    ).execute()
    content_files = content_results.get('files', [])
    
    if not content_files:
        print('No files found with exact phrase in content.')
    else:
        print(f'Found {len(content_files)} files with exact phrase in content:')
        for file in content_files:
            print(f'  - {file["name"]} ({file["mimeType"]})')
    
    print('\n✓ Google Drive search completed successfully')
    
except HttpError as e:
    print(f'HTTP Error: {e}')
except Exception as e:
    print(f'Error: {e}')
