import os
import time
import requests
from requests.adapters import HTTPAdapter
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import threading
import unicodedata
import re
import gzip
from bs4 import BeautifulSoup
from urllib.parse import urljoin

API_KEY = os.getenv("FOOTBALL_DATA_KEY")
URL_CANALI_BLU = os.getenv("URL_CANALI_BLU")
URL_SECONDA_LISTA = os.getenv("URL_SECONDA_LISTA")
URL_TERZA_LISTA = os.getenv("URL_TERZA_LISTA")
URLS_SEI_PLAYLIST = os.getenv("URLS_SEI_PLAYLIST")
URL_CALENDARIO_FOTMOB = os.getenv(
    "URL_CALENDARIO_FOTMOB",
    "https://pub.fotmob.com/prod/pub/api/v2/calendar/team/8636.ics"
)

HEADERS = {
    'X-Auth-Token': API_KEY or '',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

WEB_SCRAPE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,it;q=0.8'
}


def _crea_sessione_http(pool_maxsize=24):
    sessione = requests.Session()
    adapter = HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, max_retries=1)
    sessione.mount("http://", adapter)
    sessione.mount("https://", adapter)
    return sessione


HTTP_SESSION = _crea_sessione_http(pool_maxsize=24)

COMPETITIONS = ['SA', 'CL', 'COI', 'ITC', 'CLI', 'FR1']
TEAM_ID = 108
THESPORTSDB_TEAM_ID = "133604"

PAESI_STANDARD = [
    'it', 'fr', 'es', 'pt', 'pl', 'us', 'ca', 'ar', 'za', 'ae', 'sa', 'qa', 'eg',
    'at', 'ch', 'de', 'be', 'lu', 'nl', 'cz', 'sk', 'hr', 'ba', 'rs', 'me', 'mk', 'si',
    'hu', 'ro', 'bg', 'by', 'al', 'tr', 'ru', 'ua', 'el', 'cy', 'ge', 'md', 'kz', 'az',
    'lt', 'lv', 'ee', 'ie', 'uk', 'gb', 'is', 'mt', 'il', 'uz', 'tj', 'kg',
    'dk', 'se', 'no', 'fi', 'id', 'my', 'sg', 'th', 'vn', 'ph', 'hk', 'tw', 'cn',
    'jp', 'kr', 'in', 'pk', 'au', 'nz', 'br', 'mx', 'co', 'cl', 'pe', 'uy',
    've', 'ec', 'bo', 'py', 'cr', 'pa', 'do', 'jm', 'pr', 'ng', 'ke', 'gh', 'ma', 'tn', 'dz', 'ly'
]

# Parole chiave globali per scartare repliche e sintesi
PAROLE_ESCLUSE_REPLICHE = [
    "powtórka", "skrót", "archiwum", "classic", "retransmisja",
    "replay", "highlights", "pregled", "youth", "u19", "mlodziezowa"
]

# ==========================================
# BLACKLIST CANALI RIGOROSA
# ==========================================
BLACKLIST_CANALI = {
    "O!", "o!", "O", "o",
    "E!", "e!", "E", "e",
    "pre", "PRE",
    "Mezzo", "Mezzo Live", "mezzo", "mezzo live",
    "Focus", "HRT 4", "ORTS (480p) [Not 24/7]", "Das Erste",
    "CNews", "Court TV", "CNN", "BBC News", "BMT",
    "Tagesschau24", "W24", "10 HD", "10", "RT", ":24", "Spo",
    "DAZN", "DAZN 1", "DAZN 2", "DAZN 1 Bar", "DAZN Espana", "DAZN Portugal",
    "Serie A Football", "Coppa Italia Football", "UEFA Champions League Football",
    "Premier League", "Scottish Premiership", "Tonight", "Teams",
    "View All Teams", "View All Teams ->", "All Teams",
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Chelsea", "Coventry City", "Crystal Palace", "Everton", "Fulham",
    "Hull City", "Ipswich Town", "Leeds Utd", "Liverpool",
    "Manchester City", "Manchester Utd", "Newcastle Utd", "Nottingham Forest",
    "Sunderland", "Tottenham", "Aberdeen", "Celtic", "Hearts", "Hibs", "Rangers",
    "England", "England Women", "Northern Ireland", "Scotland", "Wales",
    "AC Milan", "Ajax", "Atletico Madrid", "Barcelona", "Bayern Munich",
    "Benfica", "FC Porto", "Juventus", "PSG", "Real Madrid",
    "Alerts", "More", "Explore", "Value Bets", "OddAlerts Alpha",
    "Bet of the Day", "Corners", "Sports Edge Bot", "Betslip Generator",
    "Foul Alerts", "Bet Builder", "Map", "Home Wins", "Suggested Alerts",
    "Bet Tracking", "Tennis Alerts", "CSV Downloads", "API",
    "Explore Pro Features", "Bet Builder Tips", "Partners",
    "Home Wins Form", "All Filter Presets", "Home Win Value Bets",
    "Over 2.5 Goals Value Bets", "Corner Betting Tips", "Your country"
}
BLACKLIST_CANALI_LOWER = {b.lower() for b in BLACKLIST_CANALI}

_FRASI_O_PAROLE_BLOCCATE_CANALI = [
    "dazn",
    "football", "premier league", "premiership", "serie a", "coppa italia",
    "champions league", "europa league", "conference league", "supercoppa",
    "view all teams", "tonight", "england women", "northern ireland",
    "manchester city", "manchester utd", "aston villa", "crystal palace",
    "nottingham forest", "ipswich town", "coventry city", "leeds utd",
    "bayern munich", "atletico madrid", "real madrid", "fc porto", "ac milan",
    "value bets", "bet builder", "betslip generator", "sports edge bot",
    "suggested alerts", "bet tracking", "tennis alerts", "foul alerts",
    "csv downloads", "filter presets", "betting tips", "bet of the day",
    "oddalerts alpha", "explore pro features", "home wins form", "your country"
]
_REGEX_BLOCCATE_CANALI = [re.compile(rf'\b{re.escape(p)}\b', re.IGNORECASE) for p in _FRASI_O_PAROLE_BLOCCATE_CANALI]

_RUMORE_UI_ODDALERTS_ESATTO = {
    "alerts", "more", "explore", "value bets", "oddalerts alpha",
    "bet of the day", "corners", "sports edge bot", "betslip generator",
    "foul alerts", "bet builder", "map", "home wins", "suggested alerts",
    "bet tracking", "tennis alerts", "csv downloads", "api",
    "explore pro features", "bet builder tips", "partners",
    "home wins form", "all filter presets", "home win value bets",
    "over 2.5 goals value bets", "corner betting tips", "your country",
    "pro features", "filter presets", "value bet", "odds", "stats",
    "standings", "table", "lineups", "fixtures", "results", "home", "away", "pre"
}
_REGEX_RUMORE_UI_ODDALERTS = [
    re.compile(r'\b(alerts?|value\s*bets?|bet\s*builder|betslip|corner\s*betting|over\s*\d+(\.\d+)?|filter\s*presets?|pro\s*features?|csv\s*downloads?|your\s*country|edge\s*bot|home\s*wins?)\b', re.IGNORECASE),
    re.compile(r'^(more|explore|corners?|map|api|partners|odds|stats|standings|table|lineups|fixtures|results|pre)$', re.IGNORECASE)
]


def _is_rumore_ui_web(testo):
    if not testo:
        return False
    low = " ".join(testo.strip().lower().split())
    if low in _RUMORE_UI_ODDALERTS_ESATTO:
        return True
    return any(rx.search(low) for rx in _REGEX_RUMORE_UI_ODDALERTS)


def is_blacklisted(nome_canale):
    if not nome_canale:
        return True
    low = " ".join(nome_canale.strip().lower().split())
    if len(low) < 2 or low in BLACKLIST_CANALI_LOWER or low in _RUMORE_UI_ODDALERTS_ESATTO:
        return True
    if any(rx.search(low) for rx in _REGEX_BLOCCATE_CANALI):
        return True
    return any(rx.search(low) for rx in _REGEX_RUMORE_UI_ODDALERTS)


def is_prime_video_channel(testo):
    if not testo:
        return False
    t = testo.lower()
    return (
        "prime video" in t
        or "amazon prime" in t
        or bool(re.search(r'\bprime\s*(video|sport|it|uk|ch|de|fr|es|pt|pl)?\b', t))
    )


def _is_eleven_sports_portugal(nome_canale):
    if not nome_canale:
        return False
    low = nome_canale.lower()
    return "eleven" in low and ("portugal" in low or re.search(r'\bpt\b', low) is not None)


def _is_max_sport_1_4(nome_canale):
    if not nome_canale:
        return False
    return bool(re.search(r'\bmax\s*sport\s*[1-4]\b', nome_canale, flags=re.IGNORECASE))


# ==========================================
# NORMALIZZAZIONE NOMI CANALI
# ==========================================
def normalizza_nome_canale(ch_name):
    if not ch_name:
        return ""

    ch_lower = ch_name.lower()

    if 'setanta' in ch_lower:
        is_eurasia = any(tag in ch_lower for tag in ['[uz]', '[ge]', '[ua]', '[kz]', 'eurasia', 'kazakhstan', 'georgia', 'ukraine', 'uzbekistan'])
        if '2' in ch_lower or 'second' in ch_lower:
            return "Setanta Sport 2 Eurasia" if is_eurasia else "Setanta Sport 2"
        return "Setanta Sport 1 Eurasia" if is_eurasia else "Setanta Sport 1"

    m_max = re.search(r'\bmax\s*sport\s*([1-4])\b', ch_name, flags=re.IGNORECASE)
    if m_max:
        return f"Max Sport {m_max.group(1)}"

    if is_prime_video_channel(ch_name):
        return "Prime Video"

    if ch_lower in {"italia uno", "italia 1"} or re.fullmatch(r'italia\s*(uno|1)', ch_lower):
        return "Italia 1"

    if ch_lower in {"canale cinque", "canale 5"} or re.fullmatch(r'canale\s*(cinque|5)', ch_lower):
        return "Canale 5"

    return ch_name.strip()


# ==========================================
# ID ESCLUSIVI EPG.PW - CANALI TV (📺)
# ==========================================
EPG_PW_TV_IDS = {
    "6338": "Eleven Sports 1",
    "6340": "Eleven Sports 2",
    "6339": "Eleven Sports 3",
    "6336": "Eleven Sports 4",
    "408445": "Eleven Sports 1",
    "408446": "Eleven Sports 2",
    "7836": "Eleven Sports 3",
    "7837": "Eleven Sports 4",
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
    "535980": "Diema Sport 3",
    "540363": "Prima Sport 1",
    "540369": "Prima Sport 2",
    "408450": "Digi Sport 1",
    "408451": "Digi Sport 2",
    "408452": "Digi Sport 3",
    "408453": "Digi Sport 4",
    "415585": "Ziggo Sport",
    "406806": "Ziggo Sport 1",
    "76654": "Canale 5",
    "465330": "Italia 1",
    "585499": "Rai 1",
    "585468": "Rai 2"
}

