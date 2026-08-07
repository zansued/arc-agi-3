# THEHARVESTER - MÓDULOS SEM API

## ✅ Módulos que NÃO precisam API (use estes):
- google
- bing  
- yahoo
- duckduckgo
- dnsdumpster
- crtsh
- certspotter
- threatcrowd
- trello
- github
- linkedin

## 🚫 Módulos que PRECISAM API (evite estes):
- shodan
- censys
- securitytrails
- zoomeye
- fofa
- quake
- hunter
- intelx
- binaryedge
- riskiq
- passivetotal

## 📝 Exemplo de comando SEM API:
```bash
python3 theHarvester.py -d exemplo.com -b google,bing,dnsdumpster,crtsh
```

## ⚠️ Aviso:
Se usar módulos com API sem chave, o theHarvester mostrará erro.
Use apenas os módulos listados acima.
