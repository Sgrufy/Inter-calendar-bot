import os
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

COMPETITIONS = ['SA', 'CL', 'COI'] # Serie A, Champions League, Coppa Italia
TEAM_ID = 108

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def get_canali_ordinati(competizione):
    # Rispetta rigorosamente la tua sequenza desiderata: Eleven, Canal+, Teleman, ESPN
    if "Champions" in competizione:
        return ["Eleven Sports", "Canal+", "Teleman", "ESPN", "Amazon Prime Video"]
    elif "Coppa" in competizione:
        return ["Eleven Sports", "Canal+", "Teleman", "ESPN", "Mediaset Infinity"]
    else:
        return ["Eleven Sports", "Canal+", "Teleman", "ESPN"]

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
            if not date_str: 
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc < adesso: 
                continue
                
            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            all_matches.append({
                'ora': date_utc + timedelta(hours=2),
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': get_canali_ordinati(comp_name)
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    all_matches.sort(key=lambda x: x['ora'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    # Identificativo V6 per forzare il riconoscimento dell'aggiornamento
    cal.add('prodid', '-//Calendario Inter V6//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'].replace(tzinfo=None))
        evento.add('dtend', (p['ora'] + timedelta(hours=2)).replace(tzinfo=None))
        
        descrizione = f"🏆 {p['competizione']}\n📺 CANALI:\n"
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File V6 generato con successo.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
