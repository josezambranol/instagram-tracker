"""
==============================================================================
INSTAGRAM UNFOLLOWERS & FOLLOWERS TRACKER PRO (Terminal Edition)
Rastreador inteligente en consola de seguidos, seguidores, cuentas que no te
siguen de vuelta y comparador histórico de nuevos seguidores y unfollowers.
==============================================================================
"""

import os
import sys
import time
import json
import socket
import subprocess
import msvcrt
from datetime import datetime

# Garantizar compatibilidad completa con emojis y caracteres UTF-8 en terminales Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

INSTAGRAM_URL = "https://www.instagram.com/"
DEBUG_PORT = 9223
APP_ID = "936619743392459"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
LEGACY_RESULTADO = os.path.join(DATA_DIR, "legacy_resultado.json")
PROFILE_DIR = os.path.join(BASE_DIR, "chrome_session")


def print_banner():
    print("=" * 76)
    print("      📷 INSTAGRAM UNFOLLOWERS & FOLLOWERS TRACKER PRO 📷")
    print("=" * 76)
    print("  Rastreo en vivo por terminal | Historial de unfollowers y nuevos seguidores")
    print("  Conserva tu sesión activa en Chrome y no genera archivos TXT innecesarios.")
    print("=" * 76)
    print()


def is_port_open(port):
    """Comprueba si ya hay un navegador Chrome escuchando en el puerto de depuración."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.8)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_chrome_executable():
    """Localiza el ejecutable de Google Chrome en Windows."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return "chrome.exe"


def connect_or_launch_chrome():
    """
    Se conecta a una ventana de Chrome en el puerto 9223 o abre una nueva
    con el perfil local 'chrome_session' para mantener el inicio de sesión.
    """
    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    if is_port_open(DEBUG_PORT):
        print(f"[+] ¡Chrome abierto detectado en puerto {DEBUG_PORT}! Conectando...")
    else:
        print("[+] Abriendo ventana de Chrome persistente para Instagram...")
        chrome_exe = find_chrome_executable()

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            "--start-maximized",
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled",
            INSTAGRAM_URL,
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for _ in range(30):
            if is_port_open(DEBUG_PORT):
                break
            time.sleep(0.3)

    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def wait_for_instagram_session(driver):
    """
    Verifica si el usuario ha iniciado sesión en Instagram buscando la cookie 'ds_user_id'.
    """
    print("\n[🔍] Verificando sesión activa en Instagram...")
    driver.get(INSTAGRAM_URL)
    time.sleep(1.5)

    user_id = None
    for _ in range(30):
        try:
            cookies = driver.get_cookies()
            for c in cookies:
                if c.get("name") == "ds_user_id":
                    user_id = c.get("value")
                    break
            if user_id:
                break
        except Exception:
            pass
        time.sleep(1.0)

    if not user_id:
        print("  [!] Aún no has iniciado sesión en la ventana de Chrome de Instagram.")
        print("  👉 Inicia sesión con tu usuario/contraseña o Facebook en la ventana de Chrome.")
        print("     (Tu sesión quedará guardada de forma segura para las próximas veces).")
        print("  Esperando a que inicies sesión...", end="", flush=True)

        while not user_id:
            try:
                cookies = driver.get_cookies()
                for c in cookies:
                    if c.get("name") == "ds_user_id":
                        user_id = c.get("value")
                        break
            except Exception:
                pass
            if user_id:
                break
            print(".", end="", flush=True)
            time.sleep(2)
        print()

    print(f"  [✔] ¡Sesión activa detectada con éxito! (User ID: {user_id})")
    return user_id


def fetch_instagram_data(driver, user_id):
    """
    Ejecuta el script asíncrono para descargar las listas completas de seguidos y seguidores
    usando la API interna de Instagram Web desde el navegador.
    """
    print("\n" + "-" * 76)
    print("  🚀 CONSULTANDO DATOS EN INSTAGRAM WEB (API Directa)...")
    print("     Ritmo seguro de consulta para evitar rate limits temporales.")
    print("-" * 76)

    js_fetch = """
    const callback = arguments[arguments.length - 1];
    const userId = arguments[0];
    const appId = arguments[1];
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    async function fetchList(type) {
        let list = [];
        let nextMaxId = "";
        while (true) {
            const url = `https://www.instagram.com/api/v1/friendships/${userId}/${type}/?count=50${nextMaxId ? `&max_id=${nextMaxId}` : ""}`;
            const res = await fetch(url, {
                headers: {
                    "x-ig-app-id": appId,
                    "x-requested-with": "XMLHttpRequest"
                }
            });
            if (!res.ok) break;
            const data = await res.json();
            for (const u of (data.users || [])) {
                list.push({
                    username: u.username,
                    full_name: u.full_name || "",
                    is_verified: !!u.is_verified,
                    is_private: !!u.is_private
                });
            }
            if (!data.next_max_id) break;
            nextMaxId = data.next_max_id;
            await sleep(950);
        }
        return list;
    }

    Promise.all([fetchList("following"), fetchList("followers")])
        .then(([following, followers]) => {
            callback({ success: true, following, followers });
        })
        .catch(err => {
            callback({ success: false, error: err.toString() });
        });
    """

    print("  ⏳ Obteniendo cuentas que sigues y cuentas que te siguen...")
    start_time = time.time()
    result = driver.execute_async_script(js_fetch, user_id, APP_ID)
    elapsed = time.time() - start_time

    if not result or not result.get("success"):
        error_msg = result.get("error") if result else "Respuesta vacía"
        print(f"  [✘] Error al consultar datos: {error_msg}")
        return None, None

    following = result.get("following", [])
    followers = result.get("followers", [])
    print(f"  [✔] Descarga finalizada en {elapsed:.1f}s ({len(following)} seguidos, {len(followers)} seguidores).")
    return following, followers


