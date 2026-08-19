import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

COMPETITIONS = ['SA', 'CL', 'COI', 'ITC']
TEAM_ID = 108

# Mappa dei canali con ID corretti per allineare Eleven Sports 1 e 2 al palinsesto reale
CANALI_EPG = {
    "Eleven Sports 1": "6339",
    "Eleven Sports 2": "6340",
    "Eleven Sports 3": "6338",
    "Eleven Sports 4": "6336",
    "Canal+ Sport": "67504",
    "Canal+ Sport 2": "67502",
    "Canal+ Extra": "407523",
    "Canal+ 1": "407672",
    "Polsat Sport 1": "452290",
    "Polsat Sport 2": "449589",
    "Polsat Sport 3": "449590",
    "TVP Sport": "5778",
    "Cosmote 1": "476569",
    "Cosmote 2": "476571",
    "Max Sport 1": "535766",
    "Max Sport 2": "535765",
    "Nova Sport 1": "6263",
    "Nova Sport 2": "7401"
}

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def get_canale_esatto_xml(date_utc, home_team, away_team):
    data_str = date_utc.strftime('%Y%m%d')
    canali_trovati = []
    
    keywords = ["inter", home_team.lower(), away_team.lower()]
    
    for nome_canale, channel_id in CANALI_EPG.items():
        url = f"https://epg.pw/api/epg.xml?lang=en&timezone=UTC&date={data_str}&channel_id={channel_id}"
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for programme in root.findall('programme'):
                    title_el = programme.find('title')
                    if title_el is not None and title_el.text:
                        t_text = title_el.text.lower()
                        if any(key in t_text for key in keywords):
                            start_str = programme.get('start')
                            if start_str:
                                try:
                                    clean_start = start_str.split(' ')[0]
                                    prog_start = datetime.strptime(clean_start, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                                    
                                    diff_seconds = (prog_start - date_utc).total_seconds()
                                    
                                    if -1200 <= diff_seconds <= 3600:
                                        if nome_canale not in canali_trovati:
                                            canali_trovati.append(nome_canale)
                                except:
                                    continue
        except Exception:
            pass
            
    return canali_trovati

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        adesso = datetime.now(timezone.utc)
        matches = data.get('matches', [])
        
        for match in matches:
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            date_str = match.get('utcDate')
            if not date_str: continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc < adesso: continue

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            canali_reali = get_canale_esatto_xml(date_utc, home, away)
            
            if not canali_reali:
                canali_reali = ["Palinsesto in aggiornamento (verrà sincronizzato a breve)"]
            
            # Salviamo direttamente l'orario UTC senza sfasamenti manuali
            all_matches.append({
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': canali_reali
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    all_matches.sort(key=lambda x: x['ora_utc'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V28 Final//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        
        # Passando direttamente l'oggetto datetime con timezone UTC,
        # icalendar scriverà correttamente il suffisso 'Z', lasciando 
        # al calendario il compito di convertirlo nell'ora locale del telefono.
        evento.add('dtstart', p['ora_utc'])
        evento.add('dtend', p['ora_utc'] + timedelta(hours=2))
        
        canali_testo = "\n".join([f"• {c}" for c in p['canali']])
        descrizione = f"Competizione: {p['competizione']}\n\nCanali TV:\n{canali_testo}"
        
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File V28 generato con successo.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
