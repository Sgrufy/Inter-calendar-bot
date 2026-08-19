import main
import sys

def run_update():
    try:
        print("Avvio aggiornamento calendario Inter...")
        # Chiama le funzioni definite nel tuo file main.py
        matches = main.fetch_next_matches()
        main.generate_ics(matches)
        print("Aggiornamento completato.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento: {e}")
        sys.exit(1) # Forza l'exit code 1 per indicare un fallimento a GitHub

if __name__ == '__main__':
    run_update()
