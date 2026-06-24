import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "Memory", "serial_config.json")

BAUD_DEFAULT = 9600

COMANDOS_AUTOCONEXION_DEFAULT = ["speed 20", "speedl 20"]
HOME_AL_CONECTAR_DEFAULT = False

_db_lock = threading.Lock()


def _db_default_con(baud: int = BAUD_DEFAULT,
                     comandos_autoconexion: list | None = None,
                     home_al_conectar: bool = HOME_AL_CONECTAR_DEFAULT) -> dict:
    return {
        "baud": baud,
        "comandos_autoconexion": list(comandos_autoconexion) if comandos_autoconexion is not None
                                  else list(COMANDOS_AUTOCONEXION_DEFAULT),
        "home_al_conectar": home_al_conectar,
    }


def _completar_con_default(data: dict) -> tuple[dict, bool]:
    cambiado = False

    if "baud" not in data:
        data["baud"] = BAUD_DEFAULT
        cambiado = True

    if "comandos_autoconexion" not in data:
        data["comandos_autoconexion"] = list(COMANDOS_AUTOCONEXION_DEFAULT)
        cambiado = True

    if "home_al_conectar" not in data:
        data["home_al_conectar"] = HOME_AL_CONECTAR_DEFAULT
        cambiado = True

    return data, cambiado


def _guardar_db_sin_lock(data: dict) -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp_path = DB_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, DB_PATH)


def cargar_config() -> dict:
    with _db_lock:
        if not os.path.exists(DB_PATH):
            data = _db_default_con()
            _guardar_db_sin_lock(data)
            return data
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                contenido = f.read()
            if not contenido.strip():
                return _db_default_con()
            data = json.loads(contenido)
            if not isinstance(data, dict):
                return _db_default_con()
            data, cambiado = _completar_con_default(data)
            if cambiado:
                _guardar_db_sin_lock(data)
            return data
        except Exception:
            return _db_default_con()


def guardar_config(data: dict) -> None:
    with _db_lock:
        _guardar_db_sin_lock(data)
