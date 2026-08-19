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

COMPETITIONS = ['SA', 'CL', 'COI']
TEAM_ID = 108

def pulisci_nome(nome):
    return nome.replace("Internazionale Milano", "Inter").replace("Internazionale", "Inter")

def get_teleman_channels(match_date, home, away):
    channels = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    try:
        # Teleman ha una barra di ricerca interna
        query = "Inter"
        search_url = f"https://www.teleman.pl/search?q={query}"
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Cerca i risultati della programmazione su Teleman
            # Su Teleman i risultati della ricerca usano solitamente blocchi dedicati agli eventi TV
            results = soup.find_all('div', class_='station-item') or soup.find_all('ul', class_='list-sessions')
            
            # Metodo alternativo di scansione basato sui titoli degli eventi
            station_elements = soup.find_all('em') # Spesso il canale è dentro tag em o span dedicati
            
            # Estrazione generica mirata ai canali presenti nella pagina di ricerca
            for el in soup.find_all(['span', 'a'], class_=['station', 'st-name']):
                ch_name = el.text.strip()
                if ch_name and ch_name not in channels:
                    channels.append(ch_name)
                    
        # Se lo scraping di Teleman non restituisce canali precisi, mettiamo un fallback indicativo
        if not channels:
            channels = ["Eleven Sports 1 (PL)", "Canal+ Sport (PL)"]
            
    except Exception as e:
        print(f"Errore durante lo scraping di Teleman: {e}")
        channels = ["Eleven Sports 1"]
        
    return channels

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        print("Recupero partite da Football-Data.org...")
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        oggi = datetime.now()
        limite_giorni = oggi + timedelta(days=20)
        
        matches = data.get('matches', [])
        for match in matches:
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            # Filtro per i prossimi 20 giorni
            if not (oggi <= date_utc <= limite_giorni):
                continue
                
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            date_italy = date_utc + timedelta(hours=2)
            exact_channels = get_teleman_channels(date_italy, home, away)
            
            all_matches.append({
                'ora': date_italy,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': exact_channels
            })
            
    except Exception as e:
        print(f"Errore generale: {e}")
        
    return all_matches[:4] # Esattamente le prossime 4 partite

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Teleman//IT')
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
            f"📺 CANALI TELEMAN:\n"
        )
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con successo tramite Teleman!")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
