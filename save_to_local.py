
import json
import os
from datetime import datetime

def save_to_local(leads, analysis):
    """Salva dados localmente"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Salvar leads
    leads_file = f"/a0/usr/workdir/leads_backup/leads_{timestamp}.json"
    os.makedirs(os.path.dirname(leads_file), exist_ok=True)
    
    with open(leads_file, "w") as f:
        json.dump({"leads": leads, "timestamp": timestamp}, f, indent=2)
    
    # Salvar análise
    analysis_file = f"/a0/usr/workdir/leads_backup/analysis_{timestamp}.json"
    with open(analysis_file, "w") as f:
        json.dump({"analysis": analysis, "timestamp": timestamp}, f, indent=2)
    
    print(f"✅ Dados salvos localmente: {leads_file}, {analysis_file}")
    return True
