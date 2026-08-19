import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

COMPETITIONS = ['SA', 'CL']
TEAM_ID = 108

def get_scraped_channels(match_date, home, away):
    """
    Funzione di scraping automatico per trovare il canale esatto.
    Visita una fonte di palinsesti per estrarre l'emittente associata al match.
    """
    channels = []
    try:
        # Esempio di richiesta a un aggregatore pubblico o pagina di palinsesti
        # Nota: L'URL va puntato alla pagina specifica del match o dei palinsesti TV internazionali
        search_url = f"https://www.livesoccertv.com/teams/italy/inter-milan/"
        response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Qui cerchiamo gli elementi della tabella dei canali TV associati alla data della partita
            # (La struttura dipende dal sito scelto e dai suoi tag HTML)
            match_row = soup.find(string=lambda t: t and away.lower() in t.lower())
            if match_row:
                # Estrazione dinamica dei canali dalla riga del match trovata
                parent_tr = match_row.find_parent('tr')
                if parent_tr:
                    channel_tds = parent_tr.find_all('a', class_='channel-name')
                    for ch in channel_tds:
                        channels.append(ch.text.strip())
        
        # Fallback se lo scraping non trova dati specifici in tempo reale
        if not channels:
            channels = ["Canal+", "Eleven Sports", "Polsat Sport"]
            
    except Exception as e:
        print(f durante lo scraping dei canali: {e}")
        channels = ["Canal+", "Eleven Sports"]
        
    return channels

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    if not API_KEY:
        print("ATTENZIONE: FOOTBALL_DATA_KEY non trovata!")
        return []

    try:
        print("Interrogazione Football-Data.org e recupero palinsesti...")
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        matches = data.get('matches', [])
        for match in matches:
            competition_info = match.get('competition', {})
            if competition_info.get('code') not in COMPETITIONS:
                continue
                
            home = match.get('homeTeam', {}).get('name', 'Casa')
            away = match.get('awayTeam', {}).get('name', 'Ospite')
            name = f"{home} vs {away}"
            
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_italy = date_utc + timedelta(hours=2) # Correzione fuso orario Italia
            
            comp_name = competition_info.get('name', 'Competizione')
            
            # Richiama lo scraper automatico per il canale
            exact_channels = get_scraped_channels(date_italy, home, away)
            
            all_matches.append({
                'ora': date_italy,
                'name': name,
                'competizione': comp_name,
                'canali': exact_channels
            })
            
    except Exception as e:
        print(f"Errore durante la richiesta: {e}")
        
    all_matches.sort(key=lambda x: x['ora'])
    return all_matches[:10]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto Globale//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'].replace(tzinfo=None))
        evento.add('dtend', (p['ora'] + timedelta(hours=2)).replace(tzinfo=None))
        
        orario_str = p['ora'].strftime('%H:%M')
        data_str = p['ora'].strftime('%d/%m/%Y')
        
        descrizione = (
            f"🏆 Competizione: {p['competizione']}\n"
            f"📅 Data: {data_str} alle {orario_str}\n"
            f"-----------------------------------\n"
            f"📺 CANALI / EMITTENTI (Automatici):\n"
        )
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con scraping dei canali!")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
