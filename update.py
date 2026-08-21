import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

COMPETITIONS = ['SA', 'CL', 'COI', 'ITC']
TEAM_ID = 108

# Dizionario canali completo (con l'aggiunta dei nuovi canali Nova Sport)
CANALI_EPG = {
    # Canali originari
    "Eleven Sports 1": "6339",
    "Eleven Sports 2": "6340",
    "Eleven Sports 3": "6338",
    "Eleven Sports 4": "6336",
    "Canal+ Sport": "67504",
    "Canal+ Sport 2": "67502",
    "Canal+ Extra": "407523",
    "Canal+ 1": "407672",
    "Polsat Sport 1": "452290",
    "Polsat Sport 2": "449589",
    "Polsat Sport 3": "449590",
    "TVP Sport": "5778",
    "Cosmote 1": "476569",
    "Cosmote 2": "476571",
    "Max Sport 1": "535766",
    "Max Sport 2": "535765",
    "Nova Sport 1": "6263",
    "Nova Sport 2": "7401",
    # Fox Sports, TNT, beIN e CBS
    "Fox Sport 2": "431621",
    "Fox Sport 2 MX": "415584",
    "Fox Sport 3 AR": "431616",
    "Fox Sport 3 MX": "415586",
    "Fox Sport 4K America": "558128",
    "Fox Sport 501 HD": "537809",
    "Fox Sport 502": "537762",
    "Fox Sport 503": "447015",
    "Fox Sport 504": "537767",
    "Fox Sport 505": "447007",
    "Fox Sport 506": "446961",
    "Fox Sport 506 HD": "560750",
    "Fox Sport 507": "537782",
    "Fox Sport HD": "431624",
    "Fox Sport More": "447025",
    "Fox Sport 1 America": "465291",
    "Fox Sport 2 HD": "465355",
    "TNT Sport 1 HD": "400477",
    "TNT Sport 10 HD": "463027",
    "TNT Sport 2 HD": "400480",
    "TNT Sport 3 HD": "400479",
    "TNT Sport 4 HD": "400478",
    "TNT Sport 5 HD": "463026",
    "TNT Sport 6 HD": "463020",
    "TNT Sport 7 HD": "463024",
    "TNT Sport 8 HD": "463025",
    "TNT Sport 9 HD": "463021",
    "TNT Sport Premium HD": "431608",
    "TNT Sports Ultimate HD": "463023",
    "beIN Sport 3 FR": "372290",
    "beIN Sport US": "407564",
    "beIN Sport HD": "369750",
    "beIN Sport 1 FR": "55773",
    "beIN Sport 1": "532981",
    "beIN Sport 2 FR": "443147",
    "beIN Sports 2 HD": "369741",
    "beIN Sport 2": "453366",
    "beIN Sport Max 9": "55983",
    "CBS Sport Golazo": "562308",
    "CBS Sports HQ": "562459",
    "CBS Sports Network": "464937",
    "CBS Sports Netw": "408622",
    # Canali Sport TV
    "Sport TV+": "405715",
    "Sport TV 7": "405669",
    "Sport TV 5": "408040",
    "Sport TV 6": "397417",
    "Sport TV 4": "397404",
    "Sport TV 3": "397419",
    "Sport TV 2": "397424",
    "Sport TV 1": "397418",
    # Altri canali
    "SS Football": "463676",
    "S Football": "450846",
    "Astro Football HD": "533442",
    "Astro Football": "399498",
    "BBC Alba": "12059",
    "BBC Alba HD 1": "486822",
    "BBC Alba HD 2": "537759",
    "Setanta Sports 1": "417364",
    "Setanta Sports 2": "417351",
    # Canali Polsat Sport Premium e Extra
    "Polsat Sport Premium 6": "452290",
    "Polsat Sport Premium 5": "449589",
    "Polsat Sport Premium 4": "449590",
    "Polsat Sport Premium 3": "408447",
    "Polsat Sport Premium 2": "7135",
    "Polsat Sport Premium 1": "7136",
    "Polsat Sport Extra": "7835",
    # Nuovi canali Nova Sport aggiunti con icona TV
    "Nova Sport 5": "35972",
    "Nova Sport 6": "392164",
    "Nova Sport 5 (Alt)": "392147",
    "Nova Sport 4": "7612",
    "Nova Sport 3": "7747"
}

# I canali esclusi da CANALI_BLU useranno l'icona della TV (📺)
CANALI_BLU = set(CANALI_EPG.keys()) - {
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Canal+ Sport", "Canal+ Sport 2", "Canal+ Extra", "Canal+ 1",
    "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3", "TVP Sport",
    "Cosmote 1", "Cosmote 2", "Max Sport 1", "Max Sport 2", "Nova Sport 1", "Nova Sport 2",
    "Polsat Sport Premium 6", "Polsat Sport Premium 5", "Polsat Sport Premium 4", 
    "Polsat Sport Premium 3", "Polsat Sport Premium 2", "Polsat Sport Premium 1", "Polsat Sport Extra",
    "Nova Sport 5", "Nova Sport 6", "Nova Sport 5 (Alt)", "Nova Sport 4", "Nova Sport 3"
}

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def controlla_singolo_canale(nome_canale, channel_id, data_str, date_utc, keywords):
    url = f"https://epg.pw/api/epg.xml?lang=en&timezone=UTC&date={data_str}&channel_id={channel_id}"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for programme in root.findall('programme'):
                title_el = programme.find('title')
                if title_el is not None and title_el.text:
                    t_text = title_el.text.lower()
                    if any(key in t_text for key in keywords):
                        start_str = programme.get('start')
                        if start_str:
                            try:
                                dt_part = start_str.split(' ')[0]
                                if len(start_str.split(' ')) > 1:
                                    offset = start_str.split(' ')[1]
                                    hours = int(offset[1:3])
                                    minutes = int(offset[3:5])
                                    sign = -1 if offset[0] == '-' else 1
                                    tz = timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
                                    prog_start = datetime.strptime(dt_part, '%Y%m%d%H%M%S').replace(tzinfo=tz)
                                else:
                                    prog_start = datetime.strptime(dt_part, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                                
                                diff_seconds = (prog_start.astimezone(timezone.utc) - date_utc).total_seconds()
                                
                                if abs(diff_seconds) <= 7200:
                                    return nome_canale
                            except:
                                continue
    except Exception:
        pass
    return None

def get_canale_esatto_xml(date_utc, home_team, away_team):
    data_str = date_utc.strftime('%Y%m%d')
    canali_trovati = []
    keywords = ["inter", home_team.lower(), away_team.lower()]
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(controlla_singolo_canale, nome, cid, data_str, date_utc, keywords): nome
            for nome, cid in CANALI_EPG.items()
        }
        
        for future in as_completed(futures):
            risultato = future.result()
            if risultato and risultato not in canali_trovati:
                canali_trovati.append(risultato)
                
    return canali_trovati

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        adesso = datetime.now(timezone.utc)
        matches = data.get('matches', [])
        
        for match in matches:
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            date_str = match.get('utcDate')
            if not date_str: continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc < adesso: continue

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            canali_reali = get_canale_esatto_xml(date_utc, home, away)
            
            if not canali_reali:
                canali_reali = ["In attesa di programmazione ufficiale ⏳"]
            
            all_matches.append({
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': canali_reali
            })
            
    except Exception as e:
        print(f"Errore: {e}")
        
    all_matches.sort(key=lambda x: x['ora_utc'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V33 Fast//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        
        evento.add('dtstart', p['ora_utc'])
        evento.add('dtend', p['ora_utc'] + timedelta(hours=2))
        
        righe_canali = []
        for c in p['canali']:
            if c in CANALI_BLU:
                righe_canali.append(f"🔵 {c}")
            elif "In attesa" in c:
                righe_canali.append(c)
            else:
                righe_canali.append(f"📺 {c}")
                
        canali_testo = "\n".join(righe_canali)
        descrizione = f"🏆 Competizione: {p['competizione']}\n\n📡 Canali TV:\n{canali_testo}"
        
        evento.add('description', descrizione)
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File V33 generato con successo.")

if __name__ == '__main__':
    matches = fetch_next_matches()
    generate_ics(matches)
