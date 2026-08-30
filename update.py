import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from icalendar import Calendar, Event
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import unicodedata
import re
import gzip

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
URL_CANALI_BLU = os.getenv("URL_CANALI_BLU")
URL_SECONDA_LISTA = os.getenv("URL_SECONDA_LISTA")
URL_TERZA_LISTA = os.getenv("URL_TERZA_LISTA")

HEADERS = {
    'X-Auth-Token': API_KEY,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

COMPETITIONS = ['SA', 'CL', 'COI', 'ITC', 'CLI', 'FR1']
TEAM_ID = 108

# ==========================================
# BLACKLIST CANALI (Falsi positivi da escludere)
# ==========================================
BLACKLIST_CANALI = {
    "Focus",
    "HRT 4",
    "Das Erste",
    "CNews",
    "Court TV",
    "CNN",
    "BBC News",
    "BMT",
    "Tagesschau24",
    "W24",
    "10 HD",
    "10",
}

# ==========================================
# ID ESCLUSIVI EPG.PW (Target mirati ad alta precisione)
# ==========================================
EPG_PW_TARGET_IDS = {
    "397418": "Sport TV 1",
    "397424": "Sport TV 2",
    "397419": "Sport TV 3",
    "397404": "Sport TV 4",
    "408040": "Sport TV 5",
    "397417": "Sport TV 6",
    "405669": "Sport TV 7",
    "405715": "Sport TV +",
    "417364": "Setanta Sports 1",
    "325011": "Setanta Sports 2",
    "534228": "Setanta Sports 3",
    "400477": "TNT Sports 1",
    "400480": "TNT Sports 2",
    "400479": "TNT Sports 3",
    "400478": "TNT Sports 4",
    "562308": "CBS Sports Golazo",
    "480375": "Okko Sport",
    "563613": "Go3 Sport",
    "55898": "Arryadia",
    "381850": "Arena Sport 1",
    "381848": "Arena Sport 2",
    "381849": "Arena Sport 3",
    "540363": "Premier Sport 1",
    "540369": "Premier Sport 2",
    "465156": "Fox Deportes",
    "465291": "Fox Sports 1",
    "415586": "Fox Sports 3",
    "415584": "Fox Sports 2",
    "465214": "Fox Soccer Plus",
    "408622": "CBS Sports Network",
    "464937": "CBS Sports Network",
    "562459": "CBS Sports"
}

# I 39 canali classici fissi con la TV 📺
CANALI_TV_CLASSICI = {
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Canal+ Sport", "Canal+ Sport 2", "Canal+ Extra", "Canal+ 1",
    "Polsat Sport", "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3", "Polsat Sport Fight", "Polsat Sport Premium 1", "Polsat Sport Premium 2",
    "Nova Sports 1", "Nova Sports 2", "Nova Sports 3", "Nova Sports 4", "Nova Sports Start",
    "Cosmote Sport 1", "Cosmote Sport 2", "Cosmote Sport 3", "Cosmote Sport 4", "Cosmote Sport 5", "Cosmote Sport 6", "Cosmote Sport 7", "Cosmote Sport 8", "Cosmote Sport 9",
    "Max Sport 1", "Max Sport 2", "Max Sport 3", "Max Sport 4",
    "Eurosport 1 Poland", "Eurosport 2 Poland",
    "TVP Sport",
    "RSI LA1", "RSI LA2",
    "Rai 1", "Rai 2", "Canale 5", "Italia 1", "TV8", "Prime Video"
}

# Canali prioritari speciali con pallino arancione 🟠 (Include i nomi associati agli ID mirati)
CANALI_PRIORITARI_SPECIALI = set(EPG_PW_TARGET_IDS.values()).union({
    "Setanta Sports Eurasia", "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", 
    "beIN Sports 4", "beIN Sports 5", "beIN Sports 6", "beIN Sports 7", "beIN Sports 8", 
    "beIN Sports 9", "beIN Sports Xtra", "beIN Sports MAX", "TNT", "Fox", "Match! Arena", 
    "Match! Igra", "Okko Sport Futbol", "Okko Sport Prime", "Okko Sport Sport", "LRT Plius", 
    "MNS Sports", "Prime TV", "S Sport", "S Sport 2", "S Sport+", "Tivibu Spor", "Tivibu Spor 1", 
    "Tivibu Spor 2", "TRT Spor", "TRT 1", "beIN Sports 1 Turkey", "beIN Sports 2 Turkey", 
    "beIN Sports 3 Turkey", "Nova Sport 1", "Nova Sport 2", "Nova Sport 3", "Nova Sport 4", 
    "Nova Sport 5", "Nova Sport 6", "Sport 1", "Sport 2"
})

INFO_CANALI = {}  
PROGRAMMI_EPG = [] 
TUTTI_I_CANALI_BLU = set()
TUTTI_I_CANALI_NERI = set()
TUTTI_I_CANALI_GIALLI = set()
URLS_EPG_DINAMICI = set()

def normalizza_testo(testo):
    if not testo:
        return ""
    
    testo_pulito = re.sub(r'\b(hd|fhd|4k|uhd|sd|hevc|iptv|live|ex)\b', '', testo, flags=re.IGNORECASE)
    testo_pulito = re.sub(r'\[.*?\]|\(.*?\)', '', testo_pulito)
    
    traduzioni_estere = {
        'интер': 'inter',     
        'ιντερ': 'inter',     
        'ınter': 'inter',     
        'inter de milao': 'inter', 
        'inter milao': 'inter',    
        'milan': 'milan',
        'ювентус': 'juventus',
        'футбол': 'football',
        'матч': 'match',
        'mecz': 'match',
        'pilka nozna': 'football',
        'mac': 'match',
        'futbol': 'football',
        'agonas': 'match',
        'podosfairo': 'football'
    }
    
    testo_lower = testo_pulito.lower()
    for estero, lat in traduzioni_estere.items():
        if estero in testo_lower:
            testo_lower = testo_lower.replace(estero, lat)

    testo_lower = testo_lower.replace('_', ' ').replace('.', ' ')

    nfkd_form = unicodedata.normalize('NFKD', testo_lower)
    risultato = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return " ".join(risultato.split()).strip()

def analizza_m3u_esteso(testo_m3u, target_set):
    global URLS_EPG_DINAMICI
    current_tvg_id = None
    for line in testo_m3u.splitlines():
        line = line.strip()
        
        if line.startswith("#EXTM3U") and 'x-tvg-url="' in line:
            try:
                parte_url = line.split('x-tvg-url="')[1].split('"')[0]
                for u in parte_url.replace(',', ' ').split():
                    u_clean = u.strip()
                    if u_clean.startswith('http'):
                        URLS_EPG_DINAMICI.add(u_clean)
            except Exception:
                pass

        if line.startswith("#EXTINF:"):
            current_tvg_id = None
            if 'tvg-id="' in line:
                try:
                    part = line.split('tvg-id="')[1]
                    current_tvg_id = part.split('"')[0].strip()
                except Exception:
                    pass
        
        if line.startswith("#EXTINF:") and "," in line:
            c_name = line.split(",")[-1].strip()
            if c_name and c_name not in BLACKLIST_CANALI:
                target_set.add(c_name)
                if current_tvg_id:
                    INFO_CANALI[c_name] = {"id": current_tvg_id}
                    INFO_CANALI[normalizza_testo(c_name)] = {"id": current_tvg_id}
        elif "," in line and not line.startswith("#") and not line.startswith("http"):
            parti = line.split(",", 1)
            c_name = parti[0].strip()
            if c_name and len(c_name) < 50 and c_name not in BLACKLIST_CANALI:
                target_set.add(c_name)

def carica_canali_esterni():
    global TUTTI_I_CANALI_BLU, TUTTI_I_CANALI_NERI, TUTTI_I_CANALI_GIALLI, URLS_EPG_DINAMICI
    playlist = [
        ("BLU", URL_CANALI_BLU, TUTTI_I_CANALI_BLU),
        ("NERA", URL_SECONDA_LISTA, TUTTI_I_CANALI_NERI),
        ("GIALLA", URL_TERZA_LISTA, TUTTI_I_CANALI_GIALLI)
    ]
    
    print("\n--- DIAGNOSTICA CARICAMENTO LISTE IPTV ---")
    for nome_lista, url, target_set in playlist:
        if url:
            try:
                print(f"Scaricamento lista {nome_lista} da URL...")
                response = requests.get(url, headers=HEADERS, timeout=20)
                print(f"Stato risposta {nome_lista}: HTTP {response.status_code}")
                if response.status_code == 200:
                    if "#EXTM3U" in response.text or "#EXTINF" in response.text:
                        analizza_m3u_esteso(response.text, target_set)
                    else:
                        for line in response.text.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and not line.startswith("http"):
                                c_name = line.split(",", 1)[0].strip() if "," in line else line
                                if c_name and len(c_name) < 50 and c_name not in BLACKLIST_CANALI:
                                    target_set.add(c_name)
                    print(f"Canali trovati e caricati in {nome_lista}: {len(target_set)}")
                else:
                    print(f"Errore HTTP per la lista {nome_lista}: {response.status_code}")
            except Exception as e:
                print(f"Eccezione durante il download della lista {nome_lista}: {e}")
        else:
            print(f"URL per la lista {nome_lista} non configurato (vuoto).")
            
    # Assicura che tutti i canali mirati siano presenti in blu e nel database INFO_CANALI
    for cid, cname in EPG_PW_TARGET_IDS.items():
        TUTTI_I_CANALI_BLU.add(cname)
        INFO_CANALI[cname] = {"id": cid}
        INFO_CANALI[normalizza_testo(cname)] = {"id": cid}

    for nc in CANALI_PRIORITARI_SPECIALI:
        if nc not in BLACKLIST_CANALI:
            TUTTI_I_CANALI_BLU.add(nc)
            if nc not in INFO_CANALI:
                INFO_CANALI[nc] = {"id": nc.lower().replace(" ", ".")}

    lista_paesi_standard = ['it', 'fr', 'es', 'pt', 'pl', 'us', 'ar', 'za', 'ae', 'sa', 'qa', 'eg', 'ch', 'cz', 'hr', 'rs', 'hu', 'sk', 'al', 'tr', 'nl', 'ru', 'ua', 'el', 'ge', 'md', 'kz', 'az', 'ie', 'my', 'bg']

    for p in lista_paesi_standard:
        URLS_EPG_DINAMICI.add(f"https://epg.lat/files/{p}.xml.gz")
        URLS_EPG_DINAMICI.add(f"https://epgshare01.online/epgshare01/epg_ripper_{p.upper()}1.xml.gz")

    open_epg_mappatura = {
        'it': 'italy1', 'fr': 'france', 'es': 'spain', 'pt': 'portugal', 'pl': 'poland', 
        'us': 'usa', 'ar': 'argentina', 'za': 'southafrica', 'ae': 'uae', 'sa': 'saudiarabia', 
        'qa': 'qatar', 'eg': 'egypt', 'ch': 'switzerland', 'cz': 'czech', 'hr': 'bosnia', 
        'rs': 'serbia', 'hu': 'hungary', 'sk': 'slovakia', 'al': 'albania', 'tr': 'turkey', 
        'nl': 'netherlands', 'ru': 'russia', 'ua': 'ukraine', 'el': 'greece', 'ge': 'georgia', 
        'md': 'moldova', 'kz': 'kazakhstan', 'az': 'azerbaijan', 'ie': 'ireland', 'my': 'malaysia1', 'bg': 'bulgaria1'
    }
    for p in lista_paesi_standard:
        nome_open = open_epg_mappatura.get(p, p)
        URLS_EPG_DINAMICI.add(f"https://www.open-epg.com/files/{nome_open}.xml.gz")

    URLS_EPG_DINAMICI.add("https://epg.pw/xmltv/epg.xml.gz")

    print(f"Trovati {len(URLS_EPG_DINAMICI)} URL EPG compressi (.gz) totali con copertura estesa.")

def carica_id_da_github():
    global INFO_CANALI
    url_api = "https://iptv-org.github.io/api/channels.json"
    tutti_i_nomi = list(TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI).union(CANALI_TV_CLASSICI).union(CANALI_PRIORITARI_SPECIALI))
    
    print(f"\nTotale canali unici da mappare: {len(tutti_i_nomi)}")
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            data = response.json()
            db_canali = {normalizza_testo(c.get('name')): {"id": c.get('id')} for c in data if c.get('name')}
            
            mappati = 0
            for nome in tutti_i_nomi:
                if nome in BLACKLIST_CANALI:
                    continue
                # Se il canale ha già un ID mirato in epg.pw, non sovrascriverlo con GitHub
                if nome in EPG_PW_TARGET_IDS.values():
                    continue
                if nome not in INFO_CANALI:
                    nome_norm = normalizza_testo(nome)
                    if nome_norm in db_canali:
                        INFO_CANALI[nome] = db_canali[nome_norm]
                        mappati += 1
                    else:
                        INFO_CANALI[nome] = {"id": nome.replace(" ", "")}
            print(f"Canali mappati tramite database GitHub: {mappati}")
    except Exception as e:
        print(f"Errore connessione a GitHub per gli ID canali: {e}")