# ==========================================
# ID ESCLUSIVI EPG.PW - CANALI TARGET (⭐)
# ==========================================
EPG_PW_TARGET_IDS = {
    "78599": "5Sport",
    "547353": "5Sport Live",
    "545663": "5Sport Plus",
    "406253": "Sport 1",
    "6507": "Sport 1 Baltic",
    "549677": "Sport 2",
    "406295": "Sport 2",
    "6086": "Sport 2 Baltic",
    "397418": "Sport TV 1",
    "397424": "Sport TV 2",
    "397419": "Sport TV 3",
    "397404": "Sport TV 4",
    "408040": "Sport TV 5",
    "397417": "Sport TV 6",
    "405669": "Sport TV 7",
    "405715": "Sport TV +",
    "417364": "Setanta Sports 1",
    "247795": "Setanta Sports 1 Eurasia",
    "62234": "Setanta Sports 2 Eurasia",
    "325011": "Setanta Sports+",
    "534194": "Setanta Sports 1 Georgia",
    "534193": "Setanta Sports 2 Georgia",
    "553867": "Setanta 1 [UZ]",
    "553861": "Setanta 2 [UZ]",
    "417351": "Setanta Sports 2 Lietuva",
    "473658": "Setanta Sport+ [KZ]",
    "567946": "Sport+ Qazaqstan",
    "62227": "Setanta Sports 1 KZ",
    "359087": "Setanta Kyrgyzstan",
    "534228": "Setanta Sports 3 Georgia",
    "408458": "Setanta Sports Premium [UA]",
    "6159": "Setanta Казахстан",
    "392163": "Setanta Украина",
    "392142": "Setanta+ Украина",
    "400477": "TNT Sports 1",
    "400480": "TNT Sports 2",
    "400479": "TNT Sports 3",
    "400478": "TNT Sports 4",
    "463026": "TNT Sports 5",
    "463020": "TNT Sports 6",
    "463024": "TNT Sports 7",
    "463025": "TNT Sports 8",
    "463021": "TNT Sports 9",
    "431608": "TNT Sport Premium",
    "562308": "CBS Sports Golazo",
    "480375": "Okko Sport",
    "563613": "Go3 Sport",
    "55898": "Arryadia",
    "381850": "Arena Sport 1",
    "381848": "Arena Sport 2",
    "381849": "Arena Sport 3",
    "465156": "Fox Deportes",
    "465291": "Fox Sports 1",
    "415584": "Fox Sports 2",
    "415586": "Fox Sports 3",
    "431624": "Fox Sport HD",
    "465214": "Fox Soccer Plus",
    "408622": "CBS Sports Network",
    "464937": "CBS Sports Network",
    "562459": "CBS Sports",
    "450100": "beIN Sports 1",
    "450101": "beIN Sports 2",
    "450102": "beIN Sports 3",
    "450103": "beIN Sports French",
    "450104": "beIN Sports English",
    "372290": "beIN Sport 3 (FR)",
    "407564": "beIN Sport (US)",
    "369750": "beIN Sports (SG)",
    "399482": "beIN Sports 1 (MY)",
    "532981": "beIN Sports 1 (RU)",
    "55773": "beIN Sports 1 (FR)",
    "524189": "beIN Sports 1 (ID)",
    "410403": "beIN Sports 1 (HK)",
    "94061": "beIN Sports 1 (EN)",
    "524097": "beIN Sports 1 HD (ID)",
    "418524": "beIN Sports 1 (SG)",
    "453376": "beIN Sports 1 (FR)",
    "532945": "beIN Sports 1 (HK)",
    "563364": "beIN Sports 1 (TR)",
    "410404": "beIN Sports 2 (HK)",
    "532982": "beIN Sports 2 (RU)",
    "369601": "beIN Sports 2 (MY)",
    "443147": "beIN Sports 2 (FR)",
    "4146": "beIN Sports 2 Astro (MY)",
    "524174": "beIN Sports 2 (ID)",
    "369741": "beIN Sports 2 HD (SG)",
    "93994": "beIN Sports 2 (EN)",
    "524987": "beIN Sports 2 HD (SG)",
    "523994": "beIN Sports 2 HD (ID)",
    "418520": "beIN Sports 2 (SG)",
    "453366": "beIN Sports 2 (FR)",
    "532942": "beIN Sports 2 (HK)",
    "540230": "beIN Sports 2 (TR)",
    "3118": "beIN Sports 3 Astro (MY)",
    "524066": "beIN Sports 3 (ID)",
    "54963": "beIN Sports 3 (FR)",
    "369662": "beIN Sports 3 (MY)",
    "532983": "beIN Sports 3 (RU)",
    "410408": "beIN Sports 3 (HK)",
    "369817": "beIN Sports 3 HD (SG)",
    "524063": "beIN Sports 3 HD (ID)",
    "524985": "beIN Sports 3 HD (SG)",
    "418536": "beIN Sports 3 (SG)",
    "532966": "beIN Sports 3 (HK)",
    "540231": "beIN Sports 3 (TR)",
    "410409": "beIN Sports 4 (HK)",
    "532977": "beIN Sports 4 (RU)",
    "523993": "beIN Sports 4 (ID)",
    "524983": "beIN Sports 4 HD (SG)",
    "558100": "beIN Sports 4K (RU)",
    "410410": "beIN Sports 5 (HK)",
    "532978": "beIN Sports 5 (RU)",
    "524159": "beIN Sports 5 (ID)",
    "524984": "beIN Sports 5 HD (SG)",
    "410411": "beIN Sports 6 (HK)",
    "532979": "beIN Sports 6 (RU)",
    "532980": "beIN Sports 7 (RU)",
    "465366": "beIN Sports En Español HD (US)",
    "51580": "beIN Sports FTA (RU)",
    "580971": "beIN Sports Haber (TR)",
    "2580": "beIN Sports HD Astro (MY)",
    "524988": "beIN Sports HD (SG)",
    "470340": "beIN Sports HD (CA)",
    "455815": "beIN Sports Max 1 (TR)",
    "443150": "beIN Sports Max 10 (FR)",
    "459106": "beIN Sports Max 10 (FR)",
    "442714": "beIN Sports Max 2 (TR)",
    "443239": "beIN Sports Max 4 (FR)",
    "459115": "beIN Sports Max 4 (FR)",
    "443103": "beIN Sports Max 5 (FR)",
    "532976": "beIN Sports Max 5 (FR)",
    "55982": "beIN Sports Max 6 (FR)",
    "459136": "beIN Sports Max 6 (FR)",
    "55920": "beIN Sports Max 7 (FR)",
    "459113": "beIN Sports Max 7 (FR)",
    "443213": "beIN Sports Max 8 (FR)",
    "459121": "beIN Sports Max 8 (FR)",
    "55983": "beIN Sports Max 9 (FR)",
    "459142": "beIN Sports Max 9 (FR)",
    "7200": "beIN Sports News",
    "549965": "beIN Sports (CA)",
    "413152": "beIN Sports Xtra (US)",
    "464754": "beIN Sports USA HD",
    "470001": "Viaplay",
    "470002": "Viaplay Sweden",
    "470003": "Viaplay Denmark",
    "480001": "Canal+",
    "490001": "Sky Sport Austria 1",
    "490002": "Sky Sport Austria 3",
    "490003": "Sky Sport Arena",
    "539623": "ORF Sport+",
    "76756": "ORF Sport+",
    "76734": "ORF 3",
    "76616": "ORF 2",
    "438442": "ORF 1",
    "580954": "A Spor"
}

TUTTI_I_TARGET_PW = {**EPG_PW_TARGET_IDS, **EPG_PW_TV_IDS}

CANALI_STELLE = {
    "QazSport", "5Sport", "5Sport Live", "5Sport Plus",
    "Sport", "Šport",
    "Sport 1", "Sport 1 Baltic", "Sport 2", "Sport 2 Baltic",
    "Setanta Sports 1", "Setanta Sport 1 Eurasia", "Setanta Sport 2 Eurasia",
    "Setanta Sports+", "Setanta Sports 1 Georgia", "Setanta Sports 2 Georgia",
    "Setanta Sports 3 Georgia", "Setanta Sports Premium [UA]",
    "Okko Futbol", "Okko Sport",
    "beIN Sports 1", "beIN Sports 2", "beIN Sports 3",
    "beIN Sports French", "beIN Sports English",
    "beIN Sport 3 (FR)", "beIN Sport (US)", "beIN Sports (SG)",
    "beIN Sports 1 (MY)", "beIN Sports 1 (RU)", "beIN Sports 1 (FR)",
    "beIN Sports 1 (ID)", "beIN Sports 1 (HK)", "beIN Sports 1 (EN)",
    "beIN Sports 1 HD (ID)",
    "beIN Sports 1 (SG)", "beIN Sports 1 (HK)", "beIN Sports 1 (TR)",
    "beIN Sports 2 (HK)", "beIN Sports 2 (RU)", "beIN Sports 2 (MY)",
    "beIN Sports 2 (FR)", "beIN Sports 2 Astro (MY)", "beIN Sports 2 (ID)",
    "beIN Sports 2 HD (SG)", "beIN Sports 2 (EN)", "beIN Sports 2 HD (ID)",
    "beIN Sports 2 (SG)", "beIN Sports 2 (HK)", "beIN Sports 2 (TR)",
    "beIN Sports 3 Astro (MY)",
    "beIN Sports 3 (ID)", "beIN Sports 3 (FR)", "beIN Sports 3 (MY)",
    "beIN Sports 3 (RU)", "beIN Sports 3 (HK)", "beIN Sports 3 HD (SG)",
    "beIN Sports 3 HD (ID)", "beIN Sports 3 (SG)", "beIN Sports 3 (TR)",
    "beIN Sports 4 (HK)", "beIN Sports 4 (RU)", "beIN Sports 4 (ID)",
    "beIN Sports 4 HD (SG)", "beIN Sports 4K (RU)",
    "beIN Sports 5 (HK)", "beIN Sports 5 (RU)", "beIN Sports 5 (ID)",
    "beIN Sports 5 HD (SG)",
    "beIN Sports 6 (HK)", "beIN Sports 6 (RU)",
    "beIN Sports 7 (RU)",
    "beIN Sports En Español HD (US)",
    "beIN Sports FTA (RU)",
    "beIN Sports Haber (TR)",
    "beIN Sports HD Astro (MY)",
    "beIN Sports HD (SG)",
    "beIN Sports HD (CA)",
    "beIN Sports Max 1 (TR)",
    "beIN Sports Max 10 (FR)",
    "beIN Sports Max 2 (TR)",
    "beIN Sports Max 4 (FR)",
    "beIN Sports Max 5 (FR)",
    "beIN Sports Max 6 (FR)",
    "beIN Sports Max 7 (FR)",
    "beIN Sports Max 8 (FR)",
    "beIN Sports Max 9 (FR)",
    "beIN Sports News",
    "beIN Sports (CA)",
    "beIN Sports Xtra (US)",
    "beIN Sports USA HD",
    "Viaplay", "Viaplay Sweden", "Viaplay Denmark", "Canal+",
    "AS3 Sport TV", "N Sports", "Sport+ Qazaqstan",
    "ORF 1", "ORF 2", "ORF 3", "ORF Sport+",
    "TNT Sports", "TNT Sports 1", "TNT Sports 2", "TNT Sports 3", "TNT Sports 4",
    "TNT Sports 5", "TNT Sports 6", "TNT Sports 7", "TNT Sports 8", "TNT Sports 9",
    "TNT Sports 7 HBO Max", "TNT Sport Premium",
    "CBS Sports Golazo", "Fox Deportes", "Fox Sports 1", "Fox Sports 2",
    "Fox Sports 3", "Fox Sport HD", "Fox Soccer Plus"
}

