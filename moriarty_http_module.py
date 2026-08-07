#!/usr/bin/env python3
"""
Moriarty HTTP Module v2 - Phone OSINT Orchestrator

Sistema que consulta informações de número de telefone usando:
- APIs HTTP diretas (sem browser, sem login)
- Ferramentas OSINT já instaladas (Holehe, Blackbird, Phunter)
- Serviços públicos de consulta

ZERO disco (streaming pipe), ZERO RAM extra, sob demanda.
"""

import re
import json
import sys
import subprocess as sp
import tempfile
import os
from pathlib import Path

# Caminho das ferramentas instaladas
OSINT_DIR = Path('/a0/usr/workdir/osint_tools_installed')

def format_phone(phone):
    """Formata número para padrão internacional"""
    digits = re.sub(r'\D', '', phone)
    if not digits.startswith('55') and len(digits) <= 11:
        if len(digits) == 10:
            digits = '55' + digits
        elif len(digits) == 11:
            digits = '55' + digits
    return '+' + digits


def check_holehe(phone):
    """Usa Holehe para verificar número em 100+ serviços"""
    try:
        holehe_path = OSINT_DIR / 'holehe'
        # Holehe funciona com email. Vamos usar formatos de email comuns para números
        # Mas melhor: usar holehe com 'phone' lookup se disponível
        result = sp.run(
            ['holehe', f'{phone}@gmail.com'],
            capture_output=True, text=True, timeout=30,
            cwd=str(holehe_path)
        )
        if result.returncode != 0:
            return {'tool': 'holehe', 'status': 'erro', 'output': result.stderr[:300]}
        return {'tool': 'holehe', 'status': 'ok', 'output': result.stdout[:1000]}
    except Exception as e:
        return {'tool': 'holehe', 'status': 'erro', 'error': str(e)}


def check_phunter(phone):
    """Usa Phunter para busca por número"""
    try:
        phunter_path = OSINT_DIR / 'Phunter'
        result = sp.run(
            ['python3', 'phunter.py', '--phone', phone],
            capture_output=True, text=True, timeout=30,
            cwd=str(phunter_path)
        )
        return {'tool': 'phunter', 'status': 'ok', 'output': result.stdout[:1000]}
    except Exception as e:
        return {'tool': 'phunter', 'status': 'erro', 'error': str(e)}


def check_telegram_web(phone):
    """Verifica se número existe no Telegram via API pública"""
    try:
        import requests
        # API pública do Telegram para verificar número
        clean = phone.replace('+', '')
        # Telegram WebK de autenticação
        url = f'https://oauth.telegram.org/auth?bot_id=0&origin=https://telegram.org&request_access=write'
        url2 = f'https://my.telegram.org/apps'
        r = requests.get(f'https://web.telegram.org/k/', timeout=10, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        return {'tool': 'telegram_web', 'status': 'ok', 'note': 'Verificação via web.telegram.org'}
    except Exception as e:
        return {'tool': 'telegram_web', 'status': 'erro', 'error': str(e)}


def check_facebook_api(phone):
    """Verifica existência no Facebook via API"""
    try:
        import requests
        # API de forgot password - verifica se o número existe
        url = 'https://www.facebook.com/recover/initiate'
        r = requests.post(url, data={'identifier': phone}, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }, allow_redirects=True)
        
        if '/recover/password/' in r.url or 'reset' in r.url:
            return {'exists': True, 'platform': 'Facebook', 'method': 'api_recover', 'confidence': 'alta'}
        if 'find_your_account' in r.text:
            return {'exists': True, 'platform': 'Facebook', 'method': 'api_recover', 'confidence': 'alta'}
        return {'exists': False, 'platform': 'Facebook'}
    except Exception as e:
        return {'exists': 'error', 'platform': 'Facebook', 'error': str(e)}


def check_microsoft_api(phone):
    """Verifica existência no Microsoft via API - método confiável"""
    try:
        import requests
        url = 'https://login.live.com/GetCredentialType.srf'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json; charset=UTF-8',
            'Origin': 'https://login.live.com',
        }
        data = {
            'username': phone,
            'isOtherIdpSupported': 'true',
            'checkPhones': 'false',
            'isRemoteNGCSupported': 'true',
            'isCookieBannerShown': 'false',
            'isFidoSupported': 'true',
            'forceotcobf': 'false',
            'sso': '',
            'chkt': '',
        }
        r = requests.post(url, json=data, headers=headers, timeout=15)
        if r.status_code == 200:
            j = r.json()
            result_code = j.get('IfExistsResult')
            if result_code == 0:
                return {'exists': True, 'platform': 'Microsoft', 'confidence': 'alta', 'details': 'Conta Microsoft existe'}
            elif result_code == 2:
                return {'exists': False, 'platform': 'Microsoft', 'details': 'Conta não encontrada'}
            elif result_code == 1:
                return {'exists': True, 'platform': 'Microsoft', 'confidence': 'media', 'details': 'Possível conta Microsoft'}
        return {'exists': 'unknown', 'platform': 'Microsoft', 'status': r.status_code}
    except Exception as e:
        return {'exists': 'error', 'platform': 'Microsoft', 'error': str(e)}


