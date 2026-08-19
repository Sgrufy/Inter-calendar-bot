import os
import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

COMPETITIONS = ['SA', 'CL', 'COI']
TEAM_ID = 108

def pulisci_nome(nome):
    return nome.replace("Internazionale Milano", "Inter").replace("Internazionale", "Inter")

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        oggi = datetime.now()
        # Allarghiamo a 90 giorni per assicurarci di catturare le partite disponibili
        limite_giorni = oggi + timedelta(days=90)
        
        matches = data.get('matches', [])
        print(f"Partite totali trovate dall'API: {len(matches)}")
        
        for match in matches:
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            if not (oggi <= date_utc <= limite_giorni):
                continue
                
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            date_italy = date_utc + timedelta(hours=2)
            
            all_matches.append({
                'ora': date_italy,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': ["Canal+", "Eleven Sports"]
            })
            
    except Exception as e:
        print(f"Errore durante il recupero: {e}")
        
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Test//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'].replace(tzinfo=None))
        evento.add('dtend', (p['ora'] + timedelta(hours=2)).replace(tzinfo=None))
        
        descrizione = f"🏆 Competizione: {p['competizione']}\n📺 CANALI:\n"
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print(f"File generato con successo con {len(matches)} partite.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
