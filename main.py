import os
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event

# Configurazione Football-Data.org
API_KEY = os.getenv("FOOTBALL_DATA_KEY")  # Nome della variabile segreta su GitHub
HEADERS = {
    'X-Auth-Token': API_KEY
}

# Competizioni su Football-Data.org: 'SA' (Serie A), 'CL' (Champions League)
# Nota: La Coppa Italia (corrispondente a coppe nazionali minori) potrebbe non essere inclusa nel piano free base di questo fornitore.
COMPETITIONS = ['SA', 'CL']
TEAM_ID = 108  # ID dell'Inter su Football-Data.org (verificabile, di solito Inter è 108)

def get_channels_for_competition(comp_name):
    comp = comp_name.lower()
    channels = [
        "Canal+", "Eleven Sports", "Polsat Sport", "TVP Sport",
        "Eurosport (PL)", "Cosmote Sport", "Max Sport", "Nova Sport"
    ]
    if "champions" in comp:
        channels.append("Amazon Prime Video")
    return channels

def fetch_next_matches():
    all_matches = []
    
    if not API_KEY:
        print("ATTENZIONE: FOOTBALL_DATA_KEY non trovata!")
        return []

    # Endpoint per le partite di una specifica squadra
    # Usiamo direttamente l'endpoint delle partite della squadra dell'Inter
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        print("Interrogazione Football-Data.org...")
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        matches = data.get('matches', [])
        for match in matches:
            competition_info = match.get('competition', {})
            comp_code = competition_info.get('code')
            
            # Filtriamo solo per le competizioni che ci interessano (es. Serie A e Champions)
            if comp_code not in COMPETITIONS:
                continue
                
            home = match.get('homeTeam', {}).get('name', 'Casa')
            away = match.get('awayTeam', {}).get('name', 'Ospite')
            name = f"{home} vs {away}"
            
            date_str = match.get('utcDate')
            if not date_str:
                continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            comp_name = competition_info.get('name', 'Competizione')
            
            all_matches.append({
                'ora': date_utc,
                'name': name,
                'competizione': comp_name,
                'canali': get_channels_for_competition(comp_name)
            })
            
    except Exception as e:
        print(f"Errore durante la richiesta a Football-Data.org: {e}")
        
    # Ordiniamo per data e prendiamo le prossime 4/10 partite
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
