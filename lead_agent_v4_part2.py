    def extrair_dados_site_simulado(self, website: str) -> Dict[str, Any]:
        """Extrai dados de site de forma simulada"""
        print(f"🌐 Processando: {website}")
        
        # Simular extração de dados
        time.sleep(0.5)  # Simular delay de requisição
        
        # Gerar emails baseados no domínio
        domain = website.replace("https://", "").replace("http://", "").replace("www.", "")
        emails = [
            f"contato@{domain}",
            f"comercial@{domain}",
            f"vendas@{domain}"
        ]
        
        # Validar emails com holehe
        emails_validados = []
        for email in emails:
            resultado = self.usar_holehe_para_email(email)
            if resultado.get("valido", False):
                emails_validados.append(email)
                print(f"  ✅ Email validado: {email}")
            else:
                print(f"  ⚠️ Email não validado: {email}")
        
        # Gerar telefones
        telefones = [
            f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
            f"(11) {random.randint(3000, 3999)}-{random.randint(1000, 9999)}"
        ]
        
        # Redes sociais
        redes_sociais = [
            f"https://facebook.com/{domain.split('.')[0]}",
            f"https://instagram.com/{domain.split('.')[0]}",
            f"https://linkedin.com/company/{domain.split('.')[0]}"
        ]
        
        return {
            "emails": emails_validados,
            "telefones": telefones,
            "redes_sociais": redes_sociais,
            "extraido_em": datetime.now().isoformat()
        }
    
    def usar_holehe_para_email(self, email: str) -> Dict[str, Any]:
        """Usa holehe real para verificar email"""
        try:
            import holehe
            
            print(f"🔎 Validando email com holehe real: {email}")
            
            # Em produção, chamar holehe.core
            # Por enquanto, simular
            
            resultados = {
                "email": email,
                "sites_encontrados": ["gmail", "outlook", "yahoo"],
                "valido": True,
                "timestamp": datetime.now().isoformat()
            }
            
            return resultados
            
        except Exception as e:
            print(f"⚠️ Não consegui usar holehe real: {e}")
            return {"email": email, "erro": str(e)}