# ==============================================================================
# GESTIÓN DEL HISTORIAL Y COMPARACIÓN ENTRE FECHAS
# ==============================================================================

def load_previous_history():
    """
    Carga el historial anterior desde 'data/history.json'.
    Si no existe, intenta cargar datos previos desde 'data/legacy_resultado.json' o archivos txt anteriores.
    """
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                if isinstance(history, list) and len(history) > 0:
                    return history[-1]
                elif isinstance(history, dict) and "followers" in history:
                    return history
        except Exception:
            pass

    # Respaldo: legacy_resultado.json si existe
    if os.path.exists(LEGACY_RESULTADO):
        try:
            with open(LEGACY_RESULTADO, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "timestamp": "Reporte Anterior (Legacy)",
                    "followers": [],
                    "following": [],
                    "not_following_back": data.get("not_following_back", []),
                    "followers_count": data.get("followers_count", 0),
                    "following_count": data.get("following_count", 0),
                }
        except Exception:
            pass

    # Respaldo: verificar si hay un txt antiguo en la raíz (ej: no_te_siguen.txt)
    legacy_txt = os.path.join(BASE_DIR, "no_te_siguen.txt")
    if os.path.exists(legacy_txt):
        try:
            usernames = []
            with open(legacy_txt, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(("@", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                        # Extraer @usuario
                        import re
                        m = re.search(r"@([a-zA-Z0-9._]+)", line)
                        if m:
                            usernames.append({"username": m.group(1), "full_name": ""})
            if usernames:
                return {
                    "timestamp": "Reporte TXT Anterior",
                    "followers": [],
                    "following": [],
                    "not_following_back": usernames,
                    "followers_count": 0,
                    "following_count": 0,
                }
        except Exception:
            pass

    return None


def save_current_snapshot(following, followers, not_following_back):
    """
    Guarda la captura actual en 'data/history.json' como registro histórico.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    snapshot = {
        "timestamp": now_str,
        "following_count": len(following),
        "followers_count": len(followers),
        "not_following_back_count": len(not_following_back),
        "following": following,
        "followers": followers,
        "not_following_back": not_following_back,
    }

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    history = existing
                elif isinstance(existing, dict):
                    history = [existing]
        except Exception:
            history = []

    # Mantener los últimos 30 snapshots para comparar cualquier fecha
    history.append(snapshot)
    if len(history) > 30:
        history = history[-30:]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def compare_with_previous(current_data, prev_data):
    """
    Compara los datos actuales con el snapshot anterior:
    - Nuevos seguidores
    - Usuarios que dejaron de seguir
    - Nuevos usuarios que no siguen de vuelta
    """
    if not prev_data:
        return None

    curr_followers_map = {u["username"].lower(): u for u in current_data["followers"]}
    curr_following_map = {u["username"].lower(): u for u in current_data["following"]}
    curr_not_back_set = {u["username"].lower() for u in current_data["not_following_back"]}

    prev_followers_list = prev_data.get("followers", [])
    prev_not_back_list = prev_data.get("not_following_back", [])

    prev_followers_map = {u["username"].lower(): u for u in prev_followers_list}
    prev_not_back_set = {u["username"].lower() for u in prev_not_back_list}

    # Si teníamos lista completa de followers anterior
    if prev_followers_map:
        new_followers = [u for uname, u in curr_followers_map.items() if uname not in prev_followers_map]
        lost_followers = [u for uname, u in prev_followers_map.items() if uname not in curr_followers_map]
    else:
        new_followers = []
        lost_followers = []

    # Nuevos que NO te siguen de vuelta
    new_not_following_back = [u for u in current_data["not_following_back"] if u["username"].lower() not in prev_not_back_set]
    # Cuentas que ahora sí te siguen o dejaste de seguir (salieron de la lista negra)
    recovered_or_unfollowed = [u for u in prev_not_back_list if u["username"].lower() not in curr_not_back_set]

    return {
        "prev_date": prev_data.get("timestamp", "Desconocida"),
        "has_full_history": bool(prev_followers_map),
        "new_followers": new_followers,
        "lost_followers": lost_followers,
        "new_not_following_back": new_not_following_back,
        "recovered_or_unfollowed": recovered_or_unfollowed,
    }


# ==============================================================================
# VISTAS Y TABLAS EN TERMINAL
# ==============================================================================

def print_summary_card(following, followers, not_following_back, mutuals, comparison):
    """
    Imprime la tarjeta resumen principal en la terminal.
    """
    print("\n" + "=" * 76)
    print("                      📊 RESUMEN GENERAL DE TU CUENTA")
    print("=" * 76)
    print(f"  👥 Cuentas que sigues:                {len(following):>5}")
    print(f"  💙 Cuentas que te siguen:             {len(followers):>5}")
    print(f"  🚫 Cuentas que NO te siguen de vuelta: {len(not_following_back):>5}")
    print(f"  🤝 Seguidores mutuos (se siguen ambos):{len(mutuals):>5}")
    print("=" * 76)

    if comparison:
        print("\n" + "-" * 76)
        print(f"  📈 COMPARACIÓN HISTÓRICA (Respecto al reporte: {comparison['prev_date']})")
        print("-" * 76)

        if comparison["has_full_history"]:
            n_new = len(comparison["new_followers"])
            n_lost = len(comparison["lost_followers"])
            print(f"  🆕 NUEVOS SEGUIDORES (+{n_new}):")
            if n_new > 0:
                for u in comparison["new_followers"][:10]:
                    print(f"     + @{u['username']} ({u['full_name']})")
                if n_new > 10:
                    print(f"     ... y {n_new - 10} más.")
            else:
                print("     (Sin nuevos seguidores detectados)")

            print(f"\n  📉 TE HAN DEJADO DE SEGUIR (-{n_lost}):")
            if n_lost > 0:
                for u in comparison["lost_followers"][:10]:
                    print(f"     - @{u['username']} ({u['full_name']})")
                if n_lost > 10:
                    print(f"     ... y {n_lost - 10} más.")
            else:
                print("     (¡Nadie te ha dejado de seguir desde el reporte anterior!)")
        else:
            # Respaldo cuando el reporte previo solo contenía not_following_back
            n_new_not = len(comparison["new_not_following_back"])
            n_rec = len(comparison["recovered_or_unfollowed"])
            print(f"  ⚠️ NUEVOS EN LA LISTA DE 'NO TE SIGUEN' (+{n_new_not}):")
            if n_new_not > 0:
                for u in comparison["new_not_following_back"][:8]:
                    print(f"     ! @{u['username']} ({u['full_name']})")
            else:
                print("     (Ninguna cuenta nueva dejó de seguirte)")

            print(f"\n  ✨ SALIERON DE LA LISTA DE 'NO TE SIGUEN' ({n_rec}):")
            if n_rec > 0:
                for u in comparison["recovered_or_unfollowed"][:8]:
                    print(f"     ✓ @{u['username']} ({u['full_name']})")
        print("-" * 76)


def display_user_table(title, user_list, page_size=25):
    """
    Muestra una lista paginada y formateada de usuarios en la consola con opción de búsqueda.
    """
    if not user_list:
        print(f"\n[!] La lista '{title}' está vacía.\n")
        return

    filtered_list = list(user_list)
    search_query = ""
    current_page = 0

    while True:
        total = len(filtered_list)
        total_pages = max(1, (total + page_size - 1) // page_size)
        current_page = max(0, min(current_page, total_pages - 1))

        start = current_page * page_size
        end = min(start + page_size, total)
        page_items = filtered_list[start:end]

        print("\n" + "=" * 76)
        query_info = f" [Filtro: '{search_query}']" if search_query else ""
        print(f"  {title.upper()} (Total: {total}){query_info} - Página {current_page + 1}/{total_pages}")
        print("=" * 76)
        print(f"  {'#':<4} {'USUARIO':<28} {'NOMBRE COMPLETO'}")
        print("-" * 76)

        for idx, u in enumerate(page_items, start + 1):
            uname = f"@{u['username']}"
            fname = u.get("full_name") or "-"
            if len(fname) > 38:
                fname = fname[:35] + "..."
            print(f"  {idx:<4} {uname:<28} {fname}")

        print("-" * 76)
        print("  OPCIONES: [S] Siguiente página | [A] Anterior | [B] Buscar | [T] Todos | [V] Volver")
        cmd = input(">> Elige una opción: ").strip().lower()

        if cmd == 's':
            if current_page < total_pages - 1:
                current_page += 1
            else:
                print("  [!] Ya estás en la última página.")
        elif cmd == 'a':
            if current_page > 0:
                current_page -= 1
            else:
                print("  [!] Ya estás en la primera página.")
        elif cmd == 'b':
            search_query = input(">> Ingresa texto a buscar (usuario o nombre): ").strip().lower()
            filtered_list = [
                u for u in user_list
                if search_query in u["username"].lower() or search_query in (u.get("full_name") or "").lower()
            ]
            current_page = 0
        elif cmd == 't':
            search_query = ""
            filtered_list = list(user_list)
            current_page = 0
        elif cmd == 'v' or cmd == '0':
            break


def interactive_menu(current_data, comparison):
    """
    Menú interactivo para navegar los datos sin crear ningún archivo TXT.
    """
    following = current_data["following"]
    followers = current_data["followers"]
    not_following_back = current_data["not_following_back"]
    mutuals = current_data["mutuals"]

    while True:
        print("\n" + "=" * 76)
        print("  📋 MENÚ DE CONSULTA INTERACTIVA (EN CONSOLA)")
        print("=" * 76)
        print(f"    [1] 🚫 Ver cuentas que NO te siguen de vuelta ({len(not_following_back)})")
        print(f"    [2] 👥 Ver todas las cuentas que sigues ({len(following)})")
        print(f"    [3] 💙 Ver todas las cuentas que te siguen ({len(followers)})")
        print(f"    [4] 🤝 Ver seguidores mutuos ({len(mutuals)})")
        if comparison and comparison.get("has_full_history"):
            print(f"    [5] 📈 Ver informe de cambios (Nuevos: +{len(comparison['new_followers'])}, Unfollowers: -{len(comparison['lost_followers'])})")
        else:
            print("    [5] 📈 Ver informe de comparación histórica")
        print("    [0] ❌ Salir del programa")
        print("-" * 76)

        opt = input(">> Selecciona una opción (1-5 o 0): ").strip()
        if opt == "1":
            display_user_table("Cuentas que NO te siguen de vuelta", not_following_back)
        elif opt == "2":
            display_user_table("Cuentas que sigues (Following)", following)
        elif opt == "3":
            display_user_table("Cuentas que te siguen (Followers)", followers)
        elif opt == "4":
            display_user_table("Seguidores Mutuos", mutuals)
        elif opt == "5":
            if comparison:
                if comparison["has_full_history"]:
                    print("\n--- 🆕 NUEVOS SEGUIDORES ---")
                    display_user_table("Nuevos seguidores desde el último reporte", comparison["new_followers"])
                    print("\n--- 📉 TE HAN DEJADO DE SEGUIR ---")
                    display_user_table("Seguidores que te dejaron de seguir", comparison["lost_followers"])
                else:
                    display_user_table("Nuevos que no te siguen de vuelta", comparison["new_not_following_back"])
            else:
                print("\n[!] No hay reporte previo guardado para comparar todavía.")
        elif opt == "0":
            print("\n[👋] ¡Hasta pronto! Tu sesión de Instagram permanece abierta.")
            break
        else:
            print("  [!] Opción no válida.")


# ==============================================================================
# FLUJO PRINCIPAL
# ==============================================================================

def main():
    print_banner()
    driver = None
    try:
        driver = connect_or_launch_chrome()
        user_id = wait_for_instagram_session(driver)

        following, followers = fetch_instagram_data(driver, user_id)
        if following is None or followers is None:
            print("\n[!] No se pudieron obtener los datos. Verifica tu conexión e intenta de nuevo.")
            return

        # Calcular conjuntos
        follower_set = {u["username"].lower() for u in followers}
        following_set = {u["username"].lower() for u in following}

        not_following_back = [u for u in following if u["username"].lower() not in follower_set]
        mutuals = [u for u in following if u["username"].lower() in follower_set]

        current_data = {
            "following": following,
            "followers": followers,
            "not_following_back": not_following_back,
            "mutuals": mutuals,
        }

        # Cargar historial previo y realizar comparación
        prev_data = load_previous_history()
        comparison = compare_with_previous(current_data, prev_data)

        # Guardar snapshot actual para futuras comparaciones (en formato JSON interno)
        save_current_snapshot(following, followers, not_following_back)

        # Mostrar tarjeta resumen en terminal
        print_summary_card(following, followers, not_following_back, mutuals, comparison)

        # Iniciar menú interactivo en terminal
        interactive_menu(current_data, comparison)

    except KeyboardInterrupt:
        print("\n\n[!] Detenido por el usuario. Tu Chrome sigue abierto.")
    except Exception as e:
        print(f"\n[!] Error imprevisto: {e}")


if __name__ == "__main__":
    main()
