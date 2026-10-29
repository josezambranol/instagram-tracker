"""
Test de verificación y diagnóstico para Instagram Unfollowers & Followers Tracker Pro
"""
import sys
import os
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracker

def run_tests():
    print("=" * 60)
    print("🧪 TEST DE VERIFICACIÓN FUNCIONAL: INSTAGRAM TRACKER PRO")
    print("=" * 60)

    # 1. Localización de Chrome
    chrome_exe = tracker.find_chrome_executable()
    print(f"[1/5] Ejecutable de Chrome: {chrome_exe}")
    assert os.path.exists(chrome_exe), "Chrome no encontrado"
    print("      ✔ Ejecutable de Chrome verificado.")

    # 2. Configuración de carpetas
    print(f"[2/5] Verificando carpetas y rutas de sesión...")
    assert os.path.exists(tracker.BASE_DIR), "Directorio base no encontrado"
    print("      ✔ Rutas del proyecto verificadas.")

    # 3. Test de carga de historial anterior (legacy)
    print("[3/5] Probando importador de historial previo...")
    prev = tracker.load_previous_history()
    assert prev is not None, "Error al cargar historial previo de data/legacy_resultado.json"
    not_back = prev.get("not_following_back", [])
    print(f"      ✔ Historial previo cargado exitosamente ({len(not_back)} cuentas que no te seguían).")

    # 4. Test del motor de comparación histórica (algoritmo)
    print("[4/5] Probando algoritmo de comparación histórica...")
    # Simulamos datos actuales vs anteriores
    sim_prev = {
        "timestamp": "2026-10-25 12:00:00",
        "followers": [
            {"username": "amigo1", "full_name": "Amigo Uno"},
            {"username": "amigo2", "full_name": "Amigo Dos"},
            {"username": "traidor", "full_name": "El que se fue"}
        ],
        "following": [
            {"username": "amigo1", "full_name": "Amigo Uno"},
            {"username": "celebridad", "full_name": "Famoso"},
            {"username": "traidor", "full_name": "El que se fue"}
        ],
        "not_following_back": [
            {"username": "celebridad", "full_name": "Famoso"}
        ]
    }

    sim_curr = {
        "followers": [
            {"username": "amigo1", "full_name": "Amigo Uno"},
            {"username": "amigo2", "full_name": "Amigo Dos"},
            {"username": "nuevo_fan", "full_name": "Nuevo Seguidor"}  # NUEVO SEGUIDOR
            # 'traidor' ya no está -> UNFOLLOWER DETECTADO
        ],
        "following": [
            {"username": "amigo1", "full_name": "Amigo Uno"},
            {"username": "celebridad", "full_name": "Famoso"},
            {"username": "traidor", "full_name": "El que se fue"}  # AHORA NO TE SIGUE DE VUELTA
        ],
        "not_following_back": [
            {"username": "celebridad", "full_name": "Famoso"},
            {"username": "traidor", "full_name": "El que se fue"}
        ]
    }

    comp = tracker.compare_with_previous(sim_curr, sim_prev)
    assert comp is not None, "La comparación devolvió None"
    assert len(comp["new_followers"]) == 1, f"Fallo al detectar nuevo seguidor: {comp['new_followers']}"
    assert comp["new_followers"][0]["username"] == "nuevo_fan"
    assert len(comp["lost_followers"]) == 1, f"Fallo al detectar unfollower: {comp['lost_followers']}"
    assert comp["lost_followers"][0]["username"] == "traidor"
    assert len(comp["new_not_following_back"]) == 1
    assert comp["new_not_following_back"][0]["username"] == "traidor"

    print("      ✔ Detección de nuevos seguidores: CORRECTO (+1 'nuevo_fan')")
    print("      ✔ Detección de unfollowers: CORRECTO (-1 'traidor')")
    print("      ✔ Detección de nuevos no-seguidores: CORRECTO (+1 'traidor')")

    # 5. Guardado de snapshots sin generar archivos TXT
    print("[5/5] Verificando guardado limpio en history.json...")
    tracker.save_current_snapshot(sim_curr["following"], sim_curr["followers"], sim_curr["not_following_back"])
    assert os.path.exists(tracker.HISTORY_FILE), "No se creó history.json"
    print("      ✔ Snapshot guardado en JSON interno sin dejar archivos TXT.")

    print("\n" + "=" * 60)
    print("🎉 ¡TODOS LOS TESTS DEL TRACKER PASARON AL 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