CANALI_TV_CLASSICI = set(EPG_PW_TV_IDS.values()).difference({"Ziggo Sport", "Ziggo Sport 1"}).union({
    "Eleven Sports 1", "Eleven Sports 2", "Eleven Sports 3", "Eleven Sports 4",
    "Eleven Sports", "Eleven Sports 1 Poland", "Eleven Sports 2 Poland", "Eleven Sports 3 Poland", "Eleven Sports 4 Poland",
    "Canal+ Sport", "Canal+ Sport 2", "Canal+ Extra", "Canal+ 1",
    "Polsat Sport", "Polsat Sport 1", "Polsat Sport 2", "Polsat Sport 3", "Polsat Sport Fight",
    "Polsat Sport Premium 1", "Polsat Sport Premium 2", "Polsat Sport Premium 3",
    "Polsat Sport Premium 4", "Polsat Sport Premium 5", "Polsat Sport Premium 6",
    "Nova Sports 1", "Nova Sports 2", "Nova Sports 3", "Nova Sports 4", "Nova Sports Start",
    "Cosmote Sport 1", "Cosmote Sport 2", "Cosmote Sport 3", "Cosmote Sport 4", "Cosmote Sport 5",
    "Cosmote Sport 6", "Cosmote Sport 7", "Cosmote Sport 8", "Cosmote Sport 9",
    "Max Sport 1", "Max Sport 2", "Max Sport 3", "Max Sport 4",
    "Diema Sport", "Diema Sport 2", "Diema Sport 3",
    "Eurosport 1 Poland", "Eurosport 2 Poland", "TVP Sport",
    "Prima Sport 1", "Prima Sport 2", "Digi Sport 1", "Digi Sport 2", "Digi Sport 3", "Digi Sport 4",
    "Sky Sport Austria 1", "Sky Sport Austria 3", "Sky Sport Arena",
    "RSI LA1", "RSI LA2", "Rai 1", "Rai 2", "Canale 5", "Italia 1", "Italia Uno", "TV8", "Prime Video"
})

INFO_CANALI = {}
PROGRAMMI_EPG = []
TUTTI_I_CANALI_BLU = set()
TUTTI_I_CANALI_NERI = set()
TUTTI_I_CANALI_GIALLI = set()
TUTTI_I_CANALI_BIANCHI = set()
URLS_EPG_DINAMICI = set()

CANALI_SOLE_ODDALERTS_PER_MATCH = {}

_CANALI_DALLE_LISTE_IPTV = set()
_CANALI_DALLE_LISTE_IPTV_NORM = set()

_EPG_PW_XML_CACHE = {}
_EPG_PW_FAILED_KEYS = set()
_EPG_PW_CACHE_LOCK = threading.Lock()
_EPG_PW_PACE_LOCK = threading.Lock()
_EPG_PW_LAST_CALL_TS = 0.0
_PRINT_LOCK = threading.Lock()
_LOGGED_DIAG_KEYS = set()


def _log(msg):
    with _PRINT_LOCK:
        print(msg)


def _log_una_volta(chiave, msg):
    with _PRINT_LOCK:
        if chiave not in _LOGGED_DIAG_KEYS:
            _LOGGED_DIAG_KEYS.add(chiave)
            print(msg)


def _parsa_start_epg_utc(start_str):
    if not start_str:
        return None
    s = " ".join(start_str.strip().split())
    m = re.match(r'^(\d{14})(?:\s*([+-]\d{4}|[+-]\d{2}:\d{2}|Z|UTC|GMT))?', s, flags=re.IGNORECASE)
    if not m:
        return None
    dt_base = datetime.strptime(m.group(1), '%Y%m%d%H%M%S')
    tz_part = (m.group(2) or "").strip().upper()

    if not tz_part or tz_part in {"Z", "UTC", "GMT"}:
        return dt_base.replace(tzinfo=timezone.utc)

    tz_clean = tz_part.replace(":", "")
    try:
        offset_dt = datetime.strptime(tz_clean, "%z")
        return dt_base.replace(tzinfo=offset_dt.tzinfo).astimezone(timezone.utc)
    except ValueError:
        return dt_base.replace(tzinfo=timezone.utc)


def _chiave_match_sole(match_name, ora_utc):
    data_g = ora_utc.strftime('%Y-%m-%d') if isinstance(ora_utc, datetime) else str(ora_utc)[:10]
    return f"{normalizza_testo(match_name)}|{data_g}"


_TRADUZIONI_ESTERE = {
    'интер': 'inter', 'ιντερ': 'inter', 'ınter': 'inter',
    'inter de milao': 'inter', 'inter milao': 'inter', 'inter mediolan': 'inter',
    'italia uno': 'italia 1', 'canale cinque': 'canale 5',
    'amazon prime video': 'prime video', 'amazon prime': 'prime video',
    'реал мадрид': 'real madrid', 'реал': 'real', 'мадрид': 'madrid',
    'милан': 'milan', 'ювентус': 'juventus', 'барселона': 'barcelona',
    'атлетико': 'atletico', 'наполи': 'napoli', 'рома': 'roma', 'as roma': 'roma',
    'лацио': 'lazio', 'аталанта': 'atalanta', 'болонья': 'болонья',
    'футбол': 'football', 'матч': 'match', 'mecz': 'match',
    'pilka nozna': 'football', 'mac': 'match', 'futbol': 'football',
    'agonas': 'match', 'podosfairo': 'football', 'окко': 'okko',
    'спорт': 'sport', 'sport': 'sport', 'ספורט 5': '5sport',
    'qazsport': 'qazsport', 'setanta': 'setanta'
}


def normalizza_testo(testo):
    if not testo:
        return ""
    testo_pulito = re.sub(r'\b(hd|fhd|4k|uhd|sd|hevc|iptv|live|ex|1080p|720p)\b', '', testo, flags=re.IGNORECASE)
    testo_pulito = re.sub(r'\[.*?\]|\(.*?\)', '', testo_pulito)
    testo_pulito = re.sub(r'[^\w\s\u0400-\u04FF\u0370-\u03FF\u0590-\u05FF]', ' ', testo_pulito)

    testo_lower = testo_pulito.lower()
    for estero, lat in _TRADUZIONI_ESTERE.items():
        if estero in testo_lower:
            testo_lower = testo_lower.replace(estero, lat)

    nfkd_form = unicodedata.normalize('NFKD', testo_lower)
    risultato = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return " ".join(risultato.split()).strip()


def _applica_alias_speciali(nome_canale):
    low = nome_canale.lower()
    if "5sport" in low or "sport 5" in low or "ספורט 5" in nome_canale:
        return "5Sport"
    if "qazsport" in low:
        return "QazSport"
    return nome_canale


def pulisci_etichetta_canale(nome_canale):
    if not nome_canale:
        return ""
    if _is_rumore_ui_web(nome_canale) or is_blacklisted(nome_canale):
        return ""
    if is_prime_video_channel(nome_canale):
        return "Prime Video"
    nome_canale = _applica_alias_speciali(normalizza_nome_canale(nome_canale))
    if nome_canale in {"5Sport", "QazSport"}:
        return nome_canale
    pulito = re.sub(r'\b(1080p|720p|4k|uhd|sd|fhd|hevc)\b', '', nome_canale, flags=re.IGNORECASE)
    pulito = re.sub(r'\[.*?\]|\(.*?\)', '', pulito)
    pulito = pulito.replace('\n', ' ').replace('\r', ' ').strip()
    pulito = re.sub(r'^[:\-\s]+', '', pulito)
    pulito_norm = _applica_alias_speciali(normalizza_nome_canale(" ".join(pulito.split())))
    if not pulito_norm or _is_rumore_ui_web(pulito_norm) or is_blacklisted(pulito_norm):
        return ""
    return "Prime Video" if is_prime_video_channel(pulito_norm) else pulito_norm


def _registra_canale_lista_iptv(nome_canale):
    if not nome_canale or is_blacklisted(nome_canale):
        return
    c_pulito = pulisci_etichetta_canale(nome_canale)
    if not c_pulito or is_blacklisted(c_pulito):
        return
    _CANALI_DALLE_LISTE_IPTV.add(c_pulito)
    norm = normalizza_testo(c_pulito)
    if norm:
        _CANALI_DALLE_LISTE_IPTV_NORM.add(norm)


def _canale_in_liste_iptv(nome_canale):
    if not nome_canale or _is_rumore_ui_web(nome_canale):
        return False
    c_pulito = pulisci_etichetta_canale(nome_canale)
    if not c_pulito or is_blacklisted(c_pulito):
        return False
    if c_pulito in _CANALI_DALLE_LISTE_IPTV:
        return True
    norm_c = normalizza_testo(c_pulito)
    if not norm_c or _is_rumore_ui_web(norm_c):
        return False
    if norm_c in _CANALI_DALLE_LISTE_IPTV_NORM:
        return True
    return any(
        len(n_lista) >= 4 and (n_lista in norm_c or norm_c in n_lista)
        for n_lista in _CANALI_DALLE_LISTE_IPTV_NORM
    )


def analizza_m3u_esteso(testo_m3u, target_set):
    current_tvg_id = None
    for line in testo_m3u.splitlines():
        line = line.strip()
        if not line:
            continue
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
                    current_tvg_id = line.split('tvg-id="')[1].split('"')[0].strip()
                except Exception:
                    pass
            if "," in line:
                c_name = line.split(",")[-1].strip()
                if c_name and not is_blacklisted(c_name):
                    c_name = _applica_alias_speciali(normalizza_nome_canale(c_name))
                    target_set.add(c_name)
                    _registra_canale_lista_iptv(c_name)
                    if current_tvg_id:
                        INFO_CANALI[c_name] = {"id": current_tvg_id}
                        INFO_CANALI[normalizza_testo(c_name)] = {"id": current_tvg_id}
        elif "," in line and not line.startswith("#") and not line.startswith("http"):
            c_name = line.split(",", 1)[0].strip()
            if c_name and len(c_name) < 50 and not is_blacklisted(c_name):
                c_name = _applica_alias_speciali(normalizza_nome_canale(c_name))
                target_set.add(c_name)
                _registra_canale_lista_iptv(c_name)


def _carica_lista_singola(url, target_set):
    if not url:
        return
    try:
        response = HTTP_SESSION.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200 or not response.text:
            return
        if "#EXTM3U" in response.text or "#EXTINF" in response.text:
            analizza_m3u_esteso(response.text, target_set)
            return
        for line in response.text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("http"):
                c_name = line.split(",", 1)[0].strip() if "," in line else line
                if c_name and len(c_name) < 50 and not is_blacklisted(c_name):
                    c_name = _applica_alias_speciali(normalizza_nome_canale(c_name))
                    target_set.add(c_name)
                    _registra_canale_lista_iptv(c_name)
    except Exception:
        pass


