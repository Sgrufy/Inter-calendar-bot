import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from calendar import Calendar, Event # o icalendar
from icalendar import Calendar, Event
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

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
    "Sport TV1", "Sport TV2", "Sport TV3", "Sport TV4", "Sport TV5", "Sport TV6",
    "RSI LA1", "RSI LA2",
    "Rai 1", "Rai 2", "Canale 5", "Italia 1", "TV8", "Prime Video"
}

INFO_CANALI = {}  
PROGRAMMI_EPG = [] # Memorizziamo i programmi trovati in modo efficiente
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

def carica_id_da_github():
    global INFO_CANALI
    url_api = "https://iptv-org.github.io/api/channels.json"
    tutti_i_nomi = list(TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI).union(CANALI_TV_CLASSICI))
    
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            data = response.json()
            db_canali = {c.get('name').lower(): {"id": c.get('id')} for c in data if c.get('name')}
            
            for nome in tutti_i_nomi:
                nome_lower = nome.lower()
                if nome_lower in db_canali:
                    INFO_CANALI[nome] = db_canali[nome_lower]
                else:
                    INFO_CANALI[nome] = {"id": nome.replace(" ", "")}
    except Exception:
        pass

def analizza_epg_stream(content_bytes, valid_channel_ids):
    """Usa iterparse per estrarre solo i programmi dei canali che ci interessano senza consumare RAM."""
    programmi_locali = []
    try:
        # Usiamo io.BytesIO per leggere il flusso binario in modo sicuro
        context = ET.iterparse(io.BytesIO(content_bytes), events=("end",))
        for event, elem in context:
            if elem.tag == 'programme':
                ch = elem.get('channel')
                if ch in valid_channel_ids:
                    title_el = elem.find('title')
                    title_text = title_el.text if (title_el is not None and title_el.text) else ""
                    start_str = elem.get('start')
                    if title_text and start_str:
                        programmi_locali.append({
                            'channel': ch,
                            'title': title_text.lower(),
                            'start': start_str
                        })
                # Svuotiamo l'elemento dalla memoria subito dopo l'uso per alleggerire RAM
                elem.clear()
    except Exception:
        pass
    return programmi_locali

def scarica_e_processa_paese(paese, valid_channel_ids):
    url_epg = f"https://iptv-epg.org/files/epg-{paese}.xml"
    try:
        res = requests.get(url_epg, headers=HEADERS, timeout=30)
        if res.status_code == 200:
            return analizza_epg_stream(res.content, valid_channel_ids)
    except Exception:
        pass
    return []

def scarica_tutti_gli_epg():
    global PROGRAMMI_EPG
    paesi = ['it', 'fr', 'es', 'pt', 'pl', 'us', 'ch', 'cz', 'al', 'tr', 'nl']
    
    # Raccogliamo tutti gli ID canale validi cercati nelle nostre liste
    valid_channel_ids = {info.get("id") for info in INFO_CANALI.values() if info.get("id")}
    
    print(f"\n--- DOWNLOAD E PARSING VERITIERO (iterparse) PER {len(paesi)} PAESI ---")
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(scarica_e_processa_paese, p, valid_channel_ids): p for p in paesi}
        for future in as_completed(futures):
            risultati_paese = future.result()
            if risultati_paese:
                PROGRAMMI_EPG.extend(risultati_paese)

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def cerca_canali_per_partita(date_utc, home_team, away_team):
    canali_trovati = []
    if not PROGRAMMI_EPG:
        return canali_trovati
        
    keywords = ["inter", home_team.lower(), away_team.lower()]
    # Creiamo un mapping inverso da channel_id a nome_canale
    id_to_names = {}
    for nome_canale, info in INFO_CANALI.items():
        ch_id = info.get("id")
        if ch_id:
            if ch_id not in id_to_names:
                id_to_names[ch_id] = []
            id_to_names[ch_id].append(nome_canale)

    for prog in PROGRAMMI_EPG:
        ch_id = prog['channel']
        if any(key in prog['title'] for key in keywords):
            start_str = prog['start']
            if start_str:
                dt_part = start_str.split(' ')[0]
                try:
                    prog_start = datetime.strptime(dt_part[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                    if abs((prog_start - date_utc).total_seconds()) <= 7200:
                        if ch_id in id_to_names:
                            for nome_canale in id_to_names[ch_id]:
                                if nome_canale not in canali_trovati:
                                    canali_trovati.append(nome_canale)
                except ValueError:
                    continue
                    
    return canali_trovati

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        adesso = datetime.now(timezone.utc)
        
        # Scarica ed elabora con precisione chirurgica
        scarica_tutti_gli_epg()
        
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
    cal.add('prodid', '-//Calendario Inter V54 Iterparse Veritiero//IT')
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
