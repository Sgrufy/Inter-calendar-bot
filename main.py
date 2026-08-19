import os
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

# Configurazione API
API_KEY = os.getenv("API_FOOTBALL_KEY")
API_HOST = "v3.football.api-sports.io"
TEAM_ID = 505  # ID dell'Inter

HEADERS = {
    'x-apisports-key': API_KEY
}

# Leghe: 135 (Serie A), 137 (Coppa Italia), 2 (Champions League)
LEAGUES = [135, 137, 2]

def get_channels_for_competition(comp_name):
    comp = comp_name.lower()
    channels = [
        "Canal+", "Eleven Sports", "Polsat Sport", "TVP Sport",
        "Eurosport (PL)", "Cosmote Sport", "Max Sport", "Nova Sport"
    ]
    if "coppa italia" in comp:
        channels.append("Mediaset")
    if "champions" in comp:
        channels.append("Amazon Prime Video")
    return channels

def fetch_next_matches():
    all_matches = []
    url = f"https://{API_HOST}/fixtures"
    
    # Controllo di sicurezza sulla chiave API
    if not API_KEY:
        print("ATTENZIONE: API_FOOTBALL_KEY non trovata nelle variabili d'ambiente!")
        return []

    # Anno corrente per la stagione calcistica (es. 2026)
    current_year = datetime.now().year
    # Se siamo a inizio anno solare (es. gennaio/giugno), la stagione è iniziata l'anno prima o è quella corrente
    # Per sicurezza passiamo direttamente la stagione corrente o lasciamo che l'API usi il filtro temporale 'next'
    
    for league_id in LEAGUES:
        params = {
            "team": TEAM_ID,
            "league": league_id,
            "season": 2026, # Specifica la stagione corrente
            "next": 4 
        }
        
        try:
            print(f"Interrogazione API per lega ID: {league_id}...")
            response = requests.get(url, headers=HEADERS, params=params, timeout=10)
            data = response.json()
            
            # Debug per vedere cosa risponde l'API nei log di GitHub
            print(f"Risposta API Lega {league_id}:", data)
            
            fixtures = data.get('response', [])
            for fixture in fixtures:
                fixture_info = fixture.get('fixture', {})
                teams = fixture.get('teams', {})
                league_info = fixture.get('league', {})
                
                home = teams.get('home', {}).get('name', 'Squadra Casa')
                away = teams.get('away', {}).get('name', 'Squadra Ospite')
                
                name = f"{home} vs {away}"
                date_str = fixture_info.get('date')
                if not date_str:
                    continue
                    
                date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                comp_name = league_info.get('name', 'Competizione')
                
                all_matches.append({
                    'ora': date_utc,
                    'name': name,
                    'competizione': comp_name,
                    'canali': get_channels_for_competition(comp_name)
                })
        except Exception as e:
            print(f"Errore critico durante la richiesta per la lega {league_id}: {e}")
            
    all_matches.sort(key=lambda x: x['ora'])
    return all_matches

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
        evento.add('dtstart', p['ora'])
        evento.add('dtend', p['ora'] + timedelta(hours=2))
        
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
    print("File inter_tv.ics generato e scritto con successo!")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
