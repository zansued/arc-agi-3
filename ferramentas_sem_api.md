# FERRAMENTAS QUE FUNCIONAM SEM API KEYS

## ✅ TOTALMENTE FUNCIONAIS SEM API:

### 1. Sherlock
- Busca usuários em redes sociais
- Usa APIs públicas sem autenticação
- 100% funcional sem API keys

### 2. Amass (funcionalidade básica)
- Enumeração passiva de subdomínios
- Muitas fontes públicas
- Funciona bem sem API keys

### 3. theHarvester (módulos selecionados)
- Google, Bing, Yahoo (sem API)
- DNSDumpster, CRT.sh (sem API)
- LinkedIn, GitHub (limitações mas funciona)

## ⚠️  PRECISA API PARA ALGUNS MÓDULOS:

### 1. theHarvester (alguns módulos)
- Shodan, Censys, SecurityTrails (precisa API)
- Hunter, IntelX (precisa API)
- **SOLUÇÃO**: Usar apenas módulos sem API

### 2. recon-ng
- Muitos módulos precisam API
- Framework funciona, mas módulos limitados
- **SOLUÇÃO**: Usar módulos que não precisam API

### 3. SpiderFoot
- Muitos módulos precisam API
- Análise básica funciona
- **SOLUÇÃO**: Configurar sem API keys

## 🗑️  O QUE REMOVER (se quiser):

### Opção 1: Remover completamente
- NADA precisa ser removido completamente
- Todas funcionam parcialmente sem API

### Opção 2: Desabilitar módulos com API
- Configurar theHarvester para não usar módulos com API
- Usar apenas módulos públicos do recon-ng
- Configurar SpiderFoot sem módulos de API

### Opção 3: Manter tudo
- Todas ferramentas funcionam sem API (com limitações)
- Usar apenas funcionalidades públicas
