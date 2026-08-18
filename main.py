import os
import requests
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event

API_KEY = os.environ.get('API_KEY')
HOST = "v3.football.api-sports.io"
TEAM_ID = 505

HEADERS = {
    'x-apisports-key': API_KEY,
}

def ottieni_canali_internazionali_e_italiani(competizione):
    """
    Assegna i canali italiani e internazionali (inclusi Canal+, Eleven Sports, 
    Polsat Sport, TVP Sport, Eurosport, Cosmote Sport, Max Sport, Nova Sport).
    """
    comp_lower = competizione.lower()
    
    if "serie a" in comp_lower:
        return [
            "DAZN", 
            "Sky Sport / NOW", 
            "Eleven Sports (Internazionale)", 
            "Cosmote Sport (Grecia)", 
            "Max Sport (Bulgaria)", 
            "Nova Sport (Rep. Ceca/Grecia)"
        ]
        
    elif "champions league" in comp_lower:
        return [
            "Amazon Prime Video (Miglior match mercoledì)", 
            "Sky Sport / NOW", 
            "Canal+ Extra / Canal+ Online (Polonia)", 
            "TVP Sport (Polonia)", 
            "Polsat Sport (Polonia)",
            "Cosmote Sport (Grecia)", 
            "Max Sport (Bulgaria)", 
            "Eurosport (Selezionati in Europa)"
        ]
        
    elif "coppa italia" in comp_lower or "supercoppa" in comp_lower:
        return [
            "Mediaset (Canale 5 / Italia 1 / Mediaset Infinity)", 
            "Polsat Sport (Polonia)"
        ]
    
    return [
        "DAZN", "Sky Sport", "Amazon Prime Video", "Mediaset", 
        "Canal+", "Eleven Sports", "Polsat Sport", "TVP Sport", 
        "Cosmote Sport", "Max Sport", "Nova Sport"
    ]

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto Globale//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    tz_italy = timezone(timedelta(hours=2))
    oggi = datetime.now(tz_italy)
    fine_range = oggi + timedelta(days=20)

    url = f"https://{HOST}/fixtures"
    querystring = {
        "team": str(TEAM_ID),
        "from": oggi.strftime("%Y-%m-%d"),
        "to": fine_range.strftime("%Y-%m-%d")
    }

    tutte_le_partite = []

    try:
        response = requests.get(url, headers=HEADERS, params=querystring, timeout=10)
        data = response.json()
        matches = data.get('response', [])

        for match in matches:
            fixture = match.get('fixture', {})
            league = match.get('league', {})
            teams = match.get('teams', {})

            date_str = fixture.get('date')
            if not date_str:
                continue

            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            ora_partita = date_utc.astimezone(tz_italy)

            if ora_partita >= oggi - timedelta(hours=3):
                home_name = teams.get('home', {}).get('name', 'Casa')
                away_name = teams.get('away', {}).get('name', 'Ospiti')
                
                if "Inter" in home_name: home_name = "Inter"
                if "Inter" in away_name: away_name = "Inter"
                
                nome_formattato = f"{home_name} vs {away_name}"
                competizione_label = league.get('name', 'Competizione Calcistica')

                # Inserimento dei canali globali ed europei richiesti
                lista_canali = ottieni_canali_internazionali_e_italiani(competizione_label)

                tutte_le_partite.append({
                    'ora': ora_partita,
                    'name': nome_formattato,
                    'competizione': competizione_label,
                    'canali': lista_canali
                })

    except Exception as e:
        print(f"Errore durante la chiamata ad API-Football: {e}")

    tutte_le_partite.sort(key=lambda x: x['ora'])
    partite_da_salvare = tutte_le_partite[:4]

    for p in partite_da_salvare:
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
            f"📺 CANALI / EMITTENTI (ITA & MONDO):\n"
        )
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con successo con i canali internazionali!")

if __name__ == '__main__':
    genera_ics_automatico()
