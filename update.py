import os
import requests
import json
import xml.etree.ElementTree as ET
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

CANALI_TV_CLASSICI = {
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Canal+ Sport", "Canal+ Sport 2", "Canal+ Extra", "Canal+ 1",
    "Cosmote Sport", "Eurosport Poland", 
    "Canal+ Sport 1", "Canal+ Sport 3", "Canal+ Sport 4", "Canal+ Sport 5",
    "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3",
    "Canal+ Sport Premium 1", "Canal+ Sport Premium 2", 
    "TVP Sport", "Max Sport", "Nova Sport",
    "RSI LA1", "RSI LA2",
    "Rai 1", "Rai 2", "Canale 5", "Italia 1", "Mediaset 20", "Mediaset Extra", "TV8",
    "Prime Video"
}

INFO_CANALI = {}  
CACHE_GUIDE = {}  
TUTTI_I_CANALI_BLU = set()
TUTTI_I_CANALI_NERI = set()
TUTTI_I_CANALI_GIALLI = set()

def carica_canali_esterni():
    global TUTTI_I_CANALI_BLU, TUTTI_I_CANALI_NERI, TUTTI_I_CANALI_GIALLI
    playlist = [
        (URL_CANALI_BLU, TUTTI_I_CANALI_BLU, "blu"),
        (URL_SECONDA_LISTA, TUTTI_I_CANALI_NERI, "neri"),
        (URL_TERZA_LISTA, TUTTI_I_CANALI_GIALLI, "gialli")
    ]
    for url, target_set, nome_playlist in playlist:
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

def carica_id_da_github():
    global INFO_CANALI
    url_api = "https://iptv-org.github.io/api/channels.json"
    tutti_i_nomi = list(TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI).union(CANALI_TV_CLASSICI))
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            data = response.json()
            db_canali = {c.get('name').lower(): {"id": c.get('id'), "country": c.get('country', 'it').lower()} for c in data if c.get('name')}
            for nome in tutti_i_nomi:
                nome_lower = nome.lower()
                if nome_lower in db_canali:
                    INFO_CANALI[nome] = db_canali[nome_lower]
                else:
                    trovato = False
                    for db_name, info in db_canali.items():
                        if nome_lower in db_name:
                            INFO_CANALI[nome] = info
                            trovato = True
                            break
                    if not trovato:
                        INFO_CANALI[nome] = {"id": nome.replace(" ", ""), "country": "it"}
    except Exception:
        pass

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def precarica_guide_necessarie():
    # Nazioni mirate principali
    nazioni = ["it", "ch", "gb", "es", "fr", "pl", "pt", "ua", "ie", "cz", "gr", "za", "tr", "us", "ca", "al"]
    print("\n--- SCARICAMENTO GUIDE IPTV-ORG PER NAZIONE ---")
    
    for country_code in nazioni:
        url_iptv = f"https://iptv-org.github.io/epg/guides/{country_code}.xml"
        try:
            res = requests.get(url_iptv, timeout=8)
            if res.status_code == 200 and len(res.content) > 500:
                CACHE_GUIDE[country_code] = ET.fromstring(res.content)
                print(f"[OK] Guida caricata per: {country_code}")
        except Exception as e:
            print(f"[ERRORE] Impossibile scaricare {country_code}: {e}")
            
    print(f"Totale guide caricate con successo in cache: {len(CACHE_GUIDE)}\n")

def cerca_canali_per_partita(date_utc, home_team, away_team):
    canali_trovati = []
    keywords = ["inter", home_team.lower(), away_team.lower()]
    
    for nome_canale, info in INFO_CANALI.items():
        channel_id = info.get("id")
        country_code = info.get("country", "it")
        
        # Cerca prima nella nazione del canale, poi nelle altre se necessario
        ordine_nazioni = [country_code] + [n for n in CACHE_GUIDE.keys() if n != country_code]
        
        trovato_per_canale = False
        for c_code in ordine_nazioni:
            if trovato_per_canale: break
            root = CACHE_GUIDE.get(c_code)
            if root is None: continue
            
            try:
                for programme in root.findall('programme'):
                    if channel_id and programme.get('channel') == channel_id:
                        title_el = programme.find('title')
                        if title_el is not None and title_el.text:
                            t_text = title_el.text.lower()
                            if any(key in t_text for key in keywords):
                                start_str = programme.get('start')
                                if start_str:
                                    dt_part = start_str.split(' ')[0]
                                    prog_start = datetime.strptime(dt_part[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                                    diff_ore = abs((prog_start - date_utc).total_seconds()) / 3600
                                    
                                    if diff_ore <= 2:
                                        if nome_canale not in canali_trovati:
                                            canali_trovati.append(nome_canale)
                                            print(f"Trovata corrispondenza! Partita: {home_team}-{away_team} | Canale: {nome_canale} | Programma: {title_el.text}")
                                        trovato_per_canale = True
                                        break
            except Exception:
                continue
                
    return canali_trovati

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        adesso = datetime.now(timezone.utc)
        
        precarica_guide_necessarie()
        
        for match in data.get('matches', []):
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            date_str = match.get('utcDate')
            if not date_str: continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc < adesso: continue

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            canali_reali = cerca_canali_per_partita(date_utc, home, away)
            if not canali_reali:
                canali_reali = ["In attesa di programmazione ufficiale ⏳"]
            
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
    cal.add('prodid', '-//Calendario Inter V41 Fast//IT')
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
            if "In attesa" in c: righe_canali.append(c)
            elif "prime" in c.lower(): righe_canali.append("🎬 Prime Video")
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
    carica_id_da_github()
    matches = fetch_next_matches()
    generate_ics(matches)
