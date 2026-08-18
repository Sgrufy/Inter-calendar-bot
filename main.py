import os
import requests
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event

# CONFIGURAZIONE API-FOOTBALL
API_KEY = os.environ.get('API_KEY')
HOST = "v3.football.api-sports.io" 
TEAM_ID = 505  # ID dell'Inter su API-Football

HEADERS = {
    'x-apisports-key': API_KEY,
}

def ottieni_canali_internazionali_e_italiani(competizione):
    """
    Assegna i canali italiani e internazionali (DAZN, Sky, Amazon Prime, 
    Mediaset, Canal+, Polsat Sport, TVP Sport, Eurosport, Cosmote Sport, Max Sport, Nova Sport)
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
    elif "champions league" in comp_lower or "ucl" in comp_lower:
        return [
            "Sky Sport / NOW",
            "Amazon Prime Video (Miglior match mercoledì)",
            "Canal+ (Francia / Internazionale)",
            "Polsat Sport (Polonia)",
            "TVP Sport (Polonia)",
            "Eurosport (Internazionale)",
            "Cosmote Sport (Grecia)"
        ]
    elif "coppa italia" in comp_lower or "supercoppa" in comp_lower:
        return [
            "Mediaset (Canale 5 / Italia 1 / Mediaset Infinity)",
            "Polsat Sport (Polonia)"
        ]
    else:
        return [
            "DAZN / Sky Sport",
            "Canal+ (Internazionale)",
            "Polsat Sport",
            "Cosmote Sport"
        ]

def main():
    if not API_KEY:
        print("ATTENZIONE: API_KEY non trovata nelle variabili d'ambiente!")
        return

    oggi = datetime.now(timezone.utc)
    fine_range = oggi + timedelta(days=60) # Aumentato a 60 giorni per sicurezza

    url = f"https://{HOST}/fixtures"
    querystring = {
        "team": str(TEAM_ID),
        "from": oggi.strftime("%Y-%m-%d"),
        "to": fine_range.strftime("%Y-%m-%d")
    }

    print(f"Interrogazione API per il team {TEAM_ID} dal {querystring['from']} al {querystring['to']}...")

    try:
        response = requests.get(url, headers=HEADERS, params=querystring)
        print(f"Stato risposta HTTP: {response.status_code}")
        
        data = response.json()
        matches = data.get("response", [])
        print(f"Partite trovate dall'API: {len(matches)}")

    except Exception as e:
        print(f"Errore durante la chiamata API: {e}")
        matches = []

    # Creazione del calendario .ics
    cal = Calendar()
    cal.add('prodid', '//Calendario Inter Auto Globale//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    # Limita alle prossime 4 partite
    for match in matches[:4]:
        fixt = match.get("fixture", {})
        league = match.get("league", {})
        teams = match.get("teams", {})

        data_str = fixt.get("date")
        if not data_str:
            continue

        dt_inizio = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        dt_fine = dt_inizio + timedelta(hours=2)

        avversario = teams.get("away", {}).get("name") if teams.get("home", {}).get("id") == TEAM_ID else teams.get("home", {}).get("name")
        casa_trasferta = "Inter - " + avversario if teams.get("home", {}).get("id") == TEAM_ID else avversario + " - Inter"
        competizione_nome = league.get("name", "Partita Inter")

        canali = ottieni_canali_internazionali_e_italiani(competizione_nome)
        canali_str = "\n".join([f"- {c}" for c in canali])

        event = Event()
        event.add('summary', f"⚽ {casa_trasferta} ({competizione_nome})")
        event.add('dtstart', dt_inizio)
        event.add('dtend', dt_fine)
        event.add('description', f"📺 CANALI / EMITTENTI (ITA & MONDO):\n{canali_str}")
        
        cal.add_component(event)

    # Salvataggio del file
    with open("inter_tv.ics", "wb") as f:
        f.write(cal.to_ical())
    
    print("File inter_tv.ics generato con successo.")

if __name__ == "__main__":
    main()
