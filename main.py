import os
import requests
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event

# URL delle API ESPN per Serie A, Coppa Italia e Champions League
URLS_API = [
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.coppa/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"
]

def ottieni_canali_emittenti(competizione):
    """
    Associa i canali di trasmissione in base alla competizione,
    includendo l'intera gamma di opzioni polacche, Mediaset e Amazon Prime.
    """
    comp_lower = competizione.lower()
    canali = []
    
    if "serie a" in comp_lower or "ita.1" in comp_lower:
        canali.extend([
            "Eleven Sports 1-4 (PL)",
            "Eleven Sports Online (PL)",
            "Polsat Sport (PL)",
            "DAZN / Sky Italia"
        ])
    elif "champions league" in comp_lower or "uefa.champions" in comp_lower:
        canali.extend([
            "Canal+ Extra / Online (PL)",
            "TVP Sport (PL)",
            "Amazon Prime Video (Italia)",
            "Mediaset / Canale 5 (Italia)",
            "Cosmote Sport (Grecia)",
            "Max Sport (Bulgaria)",
            "Nova Sport (CZ/SK)"
        ])
    elif "coppa italia" in comp_lower or "ita.coppa" in comp_lower:
        canali.extend([
            "Mediaset / Canale 5 / Italia 1 (Italia)",
            "Polsat Sport (PL)",
            "Eleven Sports (PL)"
        ])
    else:
        canali.extend([
            "Canal+ (PL)",
            "Eleven Sports (PL)",
            "Polsat Sport (PL)",
            "TVP Sport (PL)",
            "Eurosport (PL)",
            "Cosmote Sport",
            "Max Sport",
            "Nova Sport",
            "Amazon Prime Video",
            "Mediaset"
        ])
        
    return canali

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto Globale//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    tz_italy = timezone(timedelta(hours=2))
    
    for url_api in URLS_API:
        try:
            res = requests.get(url_api, timeout=10).json()
            events = res.get('events', [])
            competizione_label = res.get('leagues', [{}])[0].get('name', 'Altro')

            for event in events:
                name = event.get('name', '')
                if "Inter" in name:
                    date_str = event.get('date', '')
                    date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    ora_partita = date_utc.astimezone(tz_italy)
                    
                    if ora_partita >= datetime.now(tz_italy) - timedelta(hours=3):
                        evento = Event()
                        evento.add('summary', f"⚽ {name}")
                        evento.add('dtstart', ora_partita)
                        evento.add('dtend', ora_partita + timedelta(hours=2))
                        
                        canali = ottieni_canali_emittenti(competizione_label)
                        descrizione = f"📺 CANALI DI TRASMISSIONE:\n" + "\n".join([f"• {c}" for c in canali])
                        evento.add('description', descrizione)
                        cal.add_component(evento)
        except Exception as e:
            print(f"Errore caricamento {url_api}: {e}")

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics aggiornato con tutti i canali richiesti!")

if __name__ == '__main__':
    genera_ics_automatico()