def carica_canali_esterni():
    playlist = [
        ("BLU", URL_CANALI_BLU, TUTTI_I_CANALI_BLU),
        ("NERA", URL_SECONDA_LISTA, TUTTI_I_CANALI_NERI),
        ("GIALLA", URL_TERZA_LISTA, TUTTI_I_CANALI_GIALLI)
    ]
    urls_6 = [u.strip() for u in (URLS_SEI_PLAYLIST or "").split() if u.strip()]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_carica_lista_singola, url, target_set) for _, url, target_set in playlist if url]
        futures.extend(executor.submit(_carica_lista_singola, u, TUTTI_I_CANALI_BIANCHI) for u in urls_6)
        for fut in as_completed(futures):
            fut.result()

    for cid, cname in TUTTI_I_TARGET_PW.items():
        cname_norm = normalizza_nome_canale(cname)
        if not is_blacklisted(cname_norm):
            TUTTI_I_CANALI_BLU.add(cname_norm)
            INFO_CANALI[cname_norm] = {"id": cid}
            INFO_CANALI[normalizza_testo(cname_norm)] = {"id": cid}

    for can_it in ["Canale 5", "Italia 1", "Italia Uno", "Prime Video"]:
        can_norm = normalizza_nome_canale(can_it)
        TUTTI_I_CANALI_BLU.add(can_norm)
        INFO_CANALI[can_norm] = {"id": can_norm}
        INFO_CANALI[normalizza_testo(can_norm)] = {"id": can_norm}

    for extra_fixed, extra_id in [("5Sport", "5Sport.il"), ("QazSport", "QazSport.kz")]:
        TUTTI_I_CANALI_BLU.add(extra_fixed)
        INFO_CANALI[extra_fixed] = {"id": extra_id}
        INFO_CANALI[normalizza_testo(extra_fixed)] = {"id": extra_id}

    open_epg_mappatura = {
        'it': 'italy1', 'fr': 'france', 'es': 'spain', 'pt': 'portugal', 'pl': 'poland',
        'us': 'usa', 'ca': 'canada', 'ar': 'argentina', 'za': 'southafrica', 'ae': 'uae',
        'sa': 'saudiarabia', 'qa': 'qatar', 'eg': 'egypt', 'at': 'austria', 'ch': 'switzerland',
        'de': 'germany', 'be': 'belgium', 'lu': 'luxembourg', 'nl': 'netherlands',
        'cz': 'czech', 'sk': 'slovakia', 'hr': 'bosnia', 'ba': 'bosnia', 'rs': 'serbia',
        'me': 'montenegro', 'mk': 'macedonia', 'si': 'slovenia', 'hu': 'hungary',
        'ro': 'romania', 'bg': 'bulgaria1', 'by': 'belarus', 'al': 'albania', 'tr': 'turkey',
        'ru': 'russia', 'ua': 'ukraine', 'el': 'greece', 'cy': 'cyprus', 'ge': 'georgia',
        'md': 'moldova', 'kz': 'kazakhstan', 'az': 'azerbaijan', 'lt': 'lithuania',
        'lv': 'latvia', 'ee': 'estonia', 'ie': 'ireland', 'my': 'malaysia1', 'sg': 'singapore',
        'th': 'thailand', 'vn': 'vietnam', 'ph': 'philippines', 'hk': 'hongkong', 'tw': 'taiwan',
        'cn': 'china', 'jp': 'japan', 'kr': 'southkorea', 'in': 'india', 'pk': 'pakistan',
        'au': 'australia', 'nz': 'newzealand', 'uk': 'uk', 'gb': 'uk', 'is': 'iceland',
        'mt': 'malta', 'il': 'israel', 'uz': 'uzbekistan', 'tj': 'tajikistan', 'kg': 'kyrgyzstan',
        'dk': 'denmark', 'se': 'sweden', 'no': 'norway', 'fi': 'finland', 'id': 'indonesia',
        'br': 'brazil', 'mx': 'mexico', 'co': 'colombia', 'cl': 'chile', 'pe': 'peru',
        'uy': 'uruguay', 've': 'venezuela', 'ec': 'ecuador', 'bo': 'bolivia', 'py': 'paraguay',
        'cr': 'costarica', 'pa': 'panama', 'do': 'dominicanrepublic', 'jm': 'jamaica',
        'pr': 'puertorico', 'ng': 'nigeria', 'ke': 'kenya', 'gh': 'ghana', 'ma': 'morocco',
        'tn': 'tunisia', 'dz': 'algeria', 'ly': 'libya'
    }
    globetv_mappatura = {
        'it': 'Italy', 'fr': 'France', 'es': 'Spain', 'pt': 'Portugal', 'pl': 'Poland',
        'us': 'Usa', 'ca': 'Canada', 'ar': 'Argentina', 'za': 'Southafrica', 'ae': 'Uae',
        'sa': 'Saudiarabia', 'qa': 'Qatar', 'eg': 'Egypt', 'at': 'Austria', 'ch': 'Switzerland',
        'de': 'Germany', 'be': 'Belgium', 'lu': 'Luxembourg', 'nl': 'Netherlands',
        'cz': 'Czech', 'sk': 'Slovakia', 'hr': 'Bosnia', 'ba': 'Bosnia', 'rs': 'Serbia',
        'me': 'Montenegro', 'mk': 'Macedonia', 'si': 'Slovenia', 'hu': 'Hungary',
        'ro': 'Romania', 'bg': 'Bulgaria', 'by': 'Belarus', 'al': 'Albania', 'tr': 'Turkey',
        'ru': 'Russia', 'ua': 'Ukraine', 'el': 'Greece', 'cy': 'Cyprus', 'ge': 'Georgia',
        'md': 'Moldova', 'kz': 'Kazakhstan', 'az': 'Azerbaijan', 'lt': 'Lithuania',
        'lv': 'Latvia', 'ee': 'Estonia', 'ie': 'Ireland', 'my': 'Malaysia', 'sg': 'Singapore',
        'th': 'Thailand', 'vn': 'Vietnam', 'ph': 'Philippines', 'hk': 'Hongkong', 'tw': 'Taiwan',
        'cn': 'China', 'jp': 'Japan', 'kr': 'Southkorea', 'in': 'India', 'pk': 'Pakistan',
        'au': 'Australia', 'nz': 'Newzealand', 'uk': 'Uk', 'gb': 'Uk', 'is': 'Iceland',
        'mt': 'Malta', 'il': 'Israel', 'uz': 'Uzbekistan', 'tj': 'Tajikistan', 'kg': 'Kyrgyzstan',
        'dk': 'Denmark', 'se': 'Sweden', 'no': 'Norway', 'fi': 'Finland', 'id': 'Indonesia',
        'br': 'Brazil', 'mx': 'Mexico', 'co': 'Colombia', 'cl': 'Chile', 'pe': 'Peru',
        'uy': 'Uruguay', 've': 'Venezuela', 'ec': 'Ecuador', 'bo': 'Bolivia', 'py': 'Paraguay',
        'cr': 'Costarica', 'pa': 'Panama', 'do': 'Dominicanrepublic', 'jm': 'Jamaica',
        'pr': 'Puertorico', 'ng': 'Nigeria', 'ke': 'Kenya', 'gh': 'Ghana', 'ma': 'Morocco',
        'tn': 'Tunisia', 'dz': 'Algeria', 'ly': 'Libya'
    }

    for p in PAESI_STANDARD:
        URLS_EPG_DINAMICI.add(f"https://iptv-epg.org/files/epg-{p}.xml")
        URLS_EPG_DINAMICI.add(f"https://epg.lat/files/{p}.xml.gz")
        URLS_EPG_DINAMICI.add(f"https://epgshare01.online/epgshare01/epg_ripper_{p.upper()}1.xml.gz")
        URLS_EPG_DINAMICI.add(f"https://free-epg.de/api/epg/{p}.xml.gz")
        URLS_EPG_DINAMICI.add(f"https://iptv-org.github.io/iptv/countries/{p}.m3u")
        nome_open = open_epg_mappatura.get(p, p)
        URLS_EPG_DINAMICI.add(f"https://www.open-epg.com/files/{nome_open}.xml.gz")

    for p_code, cartella_name in globetv_mappatura.items():
        for i in range(1, 7):
            URLS_EPG_DINAMICI.add(f"https://raw.githubusercontent.com/globetvapp/epg/main/{cartella_name}/{cartella_name.lower()}{i}.xml")

    URLS_EPG_DINAMICI.update([
        "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
        "https://iptv-org.github.io/iptv/index.country.m3u",
        "https://epg.pw/xmltv/epg.xml.gz",
        "https://iptvx.one/EPG",
        "https://gist.githubusercontent.com/guiworldtv2/0b805e7f86f55c8c5ffc37e51c8990ce/raw/1bbb74431ee1b0fbba0efa2da048444be29273ea/epg%2520master.xml.gz",
        "https://raw.githubusercontent.com/globetvapp/epg/main/Sports/sports1.xml.gz",
        "https://raw.githubusercontent.com/globetvapp/epg/main/Sports/sports2.xml.gz",
        "https://raw.githubusercontent.com/globetvapp/epg/main/Sports/sports3.xml.gz",
        "http://epg.one/ru.xml.gz",
        "http://epg.one/ru2.xml.gz",
        "http://epg.one/epg.xml.gz",
        "https://tvprofil.net/xmltv/data/epg_tvprofil.net.xml"
    ])


_PAROLE_DA_SCARTARE_EPG = [
    "journal", "news", "jt ", "le 20h", "informazione", "cronaca", "edition", "bulletin",
    "notiziario", "tg", "meteo", "weather", "documentary", "documentario", "film", "serie",
    "show", "talk", "magazine", "tribunal", "court", "process", "новости", "wiadomosci",
    "haber", "deltio", "interview"
] + PAROLE_ESCLUSE_REPLICHE

_CANALI_SUBSTRING_BLOCCATI = (
    "news", "cnews", "court", "cnn", "bbc", "bmt", "tagesschau", "w24", "rt"
)


