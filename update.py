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
# ID ESCLUSIVI EPG.PW - CANALI TV (📺)
# ==========================================
EPG_PW_TV_IDS = {
    "5778": "TVP Sport",
    "535763": "Max Sport 4",
    "535764": "Max Sport 3",
    "409257": "Max Sport 2",
    "409256": "Max Sport 1",
    "476562": "Cosmote Sport 9",
    "476559": "Cosmote Sport 8",
    "476553": "Cosmote Sport 7",
    "476555": "Cosmote Sport 6",
    "476557": "Cosmote Sport 5",
    "476565": "Cosmote Sport 4",
    "476563": "Cosmote Sport 3",
    "476571": "Cosmote Sport 2",
    "476569": "Cosmote Sport 1",
    "392164": "Nova Sport 6",
    "392147": "Nova Sport 5",
    "7612": "Nova Sport 4",
    "7747": "Nova Sport 3",
    "7401": "Nova Sport 2",
    "6263": "Nova Sport 1",
    "452290": "Polsat Sport Premium 6",
    "449589": "Polsat Sport Premium 5",
    "449590": "Polsat Sport Premium 4",
    "408447": "Polsat Sport Premium 3",
    "7135": "Polsat Sport Premium 2",
    "7136": "Polsat Sport Premium 1",
    "7835": "Polsat Sport Extra",
    "6003": "Polsat Sport",
    "535982": "Diema Sport",
    "535981": "Diema Sport 2",
    "535980": "Diema Sport 3"
}

# ==========================================
# ID ESCLUSIVI EPG.PW - CANALI ARANCIONI (🟠)
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
    "325010": "Setanta Sports 1 Eurasia",
    "325011": "Setanta Sports+ Eurasia",
    "62227": "Setanta Sports 1",
    "534194": "Setanta Sports 1",
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

CANALI_TV_CLASSICI = set(EPG_PW_TV_IDS.values()).union({
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Canal+ Sport", "Canal+ Sport 2", "Canal+ Extra", "Canal+ 1",
    "Polsat Sport", "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3", "Polsat Sport Fight", 
    "Nova Sports 1", "Nova Sports 2", "Nova Sports 3", "Nova Sports 4", "Nova Sports Start",
    "Cosmote Sport 1", "Cosmote Sport 2", "Cosmote Sport 3", "Cosmote Sport 4", "Cosmote Sport 5", 
    "Cosmote Sport 6", "Cosmote Sport 7", "Cosmote Sport 8", "Cosmote Sport 9",
    "Max Sport 1", "Max Sport 2", "Max Sport 3", "Max Sport 4",
    "Diema Sport", "Diema Sport 2", "Diema Sport 3",
    "Eurosport 1 Poland", "Eurosport 2 Poland", "TVP Sport",
    "RSI LA1", "RSI LA2", "Rai 1", "Rai 2", "Canale 5", "Italia 1", "TV8", "Prime Video"
})

