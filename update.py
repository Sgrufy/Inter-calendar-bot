import os
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL-DATA_KEY") or os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

TEAM_ID = 108

def pulisci_nome(nome):
    return nome.replace("Internazionale Milano", "Inter").replace("Internazionale", "Inter")

def fetch_next_matches():
    all_matches = []
    # Richiediamo esplicitamente solo le partite programmate (status=SCHEDULED)
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        adesso = datetime.now(timezone.utc)
        matches = data.get('matches', [])
        
        for match in matches:
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            # Escludiamo eventuali date nel passato per sicurezza
            if date_utc < adesso:
                continue
                
            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            # Conversione orario per l'Italia (+2 ore in regime di ora legale)
            date_italy = date_utc + timedelta(hours=2)
            
            all_matches.append({
                'ora': date_italy,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': ["Eleven Sports 1", "Canal+ Sport", "ESPN"]
            })
            
    except Exception as e:
        print(f"Errore durante il recupero: {e}")
        
    # Ordinamento cronologico rigoroso dalla più vicina a salire
    all_matches.sort(key=lambda x: x['ora'])
    
    # Restituisce esattamente le prossime 4 partite in assoluto
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Corretto//IT')
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