def analizza_epg_stream(content_bytes, valid_channel_ids, source_label="Sorgente Sconosciuta"):
    programmi_locali = []
    try:
        channel_id_to_name = {}
        for _, elem in ET.iterparse(io.BytesIO(content_bytes), events=("end",)):
            if elem.tag == 'channel':
                ch_id = elem.get('id')
                if ch_id:
                    display_name_el = elem.find('display-name')
                    if display_name_el is not None and display_name_el.text:
                        ch_name = _applica_alias_speciali(normalizza_nome_canale(display_name_el.text.strip()))
                        if not is_blacklisted(ch_name):
                            channel_id_to_name[ch_id] = ch_name
                            valid_channel_ids.add(ch_id)
                            valid_channel_ids.add(ch_name)
                            valid_channel_ids.add(normalizza_testo(ch_name))
                            if is_prime_video_channel(ch_name):
                                valid_channel_ids.add("Prime Video")
            elem.clear()

        for _, elem in ET.iterparse(io.BytesIO(content_bytes), events=("end",)):
            if elem.tag == 'programme':
                ch = elem.get('channel') or ""
                ch_lookup = _applica_alias_speciali(normalizza_nome_canale(channel_id_to_name.get(ch, ch)))
                ch_lookup_lower = ch_lookup.lower()

                if is_blacklisted(ch_lookup) or any(b in ch_lookup_lower for b in _CANALI_SUBSTRING_BLOCCATI):
                    elem.clear()
                    continue

                if "okko" in ch_lookup_lower or "окко" in ch_lookup_lower:
                    ch_lookup = "Okko Futbol" if ("football" in ch_lookup_lower or "футбол" in ch_lookup_lower or "prajm" in ch_lookup_lower) else "Okko Sport"
                    ch_lookup_lower = ch_lookup.lower()

                title_el = elem.find('title')
                title_text = title_el.text if (title_el is not None and title_el.text) else ""
                title_norm = normalizza_testo(title_text)
                desc_el = elem.find('desc')
                desc_text = desc_el.text if (desc_el is not None and desc_el.text) else ""
                desc_norm = normalizza_testo(desc_text)

                is_prime_context = (
                    is_prime_video_channel(ch_lookup)
                    or is_prime_video_channel(title_text)
                    or is_prime_video_channel(desc_text)
                )

                if (
                    ch in TUTTI_I_TARGET_PW
                    or ch in ("5Sport.il", "QazSport.kz")
                    or ch in valid_channel_ids
                    or ch_lookup in valid_channel_ids
                    or normalizza_testo(ch_lookup) in valid_channel_ids
                    or ch.isdigit()
                    or "okko" in ch_lookup_lower
                    or "окко" in ch_lookup_lower
                    or is_prime_context
                ):
                    if ch in TUTTI_I_TARGET_PW:
                        ch_lookup = normalizza_nome_canale(TUTTI_I_TARGET_PW[ch])
                    elif ch == "5Sport.il":
                        ch_lookup = "5Sport"
                    elif ch == "QazSport.kz":
                        ch_lookup = "QazSport"
                    elif is_prime_video_channel(ch_lookup):
                        ch_lookup = "Prime Video"

                    if title_text and elem.get('start') and not any(scarto in title_norm for scarto in _PAROLE_DA_SCARTARE_EPG):
                        programmi_locali.append({
                            'channel': ch,
                            'channel_name': ch_lookup,
                            'title': title_norm,
                            'desc': desc_norm,
                            'start': elem.get('start'),
                            'source': source_label
                        })
                elem.clear()
    except ET.ParseError as e:
        _log_una_volta(f"parse_err:{source_label}", f"   ⚠️ Parse XML incompleto su {source_label}: {e}")
    except Exception as e:
        _log_una_volta(f"stream_err:{source_label}", f"   ⚠️ Errore lettura EPG su {source_label}: {e}")
    return programmi_locali


def scarica_e_processa_paese(paese, valid_channel_ids):
    label = f"IPTV-EPG Paese [{paese.upper()}]"
    try:
        res = HTTP_SESSION.get(f"https://iptv-epg.org/files/epg-{paese}.xml", headers=HEADERS, timeout=15)
        if res.status_code == 200 and res.content:
            return analizza_epg_stream(res.content, valid_channel_ids, source_label=label)
        if res.status_code != 200:
            _log_una_volta(f"paese_http:{paese}:{res.status_code}", f"   ⚠️ {label}: HTTP {res.status_code}")
    except Exception as e:
        _log_una_volta(f"paese_exc:{paese}", f"   ⚠️ {label}: timeout/errore rete ({type(e).__name__})")
    return []


def scarica_e_processa_gz_dinamico(url_dinamico, valid_channel_ids):
    label = f"URL Dinamico ({url_dinamico[:45]}...)"
    try:
        res = HTTP_SESSION.get(url_dinamico, headers=HEADERS, timeout=20)
        if res.status_code != 200:
            _log_una_volta(f"dyn_http:{url_dinamico}:{res.status_code}", f"   ⚠️ {label}: HTTP {res.status_code}")
            return []
        if ".m3u" in url_dinamico:
            analizza_m3u_esteso(res.text, valid_channel_ids)
            return []
        if not res.content:
            return []
        xml_content = gzip.decompress(res.content) if res.content[:2] == b'\x1f\x8b' else res.content
        return analizza_epg_stream(xml_content, valid_channel_ids, source_label=label)
    except Exception as e:
        _log_una_volta(f"dyn_exc:{url_dinamico}", f"   ⚠️ {label}: timeout/errore ({type(e).__name__})")
    return []


def _attendi_passo_epg_pw(min_interval=0.18):
    global _EPG_PW_LAST_CALL_TS
    with _EPG_PW_PACE_LOCK:
        now = time.monotonic()
        delta = now - _EPG_PW_LAST_CALL_TS
        if delta < min_interval:
            time.sleep(min_interval - delta)
        _EPG_PW_LAST_CALL_TS = time.monotonic()


def _sembra_xml_valido(content_bytes):
    if not content_bytes or len(content_bytes) < 120:
        return False
    testa = content_bytes.lstrip()[:200].lower()
    if testa.startswith(b"<!doctype html") or testa.startswith(b"<html"):
        return False
    return b"<programme" in content_bytes or b"<tv" in content_bytes


def _ottieni_xml_epg_pw(ch_id, data_partita_str, timeout=15, force_retry=False):
    cache_key = (data_partita_str, str(ch_id))
    with _EPG_PW_CACHE_LOCK:
        if not force_retry and cache_key in _EPG_PW_XML_CACHE:
            return _EPG_PW_XML_CACHE[cache_key]

    url = f"https://epg.pw/api/epg.xml?lang=en&timezone=VVRD&date={data_partita_str}&channel_id={ch_id}"

    for tentativo in range(2):
        _attendi_passo_epg_pw(min_interval=0.18 if tentativo == 0 else 0.65)
        try:
            res = HTTP_SESSION.get(url, headers=HEADERS, timeout=timeout)
            if res.status_code == 429:
                time.sleep(1.2 * (tentativo + 1))
                continue
            if res.status_code == 200 and _sembra_xml_valido(res.content):
                with _EPG_PW_CACHE_LOCK:
                    _EPG_PW_XML_CACHE[cache_key] = res.content
                    _EPG_PW_FAILED_KEYS.discard(cache_key)
                return res.content
        except Exception:
            if tentativo == 0:
                time.sleep(0.5)

    with _EPG_PW_CACHE_LOCK:
        _EPG_PW_FAILED_KEYS.add(cache_key)
    return b""


def scarica_singolo_id_pw(args):
    ch_id, ch_name, data_partita_str, force_retry = args
    if is_blacklisted(ch_name):
        return []
    xml_bytes = _ottieni_xml_epg_pw(ch_id, data_partita_str, timeout=15, force_retry=force_retry)
    if not xml_bytes:
        return []
    progs = analizza_epg_stream(
        xml_bytes,
        {ch_id, ch_name, normalizza_testo(ch_name)},
        source_label=f"EPG.PW (ID: {ch_id})"
    )
    nome_norm = normalizza_nome_canale(ch_name)
    for p in progs:
        p['channel_name'] = nome_norm
    return progs


def scarica_epg_mirato_per_data(data_partita_str, ids_subset=None, force_retry=False):
    mappa_ids = ids_subset if ids_subset is not None else TUTTI_I_TARGET_PW
    args_list = [(ch_id, ch_name, data_partita_str, force_retry) for ch_id, ch_name in mappa_ids.items()]
    programmi_mirati = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(scarica_singolo_id_pw, arg) for arg in args_list]
        for future in as_completed(futures):
            progs = future.result()
            if progs:
                programmi_mirati.extend(progs)
    return programmi_mirati


def scarica_tutti_gli_epg(date_str_list):
    global PROGRAMMI_EPG
    valid_channel_ids = set(TUTTI_I_TARGET_PW.keys())
    valid_channel_ids.update({"5Sport.il", "QazSport.kz", "Prime Video", "prime video"})

    for nome, info in INFO_CANALI.items():
        if not is_blacklisted(nome):
            if info.get("id"):
                valid_channel_ids.add(str(info.get("id")))
            valid_channel_ids.add(normalizza_testo(nome))
            valid_channel_ids.add(nome)

    urls_uniche = list(dict.fromkeys(URLS_EPG_DINAMICI))

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(scarica_e_processa_paese, p, valid_channel_ids) for p in PAESI_STANDARD]
        futures.extend(executor.submit(scarica_e_processa_gz_dinamico, u, valid_channel_ids) for u in urls_uniche)
        for future in as_completed(futures):
            risultati = future.result()
            if risultati:
                PROGRAMMI_EPG.extend(risultati)

    for data_str in sorted(set(date_str_list)):
        progs_mirati = scarica_epg_mirato_per_data(data_str, force_retry=False)
        if progs_mirati:
            PROGRAMMI_EPG.extend(progs_mirati)

    _log(f"Totale programmi salvati in memoria (inclusi flussi TV aggiuntivi): {len(PROGRAMMI_EPG)}")


def pulisci_nome(nome):
    return (
        nome.replace("Football Club Internazionale Milano", "Inter")
            .replace("Internazionale Milano", "Inter")
            .replace("FC Inter", "Inter")
            .replace("Internazionale", "Inter")
    )


# ==========================================
# INTEGRAZIONE CALENDARIO FOTMOB ICS (ANTI-DOPPIONI)
# ==========================================
def _dt_to_utc(dt_val):
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)
    return datetime(dt_val.year, dt_val.month, dt_val.day, 0, 0, tzinfo=timezone.utc)


def _is_doppione_partita(ora_utc, partite_esistenti, tolleranza_ore=4):
    for p in partite_esistenti:
        p_utc = p['ora_utc']
        if p_utc.date() == ora_utc.date():
            return True
        if abs((p_utc - ora_utc).total_seconds()) <= tolleranza_ore * 3600:
            return True
    return False


