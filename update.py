import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Aggiunto 'COI' per Coppa Italia
COMPETITIONS = ['SA', 'CL', 'COI']
TEAM_ID = 108

def pulisci_nome(nome):
    return nome.replace("Internazionale Milano", "Inter").replace("Internazionale", "Inter")

def get_scraped_channels(home, away):
    # ... (la funzione resta uguale a prima per lo scraping)
    # [Mantieni qui il codice precedente per get_scraped_channels]
    return ["Canal+", "Eleven Sports", "Polsat Sport"] # Fallback semplificato

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        oggi = datetime.now()
        limite_giorni = oggi + timedelta(days=20)
        
        matches = data.get('matches', [])
        for match in matches:
            date_str = match.get('utcDate')
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            # Filtra solo prossimi 20 giorni
            if not (oggi <= date_utc <= limite_giorni):
                continue
            
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            # Applica pulizia nome
            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            
            all_matches.append({
                'ora': date_utc + timedelta(hours=2),
                'name': f"{home} vs {away}",
                'competizione': match.get('competition', {}).get('name', 'Competizione'),
                'canali': get_scraped_channels(home, away)
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    return all_matches[:4] # Limita a sole 4 partite

def generate_ics(matches):
    # ... (la funzione resta uguale, usa solo i dati passati da fetch_next_matches)
    # [Mantieni qui il codice precedente per generate_ics]
    pass

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
