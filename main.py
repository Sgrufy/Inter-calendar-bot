import os
import re
import requests
a_ics_automatico()
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
            competizione = next((v for k, v in COMPETIZIONI_MAP.items() if k in url_api), "")
            for event in res.get('events', []):
                if "Inter" in event.get('name', ''):
                    date_str = event.get('date', '')
                    if date_str:
                        # Correzione fuso orario: leggiamo UTC e aggiungiamo 2 ore per l'ora legale italiana
                        date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        ora_partita = date_utc + timedelta(hours=2)
                        
                        if ora_partita >= datetime.now().astimezone() - timedelta(hours=3):
                            match_nome = f"⚽ {event.get('name', '')} ({competizione})"
                            tutti_i_canali = [f"{b.get('name')} (ESPN)" for b in event.get('competitions', [{}])[0].get('broadcasts', [])]
                            
                            tutti_gli_eventi.append({
                                'nome': match_nome, 
                                'data': ora_partita.replace(tzinfo=None), 
                                'canali': tutti_i_canali
                            })
        except: continue

    tutti_gli_eventi.sort(key=lambda x: x['data'])
    canali_teleman = cerca_tutti_i_canali_teleman()
    prossime_tre = tutti_gli_eventi[:3]

    risultati = []
    for index, p in enumerate(prossime_tre):
        canali = list(set(p['canali']))
        if index == 0:
            for c in canali_teleman:
                label = f"{c} (Teleman)"
                if label not in canali: canali.append(label)
        
        risultati.append({
            'nome': p['nome'],
            'data': p['data'],
            'canale': "\n".join([f"• {c}" for c in canali]) if canali else "• Non ancora disponibile"
        })
    return risultati

def genera_ics_automatico():
    cal = Calendar()
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Live')

    for p in ottieni_prossime_partite():
        evento = Event()
        evento.add('summary', p['nome'])
        dt_start = p['data']
        evento.add('dtstart', dt_start)
        evento.add('dtend', dt_start + timedelta(hours=2))
        evento.add('dtstamp', datetime.now().replace(tzinfo=None))
        evento.add('description', f"📺 CANALI RILEVATI:\n{p['canale']}\n\n⏰ INIZIO: {dt_start.strftime('%d/%m %H:%M')}")
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())

if __name__ == '__main__':
    genera_ics_automatico()