def recupera_partite_da_fotmob(url_fotmob, partite_esistenti):
    nuove_partite = []
    if not url_fotmob:
        return nuove_partite

    url_clean = url_fotmob.strip()
    if "cid=" in url_clean:
        url_clean = url_clean.split("cid=", 1)[1]
    if url_clean.lower().startswith("webcal://"):
        url_clean = "https://" + url_clean[9:]

    try:
        resp = HTTP_SESSION.get(url_clean, headers=HEADERS, timeout=12)
        if resp.status_code != 200 or not resp.text:
            _log(f"Calendario FotMob non disponibile (status {resp.status_code}).")
            return nuove_partite

        cal = Calendar.from_ical(resp.text)
        adesso = datetime.now(timezone.utc)

        for component in cal.walk('vevent'):
            summary_raw = str(component.get('summary', '')).strip()
            if not summary_raw:
                continue

            summary_norm = normalizza_testo(summary_raw)
            if any(pe in summary_norm for pe in PAROLE_ESCLUSE_REPLICHE):
                continue

            dtstart_prop = component.get('dtstart')
            if not dtstart_prop:
                continue

            ora_utc = _dt_to_utc(dtstart_prop.dt)
            if ora_utc.date() < adesso.date():
                continue

            if _is_doppione_partita(ora_utc, partite_esistenti + nuove_partite):
                continue

            nome_pulito = pulisci_nome(summary_raw)
            nome_pulito = re.sub(r'^[^\w\s]+\s*', '', nome_pulito).strip()

            home, away = "Inter", nome_pulito
            for sep in (" vs ", " - ", " v "):
                if sep in nome_pulito:
                    parti = nome_pulito.split(sep, 1)
                    home = pulisci_nome(parti[0].strip())
                    away = pulisci_nome(parti[1].strip())
                    break

            testo_completo = f"{summary_raw} {str(component.get('description', ''))}".lower()
            if "supercoppa" in testo_completo or "super cup" in testo_completo:
                comp_label = "Supercoppa Italiana"
            elif "coppa italia" in testo_completo or "italian cup" in testo_completo:
                comp_label = "Coppa Italia"
            else:
                comp_label = "FotMob Calendar"

            nuove_partite.append({
                'ora_utc': ora_utc,
                'name': nome_pulito if nome_pulito else f"{home} vs {away}",
                'competizione': comp_label,
                'home': home,
                'away': away
            })

        if nuove_partite:
            _log(f"Aggiunte {len(nuove_partite)} partite mancanti da FotMob.")
    except Exception as e:
        _log(f"Errore lettura calendario FotMob: {e}")

    return nuove_partite


# ==========================================
# FONTI WEB AGGIUNTIVE: PAGINE SQUADRA INTER, LIVE-FOOTBALLONTV & ODDALERTS
# ==========================================
_RUOLO_O_RUMORE_WEB = {
    "tv", "live", "stream", "streaming", "watch", "channel", "channels",
    "schedule", "fixtures", "results", "standings", "table", "news",
    "preview", "prediction", "predictions", "odds", "stats", "lineups",
    "kickoff", "ko", "serie a", "champions league", "coppa italia", "supercoppa",
    "inter", "internazionale", "inter milan", "home", "away", "vs", "v",
    "previous slide", "next slide", "show broadcasts", "read more", "read less",
    "on tv", "football", "league phase", "uefa champions league", "tonight",
    "teams", "view all teams", "premier league", "scottish premiership",
    "uk", "us", "usa", "italy", "spain", "france", "germany", "portugal",
    "poland", "greece", "croatia", "serbia", "bulgaria", "romania", "netherlands"
}

_PATTERN_RUMORE_WEB = [
    r'\b(previous|next)\s+slide\b',
    r'\b(show\s+broadcasts|read\s+(more|less)|see\s+every\s+.*game|live\s+football\s+on\s+tv|view\s+all\s+teams)\b',
    r'\b(utc|gmt|cet|cest|est|pst)\b',
    r'\b\d{1,2}:\d{2}\b',
    r'\b(mon|tue|wed|thu|fri|sat|sun)\b',
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
    r'\b(1st|2nd|3rd|\d+th)\b',
    r'\blogo\b',
    r'\b(prediction|predictions|football|premier\s+league|premiership|serie\s+a|coppa\s+italia|champions\s+league|tonight|teams|dazn)\b',
    r'\b(v|vs)\b'
]
_REGEX_RUMORE_WEB = [re.compile(pat, re.IGNORECASE) for pat in _PATTERN_RUMORE_WEB]


def _parole_avversario_match(home_team, away_team):
    h_norm = normalizza_testo(home_team)
    avversario = away_team if "inter" in h_norm else home_team
    av_norm = normalizza_testo(avversario)
    stop = {"fc", "ac", "as", "ssc", "us", "cf", "cd", "sc", "calcio", "inter", "internazionale", "milan", "vfb", "rb", "fk", "sk"}
    return [p for p in av_norm.split() if len(p) > 2 and p not in stop]


def _estrai_emittenti_da_contenitore(el, av_parole):
    trovati = []
    if not el:
        return trovati

    candidati_testo = []
    for sub in el.find_all(["a", "span", "li", "img", "td"]):
        if sub.name == "img":
            for val in ((sub.get("alt") or "").strip(), (sub.get("title") or "").strip()):
                if val and 2 <= len(val) <= 32:
                    candidati_testo.append(val)
        else:
            if len(sub.find_all(["a", "div", "tr", "li", "table"])) > 2:
                continue
            txt = " ".join(sub.get_text(" ", strip=True).split())
            if txt and 2 <= len(txt) <= 32:
                candidati_testo.append(txt)

    av_regexes = [re.compile(rf'\b{re.escape(ap)}\b') for ap in av_parole]

    for raw in candidati_testo:
        low = " ".join(raw.lower().strip().split())
        if not low or low in _RUOLO_O_RUMORE_WEB or _is_rumore_ui_web(low):
            continue
        if any(pe in low for pe in PAROLE_ESCLUSE_REPLICHE):
            continue
        if any(rx.search(low) for rx in _REGEX_RUMORE_WEB):
            continue
        low_norm = normalizza_testo(low)
        if _is_rumore_ui_web(low_norm):
            continue
        if any(arx.search(low_norm) for arx in av_regexes):
            continue
        if re.fullmatch(r'[\d\s:/\-\+\.]+', low):
            continue

        c_pulito = pulisci_etichetta_canale(raw)
        if c_pulito and len(c_pulito) >= 2 and not is_blacklisted(c_pulito):
            c_low = c_pulito.lower()
            if (
                c_low not in _RUOLO_O_RUMORE_WEB
                and not _is_rumore_ui_web(c_low)
                and not any(rx.search(c_low) for rx in _REGEX_RUMORE_WEB)
                and c_pulito not in trovati
            ):
                trovati.append(c_pulito)
    return trovati


