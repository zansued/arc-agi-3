    def salvar_leads_supabase(self, leads: List[Dict]) -> bool:
        """Salva leads no Supabase"""
        try:
            import psycopg2
            import json
            
            conn = psycopg2.connect(self.config["supabase_connection_string"])
            cursor = conn.cursor()
            
            leads_salvos = 0
            for lead in leads:
                cursor.execute("""
                    INSERT INTO lead_agent_results 
                    (nicho, nome, telefone, email, website, endereco, redes_sociais, status, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    lead.get("nicho", ""),
                    lead.get("nome", ""),
                    ", ".join(lead.get("telefones", [])),
                    ", ".join(lead.get("emails", [])),
                    lead.get("website", ""),
                    lead.get("endereco", ""),
                    lead.get("redes_sociais", []),
                    "coletado",
                    json.dumps(lead)
                ))
                leads_salvos += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ {leads_salvos} leads salvos no Supabase")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar no Supabase: {e}")
            return False
    
    def salvar_leads_google_sheets(self, leads: List[Dict], nome_planilha: str = "Leads Coletados") -> bool:
        """Salva leads no Google Sheets com fallback para Supabase"""
        if not self.gs_initialized:
            print("⚠️ Google Sheets não inicializado, usando Supabase")
            return self.salvar_leads_supabase(leads)
        
        try:
            import gspread
            
            # Tentar abrir planilha existente ou criar nova
            try:
                planilha = self.gc.open(nome_planilha)
                worksheet = planilha.sheet1
            except:
                planilha = self.gc.create(nome_planilha)
                worksheet = planilha.sheet1
                # Adicionar cabeçalhos
                cabecalhos = ["Data", "Nicho", "Nome", "Telefone", "Email", "Website", "Endereço", "Redes Sociais", "Status"]
                worksheet.append_row(cabecalhos)
            
            # Adicionar leads
            for lead in leads:
                linha = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    lead.get("nicho", ""),
                    lead.get("nome", ""),
                    ", ".join(lead.get("telefones", [])),
                    ", ".join(lead.get("emails", [])),
                    lead.get("website", ""),
                    lead.get("endereco", ""),
                    ", ".join(lead.get("redes_sociais", [])),
                    "coletado"
                ]
                worksheet.append_row(linha)
            
            print(f"✅ {len(leads)} leads salvos no Google Sheets")
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "403" in error_str or "storage" in error_str:
                print("⚠️ Quota Google Drive excedida, usando Supabase")
                return self.salvar_leads_supabase(leads)
            else:
                print(f"❌ Erro ao salvar no Google Sheets: {e}")
                print("Tentando Supabase como fallback...")
                return self.salvar_leads_supabase(leads)
    
    def salvar_analise_autopoiese(self, analise: Dict[str, Any]) -> bool:
        """Salva análise de autopoiese no Supabase"""
        try:
            import psycopg2
            import json
            
            conn = psycopg2.connect(self.config["supabase_connection_string"])
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO autopoiese_analysis 
                (execution_id, stats, metrics, recommendations, optimizations)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                analise.get("execution_id", f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                json.dumps(analise.get("stats", {})),
                json.dumps(analise.get("metrics", {})),
                analise.get("recommendations", []),
                analise.get("optimizations", [])
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Análise de autopoiese salva no Supabase")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar análise: {e}")
            # Fallback: salvar localmente
            try:
                filename = f"/a0/usr/workdir/autopoiese_analise_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w") as f:
                    json.dump(analise, f, indent=2, ensure_ascii=False)
                print(f"✅ Análise salva localmente: {filename}")
                return True
            except:
                return False