CANALI_PRIORITARI_SPECIALI = set(EPG_PW_TARGET_IDS.values()).union({
    "Setanta Sports Eurasia", "Setanta Sports+ Eurasia", 
    "Setanta Sports Ukraine", "Setanta Sports+ Ukraine",
    "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", 
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
    testo_pulito = re.sub(r'[^\w\s\u0400-\u04FF\u0370-\u03FF]', ' ', testo_pulito)
    
    traduzioni_estere = {
        'интер': 'inter', 'ιντερ': 'inter', 'ınter': 'inter',     
        'inter de milao': 'inter', 'inter milao': 'inter',    
        'milan': 'milan', 'ювентус': 'juventus', 'футбол': 'football',
        'матч': 'match', 'mecz': 'match', 'pilka nozna': 'football',
        'mac': 'match', 'futbol': 'football', 'agonas': 'match', 'podosfairo': 'football'
    }
    
    testo_lower = testo_pulito.lower()
    for estero, lat in traduzioni_estere.items():
        if estero in testo_lower:
            testo_lower = testo_lower.replace(estero, lat)

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
    
    for nome_lista, url, target_set in playlist:
        if url:
            try:
                response = requests.get(url, headers=HEADERS, timeout=20)
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
            except Exception:
                pass

    for cid, cname in EPG_PW_TV_IDS.items():
        TUTTI_I_CANALI_BLU.add(cname)
        INFO_CANALI[cname] = {"id": cid}
        INFO_CANALI[normalizza_testo(cname)] = {"id": cid}

    for cid, cname in EPG_PW_TARGET_IDS.items():
        TUTTI_I_CANALI_BLU.add(cname)
        INFO_CANALI[cname] = {"id": cid}
        INFO_CANALI[normalizza_testo(cname)] = {"id": cid}

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
    URLS_EPG_DINAMICI.add("https://gist.githubusercontent.com/guiworldtv2/0b805e7f86f55c8c5ffc37e51c8990ce/raw/1bbb74431ee1b0fbba0efa2da048444be29273ea/epg%2520master.xml.gz")

def carica_id_da_github():
    global INFO_CANALI
    url_api = "https://iptv-org.github.io/api/channels.json"
    tutti_i_nomi = list(TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI).union(CANALI_TV_CLASSICI).union(CANALI_PRIORITARI_SPECIALI))
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            data = response.json()
            db_canali = {normalizza_testo(c.get('name')): {"id": c.get('id')} for c in data if c.get('name')}
            for nome in tutti_i_nomi:
                if nome in BLACKLIST_CANALI: continue
                if nome in EPG_PW_TARGET_IDS.values() or nome in EPG_PW_TV_IDS.values(): continue
                if nome not in INFO_CANALI:
                    nome_norm = normalizza_testo(nome)
                    if nome_norm in db_canali:
                        INFO_CANALI[nome] = db_canali[nome_norm]
                    else:
                        INFO_CANALI[nome] = {"id": nome.replace(" ", "")}
    except Exception:
        pass

def analizza_epg_stream(content_bytes, valid_channel_ids):
    programmi_locali = []
    parole_da_scartare = [
        "journal", "news", "jt ", "le 20h", "informazione", "cronaca", "edition", "bulletin", 
        "notiziario", "tg", "meteo", "weather", "documentary", "documentario", "film", "serie", 
        "show", "talk", "magazine", "tribunal", "court", "process", "новости", "wiadomosci",
        "haber", "deltio", "interview"
    ]
    tutti_i_target_pw = {**EPG_PW_TARGET_IDS, **EPG_PW_TV_IDS}
    
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
                if any(b in ch_lookup.lower() for b in ["news", "cnews", "court", "cnn", "bbc", "bmt", "tagesschau", "w24"]):
                    elem.clear()
                    continue
                
                if (ch in tutti_i_target_pw or ch in valid_channel_ids or ch_lookup in valid_channel_ids or normalizza_testo(ch_lookup) in valid_channel_ids or ch.isdigit()):
                    if ch in tutti_i_target_pw:
                        ch_lookup = tutti_i_target_pw[ch]
                    
                    title_el = elem.find('title')
                    title_text = title_el.text if (title_el is not None and title_el.text) else ""
                    title_norm = normalizza_testo(title_text)
                    
                    if title_text and elem.get('start') and not any(scarto in title_norm for scarto in parole_da_scartare):
                        programmi_locali.append({
                            'channel': ch,
                            'channel_name': ch_lookup,
                            'title': title_norm,
                            'start': elem.get('start')
                        })
                elem.clear()
    except Exception:
        pass
    return programmi_locali

def scarica_e_processa_paese(paese, valid_channel_ids):
    try:
        res = requests.get(f"https://iptv-epg.org/files/epg-{paese}.xml", headers=HEADERS, timeout=25)
        if res.status_code == 200:
            return analizza_epg_stream(res.content, valid_channel_ids)
    except Exception:
        pass
    return []

def scarica_e_processa_gz_dinamico(url_gz, valid_channel_ids):
    try:
        res = requests.get(url_gz, headers=HEADERS, timeout=25)
        if res.status_code == 200:
            xml_content = gzip.decompress(res.content) if res.content[:2] == b'\x1f\x8b' else res.content
            return analizza_epg_stream(xml_content, valid_channel_ids)
    except Exception:
        pass
    return []

def scarica_singolo_id_pw(args):
    ch_id, ch_name, data_partita_str = args
    try:
        res = requests.get(f"https://epg.pw/api/epg.xml?lang=en&timezone=RXVyb3BlL1N0b2NraG9sbQ%3D%3D&date={data_partita_str}&channel_id={ch_id}", headers=HEADERS, timeout=10)
        if res.status_code == 200 and len(res.content) > 200:
            progs = analizza_epg_stream(res.content, set())
            for p in progs:
                p['channel_name'] = ch_name
            return progs
    except Exception:
        pass
    return []

def scarica_epg_mirato_per_data(data_partita_str):
    tutti_i_target_pw = {**EPG_PW_TARGET_IDS, **EPG_PW_TV_IDS}
    args_list = [(ch_id, ch_name, data_partita_str) for ch_id, ch_name in tutti_i_target_pw.items()]
    programmi_mirati = []
    
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(scarica_singolo_id_pw, arg) for arg in args_list]
        for future in as_completed(futures):
            progs = future.result()
            if progs:
                programmi_mirati.extend(progs)
    return programmi_mirati

