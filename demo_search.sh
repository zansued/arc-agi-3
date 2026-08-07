#!/bin/bash

# Script de demonstração do sistema de busca

echo "🚀 DEMONSTRAÇÃO DO SISTEMA DE BUSCA OSINT"
echo "=================================================="
echo ""

SEARCH_DIR="/a0/usr/workdir/search_tools_system"
cd "$SEARCH_DIR"

# 1. Testar análise das ferramentas
echo "1. 🔍 Analisando ferramentas de busca..."
python3 analyze_tools.py
echo ""

# 2. Testar busca básica
echo "2. 🔎 Testando busca básica..."
echo ""

QUERY="teste"
echo "Busca por: '$QUERY'"
echo ""

python3 scripts/search_tools_api.py "$QUERY" --tool filesearch

echo ""
echo "3. 📊 Exemplo de busca completa..."
echo ""

# 3. Busca completa (todas ferramentas)
echo "Executando busca completa em todas as ferramentas..."
echo "(Isso pode levar alguns segundos)"
echo ""

python3 scripts/search_tools_api.py "osint" --tool all

echo ""
echo "✅ Demonstração concluída!"
echo ""
echo "📚 COMO USAR:"
echo ""
echo "1. Busca em todas as ferramentas:"
echo "   python3 scripts/search_tools_api.py 'termo de busca'"
echo ""
echo "2. Busca em ferramenta específica:"
echo "   python3 scripts/search_tools_api.py 'termo' --tool filesearch"
echo "   python3 scripts/search_tools_api.py 'termo' --tool criminal"
echo "   python3 scripts/search_tools_api.py 'termo' --tool intelx"
echo ""
echo "3. Salvar em arquivo específico:"
echo "   python3 scripts/search_tools_api.py 'termo' --output meus_resultados.json"
echo ""
echo "🔧 Ferramentas disponíveis:"
echo "   • Complete Criminal Checks (criminal)"
echo "   • FileSearch.link (filesearch)"
echo "   • Intelx Data Search (intelx)"
echo ""