def analizza_epg_stream(content_bytes, valid_channel_ids):
    programmi_locali = []
    parole_da_scartare = [
        "journal", "news", "jt ", "le 20h", "informazione", "cronaca", "edition", "bulletin", 
        "notiziario", "tg", "meteo", "weather", "documentary", "documentario", "film", "serie", 
        "show", "talk", "magazine", "tribunal", "court", "process", "новости", "wiadomosci",
        "haber", "deltio", "interview"
    ]
    
    try:
        channel_id_to_name = {}
        for event, elem in ET.iterparse(io.BytesIO(content_bytes), events=("end",)):
            if elem.tag == 'channel':
                ch_id = elem.get('id')
                if ch_id:
                    display_name_el = elem.find('display-name')
                    if display_name_el is not None and display_name_el.text:
                        ch_name = display_name_el.text.strip()
                        channel_id_to_name[ch_id] = ch_name
                        valid_channel_ids.add(ch_id)
                        valid_channel_ids.add(ch_name)
                        valid_channel_ids.add(normalizza_testo(ch_name))
            elem.clear()

        context = ET.iterparse(io.BytesIO(content_bytes), events=("end",))
        for event, elem in context:
            if elem.tag == 'programme':
                ch = elem.get('channel')
                ch_lookup = channel_id_to_name.get(ch, ch)
                
                ch_lower = ch_lookup.lower()
                if any(b in ch_lower for b in ["news", "cnews", "court", "cnn", "bbc", "bmt", "tagesschau", "w24"]):
                    elem.clear()
                    continue
                
                # Accetta se l'ID è esplicitamente nei target mirati di epg.pw o valido
                if (ch in EPG_PW_TARGET_IDS or
                    ch in valid_channel_ids or 
                    ch_lookup in valid_channel_ids or 
                    normalizza_testo(ch_lookup) in valid_channel_ids or 
                    ch.isdigit()):
                    
                    # Se il canale è mappato in epg.pw con ID specifico, correggiamo il nome al volo
                    if ch in EPG_PW_TARGET_IDS:
                        ch_lookup = EPG_PW_TARGET_IDS[ch]
                    
                    title_el = elem.find('title')
                    title_text = title_el.text if (title_el is not None and title_el.text) else ""
                    title_norm = normalizza_testo(title_text)
                    
                    is_scartato = any(scarto in title_norm for scarto in parole_da_scartare)
                    
                    start_str = elem.get('start')
                    if title_text and start_str and not is_scartato:
                        programmi_locali.append({
                            'channel': ch,
                            'channel_name': ch_lookup,
                            'title': title_norm,
                            'start': start_str
                        })
                elem.clear()
    except Exception:
        pass
    return programmi_locali

def scarica_e_processa_paese(paese, valid_channel_ids):
    url_epg = f"https://iptv-epg.org/files/epg-{paese}.xml"
    try:
        res = requests.get(url_epg, headers=HEADERS, timeout=30)
        if res.status_code == 200:
            progs = analizza_epg_stream(res.content, valid_channel_ids)
            return progs
    except Exception:
        pass
    return []

def scarica_e_processa_gz_dinamico(url_gz, valid_channel_ids):
    try:
        res = requests.get(url_gz, headers=HEADERS, timeout=30)
        if res.status_code == 200:
            xml_content = gzip.decompress(res.content) if res.content[:2] == b'\x1f\x8b' else res.content
            progs = analizza_epg_stream(xml_content, valid_channel_ids)
            return progs
    except Exception:
        pass
    return []

def scarica_epg_mirato_per_data(data_partita_str, valid_channel_ids):
    """Scarica flussi mirati specifici per ciascuno degli ID epg.pw forniti per quella data"""
    programmi_mirati = []
    print(f"\n--- DOWNLOAD MIRATO EPG.PW PER DATA: {data_partita_str} ---")
    
    for ch_id, ch_name in EPG_PW_TARGET_IDS.items():
        url_mirato = f"https://epg.pw/api/epg.xml?lang=en&timezone=RXVyb3BlL1N0b2NraG9sbQ%3D%3D&date={data_partita_str}&channel_id={ch_id}"
        try:
            res = requests.get(url_mirato, headers=HEADERS, timeout=15)
            if res.status_code == 200 and len(res.content) > 200:
                progs = analizza_epg_stream(res.content, valid_channel_ids)
                if progs:
                    for p in progs:
                        p['channel_name'] = ch_name # Forza il nome pulito ufficiale
                    programmi_mirati.extend(progs)
                    print(f"[MIRATO OK] {ch_name} (ID: {ch_id}): trovati {len(progs)} programmi")
        except Exception as e:
            pass
            
    return programmi_mirati

def scarica_tutti_gli_epg(data_partita_str=None):
    global PROGRAMMI_EPG
    paesi = ['it', 'fr', 'es', 'pt', 'pl', 'us', 'ar', 'za', 'ae', 'sa', 'qa', 'eg', 'ch', 'cz', 'hr', 'rs', 'hu', 'sk', 'al', 'tr', 'nl', 'ru', 'ua', 'el', 'ge', 'md', 'kz', 'az', 'ie', 'my', 'bg']
    
    valid_channel_ids = set(EPG_PW_TARGET_IDS.keys())
    for nome, info in INFO_CANALI.items():
        if nome not in BLACKLIST_CANALI:
            if info.get("id"):
                valid_channel_ids.add(str(info.get("id")))
            valid_channel_ids.add(normalizza_testo(nome))
            valid_channel_ids.add(nome)
    
    print(f"\n--- DOWNLOAD E PARSING EPG GLOBALE ---")
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(scarica_e_processa_paese, p, valid_channel_ids): f"paese_{p}" for p in paesi}
        for idx, url_gz in enumerate(URLS_EPG_DINAMICI):
            futures[executor.submit(scarica_e_processa_gz_dinamico, url_gz, valid_channel_ids)] = f"gz_{idx}"

        for future in as_completed(futures):
            risultati = future.result()
            if risultati:
                PROGRAMMI_EPG.extend(risultati)
                
    # Aggiunge i dati mirati puntuali per la data della partita se fornita
    if data_partita_str:
        progs_mirati = scarica_epg_mirato_per_data(data_partita_str, valid_channel_ids)
        if progs_mirati:
            PROGRAMMI_EPG.extend(progs_mirati)
                
    print(f"Totale programmi salvati in memoria: {len(PROGRAMMI_EPG)}")

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def cerca_canali_per_partita(date_utc, home_team, away_team):
    canali_trovati = []
    
    # Estrae la data in formato YYYYMMDD per il download mirato EPG.PW
    data_str_epg = date_utc.strftime('%Y%m%d')
    scarica_tutti_gli_epg(data_str_epg)

    if not PROGRAMMI_EPG:
        return canali_trovati
        
    keywords = [normalizza_testo("inter"), normalizza_testo(home_team), normalizza_testo(away_team)]
    canali_da_evitare = ["cnews", "court tv", "news", "info", "tg", "bmt", "cnn", "bbc", "w24", "tagesschau"]

    id_to_names = {}
    for nome_canale, info in INFO_CANALI.items():
        if nome_canale in BLACKLIST_CANALI:
            continue
            
        nome_lower = nome_canale.lower()
        if any(evitare in nome_lower for evitare in canali_da_evitare):
            continue
            
        ch_id = str(info.get("id"))
        keys_to_map = [ch_id, normalizza_testo(nome_canale), nome_canale]
        
        for k in keys_to_map:
            if k:
                if k not in id_to_names:
                    id_to_names[k] = []
                if nome_canale not in id_to_names[k]:
                    id_to_names[k].append(nome_canale)

    print(f"\n--- DIAGNOSTICA CERCA CANALI PER: {home_team} vs {away_team} ({date_utc}) ---")
    match_trovati_nei_log = 0

    for prog in PROGRAMMI_EPG:
        ch_id = str(prog['channel'])
        ch_name = prog.get('channel_name', ch_id)
        title = prog['title']
        
        ha_keyword = any(key in title for key in keywords)
        
        if ha_keyword:
            start_str = prog['start']
            if start_str:
                dt_part = start_str.split(' ')[0]
                try:
                    prog_start = datetime.strptime(dt_part[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                    diff_secondi = abs((prog_start - date_utc).total_seconds())
                    
                    if diff_secondi <= 10800:
                        match_trovati_nei_log += 1
                        print(f"[TROVATO NELL'EPG] Canale ID: '{ch_id}' (Nome: '{ch_name}') | Titolo: '{title}' | Orario diff: {diff_secondi}s")

                        # Se il canale è nei nostri target ID mirati, prendiamolo subito
                        if ch_id in EPG_PW_TARGET_IDS:
                            canale_ufficiale = EPG_PW_TARGET_IDS[ch_id]
                            if canale_ufficiale not in canali_trovati and canale_ufficiale not in BLACKLIST_CANALI:
                                canali_trovati.append(canale_ufficiale)

                        matches_keys = [ch_id, ch_name, normalizza_testo(ch_id), normalizza_testo(ch_name)]
                        for mk in matches_keys:
                            if mk in id_to_names:
                                for nome_canale in id_to_names[mk]:
                                    if nome_canale not in canali_trovati and nome_canale not in BLACKLIST_CANALI:
                                        canali_trovati.append(nome_canale)
                        
                        for nc in TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI).union(CANALI_TV_CLASSICI).union(CANALI_PRIORITARI_SPECIALI):
                            if nc in BLACKLIST_CANALI:
                                continue
                            if normalizza_testo(nc) == normalizza_testo(ch_name) or normalizza_testo(nc) in normalizza_testo(ch_name):
                                if nc not in canali_trovati:
                                    canali_trovati.append(nc)

                except ValueError:
                    continue
                    
    print(f"Totale match EPG temporali trovati per questa partita: {match_trovati_nei_log}")
    print(f"Canali mappati e associati con successo: {canali_trovati}\n")
    return canali_trovati

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        adesso = datetime.now(timezone.utc)
        
        for match in data.get('matches', []):
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue
                
            date_str = match.get('utcDate')
            if not date_str: continue
                
            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc < adesso: continue

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))
            comp_name = match.get('competition', {}).get('name', 'Competizione')
            
            # Svuota i programmi precedenti per ogni partita per ricaricare i target mirati della data specifica
            global PROGRAMMI_EPG
            PROGRAMMI_EPG = []
            
            canali_reali = cerca_canali_per_partita(date_utc, home, away)
            if not canali_reali:
                canali_reali = ["In attesa di programmazione ufficiale ⏳"]
            
            all_matches.append({
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'canali': canali_reali
            })
            
    except Exception as e:
        print(f"Errore API partite: {e}")
        
    all_matches.sort(key=lambda x: x['ora_utc'])
    return all_matches[:4]

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V85 EPG FullOpen//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora_utc'])
        evento.add('dtend', p['ora_utc'] + timedelta(hours=2))
        
        righe_canali = []
        
        for c in p['canali']:
            if any(black.lower() in c.lower() for black in BLACKLIST_CANALI):
                continue
                
            if "In attesa" in c:
                righe_canali.append(c)
            elif c in CANALI_TV_CLASSICI or "prime" in c.lower():
                righe_canali.append("🎬 Prime Video" if "prime" in c.lower() else f"📺 {c}")
            elif c in CANALI_PRIORITARI_SPECIALI or c in EPG_PW_TARGET_IDS.values():
                righe_canali.append(f"🟠 {c}")
            elif c in TUTTI_I_CANALI_BLU:
                righe_canali.append(f"🔵 {c}")
            elif c in TUTTI_I_CANALI_NERI:
                righe_canali.append(f"⚫ {c}")
            elif c in TUTTI_I_CANALI_GIALLI:
                righe_canali.append(f"🟡 {c}")
            else:
                righe_canali.append(f"🟠 {c}") # Fallback sicuro per i canali mirati
                
        righe_canali = list(dict.fromkeys(righe_canali))
        if not righe_canali:
            righe_canali = ["In attesa di programmazione ufficiale ⏳"]
            
        canali_testo = "\n".join(righe_canali)
        evento.add('description', f"🏆 Competizione: {p['competizione']}\n\n📡 Canali TV:\n{canali_testo}")
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb5') if False else open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File ICS generato con successo.")

if __name__ == '__main__':
    carica_canali_esterni()
    carica_id_da_github()
    matches = fetch_next_matches()
    generate_ics(matches)
