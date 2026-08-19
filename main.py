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
    Estrae le squadre dalle informazioni di ESPN formattandole correttamente.
    """
    try:
        competitions = event.get('competitions', [])
        if competitions:
            competitors = competitions[0].get('competitors', [])
            if len(competitors) == 2:
                home_team = None
                away_team = None
                
                for comp in competitors:
                    name = comp.get('team', {}).get('shortDisplayName') or comp.get('team', {}).get('displayName', '')
                    if "inter" in name.lower():
                        name = "Inter"
                        
                    if comp.get('homeAway') == 'home':
                        home_team = name
                    elif comp.get('homeAway') == 'away':
                        away_team = name
                
                if home_team and away_team:
                    return f"{home_team} vs {away_team}"
    except Exception:
        pass
    
    name = event.get('name', '')
    if " at " in name:
        parts = name.split(" at ")
        if len(parts) == 2:
            team1, team2 = parts[0].strip(), parts[1].strip()
            if "inter" in team1.lower(): team1 = "Inter"
            if "inter" in team2.lower(): team2 = "Inter"
            
            if team2 == "Inter":
                return f"Inter vs {team1}"
            elif team1 == "Inter":
                return f"{team2} vs Inter"
            else:
                return f"{team2} vs {team1}"
                
    return name

def genera_ics_automatico():
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter Auto Globale//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    tz_italy = timezone(timedelta(hours=2))
    tutte_le_partite = []
    eventi_visti = set() # Per evitare duplicati

    oggi = datetime.now(tz_italy)
    fine_range = oggi + timedelta(days=20)
    date_range = f"{oggi.strftime('%Y%m%d')}-{fine_range.strftime('%Y%m%d')}"

    for url_api in URLS_API:
        url_con_date = f"{url_api}?dates={date_range}"
        try:
            res = requests.get(url_con_date, timeout=10).json()
            events = res.get('events', [])
            competizione_label = res.get('leagues', [{}])[0].get('name', 'Altro')

            for event in events:
                name = event.get('name', '')
                if "Inter" in name:
                    date_str = event.get('date', '')
                    if not date_str:
                        continue
                        
                    date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    ora_partita = date_utc.astimezone(tz_italy)
                    
                    # Evitiamo duplicati basandoci su orario esatto e nome
                    chiave_univoca = (ora_partita, name)
                    if chiave_univoca in eventi_visti:
                        continue
                    eventi_visti.add(chiave_univoca)
                    
                    if ora_partita >= datetime.now(tz_italy) - timedelta(hours=3):
                        canale_esatto = estrai_canale_specifico(event)
                        
                        if canale_esatto:
                            lista_canali = [f"{canale_esatto} (Palinsesto Ufficiale)"]
                        else:
                            lista_canali = ottieni_canali_fallback(competizione_label)

                        nome_formattato = formatta_nome_partita(event)

                        tutte_le_partite.append({
                            'ora': ora_partita,
                            'name': nome_formattato,
                            'competizione': competizione_label,
                            'canali': lista_canali
                        })
        except Exception as e:
            print(f"Errore caricamento {url_api}: {e}")

    tutte_le_partite.sort(key=lambda x: x['ora'])

    for p in tutte_le_partite:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora'])
        evento.add('dtend', p['ora'] + timedelta(hours=2))
        
        # --- LAYOUT MIGLIORATO DELLA DESCRIZIONE ---
        orario_str = p['ora'].strftime('%H:%M')
        data_str = p['ora'].strftime('%d/%m/%Y')
        
        descrizione = (
            f"🏆 Competizione: {p['competizione']}\n"
            f"📅 Data: {data_str} alle {orario_str}\n"
            f"-----------------------------------\n"
            f"📺 CANALI / EMITTENTI:\n"
        )
        for c in p['canali']:
            descrizione += f"  • {c}\n"
            
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File inter_tv.ics generato con successo!")

if __name__ == '__main__':
    genera_ics_automatico()
