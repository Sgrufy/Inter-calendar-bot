import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event

# Elenco completo dei canali monitorati
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

COMPETIZIONI_MAP = {
    "ita.1": "Serie A",
    "ita.2": "Serie B",
    "uefa.champions": "Champions League"
}

def cerca_tutti_i_canali_teleman():
    headers = {'User-Agent': 'Mozilla/5.0'}
    canali_trovati = []
    try:
        res = requests.get("https://www.teleman.pl/szukaj?q=Inter", headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            testo = soup.get_text()
            for canale in ELENCO_CANALI:
                if re.search(r'\b' + re.escape(canale) + r'\b', testo, re.IGNORECASE) and canale not in canali_trovati:
                    canali_trovati.append(canale)
    except: pass
    return canali_trovati

def ottieni_prossime_partite():
    tutti_gli_eventi = []
    for url_api in URLS_API:
        try:
            res = requests.get(url_api, timeout=10).json()
            events = res.get('events', [])
            
            competizione_nome = ""
            for key, comp_label in COMPETIZIONI_MAP.items():
                if key in url_api:
                    competizione_nome = comp_label
                    break

            for event in events:
                name = event.get('name', '')
                if "Inter" in name or "Internazionale" in name:
                    date_str = event.get('date', '')
                    if date_str:
                        date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        ora_partita = date_utc.astimezone() + timedelta(hours=2)
                        
                        if ora_partita >= datetime.now().astimezone() - timedelta(hours=3):
                            if " at " in name:
                                squadre = name.split(" at ")
                                avversaria = squadre[0] if "Inter" in squadre[1] else squadre[1]
                                match_nome = f"⚽ Inter - {avversaria}"
                            else:
                                match_nome = f"⚽ {name}"
                            
                            if competizione_nome:
                                match_nome += f" ({competizione_nome})"
                            
                            tutti_i_canali = []
                            competitions = event.get('competitions', [])
                            if competitions:
                                broadcasts = competitions[0].get('broadcasts', [])
                                for b in broadcasts:
                                    nome_b = b.get('name')
                                    if nome_b:
                                        etichetta_espn = f"{nome_b} (ESPN)"
                                        if etichetta_espn not in tutti_i_canali:
                                            tutti_i_canali.append(etichetta_espn)

                            tutti_gli_eventi.append({
                                'nome': match_nome,
                                'data': ora_partita,
                                'canali': tutti_i_canali
                            })
        except Exception as e:
            print(f"Errore orario API ({url_api}): {e}")

    tutti_gli_eventi = sorted(tutti_gli_eventi, key=lambda x: x['data'])
    canali_teleman = cerca_tutti_i_canali_teleman()
    prossime_tre = tutti_gli_eventi[:3]

    risultati_finali = []
    for index, p in enumerate(prossime_tre):
        canali_partita = p['canali'].copy()
        
        if index == 0:
            for c in canali_teleman:
                etichetta_teleman = f"{c} (Teleman)"
                if etichetta_teleman not in canali_partita:
                    canali_partita.append(etichetta_teleman)

        if canali_partita:
            canale_str = "\n".join([f"• {c}" for c in canali_partita])
        else:
            canale_str = "• Non ancora disponibile"

        risultati_finali.append({
            'nome': p['nome'],
            'data': p['data'],
            'canale': canale_str
        })

    return risultati_finali

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Live')

    partite = ottieni_prossime_partite()

    if not partite:
        print("Nessuna partita futura trovata.")
        return

    for p in partite:
        evento = Event()
        evento.add('summary', p['nome'])
        evento.add('dtstart', p['data'])
        evento.add('dtend', p['data'] + timedelta(hours=2))
        evento.add('dtstamp', datetime.now().astimezone())

        ora_inizio_testo = p['data'].strftime('%H:%M')

        descrizione = f"📺 CANALI RILEVATI:\n"
        descrizione += f"{p['canale']}\n\n"
        descrizione += f"⏰ ORARIO INIZIO: {ora_inizio_testo} (Ora Italiana)"

        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())

if __name__ == '__main__':
    genera_ics_automatico()
