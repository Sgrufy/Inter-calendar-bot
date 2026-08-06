import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import pytz # Assicurati di avere pytz installato: pip install pytz

# Elenco canali e configurazioni invariati...
ELENCO_CANALI = [
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4", "Eleven Sports",
    "Canal+ Sport 1", "Canal+ Sport 2", "Canal+ Sport 3", "Canal+ Sport 4", "Canal+ Sport 5", "Canal+ Sport", "Canal+",
    "Polsat Sport Premium 1", "Polsat Sport Premium 2", "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3", "Polsat Sport",
    "TVP Sport", "Eurosport 1 Poland", "Eurosport 2 Poland", "Eurosport Poland", "Eurosport",
    "Cosmote Sport 1 HD", "Cosmote Sport 2 HD", "Cosmote Sport 3 HD", "Cosmote Sport 4 HD",
    "Cosmote Sport 5 HD", "Cosmote Sport 6 HD", "Cosmote Sport 7 HD", "Cosmote Sport 8 HD",
    "Cosmote Sport 9 HD", "Cosmote Sport",
    "Max Sport 1", "Max Sport 2", "Max Sport 3", "Max Sport 4", "Max Sport",
    "Nova Sport 1", "Nova Sport 2", "Nova Sport 3", "Nova Sport 4", "Nova Sport",
    "Sky Sport Uno", "DAZN", "Amazon Prime Video", "Canale 5 HD", "TV8 HD"
]

URLS_API = [
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"
]

COMPETIZIONI_MAP = {"ita.1": "Serie A", "ita.2": "Serie B", "uefa.champions": "Champions League"}

def ottieni_prossime_partite():
    tutti_gli_eventi = []
    tz_italy = pytz.timezone('Europe/Rome')
    
    for url_api in URLS_API:
        try:
            res = requests.get(url_api, timeout=10).json()
            events = res.get('events', [])
            
            for event in events:
                name = event.get('name', '')
                if "Inter" in name or "Internazionale" in name:
                    date_str = event.get('date', '')
                    if date_str:
                        # 1. Parsing data UTC originale
                        date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        # 2. Conversione diretta in orario italiano (gestisce autonomamente ora legale/solare)
                        ora_partita = date_utc.astimezone(tz_italy)
                        
                        if ora_partita >= datetime.now(tz_italy) - timedelta(hours=3):
                            # Logica nomi squadre invariata...
                            match_nome = f"⚽ {name}" 
                            
                            tutti_gli_eventi.append({
                                'nome': match_nome,
                                'data': ora_partita,
                                'canali': [] # Aggiungi qui la logica canali se necessaria
                            })
        except Exception as e:
            print(f"Errore: {e}")
    
    return sorted(tutti_gli_eventi, key=lambda x: x['data'])[:3]

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Live')

    partite = ottieni_prossime_partite()

    for p in partite:
        evento = Event()
        evento.add('summary', p['nome'])
        # Passiamo l'oggetto datetime già corretto nel fuso orario locale
        evento.add('dtstart', p['data'])
        evento.add('dtend', p['data'] + timedelta(hours=2))
        evento.add('dtstamp', datetime.now(pytz.utc))

        descrizione = f"📺 CANALI RILEVATI:\n{p['canale'] if 'canale' in p else 'N/A'}\n\n"
        descrizione += f"⏰ ORARIO INIZIO: {p['data'].strftime('%H:%M')} (Ora Italiana)"

        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())

if __name__ == '__main__':
    genera_ics_automatico()
