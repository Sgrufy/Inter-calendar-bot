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

# Mappa completa di tutti i canali basata sugli ID di epg.pw
CANALI_EPG = {
    # Eleven Sports
    "Eleven Sports 1": "6340",
    "Eleven Sports 2": "6339",
    "Eleven Sports 3": "6338",
    "Eleven Sports 4": "6336",
    
    # Canal+
    "Canal+ Sport": "67504",
    "Canal+ Sport 2": "67502",
    "Canal+ Extra": "407523",
    
    # Altri canali ed eventi
    "ESPN": "5831",
    "Teleman": "5830",
    "LiveSoccer TV": "5829"
}

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def cerca_su_epg_pw(data_partita, nome_squadra):
    canali_trovati = []
    data_str = data_partita.strftime('%Y%m%d')
    
    for nome_canale, channel_id in CANALI_EPG.items():
        url = f"https://epg.pw/api/epg.xml?lang=en&timezone=RXVyb3BlL1N0b2NraG9sbQ%3D%3D&date={data_str}&channel_id={channel_id}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for programme in root.findall('programme'):
                    title_el = programme.find('title')
                    if title_el is not None and title_el.text:
                        if nome_squadra.lower() in title_el.text.lower():
                            if nome_canale not in canali_trovati:
                                canali_trovati.append(nome_canale)
        except Exception as e:
            print(f"Errore lettura EPG per {nome_canale}: {e}")
            
    return canali_trovati

def get_canali_strutturati(home, away, data_utc, competizione):
    canali = cerca_su_epg_pw(data_utc, "Inter")
    
    # Ordine di preferenza richiesto: Eleven Sports, Canal+, ESPN, Teleman, LiveSoccer TV
    ordinamento = ["Eleven Sports", "Canal+", "ESPN", "Teleman", "LiveSoccer TV"]
    
    canali_ordinati = []
    for pref in ordinamento:
        for c in canali:
            if pref.lower() in c.lower() and c not in canali_ordinati:
                canali_ordinati.append(c)
                
    # Fallback nel caso in cui l'EPG non elenchi ancora il match per una data specifica
    if not canali_ordinati:
        if "Champions" in competizione:
            canali_ordinati = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: Amazon Prime Video)"]
        elif "Coppa" in competizione:
            canali_ordinati = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: Mediaset Infinity)"]
        elif "Supercoppa" in competizione:
            canali_ordinati = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: Mediaset Infinity)"]
        else:
            canali_ordinati = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: DAZN / Sky)"]
            
    return canali_ordinati[:4]

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
            
            all_matches.append({
                'ora': date_utc + timedelta(hours=2),
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
    cal.add('prodid', '-//Calendario Inter V11 EPG Live//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'].replace(tzinfo=None))
        evento.add('dtend', (p['ora'] + timedelta(hours=2)).replace(tzinfo=None))
        descrizione = f"🏆 {p['competizione']}\n📺 CANALI:\n" + "\n".join([f"  • {c}" for c in p['canali']])
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File V11 EPG Live generato con successo.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