def scarica_tutti_gli_epg(date_str_list):
    global PROGRAMMI_EPG
    paesi = ['it', 'fr', 'es', 'pt', 'pl', 'us', 'ar', 'za', 'ae', 'sa', 'qa', 'eg', 'ch', 'cz', 'hr', 'rs', 'hu', 'sk', 'al', 'tr', 'nl', 'ru', 'ua', 'el', 'ge', 'md', 'kz', 'az', 'ie', 'my', 'bg']
    
    tutti_i_target_pw = {**EPG_PW_TARGET_IDS, **EPG_PW_TV_IDS}
    valid_channel_ids = set(tutti_i_target_pw.keys())
    
    for nome, info in INFO_CANALI.items():
        if nome not in BLACKLIST_CANALI:
            if info.get("id"): valid_channel_ids.add(str(info.get("id")))
            valid_channel_ids.add(normalizza_testo(nome))
            valid_channel_ids.add(nome)
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(scarica_e_processa_paese, p, valid_channel_ids): f"paese_{p}" for p in paesi}
        for idx, url_gz in enumerate(URLS_EPG_DINAMICI):
            futures[executor.submit(scarica_e_processa_gz_dinamico, url_gz, valid_channel_ids)] = f"gz_{idx}"

        for future in as_completed(futures):
            risultati = future.result()
            if risultati:
                PROGRAMMI_EPG.extend(risultati)
                
    for data_str in date_str_list:
        progs_mirati = scarica_epg_mirato_per_data(data_str)
        if progs_mirati:
            PROGRAMMI_EPG.extend(progs_mirati)
            
    # Contatore ripristinato per i log di GitHub Actions
    print(f"Totale programmi salvati in memoria: {len(PROGRAMMI_EPG)}")

def pulisci_nome(nome):
    return (nome.replace("Football Club Internazionale Milano", "Inter")
                .replace("Internazionale Milano", "Inter")
                .replace("FC Inter", "Inter")
                .replace("Internazionale", "Inter"))

