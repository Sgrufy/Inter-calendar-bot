import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event

# Mappa dei canali di Teleman con i relativi slug URL per le pagine dei palinsesti
TELEMAN_CANALI_SLUG = {
    "Eleven Sports 1": "Eleven-Sports-1",
    "Eleven Sports 2": "Eleven-Sports-2",
    "Eleven Sports 3": "Eleven-Sports-3",
    "Eleven Sports 4": "Eleven-Sports-4",
    "Eleven Sports": "Eleven-Sports",
    "Canal+ Sport 1": "Canal-Plus-Sport",
    "Canal+ Sport 2": "Canal-Plus-Sport-2",
    "TVP Sport": "TVP-Sport",
    "Eurosport 1 Poland": "Eurosport-1",
    "Eurosport 2 Poland": "Eurosport-2",
}

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

def cerca_canale_teleman_per_partita(data_partita, avversaria):
    """
    Controlla i palinsesti dei canali polacchi su Teleman cercando 
    riferimenti all'Inter, all'avversaria o alla Serie A nei blocchi dei programmi.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    canali_trovati = []
    
    data_str = data_partita.strftime('%Y-%m-%d')
    avversaria_clean = avversaria.lower().strip()
    
    for nome_canale, slug in TELEMAN_CANALI_SLUG.items():
        url = f"https://www.teleman.pl/stacja/{slug}?date={data_str}"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Cerca in tutti i blocchi testuali e tag rilevanti della pagina
                elementi_programmi = soup.find_all(['div', 'li', 'td', 'span', 'a'])
                
                match_trovato = False
                for el in elementi_programmi:
                    testo_el = el.get_text().lower()
                    # Condizione allargata per intercettare "Inter", "Mediolan" o "Liga włoska" insieme all'avversaria
                    if "inter" in testo_el or "mediolan" in testo_el:
                        if avversaria_clean in testo_el or "liga włoska" in testo_el:
                            match_trovato = True
                            break
                
                if match_trovato:
                    if nome_canale not in canali_trovati:
                        canali_trovati.append(nome_canale)
        except Exception as e:
            continue
            
    return canali_trovati

def ottieni_prossime_partite():
    tutti_gli_eventi = []
    tz_italy = timezone(timedelta(hours=2))
    
    oggi = datetime.now(tz_italy)
    fine_range = oggi + timedelta(days=14)
    date_range = f"{oggi.strftime('%Y%m%d')}-{fine_range.strftime('%Y%m%d')}"
    
    for url_api in URLS_API:
        url_con_date = f"{url_api}?dates={date_range}"
        try:
            res = requests.get(url_con_date, timeout=10).json()
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
                        ora_partita = date_utc.astimezone(tz_italy)
                        
                        if ora_partita >= datetime.now(tz_italy) - timedelta(hours=3):
                            if " at " in name:
                                squadre = name.split(" at ")
                                avversaria = squadre[0] if "Inter" in squadre[1] else squadre[1]
                                match_nome = f"⚽ Inter - {avversaria}"
                            else:
                                avversaria = name.replace("Inter", "").replace("FC", "").strip()
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
                                'avversaria': avversaria,
                                'data': ora_partita,
                                'canali': tutti_i_canali
                            })
        except Exception as e:
            print(f"Errore orario API ({url_api}): {e}")

    tutti_gli_eventi = sorted(tutti_gli_eventi, key=lambda x: x['data'])
    prossime_tre = tutti_gli_eventi[:3]

    risultati_finali = []
    for p in prossime_tre:
        canali_partita = p['canali'].copy()
        
        canali_teleman = cerca_canale_teleman_per_partita(p['data'], p['avversaria'])
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
        
        data_utc = p['data'].astimezone(timezone.utc)
        
        evento.add('dtstart', data_utc)
        evento.add('dtend', data_utc + timedelta(hours=2))
        evento.add('dtstamp', datetime.now(timezone.utc))

        ora_inizio_testo = p['data'].strftime('%H:%M')

        descrizione = f"📺 CANALI IN DIRETTA:\n"
        descrizione += f"{p['canale']}\n\n"
        descrizione += f"⏰ Inizio match: {ora_inizio_testo}"

        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con successo!")

if __name__ == '__main__':
    genera_ics_automatico()
