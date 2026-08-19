import os
import requests
from bs4 import BeautifulSoup
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

def scansiona_elevensports(home, away):
    channels = []
    try:
        response = requests.get("https://elevensports.pl/", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all(['span', 'div', 'a'], class_=['channel', 'match-channel', 'station']):
                ch = el.text.strip()
                if "Eleven" in ch and ch not in channels:
                    channels.append(ch)
    except Exception: pass
    return channels

def scansiona_canalplus(home, away):
    channels = []
    try:
        response = requests.get("https://www.canalplus.com/", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all(['span', 'a'], class_=['channel', 'brand']):
                ch = el.text.strip()
                if "Canal+" in ch and ch not in channels:
                    channels.append(ch)
    except Exception: pass
    return channels

def scansiona_espn(home, away):
    channels = []
    try:
        response = requests.get("https://www.espn.com/soccer/team/_/id/110/inter-milan", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all(['span', 'div'], class_=['broadcast', 'network']):
                ch = el.text.strip()
                if ch and ch not in channels:
                    channels.append(f"ESPN: {ch}" if "ESPN" not in ch else ch)
    except Exception: pass
    return channels

def scansiona_teleman(home, away):
    channels = []
    try:
        response = requests.get("https://www.teleman.pl/search?q=Inter", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all(['span', 'a'], class_=['station', 'st-name']):
                ch = el.text.strip()
                if ch and ch not in channels:
                    channels.append(ch)
    except Exception: pass
    return channels

def scansiona_livesoccertv(home, away):
    channels = []
    try:
        response = requests.get("https://www.livesoccertv.com/teams/italy/inter-milan/", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for el in soup.find_all('td', class_='ext-ch'):
                ch = el.text.strip()
                if ch and ch not in channels:
                    channels.append(ch)
    except Exception: pass
    return channels

def get_canali_in_tempo_reale(home, away, competizione):
    canali = []
    
    # 1. Eleven Sports
    canali.extend(scansiona_elevensports(home, away))
    
    # 2. Canal+
    canali.extend(scansiona_canalplus(home, away))
    
    # 3. ESPN
    canali.extend(scansiona_espn(home, away))
    
    # 4. Teleman
    canali.extend(scansiona_teleman(home, away))
    
    # 5. LiveSoccer TV
    canali.extend(scansiona_livesoccertv(home, away))
    
    # Rimuovi eventuali duplicati mantenendo l'ordine
    canali_uniti = []
    for c in canali:
        if c not in canali_uniti:
            canali_uniti.append(c)
            
    # Fallback se lo scraping non trova nulla a causa dei blocchi
    if not canali_uniti:
        if "Champions" in competizione:
            canali_uniti = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: Amazon Prime Video)"]
        elif "Coppa" in competizione:
            canali_uniti = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: Mediaset Infinity)"]
        else:
            canali_uniti = ["Eleven Sports 1", "Canal+ Sport", "ESPN", "Teleman", "LiveSoccer TV (Fallback: DAZN / Sky)"]
            
    return canali_uniti[:4]

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
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': get_canali_in_tempo_reale(home, away, comp_name)
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    all_matches.sort(key=lambda x: x['ora'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V8 Live//IT')
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
    print("File V8 Live generato con successo.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
