import pickle
import socket
import struct
import threading

PORT = 8889


class AuthServer:
    def __init__(self, get_token_fn, log_fn=None, port: int = PORT):
        self._get_token = get_token_fn
        self._log       = log_fn or (lambda m: None)
        self._port      = port
        self._srv: socket.socket | None = None
        self._activo    = False

    def iniciar(self):
        if self._activo:
            return
        self._activo = True
        threading.Thread(target=self._escuchar, daemon=True).start()

    def detener(self):
        self._activo = False
        if self._srv:
            try:
                self._srv.close()
            except Exception:
                pass
            self._srv = None

    def _escuchar(self):
        try:
            self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._srv.bind(("0.0.0.0", self._port))
            self._srv.listen(5)
        except Exception as e:
            self._log(f"[auth] no se pudo abrir el puerto {self._port}: {e}")
            self._activo = False
            return

        self._log(f"[auth] escuchando token en puerto {self._port}")
        while self._activo:
            try:
                conn, addr = self._srv.accept()
            except Exception:
                break
            threading.Thread(target=self._atender, args=(conn, addr), daemon=True).start()

    def _atender(self, conn: socket.socket, addr):
        try:
            conn.settimeout(5.0)
            header = _recv_exact(conn, 8)
            if header is None:
                return
            size = struct.unpack("Q", header)[0]
            raw = _recv_exact(conn, size)
            if raw is None:
                return
            pedido        = pickle.loads(raw)
            token_cliente = str(pedido.get("token", ""))
            token_actual  = str(self._get_token() or "").strip()

            ok = bool(token_actual) and token_cliente == token_actual
            motivo = "" if ok else "token incorrecto"
            self._log(f"[auth] {addr[0]} -> {'OK' if ok else 'RECHAZADO'}")

            resp = pickle.dumps({"ok": ok, "motivo": motivo})
            conn.sendall(struct.pack("Q", len(resp)) + resp)
        except Exception as e:
            self._log(f"[auth] error con {addr[0]}: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass


def _recv_exact(conn: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf
