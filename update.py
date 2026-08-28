import os
import requests
import json
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
URL_CANALI_BLU = os.getenv("URL_CANALI_BLU")
URL_SECONDA_LISTA = os.getenv("URL_SECONDA_LISTA")
URL_TERZA_LISTA = os.getenv("URL_TERZA_LISTA")

HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

COMPETITIONS = ['SA', 'CL', 'COI', 'ITC', 'CLI', 'FR1']
TEAM_ID = 108

# Mappatura di sicurezza predefinita per i canali principali in base alla competizione
MAPPATURA_STANDARD = {
    "SA": ["DAZN 1", "Sky Sport Calcio", "Sky Sport Uno"],
    "CL": ["Sky Sport Uno", "Sky Sport Calcio", "Prime Video"],
    "COI": ["Mediaset 20", "Canale 5", "Italia 1"],
    "FR1": ["Canal+ Sport", "Prime Video"]
}

TUTTI_I_CANALI_BLU = set()
TUTTI_I_CANALI_NERI = set()
TUTTI_I_CANALI_GIALLI = set()

def carica_canali_esterni():
    global TUTTI_I_CANALI_BLU, TUTTI_I_CANALI_NERI, TUTTI_I_CANALI_GIALLI
    playlist = [
        (URL_CANALI_BLU, TUTTI_I_CANALI_BLU),
        (URL_SECONDA_LISTA, TUTTI_I_CANALI_NERI),
        (URL_TERZA_LISTA, TUTTI_I_CANALI_GIALLI)
    ]
    for url, target_set in playlist:
        if url:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            c_name = line.split(",", 1)[1].strip() if "," in line else line
                            if c_name:
                                target_set.add(c_name)
            except Exception:
                pass

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def trova_canali_per_competizione(comp_code):
    canali_trovati = []
    # Prende i canali standard associati alla competizione
    standard = MAPPATURA_STANDARD.get(comp_code, ["Sky Sport Calcio", "DAZN 1"])
    
    # Unisce le liste caricate dall'utente
    tutti_disponibili = list(TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI))
    
    for s in standard:
        # Cerca se il canale standard è presente nelle liste personalizzate
        trovato_nelle_liste = False
        for c in tutti_disponibili:
            if s.lower() in c.lower():
                canali_trovati.append(c)
                trovato_nelle_liste = True
        if not trovato_nelle_liste:
            canali_trovati.append(s)
            
    return list(dict.fromkeys(canali_trovati))

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        adesso = datetime.now(timezone.utc)
        
        for match in data.get('matches', []):
            comp_info = match.get('competition', {})
            comp_code = comp_info.get('code')
            if comp_code not in COMPETITIONS:
                continue
                
            date_str = match.get('utcDate')
            if not date_str: continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc < adesso: continue

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = comp_info.get('name', 'Competizione')
            
            canali_reali = trova_canali_per_competizione(comp_code)
            
            all_matches.append({
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': canali_reali
            })
            
    except Exception as e:
        print(f"Errore API partite: {e}")
        
    all_matches.sort(key=lambda x: x['ora_utc'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V44 Definitivo//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora_utc'])
        evento.add('dtend', p['ora_utc'] + timedelta(hours=2))
        
        canali_blu, canali_neri, canali_gialli, altri_canali = [], [], [], []
        
        for c in p['canali']:
            if c in TUTTI_I_CANALI_BLU: canali_blu.append(c)
            elif c in TUTTI_I_CANALI_NERI: canali_neri.append(c)
            elif c in TUTTI_I_CANALI_GIALLI: canali_gialli.append(c)
            else: altri_canali.append(c)
                
        canali_blu.sort()
        canali_neri.sort()
        canali_gialli.sort()
        
        righe_canali = []
        for c in canali_blu:
            righe_canali.append("🎬 Prime Video" if "prime" in c.lower() else f"🔵 {c}")
        for c in canali_neri:
            righe_canali.append("🎬 Prime Video" if "prime" in c.lower() else f"⚫ {c}")
        for c in canali_gialli:
            righe_canali.append("🎬 Prime Video" if "prime" in c.lower() else f"🟡 {c}")
        for c in altri_canali:
            if "prime" in c.lower(): righe_canali.append("🎬 Prime Video")
            else: righe_canali.append(f"📺 {c}")
                
        righe_canali = list(dict.fromkeys(righe_canali))
        canali_testo = "\n".join(righe_canali)
        evento.add('description', f"🏆 Competizione: {p['competizione']}\n\n📡 Canali TV:\n{canali_testo}")
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File ICS generato con successo.")

if __name__ == '__main__':
    carica_canali_esterni()
    matches = fetch_next_matches()
    generate_ics(matches)
