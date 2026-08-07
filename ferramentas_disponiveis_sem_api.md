# FERRAMENTAS DISPONÍVEIS SEM API KEYS

## ✅ TOTALMENTE FUNCIONAIS:

### 1. Sherlock
- Busca usuários em redes sociais
- 100% funcional sem API
- Comando: `python3 sherlock usuario`

### 2. Amass  
- Enumeração de subdomínios
- Funcionalidade básica sem API
- Comando: `amass enum -passive -d exemplo.com`

### 3. theHarvester (limitado)
- Módulos sem API: google, bing, dnsdumpster, crtsh, etc.
- Comando: `python3 theHarvester.py -d exemplo.com -b google,bing,dnsdumpster`

### 4. Awesome-OSINT (catálogo)
- Lista de ferramentas (apenas referência)
- Nenhuma API necessária

## ⚠️  REMOVIDAS/COM LIMITAÇÕES:

### 1. SpiderFoot ❌ REMOVIDO
- 522 módulos precisam API keys
- Removido do sistema

### 2. recon-ng ⚠️  MANTIDO COM LIMITAÇÕES
- Alguns módulos precisam API
- Framework funciona, módulos limitados
- Use módulos públicos

## 🗃️  SISTEMA EXISTENTE:

### 1. CPF Database (223.7M registros)
- Nenhuma API necessária
- Comando: `./busca_rapida.sh "Nome" nome`

### 2. Insta-OSINT
- Pode ter limitações de rate limiting
- Funciona sem API

### 3. Cybhorsearch (95k registros)
- Dados locais, sem API