def cerca_canali_pagine_squadra_inter(home_team, away_team, data_partita):
    canali_trovati = []
    av_parole = _parole_avversario_match(home_team, away_team)
    av_regexes = [re.compile(rf'\b{re.escape(ap)}\b') for ap in av_parole]
    data_str = data_partita.strftime('%Y-%m-%d') if isinstance(data_partita, datetime) else str(data_partita)[:10]

    pagine_squadra = [
        "https://whichtvchannel.com/football/teams/inter-milan",
        "https://www.wheresthematch.com/Football/Inter-Milan.asp"
    ]

    for url in pagine_squadra:
        try:
            resp = HTTP_SESSION.get(url, headers=WEB_SCRAPE_HEADERS, timeout=11)
            if resp.status_code != 200 or not resp.text:
                _log_una_volta(f"web_http:{url}:{data_str}:{resp.status_code}", f"   ⚠️ Pagina Squadra ({url}): HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for blocco in soup.find_all(["tr", "li", "article"]):
                testo_blocco = normalizza_testo(blocco.get_text(" ", strip=True))
                if "inter" not in testo_blocco or len(testo_blocco) > 900:
                    continue
                if av_regexes and not any(arx.search(testo_blocco) for arx in av_regexes):
                    continue

                for c in _estrai_emittenti_da_contenitore(blocco, av_parole):
                    if c not in canali_trovati:
                        _log(f"   ✅ CANALE AGGIUNTO da Pagina Squadra ({url}): {c} [{data_str}]")
                        canali_trovati.append(c)
        except Exception as e:
            _log_una_volta(f"web_exc:{url}:{data_str}", f"   ⚠️ Pagina Squadra ({url}): timeout/errore ({type(e).__name__})")

    return canali_trovati


def cerca_canali_live_footballontv(home_team, away_team, data_partita):
    canali_trovati = []
    av_parole = _parole_avversario_match(home_team, away_team)
    av_regexes = [re.compile(rf'\b{re.escape(ap)}\b') for ap in av_parole]

    try:
        dt_obj = data_partita if isinstance(data_partita, datetime) else datetime.now(timezone.utc)
        anchor = dt_obj.strftime("%Y%b%d")
        base_url = "https://www.live-footballontv.com/live-italian-football-on-tv.html"

        for url in (f"{base_url}#{anchor}", base_url):
            resp = HTTP_SESSION.get(url, headers=WEB_SCRAPE_HEADERS, timeout=11)
            if resp.status_code != 200 or not resp.text:
                _log_una_volta(f"lfot_http:{anchor}:{resp.status_code}", f"   ⚠️ Live-FootballOnTV: HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            target_container = soup.find(id=anchor) or soup.find("a", attrs={"name": anchor}) or soup

            for blocco in target_container.find_all(["tr", "li", "article", "p"]):
                testo_blocco = normalizza_testo(blocco.get_text(" ", strip=True))
                if "inter" not in testo_blocco or len(testo_blocco) > 900:
                    continue
                if av_regexes and not any(arx.search(testo_blocco) for arx in av_regexes):
                    continue

                for c in _estrai_emittenti_da_contenitore(blocco, av_parole):
                    if c not in canali_trovati:
                        _log(f"   ✅ CANALE AGGIUNTO da Live-FootballOnTV: {c}")
                        canali_trovati.append(c)

            if canali_trovati:
                break
    except Exception as e:
        _log_una_volta(f"lfot_exc:{data_partita}", f"   ⚠️ Live-FootballOnTV: timeout/errore ({type(e).__name__})")

    return canali_trovati


def cerca_canali_oddalerts(home_team, away_team, data_partita):
    canali_trovati = []
    av_parole = _parole_avversario_match(home_team, away_team)
    av_regexes = [re.compile(rf'\b{re.escape(ap)}\b') for ap in av_parole]
    dt_obj = data_partita if isinstance(data_partita, datetime) else datetime.now(timezone.utc)
    data_iso = dt_obj.strftime("%Y-%m-%d")

    chiave_sole = _chiave_match_sole(f"{home_team} vs {away_team}", dt_obj)
    CANALI_SOLE_ODDALERTS_PER_MATCH.setdefault(chiave_sole, set())

    def _aggiungi_se_in_liste(cand):
        if _is_rumore_ui_web(cand):
            return
        c_pulito = pulisci_etichetta_canale(cand)
        if not c_pulito or is_blacklisted(c_pulito) or _is_rumore_ui_web(c_pulito) or not _canale_in_liste_iptv(c_pulito):
            return
        if c_pulito not in canali_trovati:
            canali_trovati.append(c_pulito)
        CANALI_SOLE_ODDALERTS_PER_MATCH[chiave_sole].add(c_pulito)

    pagine_indice = [
        f"https://www.oddalerts.com/livescores?date={data_iso}",
        "https://www.oddalerts.com/livescores",
        "https://www.oddalerts.com/tv-guide/italy"
    ]
    link_match_trovati = []

    try:
        for idx_url in pagine_indice:
            resp = HTTP_SESSION.get(idx_url, headers=WEB_SCRAPE_HEADERS, timeout=11)
            if resp.status_code != 200 or not resp.text:
                _log_una_volta(f"oa_http:{idx_url}:{resp.status_code}", f"   ⚠️ OddAlerts ({idx_url}): HTTP {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if "/livescores/" in href:
                    testo_link = normalizza_testo(a_tag.get_text(" ", strip=True))
                    href_norm = normalizza_testo(href)
                    ha_inter = ("inter" in href_norm) or ("inter" in testo_link)
                    ha_avv = any(arx.search(f"{href_norm} {testo_link}") for arx in av_regexes) if av_regexes else False
                    if ha_inter and (ha_avv or not av_regexes):
                        full_url = urljoin("https://www.oddalerts.com", href)
                        if full_url not in link_match_trovati:
                            link_match_trovati.append(full_url)

            if "/tv-guide/" in idx_url:
                for blocco in soup.find_all(["tr", "li", "article"]):
                    testo_blocco = normalizza_testo(blocco.get_text(" ", strip=True))
                    if "inter" in testo_blocco and len(testo_blocco) < 700 and (not av_regexes or any(arx.search(testo_blocco) for arx in av_regexes)):
                        for c in _estrai_emittenti_da_contenitore(blocco, av_parole):
                            _aggiungi_se_in_liste(c)

            if link_match_trovati:
                break

        for match_url in link_match_trovati[:2]:
            resp_m = HTTP_SESSION.get(match_url, headers=WEB_SCRAPE_HEADERS, timeout=11)
            if resp_m.status_code != 200 or not resp_m.text:
                continue

            soup_m = BeautifulSoup(resp_m.text, "html.parser")
            for sez in soup_m.find_all(["section", "div", "table", "ul"]):
                txt_sez = normalizza_testo(sez.get_text(" ", strip=True))
                if len(txt_sez) < 1600 and any(k in txt_sez for k in ("tv channel", "where to watch", "broadcast", "live stream", "canali", "tv guide")):
                    for c in _estrai_emittenti_da_contenitore(sez, av_parole):
                        _aggiungi_se_in_liste(c)

        for c in canali_trovati:
            _log(f"   ✅ CANALE AGGIUNTO da OddAlerts (presente in liste IPTV): {c}")
    except Exception as e:
        _log_una_volta(f"oa_exc:{data_iso}", f"   ⚠️ OddAlerts: timeout/errore ({type(e).__name__})")

    return canali_trovati


# ==========================================
# CONTROLLO MIRATO UNIVERSALE CON FILTRO ORARIO (±6 ORE) E REPLICHE
# ==========================================
_COPPE_KEYWORDS = ("champions", "ucl", "serie a", "coppa italia", "supercoppa")
TOLLERANZA_ORARIA_SECONDI = 21600  # ±6 ore


def _controlla_singolo_canale_mirato(args):
    data_str, ch_id, ch_name, inter_regexes, av_regexes, match_ora_utc, force_retry = args
    ch_name_norm = normalizza_nome_canale(ch_name)
    if is_blacklisted(ch_name_norm):
        return []

    xml_bytes = _ottieni_xml_epg_pw(ch_id, data_str, timeout=15, force_retry=force_retry)
    if not xml_bytes:
        return []

    trovati = []
    try:
        progs = analizza_epg_stream(
            xml_bytes,
            {ch_id, ch_name_norm, normalizza_testo(ch_name_norm)},
            source_label=f"EPG.PW Mirato (ID {ch_id})"
        )
        for p in progs:
            title = p['title']
            title_lower = title.lower()
            if any(pe in title_lower for pe in PAROLE_ESCLUSE_REPLICHE):
                continue

            if match_ora_utc and p.get('start'):
                prog_start = _parsa_start_epg_utc(p['start'])
                if prog_start and abs((prog_start - match_ora_utc).total_seconds()) > TOLLERANZA_ORARIA_SECONDI:
                    continue

            contiene_inter = any(rx.search(title) for rx in inter_regexes)
            contiene_avversario = any(rx.search(title) for rx in av_regexes) if av_regexes else False

            if contiene_inter and (contiene_avversario or any(coppa in title for coppa in _COPPE_KEYWORDS)):
                c_pulito = pulisci_etichetta_canale(ch_name_norm)
                if c_pulito and not is_blacklisted(c_pulito) and all(item[0] != c_pulito for item in trovati):
                    trovati.append((c_pulito, title, ch_id))
    except Exception:
        pass
    return trovati


def controllo_mirato_epg_pw(date_str_list, home_team, away_team, match_ora_utc=None):
    canali_trovati_extra = []
    inter_keywords = ["inter", "internazionale", "интер", "ιντερ"]
    inter_regexes = [re.compile(rf'\b{k}\b') for k in inter_keywords]
    av_norm = normalizza_testo(away_team if "inter" in normalizza_testo(home_team) else home_team)
    av_parole = [p for p in av_norm.split() if len(p) > 2 and p not in inter_keywords]
    av_regexes = [re.compile(rf'\b{re.escape(ap)}\b') for ap in av_parole]
    date_ordinate = sorted(set(date_str_list))

    def _esegui_lotto(mappa_ids, force_retry):
        tasks = [
            (data_str, ch_id, ch_name, inter_regexes, av_regexes, match_ora_utc, force_retry)
            for data_str in date_ordinate
            for ch_id, ch_name in mappa_ids.items()
        ]
        if not tasks:
            return
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_controlla_singolo_canale_mirato, t) for t in tasks]
            for future in as_completed(futures):
                for c_pulito, title, ch_id in future.result():
                    if c_pulito not in canali_trovati_extra:
                        _log(f"   ✅ CANALE AGGIUNTO: {c_pulito} (grazie a '{title}' | Fonte: EPG.PW ID {ch_id})")
                        canali_trovati_extra.append(c_pulito)

    # Primo giro su tutti i canali target di epg.pw
    _esegui_lotto(TUTTI_I_TARGET_PW, force_retry=False)

    # Secondo giro di recupero per tutti gli ID target che non hanno ancora portato risultato
    canali_gia_trovati_lower = {c.lower() for c in canali_trovati_extra}
    ids_da_riprovare = {
        ch_id: ch_name
        for ch_id, ch_name in TUTTI_I_TARGET_PW.items()
        if normalizza_nome_canale(ch_name).lower() not in canali_gia_trovati_lower
    }
    if ids_da_riprovare:
        _log(f"   ↻ Recupero mirato EPG.PW su {len(ids_da_riprovare)} ID non ancora agganciati...")
        time.sleep(0.8)
        _esegui_lotto(ids_da_riprovare, force_retry=True)

    return canali_trovati_extra


# ==========================================
# INTEGRAZIONE THESPORTSDB V1
# ==========================================
def cerca_canali_thesportsdb(home_team, away_team, data_partita):
    canali_tsdb = []
    try:
        data_str = data_partita.strftime('%Y-%m-%d')
        url_search = f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={data_str}&s=Soccer"
        response = HTTP_SESSION.get(url_search, headers=HEADERS, timeout=11)
        if response.status_code == 200:
            events = (response.json() or {}).get('events') or []
            h_low = home_team.lower()
            a_low = away_team.lower()

            for ev in events:
                h_ev = (ev.get('strHomeTeam') or '').lower()
                a_ev = (ev.get('strAwayTeam') or '').lower()
                if (h_low in h_ev or h_ev in h_low) and (a_low in a_ev or a_ev in a_low):
                    event_id = ev.get('idEvent')
                    if event_id:
                        res_tv = HTTP_SESSION.get(
                            f"https://www.thesportsdb.com/api/v1/json/123/lookuptv.php?id={event_id}",
                            headers=HEADERS,
                            timeout=11
                        )
                        if res_tv.status_code == 200:
                            channels = (res_tv.json() or {}).get('tvevents') or []
                            for ch in channels:
                                nome_canale = normalizza_nome_canale(ch.get('strChannel') or "")
                                if nome_canale and not is_blacklisted(nome_canale) and nome_canale not in canali_tsdb:
                                    _log(f"   ✅ CANALE AGGIUNTO da TheSportsDB: {nome_canale}")
                                    canali_tsdb.append(nome_canale)
    except Exception as e:
        _log(f"Errore integrazione TheSportsDB: {e}")

    return canali_tsdb


def cerca_canali_per_partita_ottimizzato(date_utc, home_team, away_team):
    canali_trovati = []
    if not PROGRAMMI_EPG:
        return canali_trovati

    h_norm = normalizza_testo(home_team)
    inter_keywords = ["inter", "internazionale", "интер"]
    inter_regexes = [re.compile(rf'\b{k}\b') for k in inter_keywords]
    parole_da_ignorare = {"ssc", "fc", "ac", "as", "calcio", "cd", "sad", "cf", "s.p.a."}

    avversario_full = away_team if ("inter" in h_norm or "интер" in h_norm) else home_team
    av_norm = normalizza_testo(avversario_full)
    av_parole = [p for p in av_norm.split() if p not in parole_da_ignorare and not p.isdigit() and p not in inter_keywords]
    av_regexes = [re.compile(rf'\b{re.escape(ap)}\b') for ap in av_parole]

    tutti_i_validi = (
        TUTTI_I_CANALI_BLU
        .union(TUTTI_I_CANALI_NERI)
        .union(TUTTI_I_CANALI_GIALLI)
        .union(TUTTI_I_CANALI_BIANCHI)
        .union(CANALI_TV_CLASSICI)
    )
    validi_precalc = []
    for nc in tutti_i_validi:
        if not is_blacklisted(nc):
            norm_nc = normalizza_testo(nc)
            if norm_nc:
                validi_precalc.append((nc, norm_nc))

    for prog in PROGRAMMI_EPG:
        ch_id = str(prog['channel'])
        ch_name = normalizza_nome_canale(prog.get('channel_name', ch_id))
        source_epg = prog.get('source', 'EPG Generale')

        if is_blacklisted(ch_name):
            continue

        title = prog['title']
        title_lower = title.lower()
        if any(pe in title_lower for pe in PAROLE_ESCLUSE_REPLICHE):
            continue

        contiene_inter = any(rx.search(title) for rx in inter_regexes)
        contiene_avversario = any(rx.search(title) for rx in av_regexes) if av_regexes else False
        match_trovato = contiene_inter and (
            contiene_avversario
            or any(coppa in title for coppa in ("champions", "ucl", "serie a", "coppa italia", "supercoppa", "liga"))
        )

        if not match_trovato:
            continue

        start_str = prog['start']
        if not start_str:
            continue

        prog_start = _parsa_start_epg_utc(start_str)
        if not prog_start:
            continue
        if abs((prog_start - date_utc).total_seconds()) > TOLLERANZA_ORARIA_SECONDI:
            continue

        desc_norm = prog.get('desc', '')
        c_uff = None
        ch_name_lower = ch_name.lower()

        if "5sport" in ch_name_lower or "sport 5" in ch_name_lower or "ספורט 5" in ch_name or ch_id == "5Sport.il":
            c_uff = "5Sport"
        elif "qazsport" in ch_name_lower or ch_id == "QazSport.kz":
            c_uff = "QazSport"
        elif "okko" in ch_name_lower or "окко" in ch_name_lower:
            c_uff = "Okko Futbol" if ("football" in ch_name_lower or "футбол" in ch_name_lower or "prajm" in ch_name_lower) else "Okko Sport"
        elif is_prime_video_channel(ch_name) or is_prime_video_channel(title) or is_prime_video_channel(desc_norm):
            c_uff = "Prime Video"
        elif ch_id in TUTTI_I_TARGET_PW:
            c_uff = normalizza_nome_canale(TUTTI_I_TARGET_PW[ch_id])
        elif ch_name and not ch_name.isdigit():
            c_uff = normalizza_nome_canale(ch_name)

        if c_uff:
            c_pulito = pulisci_etichetta_canale(c_uff)
            if c_pulito and c_pulito not in canali_trovati and not is_blacklisted(c_pulito):
                _log(f"   ✅ CANALE AGGIUNTO (Generale): {c_pulito} (Match '{title}' trovato su EPG | Fonte: {source_epg})")
                canali_trovati.append(c_pulito)

        norm_ch = normalizza_testo(ch_name)
        for nc, norm_nc in validi_precalc:
            if norm_nc == norm_ch or (len(norm_nc) > 2 and (norm_nc in norm_ch or norm_ch in norm_nc)):
                nc_pulito = pulisci_etichetta_canale(nc)
                if nc_pulito and nc_pulito not in canali_trovati and not is_blacklisted(nc_pulito):
                    _log(f"   ✅ CANALE AGGIUNTO (Mapping Lista): {nc_pulito} (Match '{title}' | Fonte: {source_epg})")
                    canali_trovati.append(nc_pulito)

    return canali_trovati


def _arricchisci_canali_partita(p, date_str_list):
    _log(f"\n🔍 Elaborazione match: {p['name']} ({p['ora_utc']})")
    canali_reali = cerca_canali_per_partita_ottimizzato(p['ora_utc'], p['home'], p['away'])

    fonti_extra = [
        controllo_mirato_epg_pw(date_str_list, p['home'], p['away'], p['ora_utc']),
        cerca_canali_thesportsdb(p['home'], p['away'], p['ora_utc']),
        cerca_canali_pagine_squadra_inter(p['home'], p['away'], p['ora_utc']),
        cerca_canali_live_footballontv(p['home'], p['away'], p['ora_utc']),
        cerca_canali_oddalerts(p['home'], p['away'], p['ora_utc']),
    ]
    for lista_canali in fonti_extra:
        for c in lista_canali:
            if c not in canali_reali:
                canali_reali.append(c)

    if not canali_reali:
        canali_reali = ["In attesa di programmazione ufficiale ⏳"]

    return {
        'ora_utc': p['ora_utc'],
        'name': p['name'],
        'competizione': p['competizione'],
        'canali': canali_reali
    }


def fetch_next_matches():
    all_matches = []
    url = f"https://api.football-data.org/v4/teams/{TEAM_ID}/matches?status=SCHEDULED,TIMED"

    try:
        response = HTTP_SESSION.get(url, headers=HEADERS, timeout=12)
        data = response.json()

        partite_da_analizzare = []
        adesso = datetime.now(timezone.utc)

        for match in data.get('matches', []):
            if match.get('competition', {}).get('code') not in COMPETITIONS:
                continue

            comp_name = match.get('competition', {}).get('name', 'Competizione')
            if "youth" in comp_name.lower() or "u19" in comp_name.lower():
                continue

            date_str = match.get('utcDate')
            if not date_str:
                continue

            date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date_utc.date() < adesso.date():
                continue

            if _is_doppione_partita(date_utc, partite_da_analizzare):
                continue

            home = pulisci_nome(match.get('homeTeam', {}).get('name', 'Casa'))
            away = pulisci_nome(match.get('awayTeam', {}).get('name', 'Ospite'))

            partite_da_analizzare.append({
                'ora_utc': date_utc,
                'name': f"{home} vs {away}",
                'competizione': comp_name,
                'home': home,
                'away': away
            })

        extra_fotmob = recupera_partite_da_fotmob(URL_CALENDARIO_FOTMOB, partite_da_analizzare)
        partite_da_analizzare.extend(extra_fotmob)

        partite_da_analizzare.sort(key=lambda x: x['ora_utc'])
        partite_da_analizzare = partite_da_analizzare[:6]

        if partite_da_analizzare:
            date_da_scaricare = {datetime.now(timezone.utc).strftime('%Y%m%d')}
            for p in partite_da_analizzare:
                date_da_scaricare.add(p['ora_utc'].strftime('%Y%m%d'))

            scarica_tutti_gli_epg(list(date_da_scaricare))
            date_list_sorted = sorted(date_da_scaricare)

            for p in partite_da_analizzare:
                all_matches.append(_arricchisci_canali_partita(p, date_list_sorted))

    except Exception as e:
        _log(f"Errore API partite: {e}")

    return all_matches


def _formatta_canale_per_gruppo(c, canali_sole_set):
    if _is_rumore_ui_web(c):
        return None, None
    c_pulito = pulisci_etichetta_canale(c)
    if not c_pulito or is_blacklisted(c_pulito) or _is_rumore_ui_web(c_pulito):
        return None, None

    c_lower = c_pulito.lower()

    if "5sport" in c_lower or "sport 5" in c_lower:
        c_pulito = "5Sport"
    elif "qazsport" in c_lower:
        c_pulito = "QazSport"
    elif "okko" in c_lower or "окко" in c_lower:
        c_pulito = "Okko Futbol" if ("football" in c_lower or "футбол" in c_lower or "prajm" in c_lower) else "Okko Sport"
    elif is_prime_video_channel(c_pulito):
        c_pulito = "Prime Video"

    if "In attesa" in c_pulito:
        return "arancione", f"⏳ {c_pulito}"
    if _is_eleven_sports_portugal(c_pulito):
        return "stelle", f"⭐ {c_pulito}"
    if _is_max_sport_1_4(c_pulito):
        return "tv", f"📺 {c_pulito}"
    if (
        c_pulito in CANALI_STELLE
        or c_lower in {"sport", "šport"}
        or "tnt sports" in c_lower
        or "okko" in c_lower
        or "setanta" in c_lower
        or "bein" in c_lower
        or c_pulito in {"5Sport", "QazSport", "5Sport Live", "5Sport Plus", "Sport", "Šport", "Sport 1", "Sport 1 Baltic", "Sport 2", "Sport 2 Baltic"}
    ):
        return "stelle", f"⭐ {c_pulito}"
    if (
        c_pulito in CANALI_TV_CLASSICI
        or any(tv_ok in c_pulito for tv_ok in ("Max Sport", "Nova Sport", "Polsat", "Cosmote", "Diema", "Digi Sport", "Prime Video", "Eleven Sports"))
    ):
        nome_formattato = "🎬 Prime Video" if is_prime_video_channel(c_pulito) else f"📺 {c_pulito}"
        return "tv", nome_formattato
    if c_pulito in TUTTI_I_CANALI_BLU:
        return "blu", f"🔵 {c_pulito}"
    if c_pulito in TUTTI_I_CANALI_NERI:
        return "nero", f"⚫ {c_pulito}"
    if c_pulito in TUTTI_I_CANALI_GIALLI:
        return "giallo", f"🟡 {c_pulito}"
    if c_pulito in TUTTI_I_CANALI_BIANCHI:
        return "bianco", f"⚪ {c_pulito}"
    if c_pulito in canali_sole_set or c in canali_sole_set:
        return "sole", f"☀️ {c_pulito}"
    return "arancione", f"🟠 {c_pulito}"


def _raggruppa_canali_match(p, fallback_vuoto):
    chiave_sole = _chiave_match_sole(p['name'], p['ora_utc'])
    canali_sole_set = CANALI_SOLE_ODDALERTS_PER_MATCH.get(chiave_sole, set())

    gruppi = {
        "tv": [],
        "stelle": [],
        "blu": [],
        "nero": [],
        "giallo": [],
        "bianco": [],
        "sole": [],
        "arancione": []
    }

    for c in p['canali']:
        gruppo, nome_formattato = _formatta_canale_per_gruppo(c, canali_sole_set)
        if gruppo and nome_formattato and nome_formattato not in gruppi[gruppo]:
            gruppi[gruppo].append(nome_formattato)

    righe_ordinate = (
        gruppi["tv"]
        + gruppi["stelle"]
        + gruppi["blu"]
        + gruppi["nero"]
        + gruppi["giallo"]
        + gruppi["bianco"]
        + gruppi["sole"]
        + gruppi["arancione"]
    )
    return righe_ordinate if righe_ordinate else [fallback_vuoto]


def _scrivi_se_modificato(percorso, contenuto_bytes):
    if os.path.exists(percorso):
        with open(percorso, 'rb') as existing:
            if existing.read() == contenuto_bytes:
                _log(f"Nessuna variazione di contenuto per {percorso} (scrittura saltata).")
                return False
    with open(percorso, 'wb') as f:
        f.write(contenuto_bytes)
    return True


def generate_ics(matches):
    cal = Calendar()
    cal.add('prodid', '-//Calendario Inter V89 EPG//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Inter TV Broadcasts')

    for p in matches:
        evento = Event()
        evento.add('summary', f"⚽ {p['name']}")
        evento.add('dtstart', p['ora_utc'])
        evento.add('dtend', p['ora_utc'] + timedelta(hours=2))

        righe_ordinate = _raggruppa_canali_match(p, "In attesa di programmazione ufficiale ⏳")
        canali_testo = "\n".join(righe_ordinate)
        evento.add('description', f"🏆 Competizione: {p['competizione']}\n\n📡 Canali TV:\n{canali_testo}")
        cal.add_component(evento)

    if _scrivi_se_modificato("inter_tv.ics", cal.to_ical()):
        _log("File ICS generato con successo e raggruppato per tipo.")


def generate_html_palinsesto(matches):
    cards = []
    for p in matches:
        ora_italiana = p['ora_utc'].astimezone(ZoneInfo("Europe/Rome"))
        ora_locale = ora_italiana.strftime('%d/%m/%Y alle %H:%M')

        righe_ordinate = _raggruppa_canali_match(p, "⏳ In attesa di programmazione ufficiale")
        canali_str = "\n".join(righe_ordinate)

        cards.append(f"""
        <div class="match-card">
            <div class="match-title">⚽ {p['name']}</div>
            <div class="match-date">📅 {ora_locale} | 🏆 {p['competizione']}</div>
            <div class="channels">{canali_str}</div>
        </div>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Palinsesto INTER</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚽</text></svg>">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        h1 {{ font-size: 1.5rem; text-align: center; margin-bottom: 20px; color: #38bdf8; }}
        .match-card {{ background: #1e293b; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        .match-title {{ font-size: 1.1rem; font-weight: bold; margin-bottom: 6px; }}
        .match-date {{ font-size: 0.9rem; color: #94a3b8; margin-bottom: 10px; }}
        .channels {{ font-size: 0.95rem; line-height: 1.5; white-space: pre-line; background: #0f172a; padding: 10px; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📺 Palinsesto INTER</h1>
{"".join(cards)}
    </div>
</body>
</html>
"""

    if _scrivi_se_modificato("index.html", html_content.encode("utf-8")):
        _log("Pagina HTML generata con successo (index.html).")


if __name__ == '__main__':
    carica_canali_esterni()
    matches = fetch_next_matches()
    generate_ics(matches)
    generate_html_palinsesto(matches)
