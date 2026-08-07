# COMANDOS RÁPIDOS OSINT

## theHarvester (coleta emails/subdomínios):
```bash
cd /a0/usr/workdir/theHarvester
# Buscar informações de domínio
python3 theHarvester.py -d exemplo.com -b google
# Buscar com todas fontes
python3 theHarvester.py -d exemplo.com -b all
# Salvar em arquivo
python3 theHarvester.py -d exemplo.com -b google -f resultado.txt
```

## recon-ng (framework OSINT):
```bash
cd /a0/usr/workdir/recon-ng
# Iniciar console
./recon-ng
# Comandos dentro do console:
#   modules search
#   modules load recon/domains-hosts/brute_hosts
#   info
#   options set SOURCE exemplo.com
#   run
```

## Amass (enumeração subdomínios):
```bash
# Scan passivo
amass enum -passive -d exemplo.com
# Scan ativo
amass enum -active -d exemplo.com -brute
# Com saída
amass enum -d exemplo.com -o resultado.txt
```

## Sherlock (busca usuários):
```bash
cd /a0/usr/workdir/sherlock
# Buscar usuário
python3 sherlock usuario
# Buscar múltiplos usuários
python3 sherlock usuario1 usuario2
# Com saída JSON
python3 sherlock usuario --json
```

## SpiderFoot (automação OSINT):
```bash
cd /a0/usr/workdir/spiderfoot
# Interface web
python3 sf.py -l 127.0.0.1:5001
# Acessar: http://127.0.0.1:5001
# CLI
python3 sf.py -s exemplo.com -m all
```

## Awesome-OSINT (catálogo):
```bash
cd /a0/usr/workdir/awesome-osint
# Ver categorias
grep -n "## " README.md
# Buscar ferramentas
grep -i "email\|phone\|social" README.md
```

## CPF Database (223.7M registros):
```bash
cd /a0/usr/workdir/cpf_database
./busca_rapida.sh "Nome" nome
./busca_rapida.sh "CPF" cpf
./busca_rapida.sh "01/01/1990" nascimento
```

## Insta-OSINT (Instagram):
```bash
cd /a0/usr/workdir/Insta-OSINT
python3 osint.py
```
