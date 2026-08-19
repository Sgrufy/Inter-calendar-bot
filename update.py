import os
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY
}

# Includiamo anche la Coppa Italia se supportata o lasciamo le competizioni attive
COMPETITIONS = ['SA', 'CL']
TEAM_ID = 108  # ID dell'Inter su Football-Data.org

def get_exact_channels(comp_name):
    comp = comp_name.lower()
    # La tua lista esatta di canali internazionali richiesti
    channels = [
        "Canal+",
        "Eleven Sports",
        "Polsat Sport",
        "TVP Sport",
        "Eurosport (PL)",
        "Cosmote Sport",
        "Max Sport",
        "Nova Sport"
    ]
    
    # Aggiunte specifiche per l'Italia richieste
    if "champions" in comp:
        channels.append("Amazon Prime Video")
    elif "coppa italia" in comp:
        channels.append("Mediaset")
    else:
        channels.append("DAZN / Sky Sport")
        
    return channels

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    if not API_KEY:
        print("ATTENZIONE: FOOTBALL_DATA_KEY non trovata!")
        return []

    try:
        print("Interrogazione Football-Data.org...")
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        matches = data.get('matches', [])
        for match in matches:
            competition_info = match.get('competition', {})
            comp_code = competition_info.get('code')
            
            if comp_code not in COMPETITIONS:
                continue
                
            home = match.get('homeTeam', {}).get('name', 'Casa')
            away = match.get('awayTeam', {}).get('name', 'Ospite')
            name = f"{home} vs {away}"
            
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            # Orario UTC dall'API
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            # Correzione fuso orario per l'Italia (+2 ore in regime di ora legale estiva CEST)
            date_italy = date_utc + timedelta(hours=2)
            
            comp_name = competition_info.get('name', 'Competizione')
            
            all_matches.append({
                'ora': date_italy,
                'name': name,
                'competizione': comp_name,
                'canali': get_exact_channels(comp_name)
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

    if not matches:
        print("Nessuna partita trovata da inserire nel calendario!")

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        # Rimuoviamo il fuso orario UTC esplicito per fare in modo che il calendario legga l'ora dritta
        evento.add('dtstart', p['ora'].replace(tzinfo=None))
        evento.add('dtend', (p['ora'] + timedelta(hours=2)).replace(tzinfo=None))
        
        orario_str = p['ora'].strftime('%H:%M')
        data_str = p['ora'].strftime('%d/%m/%Y')
        
        descrizione = (
            f"🏆 Competizione: {p['competizione']}\n"
            f"📅 Data: {data_str} alle {orario_str}\n"
            f"-----------------------------------\n"
            f"📺 CANALI / EMITTENTI:\n"
        )
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con successo!")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
