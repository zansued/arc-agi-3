#!/usr/bin/env python3
"""
Instagram OSINT Ultimate — Script personalizado com instagrapi
Uso: python3 instagram_osint_ultimate.py --username PERFIL_ALVO [--download] [--seguidores] [--seguindo]
"""
import argparse
import json
import os
import sys
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, BadPassword, ClientError, ChallengeRequired, PleaseWaitFewMinutes

# Credenciais da conta burner
USERNAME = "lucas.mikaelson01"
PASSWORD = "bratva2529"

class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

BANNER = f"""{colors.OKBLUE}
██╗██████╗ ███████╗████████╗ █████╗  ██████╗ ██████╗  █████╗ ███╗   ███╗
██║██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔════╝ ██╔══██╗██╔══██╗████╗ ████║
██║██████╔╝███████╗   ██║   ███████║██║  ███╗██████╔╝███████║██╔████╔██║
██║██╔══██╗╚════██║   ██║   ██╔══██║██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║
██║██║  ██║███████║   ██║   ██║  ██║╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║
╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
{colors.ENDC}
"""

def login():
    """Faz login no Instagram usando instagrapi"""
    cl = Client()
    cl.delay_range = [1, 3]  # Delay entre requisições para evitar bloqueio

    print(f"{colors.OKGREEN}[*] Logando como {USERNAME}...{colors.ENDC}")
    try:
        cl.login(USERNAME, PASSWORD)
        print(f"{colors.OKGREEN}[+] Login bem-sucedido!{colors.ENDC}")
        return cl
    except BadPassword:
        print(f"{colors.FAIL}[-] Senha incorreta para {USERNAME}{colors.ENDC}")
        sys.exit(1)
    except ChallengeRequired:
        print(f"{colors.WARNING}[!] Desafio de segurança exigido pelo Instagram!{colors.ENDC}")
        print(f"{colors.WARNING}[!] Verifique seu email/app Instagram para confirmar o login.{colors.ENDC}")
        sys.exit(1)
    except PleaseWaitFewMinutes as e:
        print(f"{colors.WARNING}[!] Instagram pede para esperar: {e}{colors.ENDC}")
        sys.exit(1)
    except ClientError as e:
        print(f"{colors.FAIL}[-] Erro do cliente: {e}{colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{colors.FAIL}[-] Erro inesperado: {e}{colors.ENDC}")
        sys.exit(1)

def get_user_info(cl, username):
    """Obtém informações completas de um perfil"""
    print(f"{colors.OKGREEN}[*] Obtendo informações de @{username}...{colors.ENDC}")
    try:
        user_id = cl.user_id_from_username(username)
        info = cl.user_info(user_id)
        return info
    except Exception as e:
        print(f"{colors.FAIL}[-] Erro ao buscar perfil @{username}: {e}{colors.ENDC}")
        return None

def display_info(info):
    """Exibe informações do perfil formatadas"""
    nova_linha = '\n'
    print(f"\n{colors.HEADER}{'='*60}{colors.ENDC}")
    print(f"{colors.OKGREEN}📊 INFORMAÇÕES DO PERFIL{colors.ENDC}")
    print(f"{colors.HEADER}{'='*60}{colors.ENDC}")
    print(f"👤 Nome de usuário: {colors.BOLD}@{info.username}{colors.ENDC}")
    print(f"📝 Nome completo: {info.full_name}")
    print(f"📖 Bio: {info.biography or '(vazia)'}")
    print(f"🔗 URL externa: {info.external_url or '(não tem)'}")
    print()
    print(f"👥 Seguidores: {info.follower_count:,}")
    print(f"➡️ Seguindo: {info.following_count:,}")
    print(f"📸 Posts: {info.media_count:,}")
    print()
    print(f"🔒 Conta privada: {'✅ Sim' if info.is_private else '❌ Não'}")
    print(f"✅ Verificada: {'✅ Sim' if info.is_verified else '❌ Não'}")
    print(f"🏢 Conta comercial: {'✅ Sim' if info.is_business else '❌ Não'}")
    if info.is_business and info.business_category_name:
        print(f"   Categoria: {info.business_category_name}")
    print(f"📱 Conectada ao Facebook: {'✅ Sim' if info.connected_fb_page else '❌ Não'}")
    print(f"🆕 Entrou recentemente: {'✅ Sim' if info.is_joined_recently else '❌ Não'}")
    print()
    print(f"🆔 User ID: {info.pk}")
    print(f"📧 Email público: {info.public_email or 'não informado'}")
    print(f"☎️ Telefone público: {info.public_phone_number or 'não informado'}")
    print(f"{colors.HEADER}{'='*60}{colors.ENDC}")
    return info

def download_profile_pic(cl, info, output_dir):
    """Baixa a foto do perfil"""
    if info.profile_pic_url_hd:
        os.makedirs(output_dir, exist_ok=True)
        print(f"{colors.OKGREEN}[*] Baixando foto de perfil...{colors.ENDC}")
        try:
            cl.photo_download(info.pk, folder=output_dir, filename=info.username)
            print(f"{colors.OKGREEN}[+] Foto salva em {output_dir}/{info.username}.jpg{colors.ENDC}")
        except Exception as e:
            print(f"{colors.WARNING}[!] Erro ao baixar foto: {e}{colors.ENDC}")

