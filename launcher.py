"""
Lanceur pour la version "application de bureau" (packagée en .exe).
Démarre le serveur Streamlit en arrière-plan et ouvre le navigateur
par défaut sur l'application.
"""
import os
import sys
import threading
import time
import webbrowser

def _open_browser():
    time.sleep(2.5)
    webbrowser.open("http://localhost:8501")

def main():
    # Se placer dans le dossier où se trouvent app.py / les CSV,
    # que le programme soit lancé en .py ou en .exe (PyInstaller).
    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS  # dossier temporaire créé par PyInstaller
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    threading.Thread(target=_open_browser, daemon=True).start()

    from streamlit.web import cli as stcli
    sys.argv = [
        "streamlit", "run", "app.py",
        "--server.headless=true",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