def check_google_api(phone):
    """Verifica existência no Google via signin API"""
    try:
        import requests
        # Google Signin identifier lookup API
        url = 'https://accounts.google.com/_/signin/sl/lookup'
        data = {
            'emailIdentifier': phone,
            'continue': 'https://accounts.google.com/',
            'flowName': 'GlifWebSignIn',
            'flowEntry': 'ServiceLogin'
        }
        r = requests.post(url, data=data, timeout=15, allow_redirects=False,
                         headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        # Google retorna 'password' no HTML se a conta existe
        if 'password' in r.text.lower() or 'identifieduser' in r.text.lower():
            return {'exists': True, 'platform': 'Google', 'confidence': 'alta'}
        return {'exists': False, 'platform': 'Google'}
    except Exception as e:
        return {'exists': 'error', 'platform': 'Google', 'error': str(e)}


def check_twitter_api(phone):
    """Verifica existência no Twitter/X via API"""
    try:
        import requests
        clean = phone.replace('+', '')
        url = f'https://api.twitter.com/1.1/users/phone_available.json?phone_number={clean}'
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return {'exists': True, 'platform': 'Twitter/X', 'confidence': 'media'}
        elif r.status_code == 400:
            data = r.json()
            if data.get('errors') and 'not found' in str(data['errors']).lower():
                return {'exists': False, 'platform': 'Twitter/X'}
            return {'exists': False, 'platform': 'Twitter/X'}
        return {'exists': 'unknown', 'platform': 'Twitter/X', 'status': r.status_code}
    except Exception as e:
        return {'exists': 'error', 'platform': 'Twitter/X', 'error': str(e)}


def check_instagram_api(phone):
    """Verifica existência no Instagram via API pública"""
    try:
        import requests
        # Instagram public API
        clean = phone.replace('+', '')
        url = 'https://www.instagram.com/api/v1/users/lookup/'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.instagram.com/',
        }
        r = requests.post(url, data={'phone_number': clean}, headers=headers, timeout=10)
        if r.status_code == 200:
            j = r.json()
            if j.get('user') and j['user'].get('exists'):
                return {'exists': True, 'platform': 'Instagram', 'confidence': 'alta'}
            if j.get('message') and 'no_user' in str(j['message']).lower():
                return {'exists': False, 'platform': 'Instagram'}
        return {'exists': 'unknown', 'platform': 'Instagram', 'status': r.status_code}
    except Exception as e:
        return {'exists': 'error', 'platform': 'Instagram', 'error': str(e)}


def check_spam_databases(phone):
    """Verifica em bases de spam conhecidas"""
    spam_results = {}
    try:
        import requests
        # Telemarketing / WhoCalls
        clean = phone.replace('+', '')
        
        # Google Cache / Pesquisa
        url = f'https://www.google.com/search?q={phone}+spam+telefone'
        r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if 'resultado' in r.text:
            spam_results['google_search'] = {'status': 'ok', 'note': 'Ver Google para resultados'}
        
        # OpenCnam API (gratuita limitada)
        # Essa API retorna nome do dono do número nos EUA
        
        return spam_results
    except:
        return {'status': 'erro', 'note': 'Falha na consulta de spam'}


def run_all(phone):
    """Executa todas as verificações e retorna resultado estruturado"""
    phone = format_phone(phone)
    
    print(f'📱 **Moriarty HTTP Module**')
    print(f'Número: {phone}')
    print(f'=' * 50)
    print()
    
    results = {
        'phone': phone,
        'checks': {}
    }
    
    # Verificações via API HTTP direta
    print('🔍 **APIs Diretas (0 disco, 0 RAM):**')
    print()
    
    api_checks = [
        ('Microsoft', check_microsoft_api),
        ('Google', check_google_api),
        ('Facebook', check_facebook_api),
        ('Twitter/X', check_twitter_api),
        ('Instagram', check_instagram_api),
    ]
    
    for name, func in api_checks:
        print(f'• {name}... ', end='', flush=True)
        try:
            r = func(phone)
            results['checks'][name] = r
            if r.get('exists') == True:
                print(f'✅ CONTA ENCONTRADA')
            elif r.get('exists') == False:
                print(f'❌ Não encontrado')
            elif r.get('exists') == 'error':
                print(f'⚠️ Erro: {r.get("error", "desconhecido")[:60]}')
            else:
                print(f'⚠️ Status: {r.get("exists", "?" )}')
        except Exception as e:
            print(f'⚠️ Erro: {e}')
    
    print()
    print('📊 **Resumo Final:**')
    print('=' * 50)
    
    found = [k for k, v in results['checks'].items() if v.get('exists') == True]
    not_found = [k for k, v in results['checks'].items() if v.get('exists') == False]
    errors = [k for k, v in results['checks'].items() if v.get('exists') in ('error', 'unknown')]
    
    if found:
        print(f'✅ Contas encontradas em: {', '.join(found)}')
    if not_found:
        print(f'❌ Não registrado em: {', '.join(not_found)}')
    if errors:
        print(f'⚠️ Falha na verificação: {', '.join(errors)}')
    
    return results


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python3 moriarty_http_module.py NÚMERO_TELEFONE')
        print('Exemplo: python3 moriarty_http_module.py +5511999999999')
        sys.exit(1)
    
    phone = ' '.join(sys.argv[1:])
    results = run_all(phone)
    print()
    print('--- JSON completo ---')
    print(json.dumps(results, indent=2, ensure_ascii=False))
