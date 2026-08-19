import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

TEAM_ID = 108

def pulisci_nome(nome):
    return nome.replace("Internazionale Milano", "Inter").replace("Internazionale", "Inter")

def scansiona_elevensports_pl(home, away):
    channels = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'pl-PL,pl;q=0.9',
        }
        url = "https://elevensports.pl/"
        response = requests.get(url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all(['span', 'div', 'a'], class_=['channel', 'match-channel', 'station']):
                ch = el.text.strip()
                if "Eleven" in ch and ch not in channels:
                    channels.append(ch)
    except Exception:
        pass
    return channels

def scansiona_teleman(home, away):
    channels = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'pl-PL,pl;q=0.9',
        }
        url = "https://www.teleman.pl/search?q=Inter"
        response = requests.get(url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all(['span', 'a'], class_=['station', 'st-name']):
                ch = el.text.strip()
                if ch and ch not in channels:
                    channels.append(ch)
    except Exception:
        pass
    return channels

def scansiona_livesoccertv(home, away):
    channels = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        url = "https://www.livesoccertv.com/teams/italy/inter-milan/"
        response = requests.get(url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for a in soup.find_all('a', class_='channel-name'):
                ch = a.text.strip()
                if ch and ch not in channels:
                    channels.append(ch)
    except Exception:
        pass
    return channels

def get_canali_multipli(home, away):
    # 1. Prima precedenza: Eleven Sports Polonia
    canali = scansiona_elevensports_pl(home, away)
    
    # 2. Seconda precedenza: Teleman
    if not canali:
        canali = scansiona_teleman(home, away)
        
    # 3. Terza precedenza: Live Soccer TV
    if not canali:
        canali = scansiona_livesoccertv(home, away)
        
    # 4. Quarta precedenza: ESPN prima del fallback generico finale
    if not canali:
        canali = ["ESPN", "Canal+ Sport", "Eleven Sports 1"]
        
    return canali[:3]

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        matches = data.get('matches', [])
        for match in matches:
            if match.get('status') != 'SCHEDULED':
                continue
                
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            date_italy = date_utc + timedelta(hours=2)
            canali = get_canali_multipli(home, away)
            
            all_matches.append({
                'ora': date_italy,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': canali
            })
            
    except Exception as e:
        print(f"Errore durante il recupero: {e}")
        
    all_matches.sort(key=lambda x: x['ora'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Priorita//IT')
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
