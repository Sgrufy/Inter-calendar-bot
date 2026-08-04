import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from icalendar import Calendar, Event

ELENCO_CANALI = [
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Canal+ Sport 1", "Canal+ Sport 2", "Canal+ Sport 3", "Canal+ Sport 4", "Canal+ Sport 5",
    "Polsat Sport Premium 1", "Polsat Sport Premium 2", "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3",
    "TVP Sport", "Sky Sport Uno", "DAZN", "Amazon Prime Video"
]

def cerca_canale_reale_sul_palinsesto():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    canale_estratto = None
    search_url = "https://www.teleman.pl/szukaj?q=Inter"
    try:
        res = requests.get(search_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            testo_pagina = soup.get_text()
            for canale in ELENCO_CANALI:
                pattern = r'\b' + re.escape(canale) + r'\b'
                if re.search(pattern, testo_pagina, re.IGNORECASE):
                    canale_estratto = f"{canale} (Palinsesto Reale)"
                    break
    except Exception as e:
        print(f"Errore scraping: {e}")

    return canale_estratto

def ottieni_partita_dinamica():
    url_api = "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard"
    match_nome = "⚽ Inter - Match"
    ora_partita = datetime.now()
    try:
        res = requests.get(url_api, timeout=10).json()
        events = res.get('events', [])
        for event in events:
            name = event.get('name', '')
            if "Inter" in name or "Internazionale" in name:
                match_nome = f"⚽ {name}"
                date_str = event.get('date', '')
                if date_str:
                    date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    ora_partita = date_utc.astimezone()
                break
    except Exception as e:
        print(f"Errore orario API: {e}")

    canale_reale = cerca_canale_reale_sul_palinsesto()
    if not canale_reale:
        canale_reale = "Verifica Palinsesto in corso (Eleven Sports / Polsat / Canal+)"

    return match_nome, ora_partita, canale_reale

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Live')

    titolo, data_ora, canale = ottieni_partita_dinamica()

    evento = Event()
    evento.add('summary', titolo)
    evento.add('dtstart', data_ora)
    evento.add('dtend', data_ora.replace(hour=(data_ora.hour + 2) % 24))
    evento.add('dtstamp', datetime.now())

    descrizione = f"📺 CANALE RILEVATO DA PALINSESTO REALE:\n"
    descrizione += f"🔥 DIRECT TV: {canale}\n"
    descrizione += f"⏰ ORARIO INIZIO: {data_ora.strftime('%H:%M')} (Ora Italiana)\n"

    evento.add('description', descrizione)
    cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())

if __name__ == '__main__':
    genera_ics_automatico()
