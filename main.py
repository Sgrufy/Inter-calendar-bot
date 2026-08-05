import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event

# Elenco completo dei canali monitorati (Polonia, Internazionali e Streaming)
ELENCO_CANALI = [
    # Eleven Sports
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Eleven Sports",
    # Canal+ Sport
    "Canal+ Sport 1", "Canal+ Sport 2", "Canal+ Sport 3", "Canal+ Sport 4", "Canal+ Sport 5",
    "Canal+ Sport", "Canal+",
    # Polsat Sport
    "Polsat Sport Premium 1", "Polsat Sport Premium 2", "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3",
    "Polsat Sport",
    # TVP Sport
    "TVP Sport",
    # Eurosport Poland
    "Eurosport 1 Poland", "Eurosport 2 Poland", "Eurosport Poland", "Eurosport",
    # Cosmote Sport
    "Cosmote Sport 1 HD", "Cosmote Sport 2 HD", "Cosmote Sport 3 HD", "Cosmote Sport 4 HD",
    "Cosmote Sport 5 HD", "Cosmote Sport 6 HD", "Cosmote Sport 7 HD", "Cosmote Sport 8 HD",
    "Cosmote Sport 9 HD", "Cosmote Sport",
    # Max Sport
    "Max Sport 1", "Max Sport 2", "Max Sport 3", "Max Sport 4", "Max Sport",
    # Nova Sport
    "Nova Sport 1", "Nova Sport 2", "Nova Sport 3", "Nova Sport 4", "Nova Sport",
    # Altri principali
    "Sky Sport Uno", "DAZN", "Amazon Prime Video"
]

# Elenco delle competizioni da controllare tramite ESPN (Serie A, Coppa Italia, Champions League)
URLS_API = [
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.2/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard"
]

def cerca_tutti_i_canali_teleman():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    canali_trovati = []
    search_url = "https://www.teleman.pl/szukaj?q=Inter"
    try:
        res = requests.get(search_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            testo_pagina = soup.get_text()
            for canale in ELENCO_CANALI:
                pattern = r'\b' + re.escape(canale) + r'\b'
                if re.search(pattern, testo_pagina, re.IGNORECASE) and canale not in canali_trovati:
                    canali_trovati.append(canale)
    except Exception as e:
        print(f"Errore scraping Teleman: {e}")

    return canali_trovati

def ottieni_partita_dinamica():
    match_nome = "⚽ Inter - Match"
    ora_partita = datetime.now().astimezone()
    tutti_i_canali = []
    partita_trovata = False

    for url_api in URLS_API:
        if partita_trovata:
            break
        try:
            res = requests.get(url_api, timeout=10).json()
            events = res.get('events', [])
            for event in events:
                name = event.get('name', '')
                if "Inter" in name or "Internazionale" in name:
                    # Formattazione titolo all'italiana (es. Inter - Monza)
                    if " at " in name:
                        squadre = name.split(" at ")
                        match_nome = f"⚽ Inter - {squadre[0]}" if "Inter" in squadre[1] else f"⚽ {name}"
                    else:
                        match_nome = f"⚽ {name}"
                    
                    date_str = event.get('date', '')
                    if date_str:
                        date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        ora_partita = date_utc.astimezone()
                    
                    # Raccoglie TUTTI i canali disponibili da ESPN
                    competitions = event.get('competitions', [])
                    if competitions:
                        broadcasts = competitions[0].get('broadcasts', [])
                        for b in broadcasts:
                            nome_b = b.get('name')
                            if nome_b:
                                etichetta_espn = f"{nome_b} (ESPN)"
                                if etichetta_espn not in tutti_i_canali:
                                    tutti_i_canali.append(etichetta_espn)

                    partita_trovata = True
                    break
        except Exception as e:
            print(f"Errore orario API ({url_api}): {e}")

    # Raccoglie anche TUTTI i canali trovati su Teleman
    canali_teleman = cerca_tutti_i_canali_teleman()
    for c in canali_teleman:
        etichetta_teleman = f"{c} (Teleman)"
        if etichetta_teleman not in tutti_i_canali:
            tutti_i_canali.append(etichetta_teleman)

    # Gestione finale dell'output testuale dei canali
    if tutti_i_canali:
        canale_trovato = ", ".join(tutti_i_canali)
    else:
        canale_trovato = "Verifica Palinsesto in corso (Nessun canale rilevato)"

    return match_nome, ora_partita, canale_trovato

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Live')

    titolo, data_ora, canale = ottieni_partita_dinamica()

    evento = Event()
    evento.add('summary', titolo)
    evento.add('dtstart', data_ora)
    evento.add('dtend', data_ora + timedelta(hours=2))
    evento.add('dtstamp', datetime.now().astimezone())

    # Correzione dell'orario nella descrizione per mostrare l'ora italiana corretta
    ora_italiana_testo = data_ora + timedelta(hours=2)

    descrizione = f"📺 CANALI RILEVATI:\n"
    descrizione += f"🔥 DIRECT TV: {canale}\n"
    descrizione += f"⏰ ORARIO INIZIO: {ora_italiana_testo.strftime('%H:%M')} (Ora Italiana)\n"

    evento.add('description', descrizione)
    cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())

if __name__ == '__main__':
    genera_ics_automatico()
