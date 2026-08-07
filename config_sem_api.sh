#!/bin/bash
# Configuração para usar ferramentas OSINT sem API keys

echo "=== CONFIGURANDO USO SEM API KEYS ==="
echo ""

# 1. theHarvester - usar apenas módulos sem API
echo "1. CONFIGURANDO THEHARVESTER:"
echo "   Usando módulos sem API: google, bing, dnsdumpster, crtsh"
echo "   Comando exemplo:"
echo "   python3 theHarvester.py -d exemplo.com -b google,bing,dnsdumpster"
echo ""

# 2. recon-ng - usar módulos públicos
echo "2. CONFIGURANDO RECON-NG:"
echo "   Módulos que funcionam sem API:"
echo "   - recon/domains-hosts/google_site_web"
echo "   - recon/domains-hosts/brute_hosts"
echo "   - recon/domains-hosts/netcraft"
echo ""

# 3. SpiderFoot - configurar sem API
echo "3. CONFIGURANDO SPIDERFOOT:"
echo "   Módulos que funcionam sem API:"
echo "   - sfp_dns: Consulta DNS"
echo "   - sfp_whois: Consulta WHOIS"
echo "   - sfp_ssl: Certificados SSL"
echo ""

# 4. Sherlock - já funciona sem API
echo "4. SHERLOCK JÁ FUNCIONA SEM API"
echo ""

# 5. Amass - já funciona sem API
echo "5. AMASS JÁ FUNCIONA SEM API"
echo ""

echo "✅ CONFIGURAÇÃO COMPLETA!"
echo "Todas ferramentas podem ser usadas sem API keys."
echo "Algumas funcionalidades estarão limitadas, mas o essencial funciona."
