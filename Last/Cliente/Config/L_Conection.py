import socket
import struct
import pickle
import threading
import queue


PORT = 8888


class Conection:
    def __init__(self, cam_index: int, ip: str, port: int = PORT,
                 on_serial_fn=None, on_msg_fn=None, on_error_fn=None):
        self.cam_index = cam_index
        self.ip        = ip
        self.port      = port
        self.on_serial = on_serial_fn or (lambda cmd: None)
        self.on_msg    = on_msg_fn    or (lambda msg: None)
        self.on_error  = on_error_fn  or (lambda idx, e: None)
        self.sock      = None
        self.activo    = False
        self._frame_q  = queue.Queue(maxsize=1)
        self._send_lock = threading.Lock()

    def conectar(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
            try:
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
        except Exception as e:
            self.on_error(self.cam_index, f"TCP connect: {e}")
            return False
        self.activo = True
        threading.Thread(target=self._hilo_enviar,  daemon=True).start()
        threading.Thread(target=self._hilo_recibir, daemon=True).start()
        return True

    def desconectar(self):
        self.activo = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def push_frame(self, jpg_buf):
        try:
            self._frame_q.put_nowait(jpg_buf)
        except queue.Full:
            try:
                self._frame_q.get_nowait()
            except queue.Empty:
                pass
            self._frame_q.put_nowait(jpg_buf)

    def enviar_mensaje(self, msg: str) -> bool:
        """Manda un mensaje de control (chat) al servidor por el mismo socket
        que el video, pero serializado con el lock para no pisarse con el
        hilo que esta mandando frames al mismo tiempo."""
        if not self.activo or not self.sock:
            return False
        try:
            data   = pickle.dumps(("MSG", msg))
            header = struct.pack("Q", len(data))
            with self._send_lock:
                self.sock.sendall(header + data)
            return True
        except Exception as e:
            self.on_error(self.cam_index, f"envio mensaje: {e}")
            return False

    def _hilo_enviar(self):
        try:
            while self.activo:
                try:
                    jpg_buf = self._frame_q.get(timeout=1.0)
                except queue.Empty:
                    continue
                if jpg_buf is None:
                    break
                data   = pickle.dumps((self.cam_index, jpg_buf))
                header = struct.pack("Q", len(data))
                with self._send_lock:
                    self.sock.sendall(header + data)
        except Exception as e:
            if self.activo:
                self.on_error(self.cam_index, f"envio: {e}")

    def _hilo_recibir(self):
        buf = ""
        try:
            while self.activo:
                chunk = self.sock.recv(1024)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    msg = line.strip()
                    if not msg:
                        continue
                    if msg.startswith("SERIAL:"):
                        self.on_serial(msg[7:])
                    else:
                        self.on_msg(msg)
        except Exception:
            pass