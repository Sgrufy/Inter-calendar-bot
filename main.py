def ottieni_prossime_partite():
    partite_trovate = []
    
    # Raccogliamo prima tutti gli eventi futuri da tutte le API
    tutti_gli_eventi = []
    for url_api in URLS_API:
        try:
            res = requests.get(url_api, timeout=10).json()
            events = res.get('events', [])
            
            # Identifica la competizione dall'URL
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
                        # Parsing UTC e aggiunta di 2 ore fisse per l'orario italiano corretto
                        date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        ora_partita = date_utc.astimezone() + timedelta(hours=2)
                        
                        # Filtriamo solo le partite che devono ancora iniziare (o in corso)
                        if ora_partita >= datetime.now().astimezone() - timedelta(hours=3):
                            
                            # Formattazione titolo con competizione
                            if " at " in name:
                                squadre = name.split(" at ")
                                avversaria = squadre[0] if "Inter" in squadre[1] else squadre[1]
                                match_nome = f"⚽ Inter - {avversaria}"
                            else:
                                match_nome = f"⚽ {name}"
                            
                            if competizione_nome:
                                match_nome += f" ({competizione_nome})"
                            
                            # Raccoglie i canali da ESPN per questa partita
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

    # Ordiniamo tutte le partite trovate in ordine cronologico (dalla più vicina)
    tutti_gli_eventi = sorted(tutti_gli_eventi, key=lambda x: x['data'])

    # Raccogliamo anche i canali Teleman (nota: Teleman di solito mostra la partita imminente)
    canali_teleman = cerca_tutti_i_canali_teleman()

    # Prendiamo le prime 3 partite in programma
    prossime_tre = tutti_gli_eventi[:3]

    risultati_finali = []
    for index, p in enumerate(prossime_tre):
        canali_partita = p['canali'].copy()
        
        # Se è la primissima partita (la più vicina), possiamo aggiungere anche i canali Teleman trovati
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
        # Fallback se non trova nulla
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

    with open("inter_tv.ics", 'wb'] as f:
        f.write(cal.to_ical())
