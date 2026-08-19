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

COMPETITIONS = ['SA', 'CL', 'COI', 'ITC'] # Serie A, Champions League, Coppa Italia, Supercoppa Italiana
TEAM_ID = 108

# Mappa completa di TUTTI i canali
CANALI_EPG = {
    "Eleven Sports 1": "6340",
    "Eleven Sports 2": "6339",
    "Eleven Sports 3": "6338",
    "Eleven Sports 4": "6336",
    "Canal+ Sport": "67504",
    "Canal+ Sport 2": "67502",
    "Canal+ Extra": "407523",
    "Canal+ 1": "407672",
    "Polsat Sport 1": "452290",
    "Polsat Sport 2": "449589",
    "Polsat Sport 3": "449590",
    "Polsat Sport Extra 1": "408447",
    "Polsat Sport Extra 2": "7135",
    "Polsat Sport Extra 3": "7136",
    "Polsat Sport Extra 4": "7221",
    "Polsat Sport Extra 5": "6268",
    "Polsat Sport Extra 6": "7835",
    "Polsat Sport Extra 7": "6003",
    "Polsat Sport Extra 8": "535972",
    "TVP Sport": "5778",
    "Nova": "548829",
    "Cosmote 1": "476569",
    "Cosmote 2": "476571",
    "Cosmote 3": "476563",
    "Cosmote 4": "476565",
    "Cosmote 5": "476557",
    "Cosmote 6": "476555",
    "Cosmote 7": "476553",
    "Cosmote 8": "476559",
    "Cosmote 9": "476562",
    "Max Sport 1": "535766",
    "Max Sport 2": "535765",
    "Max Sport 3": "409256",
    "Max Sport 4": "409257",
    "Max Sport 5": "535764",
    "Max Sport 6": "535763",
    "Nova Sport 1": "6263",
    "Nova Sport 2": "7401",
    "Nova Sport 3": "7747",
    "Nova Sport 4": "7612",
    "Nova Sport Extra 1": "392147",
    "Nova Sport Extra 2": "392164",
    "Nova Sport Extra 3": "535972",
    "ESPN": "5831",
    "Teleman": "5830"
}

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def get_canali_strutturati(home, away, data_utc, competizione):
    canali_trovati = []
    data_str = data_utc.strftime('%Y%m%d')
    
    ordinamento = ["Eleven Sports", "Canal+", "Polsat Sport", "TVP Sport", "Cosmote", "Max Sport", "Nova Sport", "Nova", "ESPN", "Teleman"]
    
    for pref in ordinamento:
        for nome_canale, channel_id in CANALI_EPG.items():
            if pref.lower() in nome_canale.lower() and nome_canale not in canali_trovati:
                url = f"https://epg.pw/api/epg.xml?lang=en&timezone=RXVyb3BlL1N0b2NraG9sbQ%3D%3D&date={data_str}&channel_id={channel_id}"
                try:
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        root = ET.fromstring(response.content)
                        for programme in root.findall('programme'):
                            title_el = programme.find('title')
                            if title_el is not None and title_el.text:
                                if "inter" in title_el.text.lower():
                                    if nome_canale not in canali_trovati:
                                        canali_trovati.append(nome_canale)
                                        break
                except Exception:
                    pass
                
                if len(canali_trovati) >= 6:
                    break
        if len(canali_trovati) >= 6:
            break
                
    if not canali_trovati:
        if "Champions" in competizione:
            canali_trovati = ["Eleven Sports 1", "Canal+ Sport", "Polsat Sport 1", "TVP Sport", "Cosmote 1", "Max Sport 1 (Fallback: Amazon Prime Video)"]
        elif "Coppa" in competizione:
            canali_trovati = ["Eleven Sports 1", "Canal+ Sport", "Polsat Sport 1", "TVP Sport", "Cosmote 1", "Max Sport 1 (Fallback: Mediaset Infinity)"]
        elif "Supercoppa" in competizione:
            canali_trovati = ["Eleven Sports 1", "Canal+ Sport", "Polsat Sport 1", "TVP Sport", "Cosmote 1", "Max Sport 1 (Fallback: Mediaset Infinity)"]
        else:
            canali_trovati = ["Eleven Sports 1", "Canal+ Sport", "Polsat Sport 1", "TVP Sport", "Cosmote 1", "Max Sport 1 (Fallback: DAZN / Sky)"]
            
    return canali_trovati[:6]

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
                
            is_dst = date_utc.month in [4, 5, 6, 7, 8, 9, 10]
            offset_ore = 2 if is_dst else 1
            ora_locale = date_utc + timedelta(hours=offset_ore)

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            all_matches.append({
                'ora': ora_locale,
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': get_canali_strutturati(home, away, date_utc, comp_name)
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    all_matches.sort(key=lambda x: x['ora'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V19 Clean UI//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'].replace(tzinfo=None))
        evento.add('dtend', (p['ora'] + timedelta(hours=2)).replace(tzinfo=None))
        
        canali_testo = "\n".join([f"• {c}" for c in p['canali']])
        descrizione = f"Competizione: {p['competizione']}\n\nCanali TV:\n{canali_testo}"
        
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File V19 Clean UI generato con successo.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
