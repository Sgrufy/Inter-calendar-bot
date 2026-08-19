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

COMPETITIONS = ['SA', 'CL']
TEAM_ID = 108

def get_scraped_channels(home, away):
    channels = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        search_url = "https://www.livesoccertv.com/teams/italy/inter-milan/"
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Cerca le righe della tabella dei match
            match_elements = soup.find_all('tr')
            
            for tr in match_elements:
                if away.lower() in tr.text.lower() or home.lower() in tr.text.lower():
                    # Cerca i tag dei canali
                    channel_tags = tr.find_all('a', class_='channel-name')
                    for ch in channel_tags:
                        channel_text = ch.text.strip()
                        # Filtro per i tuoi network di interesse
                        if any(c in channel_text for c in ['Canal+', 'Eleven', 'Polsat', 'TVP', 'Eurosport', 'Cosmote', 'Max', 'Nova']):
                            if channel_text not in channels:
                                channels.append(channel_text)
                    if channels: break
        
        if not channels:
            channels = ["Canal+", "Eleven Sports", "Polsat Sport"]
            
    except Exception as e:
        print(f"Errore durante lo scraping di LiveSoccerTV: {e}")
        channels = ["Canal+", "Eleven Sports"]
        
    return channels

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        print("Recupero partite da Football-Data.org...")
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        matches = data.get('matches', [])
        for match in matches:
            competition_info = match.get('competition', {})
            if competition_info.get('code') not in COMPETITIONS:
                continue
                
            home = match.get('homeTeam', {}).get('name', 'Casa')
            away = match.get('awayTeam', {}).get('name', 'Ospite')
            
            date_str = match.get('utcDate')
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_italy = date_utc + timedelta(hours=2)
            
            comp_name = competition_info.get('name', 'Competizione')
            exact_channels = get_scraped_channels(home, away)
            
            all_matches.append({
                'ora': date_italy,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': exact_channels
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    return all_matches[:10]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto//IT')
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
    print("File inter_tv.ics generato.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