def get_followers(cl, user_id, amount=0):
    """Obtém lista de seguidores (limitado pelo Instagram)"""
    print(f"{colors.OKGREEN}[*] Obtendo seguidores...{colors.ENDC}")
    try:
        followers = cl.user_followers(user_id, amount=amount or None)
        print(f"{colors.OKGREEN}[+] {len(followers)} seguidores obtidos{colors.ENDC}")
        return followers
    except Exception as e:
        print(f"{colors.FAIL}[-] Erro ao obter seguidores: {e}{colors.ENDC}")
        return {}

def get_following(cl, user_id, amount=0):
    """Obtém lista de seguindo"""
    print(f"{colors.OKGREEN}[*] Obtendo lista de seguindo...{colors.ENDC}")
    try:
        following = cl.user_following(user_id, amount=amount or None)
        print(f"{colors.OKGREEN}[+] {len(following)} contas seguidas obtidas{colors.ENDC}")
        return following
    except Exception as e:
        print(f"{colors.FAIL}[-] Erro ao obter seguindo: {e}{colors.ENDC}")
        return {}

def save_json(data, filepath):
    """Salva dados em JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        clean = {}
        for k, v in data.items():
            if hasattr(v, '__dict__'):
                clean[k] = str(v)
            else:
                try:
                    json.dumps({k: v})
                    clean[k] = v
                except:
                    clean[k] = str(v)
        json.dump(clean, f, indent=2, ensure_ascii=False)
    print(f"{colors.OKGREEN}[+] Dados salvos em {filepath}{colors.ENDC}")

def main():
    parser = argparse.ArgumentParser(description="Instagram OSINT Ultimate — Extração completa de perfis")
    parser.add_argument("--username", help="Username do perfil alvo", required=True)
    parser.add_argument("--download", help="Baixar foto de perfil", action='store_true', default=False)
    parser.add_argument("--seguidores", help="Extrair lista de seguidores (limitado pelo Instagram)", action='store_true', default=False)
    parser.add_argument("--seguindo", help="Extrair lista de contas que o alvo segue", action='store_true', default=False)
    args = parser.parse_args()

    print(BANNER)
    print(f"{colors.HEADER}🚀 Instagram OSINT Ultimate — v1.0{colors.ENDC}")
    print(f"{colors.HEADER}🎯 Alvo: @{args.username}{colors.ENDC}\n")

    cl = login()
    info = get_user_info(cl, args.username)

    if not info:
        sys.exit(1)

    display_info(info)

    output_dir = f"resultados_instagram/{args.username}"
    os.makedirs(output_dir, exist_ok=True)

    # Salvar dados em JSON
    info_dict = {
        "username": info.username,
        "full_name": info.full_name,
        "biography": info.biography,
        "external_url": info.external_url,
        "follower_count": info.follower_count,
        "following_count": info.following_count,
        "media_count": info.media_count,
        "is_private": info.is_private,
        "is_verified": info.is_verified,
        "is_business": info.is_business,
        "business_category_name": info.business_category_name,
        "connected_fb_page": info.connected_fb_page,
        "is_joined_recently": info.is_joined_recently,
        "pk": info.pk,
        "profile_pic_url_hd": info.profile_pic_url_hd,
        "public_email": info.public_email,
        "public_phone_number": info.public_phone_number,
    }
    save_json(info_dict, os.path.join(output_dir, "profile_info.json"))

    # Download da foto de perfil
    if args.download:
        download_profile_pic(cl, info, output_dir)

    # Extrair seguidores
    if args.seguidores:
        followers = get_followers(cl, info.pk)
        if followers:
            followers_list = {str(uid): {"username": u.username, "full_name": u.full_name} for uid, u in followers.items()}
            save_json(followers_list, os.path.join(output_dir, "seguidores.json"))
            print(f"\n{colors.OKGREEN}📋 AMOSTRA DOS SEGUIDORES:{colors.ENDC}")
            for i, (uid, u) in enumerate(followers_list.items()):
                if i >= 10:
                    print(f"  ... e mais {len(followers_list) - 10} seguidores")
                    break
                print(f"  {i+1}. @{u['username']} — {u['full_name']}")

    # Extrair seguindo
    if args.seguindo:
        following = get_following(cl, info.pk)
        if following:
            following_list = {str(uid): {"username": u.username, "full_name": u.full_name} for uid, u in following.items()}
            save_json(following_list, os.path.join(output_dir, "seguindo.json"))
            print(f"\n{colors.OKGREEN}📋 AMOSTRA DE QUEM SEGUE:{colors.ENDC}")
            for i, (uid, u) in enumerate(following_list.items()):
                if i >= 10:
                    print(f"  ... e mais {len(following_list) - 10} contas")
                    break
                print(f"  {i+1}. @{u['username']} — {u['full_name']}")

    print(f"\n{colors.OKGREEN}✅ Concluído! Resultados em: {output_dir}/{colors.ENDC}")

if __name__ == "__main__":
    main()