def cerca_canali_per_partita_ottimizzato(date_utc, home_team, away_team):
    canali_trovati = []
    if not PROGRAMMI_EPG:
        return canali_trovati
        
    h_norm = normalizza_testo(home_team)
    a_norm = normalizza_testo(away_team)
    inter_keywords = ["inter", "internazionale"]
    
    canali_da_evitare = ["cnews", "court tv", "news", "info", "tg", "bmt", "cnn", "bbc", "w24", "tagesschau"]

    id_to_names = {}
    for nome_canale, info in INFO_CANALI.items():
        if nome_canale in BLACKLIST_CANALI: continue
        if any(evitare in nome_canale.lower() for evitare in canali_da_evitare): continue
            
        ch_id = str(info.get("id"))
        for k in [ch_id, normalizza_testo(nome_canale), nome_canale]:
            if k:
                if k not in id_to_names: id_to_names[k] = []
                if nome_canale not in id_to_names[k]: id_to_names[k].append(nome_canale)

    for prog in PROGRAMMI_EPG:
        ch_id = str(prog['channel'])
        ch_name = prog.get('channel_name', ch_id)
        title = prog['title']
        
        match_trovato = False
        contiene_inter = any(k in title for k in inter_keywords)
        contiene_avversario = (h_norm in title and "inter" not in h_norm) or (a_norm in title and "inter" not in a_norm)
        
        if contiene_inter and contiene_avversario:
            match_trovato = True
        elif contiene_inter and any(coppa in title for coppa in ["champions", "ucl", "serie a", "coppa italia"]):
            match_trovato = True

        if match_trovato:
            start_str = prog['start']
            if start_str:
                try:
                    prog_start = datetime.strptime(start_str.split(' ')[0][:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                    if abs((prog_start - date_utc).total_seconds()) <= 10800:
                        
                        if ch_id in EPG_PW_TARGET_IDS:
                            c_uff = EPG_PW_TARGET_IDS[ch_id]
                            if c_uff not in canali_trovati and c_uff not in BLACKLIST_CANALI: canali_trovati.append(c_uff)

                        if ch_id in EPG_PW_TV_IDS:
                            c_uff = EPG_PW_TV_IDS[ch_id]
                            if c_uff not in canali_trovati and c_uff not in BLACKLIST_CANALI: canali_trovati.append(c_uff)

                        for mk in [ch_id, ch_name, normalizza_testo(ch_id), normalizza_testo(ch_name)]:
                            if mk in id_to_names:
                                for nc in id_to_names[mk]:
                                    if nc not in canali_trovati and nc not in BLACKLIST_CANALI: canali_trovati.append(nc)
                        
                        for nc in TUTTI_I_CANALI_BLU.union(TUTTI_I_CANALI_NERI).union(TUTTI_I_CANALI_GIALLI).union(CANALI_TV_CLASSICI).union(CANALI_PRIORITARI_SPECIALI):
                            if nc in BLACKLIST_CANALI: continue
                            norm_nc = normalizza_testo(nc)
                            norm_ch = normalizza_testo(ch_name)
                            if norm_nc and (norm_nc == norm_ch or norm_nc in norm_ch or norm_ch in norm_nc):
                                if nc not in canali_trovati: canali_trovati.append(nc)
                except ValueError:
                    continue
                    
    return canali_trovati

def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        adesso = datetime.now(timezone.utc)
        
        partite_da_analizzare = []
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
            
            partite_da_analizzare.append({
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'home': home,
                'away': away
            })
            
        partite_da_analizzare.sort(key=lambda x: x['ora_utc'])
        partite_da_analizzare = partite_da_analizzare[:4]
        
        if partite_da_analizzare:
            date_da_scaricare = {datetime.now(timezone.utc).strftime('%Y%m%d'), partite_da_analizzare[0]['ora_utc'].strftime('%Y%m%d')}
            scarica_tutti_gli_epg(list(date_da_scaricare))
            
            for p in partite_da_analizzare:
                canali_reali = cerca_canali_per_partita_ottimizzato(p['ora_utc'], p['home'], p['away'])
                if not canali_reali:
                    canali_reali = ["In attesa di programmazione ufficiale ⏳"]
                
                all_matches.append({
                    'ora_utc': p['ora_utc'],
                    'name': p['name'],
                    'competizione': p['competizione'],
                    'canali': canali_reali
                })
            
    except Exception as e:
        print(f"Errore API partite: {e}")
        
    return all_matches

def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V86 EPG Grouped//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora_utc'])
        evento.add('dtend', p['ora_utc'] + timedelta(hours=2))
        
        gruppo_tv = []
        gruppo_blu = []
        gruppo_nero = []
        gruppo_giallo = []
        gruppo_arancione = []
        
        for c in p['canali']:
            if any(black.lower() in c.lower() for black in BLACKLIST_CANALI):
                continue
                
            if "In attesa" in c:
                gruppo_arancione.append(c)
            elif c in CANALI_TV_CLASSICI or c in EPG_PW_TV_IDS.values() or "prime" in c.lower():
                nome_formattato = "🎬 Prime Video" if "prime" in c.lower() else f"📺 {c}"
                if nome_formattato not in gruppo_tv: gruppo_tv.append(nome_formattato)
            elif c in TUTTI_I_CANALI_BLU:
                nome_formattato = f"🔵 {c}"
                if nome_formattato not in gruppo_blu: gruppo_blu.append(nome_formattato)
            elif c in TUTTI_I_CANALI_NERI:
                nome_formattato = f"⚫ {c}"
                if nome_formattato not in gruppo_nero: gruppo_nero.append(nome_formattato)
            elif c in TUTTI_I_CANALI_GIALLI:
                nome_formattato = f"🟡 {c}"
                if nome_formattato not in gruppo_giallo: gruppo_giallo.append(nome_formattato)
            else:
                nome_formattato = f"🟠 {c}"
                if nome_formattato not in gruppo_arancione: gruppo_arancione.append(nome_formattato)
                
        righe_ordinate = gruppo_tv + gruppo_blu + gruppo_nero + gruppo_giallo + gruppo_arancione
        if not righe_ordinate:
            righe_ordinate = ["In attesa di programmazione ufficiale ⏳"]
            
        canali_testo = "\n".join(righe_ordinate)
        evento.add('description', f"🏆 Competizione: {p['competizione']}\n\n📡 Canali TV:\n{canali_testo}")
        cal.add_component(evento)

    with open("inter_tv.ics", 'wb') as f:
        f.write(cal.to_ical())
    print("File ICS generato con successo e raggruppato per tipo.")

if __name__ == '__main__':
    carica_canali_esterni()
    carica_id_da_github()
    matches = fetch_next_matches()
    generate_ics(matches)
