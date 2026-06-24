import json
import os
import pickle
import secrets
import socket
import struct
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "Memory", "login_db.json")

AUTH_PORT = 8889

USUARIO_DEFAULT    = "CIMUBB"
CONTRASENA_DEFAULT = "2002"

_db_lock = threading.Lock()


def _db_default_con(usuario: str = USUARIO_DEFAULT, contraseña: str = CONTRASENA_DEFAULT) -> dict:
    return {"usuario": usuario, "contraseña": contraseña}


def _completar_con_default(data: dict) -> tuple[dict, bool]:
    cambiado = False

    if "usuario" not in data:
        data["usuario"] = USUARIO_DEFAULT
        cambiado = True

    if "contraseña" not in data:
        data["contraseña"] = CONTRASENA_DEFAULT
        cambiado = True

    return data, cambiado


def _cargar_db() -> dict:
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


def _guardar_db_sin_lock(data: dict) -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp_path = DB_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, DB_PATH)


def _guardar_db(data: dict) -> None:
    with _db_lock:
        _guardar_db_sin_lock(data)


def validar_usuario(usuario: str) -> tuple[bool, str]:
    usuario = (usuario or "").strip()
    if not usuario:
        return False, "el usuario esta vacio"
    return True, ""


class LoginManager:
    def __init__(self):
        self._db = _cargar_db()
        self.token_actual: str | None = None

    def _refrescar_db(self):
        self._db = _cargar_db()

    def validar_usuario(self, usuario: str) -> tuple[bool, str]:
        return validar_usuario(usuario)

    def validar_credenciales(self, usuario: str, clave: str) -> tuple[bool, str]:
        ok, motivo = self.validar_usuario(usuario)
        if not ok:
            return False, motivo
        if not clave:
            return False, "falta la contraseña"

        self._refrescar_db()
        usuario_db = self._db.get("usuario", USUARIO_DEFAULT)
        clave_db   = self._db.get("contraseña", CONTRASENA_DEFAULT)

        if usuario.strip() != usuario_db:
            return False, "usuario incorrecto"
        if clave != clave_db:
            return False, "contraseña incorrecta"
        return True, ""

    def cambiar_usuario(self, clave_actual: str, usuario_nuevo: str) -> tuple[bool, str]:
        self._refrescar_db()
        if clave_actual != self._db.get("contraseña", CONTRASENA_DEFAULT):
            return False, "contraseña incorrecta"
        usuario_nuevo = (usuario_nuevo or "").strip()
        if not usuario_nuevo:
            return False, "el usuario nuevo esta vacio"
        self._db["usuario"] = usuario_nuevo
        _guardar_db(self._db)
        return True, ""

    def cambiar_clave(self, clave_actual: str, clave_nueva: str) -> tuple[bool, str]:
        self._refrescar_db()
        if clave_actual != self._db.get("contraseña", CONTRASENA_DEFAULT):
            return False, "contraseña incorrecta"
        if not clave_nueva:
            return False, "la contraseña nueva esta vacia"
        self._db["contraseña"] = clave_nueva
        _guardar_db(self._db)
        return True, ""

    def generar_token(self) -> str:
        self.token_actual = secrets.token_hex(3).upper()
        return self.token_actual

    def verificar_token_con_servidor(self, ip: str, token: str | None = None,
                                      puerto: int = AUTH_PORT,
                                      timeout: float = 3.0) -> tuple[bool, str]:
        token = token if token is not None else self.token_actual
        if not token:
            return False, "primero generá un token"
        if not ip:
            return False, "falta la IP del servidor"
        try:
            with socket.create_connection((ip, puerto), timeout=timeout) as s:
                s.settimeout(timeout)
                pedido = pickle.dumps({"token": token})
                s.sendall(struct.pack("Q", len(pedido)) + pedido)

                header = _recv_exact(s, 8, timeout)
                if header is None:
                    return False, "el servidor no respondio"
                size = struct.unpack("Q", header)[0]
                raw = _recv_exact(s, size, timeout)
                if raw is None:
                    return False, "respuesta incompleta del servidor"
                resp = pickle.loads(raw)
        except (socket.timeout, TimeoutError):
            return False, "tiempo de espera agotado"
        except (ConnectionRefusedError, OSError) as e:
            return False, f"no se pudo conectar al servidor: {e}"
        except Exception as e:
            return False, f"no se pudo validar con el servidor: {e}"

        if not isinstance(resp, dict):
            return False, "respuesta invalida del servidor"

        if resp.get("ok"):
            return True, ""
        return False, resp.get("motivo", "token incorrecto")


def _recv_exact(sock: socket.socket, n: int, timeout: float) -> bytes | None:
    buf = b""
    sock.settimeout(timeout)
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf
