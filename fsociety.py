#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FSOCIETY — Terminal Interface v3.0
Simulated environment for demonstration purposes only.
"Hello, friend."
"""

import os
import sys
import time
import random
import shutil

# ─── Cores ANSI ────────────────────────────────────────
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
CYAN   = '\033[96m'
WHITE  = '\033[97m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

# ─── Utilitários ───────────────────────────────────────

def clear():
    os.system('clear' if os.name == 'posix' else 'cls')

def slow(text, delay=0.04):
    for ch in text:
        print(ch, end='', flush=True)
        time.sleep(delay)
    print()

def bar(duration=2.0, label=''):
    w = 40
    for i in range(w + 1):
        pct = int(i / w * 100)
        fill = '█' * i
        emp  = '░' * (w - i)
        print(f'\r[{GREEN}{fill}{RESET}{emp}] {GREEN}{pct:3d}%{RESET}  {label}', end='', flush=True)
        time.sleep(duration / w)
    print()

def line(c='─', n=58):
    print(f'{GREEN}{c * n}{RESET}')

def box(text, c=GREEN):
    """Centraliza texto em moldura."""
    w = 58
    t = text.center(w - 4)
    print(f'{c}╔{'═' * (w-2)}╗{RESET}')
    print(f'{c}║ {t} ║{RESET}')
    print(f'{c}╚{'═' * (w-2)}╝{RESET}')

def rain(n=5, col=GREEN):
    for _ in range(n):
        s = ''.join(random.choice('01アイウエオカキクケコサシスセソタチツテト') for _ in range(50))
        print(f'  {col}{s}{RESET}')
        time.sleep(0.08)

# ─── Banner principal ──────────────────────────────────

BANNER = f"""{GREEN}
{'╔' + '═'*50 + '╗'}
{'║' + ' '*50 + '║'}
{'║'}{' '*13}{BOLD}░█▀▀░█▀█░█▀▀░▀█▀░█▀▀░█▀▄░▀█▀{' '*14}{'║'}
{'║'}{' '*13}░█▀▀░█░█░▀▀█░░█░░█▀▀░█▀▄░░█░{' '*14}{'║'}
{'║'}{' '*13}░▀▀▀░▀░▀░▀▀▀░░▀░░▀▀▀░▀░▀░▀▀▀{' '*14}{'║'}
{'║' + ' '*50 + '║'}
{'║'}{' '*12}{BOLD}F  S  O  C  I  E  T  Y{' '*14}{'║'}
{'║' + ' '*50 + '║'}
{'╚' + '═'*50 + '╝'}{RESET}
"""

# ─── Telas ─────────────────────────────────────────────

def tela_boot():
    clear()
    print(f'{GREEN}{BOLD}INICIALIZANDO SISTEMA FSOCIETY...{RESET}')
    print()
    rain(4, GREEN)
    print()
    bar(1.5, 'modulos de kernel')
    bar(1.2, 'interfaces de rede')
    bar(0.8, 'bibliotecas criptograficas')
    print()
    slow(f'{YELLOW}[!] AVISO: Este e um ambiente simulado.{RESET}')
    slow(f'{YELLOW}[!] Todas as acoes sao ficticias — apenas para demonstracao.{RESET}')
    time.sleep(1.0)

def tela_boas_vindas():
    clear()
    print(BANNER)
    line()
    print()
    msg = f'{BOLD}SEJA BEM VINDO SENHOR LUAN{RESET}'
    print(f'  {GREEN}{msg}{RESET}')
    print()
    slow(f'  {GREEN}ACESSO AUTORIZADO. BEM-VINDO A FSOCIETY.{RESET}')
    print()
    line()
    time.sleep(1.5)

def tela_modulos():
    modulos = [
        ('01', 'INVADIR SISTEMAS',       'Framework de penetracao — 12 exploits carregados em memoria'),
        ('02', 'ACESSAR CAMERAS',         'Scanner RTSP/ONVIF — 4 protocolos ativos na rede local'),
        ('03', 'QUEBRAR SENHAS',          'Hashcat + tabelas Rainbow — 200 milhoes de hashes por segundo'),
        ('04', 'RASTREAR IP',             'GeoIP + identificacao de ISP e VPN — 98% de precisao'),
        ('05', 'EXTRAIR METADADOS',       'EXIF, GPS e propriedades de documentos em lote'),
        ('06', 'MONITORAR REDE',          'Packet sniffer — analise ARP, DNS e HTTP em tempo real'),
        ('07', 'CLONAR SITE',             'wget mirror + HTTrack + varredura de dominios'),
        ('08', 'INJECAO SQL',             'SQLMap + 15 engines de bypass e tamper customizados'),
        ('09', 'BYPASS FIREWALL',         'Proxy chain + Tor + tunelamento SSH multi-camada'),
        ('10', 'ESCANEAR PORTAS',         'TCP/UDP SYN scan — 65535 portas em menos de 30 segundos'),
        ('11', 'DECODIFICAR MENSAGENS',   'Base64, Hex, ROT13, AES, RSA — suite completa de cifras'),
        ('12', 'ACESSAR DARK WEB',        'Navegador Tor + crawler do HiddenWiki ja ativos'),
        ('13', 'SPOOFAR IDENTIDADE',      'Randomizador de MAC, IP e User-Agent por sessao'),
        ('14', 'MINERAR BITCOIN',         'Pool XMRig — rendimento estimado de 0.0001 BTC/dia'),
        ('15', 'APAGAR LOGS',             'Apagamento seguro — padrao DoD 5220.22-M'),
    ]

    box(' MODULOS DISPONIVEIS ')
    print()
    for mod_id, titulo, desc in modulos:
        n = int(mod_id)
        cor = CYAN if n % 2 == 0 else GREEN
        print(f'  {cor}[{mod_id}]{RESET} {WHITE}{BOLD}{titulo}{RESET}')
        time.sleep(0.06)
    print()
    line()

def executar_modulo(escolha):
    nomes = [
        'INVADIR SISTEMAS', 'ACESSAR CAMERAS', 'QUEBRAR SENHAS',
        'RASTREAR IP', 'EXTRAIR METADADOS', 'MONITORAR REDE',
        'CLONAR SITE', 'INJECAO SQL', 'BYPASS FIREWALL',
        'ESCANEAR PORTAS', 'DECODIFICAR MENSAGENS', 'ACESSAR DARK WEB',
        'SPOOFAR IDENTIDADE', 'MINERAR BITCOIN', 'APAGAR LOGS'
    ][escolha - 1]

    print()
    slow(f'{GREEN}[+] Inicializando modulo: {BOLD}{nomes}{RESET}')
    bar(2.5, 'processando')
    print()
    slow(f'{YELLOW}[!] SIMULACAO — Modulo "{nomes}" executado com sucesso.{RESET}')
    slow(f'{YELLOW}[!] Nenhuma acao real foi realizada. Apenas para fins educacionais.{RESET}')
    print()
    line('─')
    rain(3, CYAN)
    line('─')
    time.sleep(1.5)

def menu_interativo():
    while True:
        print()
        slow(f'{YELLOW}Digite o numero do modulo para executar (ou 0 para sair):{RESET}')
        try:
            inp = input(f'{GREEN}>> {RESET}').strip()
        except (EOFError, KeyboardInterrupt):
            break

        if inp == '0' or inp == '':
            break

        if inp.isdigit() and 1 <= int(inp) <= 15:
            executar_modulo(int(inp))
        else:
            print()
            slow(f'{RED}[!] Modulo invalido. Tente novamente.{RESET}')
            time.sleep(0.8)

def tela_encerramento():
    print()
    slow(f'{RED}Desconectando da FSOCIETY...{RESET}')
    time.sleep(0.3)
    rain(4, RED)
    slow(f'{RED}Sistema encerrado.{RESET}')
    time.sleep(0.5)
    print()
    box(' O mundo e uma pergunta. E voce e a resposta. ', CYAN)
    print(f'  {CYAN}— Elliot Alderson{RESET}')
    print()

# ─── Main ────────────────────────────────────────────

def main():
    try:
        tela_boot()
        tela_boas_vindas()
        tela_modulos()
        menu_interativo()
    except KeyboardInterrupt:
        print()
        slow(f'{RED}[!] Interrompido pelo usuario.{RESET}')
        time.sleep(0.3)
    finally:
        tela_encerramento()


if __name__ == '__main__':
    main()
