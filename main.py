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

def estrai_canale_specifico(event):
    """
    Cerca di estrarre il canale esatto dai dati di broadcast dell'evento ESPN.
    Se non è ancora disponibile, restituisce None.
    """
    try:
        broadcasts = event.get('broadcasts', [])
        for b in broadcasts:
            names = b.get('names', [])
            if names:
                return ", ".join(names)
    except Exception:
        pass
    return None

def ottieni_canali_fallback(competizione):
    """
    Elenco di fallback se il palinsesto esatto non è ancora online.
    """
    comp_lower = competizione.lower()
    if "serie a" in comp_lower or "ita.1" in comp_lower:
        return [
            "Eleven Sports 1 (PL)", "Eleven Sports 2 (PL)", 
            "Eleven Sports 3 (PL)", "Eleven Sports 4 (PL)", 
            "Eleven Sports Online (PL)"
        ]
    elif "champions league" in comp_lower or "uefa.champions" in comp_lower:
        return [
            "Canal+ Extra 1 (PL)", "Canal+ Extra 2 (PL)", 
            "Canal+ Extra 3 (PL)", "Canal+ Online (PL)", 
            "TVP Sport (PL)", "Amazon Prime Video", "Mediaset"
        ]
    elif "coppa italia" in comp_lower or "ita.coppa" in comp_lower:
        return ["Polsat Sport (PL)", "Mediaset / Canale 5"]
    
    return ["Canal+", "Eleven Sports", "Polsat Sport", "TVP Sport"]

def formatta_nome_partita(event):
    """
    Estrae le squadre dalle informazioni di ESPN assicurandosi che:
    - Se l'Inter è in casa -> Inter vs [Avversario]
    - Se l'Inter è in trasferta -> [Avversario] vs Inter
    """
    try:
        competitions = event.get('competitions', [])
        if competitions:
            competitors = competitions[0].get('competitors', [])
            if len(competitors) == 2:
                home_team = ""
                away_team = ""
                
                for comp in competitors:
                    team_name = comp.get('team', {}).get('displayName', '')
                    if comp.get('homeAway') == 'home':
                        home_team = team_name
                    elif comp.get('homeAway') == 'away':
                        away_team = team_name
                
                if home_team and away_team:
                    # Garantisce sempre il formato Casa vs Trasferta
                    return f"{home_team} vs {away_team}"
    except Exception:
        pass
    
    # Gestione di sicurezza nel caso i dati dettagliati non siano disponibili
    name = event.get('name', '')
    if " at " in name:
        parts = name.split(" at ")
        if len(parts) == 2:
            # ESPN usa solitamente "Away at Home"
            return f"{parts[1]} vs {parts[0]}"
            
    return name

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto Globale//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    tz_italy = timezone(timedelta(hours=2))
    tutte_le_partite = []

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
                        canale_esatto = estrai_canale_specifico(event)
                        
                        if canale_esatto:
                            lista_canali = [f"{canale_esatto} (Palinsesto Ufficiale)"]
                        else:
                            lista_canali = ottieni_canali_fallback(competizione_label)

                        # Formattazione corretta Casa vs Trasferta
                        nome_formattato = formatta_nome_partita(event)

                        tutte_le_partite.append({
                            'ora': ora_partita,
                            'name': nome_formattato,
                            'canali': lista_canali
                        })
        except Exception as e:
            print(f"Errore caricamento {url_api}: {e}")

    tutte_le_partite.sort(key=lambda x: x['ora'])
    partite_da_inserire = tutte_le_partite[:3]

    for p in partite_da_inserire:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'])
        evento.add('dtend', p['ora'] + timedelta(hours=2))
        
        descrizione = f"📺 CANALE DI TRASMISSIONE:\n" + "\n".join([f"• {c}" for c in p['canali']])
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con successo!")

if __name__ == '__main__':
    genera_ics_automatico()
