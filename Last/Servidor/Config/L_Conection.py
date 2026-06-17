import socket
import threading
import struct
import pickle
import platform
import subprocess
import os
import atexit

PORT       = 8888
AUDIO_PORT = 9999
MAX_CLIENTS = 4
RULE_NAME  = "CastorServer_Temp_8888"
RULE_AUDIO = "CastorServer_Temp_9999"


def is_admin() -> bool:
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def _fw_open(port: int, rule: str):
    if platform.system() == "Windows":
        subprocess.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule}", "dir=in", "action=allow",
            "protocol=TCP", f"localport={port}", "profile=private,domain"
        ], capture_output=True)
    else:
        subprocess.run(
            ["pkexec", "firewall-cmd", f"--add-port={port}/tcp", "--temporary"],
            capture_output=True
        )


def _fw_close(port: int, rule: str):
    if platform.system() == "Windows":
        subprocess.run([
            "netsh", "advfirewall", "firewall", "delete", "rule",
            f"name={rule}"
        ], capture_output=True)
    else:
        subprocess.Popen(
            ["pkexec", "firewall-cmd", f"--remove-port={port}/tcp"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def open_ports(log_fn=None):
    _log = log_fn or (lambda m: None)
    _fw_open(PORT, RULE_NAME)
    _fw_open(AUDIO_PORT, RULE_AUDIO)
    _log(f"puertos {PORT} y {AUDIO_PORT} abiertos en firewall")
    if platform.system() == "Windows":
        atexit.register(lambda: close_ports())


def close_ports():
    _fw_close(PORT, RULE_NAME)
    _fw_close(AUDIO_PORT, RULE_AUDIO)


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ConectionServer:
    def __init__(self, slots: list[dict], log_fn=None, on_serial_fn=None, on_layout_fn=None, on_yolo_fn=None):
        self._slots      = slots
        self._log        = log_fn or (lambda m: None)
        self._on_serial  = on_serial_fn or (lambda cmd: None)
        self._on_layout  = on_layout_fn or (lambda n: None)
        self._on_yolo    = on_yolo_fn or (lambda color: None)
        self._clients: dict = {}
        self._lock       = threading.Lock()
        self._primary_addr: str | None = None
        self._counter    = 0
        self._activo     = False
        self._server_sock: socket.socket | None = None
        self._pending    = [False] * MAX_CLIENTS

    def iniciar(self):
        if self._activo:
            return
        self._activo = True
        open_ports(self._log)
        threading.Thread(target=self._escuchar, daemon=True).start()
        self._log(f"servidor iniciado en :{PORT}")

    def detener(self):
        self._activo = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        with self._lock:
            for info in self._clients.values():
                try:
                    info["conn"].shutdown(socket.SHUT_RDWR)
                    info["conn"].close()
                except Exception:
                    pass
            self._clients.clear()
            self._primary_addr = None
        close_ports()
        self._log("servidor detenido")

    def swap_primary(self, slot_index: int):
        with self._lock:
            target_key = None
            old_primary = self._primary_addr
            for ak, info in self._clients.items():
                if info["slot"] == slot_index:
                    target_key = ak
                    break
            if target_key is None or target_key == old_primary:
                return
            self._clients[target_key]["slot"] = 0
            if old_primary and old_primary in self._clients:
                self._clients[old_primary]["slot"] = slot_index
            self._primary_addr = target_key

    def active_slots(self) -> list[int]:
        with self._lock:
            return sorted({info["slot"] for info in self._clients.values()})

    def enviar_a_todos(self, msg: str):
        data = (msg + "\n").encode("utf-8")
        with self._lock:
            for info in list(self._clients.values()):
                try:
                    info["conn"].sendall(data)
                except Exception:
                    pass

    def enviar_serial(self, cmd: str):
        self.enviar_a_todos(f"SERIAL:{cmd}")

    def _escuchar(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("", PORT))
            srv.listen(MAX_CLIENTS)
            self._server_sock = srv
            self._log(f"escuchando en :{PORT}")
            while self._activo:
                try:
                    conn, addr = srv.accept()
                    if not self._activo:
                        break
                    with self._lock:
                        if len(self._clients) >= MAX_CLIENTS:
                            self._log(f"rechazado (max {MAX_CLIENTS}): {addr[0]}")
                            conn.close()
                            continue
                    self._log(f"cliente: {addr[0]}:{addr[1]}")
                    threading.Thread(
                        target=self._recibir,
                        args=(conn, addr), daemon=True
                    ).start()
                except Exception:
                    break
        except Exception as e:
            self._log(f"error servidor: {e}")

    def _asignar_slot(self, ak: str) -> int:
        if self._primary_addr and self._primary_addr not in self._clients:
            self._primary_addr = None
        used = {info["slot"] for info in self._clients.values()}
        if self._primary_addr is None:
            self._primary_addr = ak
            return 0
        for s in range(1, MAX_CLIENTS):
            if s not in used:
                return s
        return -1

    def _recibir(self, conn: socket.socket, addr):
        import numpy as np
        import cv2
        try:
            from PIL import Image
            import customtkinter as ctk
            PIL_OK = True
        except ImportError:
            PIL_OK = False

        ak = f"{addr[0]}:{addr[1]}"
        conn.settimeout(5.0)

        with self._lock:
            self._counter += 1
            num  = self._counter
            slot = self._asignar_slot(ak)
            self._clients[ak] = {
                "conn": conn, "slot": slot,
                "cam_id": "?", "num": num,
                "latest": None, "yolo_latest": None,
                "yolo_color": None,
            }

        self._log(f"#{num} → slot {slot}")
        with self._lock:
            n = len(self._clients)
        self._on_layout(n)
        threading.Thread(
            target=self._procesar, args=(ak, num), daemon=True
        ).start()
        threading.Thread(
            target=self._yolo_loop, args=(ak, num), daemon=True
        ).start()
        buf      = b""
        hdr_size = struct.calcsize("Q")

        while self._activo:
            try:
                while len(buf) < hdr_size:
                    chunk = conn.recv(65536)
                    if not chunk:
                        raise ConnectionResetError("cliente cerrado")
                    buf += chunk

                msg_size = struct.unpack("Q", buf[:hdr_size])[0]
                buf = buf[hdr_size:]

                while len(buf) < msg_size:
                    chunk = conn.recv(65536)
                    if not chunk:
                        raise ConnectionResetError("stream cortado")
                    buf += chunk

                raw     = buf[:msg_size]
                buf     = buf[msg_size:]
                payload = pickle.loads(raw)

                if isinstance(payload, tuple) and len(payload) == 2:
                    cam_id, frame = payload
                else:
                    cam_id, frame = "?", payload

                if isinstance(frame, np.ndarray) and frame.ndim == 3:
                    bgr = frame
                else:
                    arr = np.frombuffer(bytes(frame), dtype=np.uint8)
                    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                with self._lock:
                    if ak not in self._clients:
                        break
                    str_id = str(cam_id)
                    if str_id != "?":
                        for old_ak, old_info in list(self._clients.items()):
                            if old_ak != ak and old_info.get("cam_id") == str_id:
                                self._log(f"reconexión cam '{str_id}'")
                                self._clients[ak]["slot"] = old_info["slot"]
                                try:
                                    old_info["conn"].shutdown(socket.SHUT_RDWR)
                                    old_info["conn"].close()
                                except Exception:
                                    pass
                                self._clients.pop(old_ak, None)
                    self._clients[ak]["cam_id"] = str_id
                    if bgr is not None:
                        self._clients[ak]["latest"]      = bgr
                        self._clients[ak]["yolo_latest"]  = bgr

            except (socket.timeout, TimeoutError):
                self._log(f"#{num} timeout")
                break
            except Exception as e:
                if self._activo:
                    self._log(f"#{num} fin: {e}")
                break

        slots_libres = []
        with self._lock:
            if ak in self._clients:
                freed = self._clients[ak]["slot"]
                self._clients.pop(ak, None)
                if freed >= 0 and not any(
                    i["slot"] == freed for i in self._clients.values()
                ):
                    slots_libres.append(freed)
            if self._primary_addr == ak:
                self._primary_addr = None
                remaining = sorted(
                    self._clients.items(), key=lambda x: x[1]["slot"]
                )
                if remaining:
                    next_ak, next_info = remaining[0]
                    old_s = next_info["slot"]
                    next_info["slot"] = 0
                    self._primary_addr = next_ak
                    if not any(
                        i["slot"] == old_s for i in self._clients.values()
                    ):
                        slots_libres.append(old_s)

        def _limpiar(slots):
            for s in slots:
                if 0 <= s < len(self._slots):
                    lbl = self._slots[s]["label"]
                    frm = self._slots[s]["frame"]
                    lbl.configure(image=None, text="")
                    frm.configure(border_color="#1e1e1e")

        if slots_libres:
            try:
                self._slots[0]["frame"].after(0, lambda: _limpiar(slots_libres))
            except Exception:
                pass

        try:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        except Exception:
            pass
        with self._lock:
            n = len(self._clients)
        self._on_layout(n)
        self._log(f"#{num} desconectado")

    def _procesar(self, ak: str, num: int):
        try:
            from PIL import Image
            import customtkinter as ctk
            PIL_OK = True
        except ImportError:
            PIL_OK = False

        import cv2

        SLOT_COLORS = {"#e74c3c": 5, "#f39c12": 3, "#27ae60": 1}

        def _resize_cover(frame_bgr, w, h):
            ih, iw = frame_bgr.shape[:2]
            scale  = max(w / iw, h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
            left   = (nw - w) // 2
            top    = (nh - h) // 2
            cropped = resized[top:top + h, left:left + w]
            rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb)

        while self._activo:
            bgr          = None
            current_slot = -1
            color        = None

            with self._lock:
                if ak not in self._clients:
                    break
                info = self._clients[ak]
                if info["latest"] is not None:
                    bgr            = info["latest"]
                    info["latest"] = None
                    current_slot   = info["slot"]
                    color          = info.get("yolo_color")

            if bgr is None:
                threading.Event().wait(0.01)
                continue

            if not PIL_OK or current_slot < 0 or current_slot >= len(self._slots):
                continue

            try:
                slot_data = self._slots[current_slot]
                sw = slot_data["w"]
                sh = slot_data["h"]
                pil_img = _resize_cover(bgr, sw, sh)
                ctk_img = ctk.CTkImage(
                    light_image=pil_img, dark_image=pil_img, size=(sw, sh)
                )

                if not self._pending[current_slot]:
                    self._pending[current_slot] = True

                    def _render(s=current_slot, img=ctk_img, c=color, key=ak):
                        try:
                            with self._lock:
                                if key not in self._clients:
                                    return
                                if self._clients[key]["slot"] != s:
                                    return
                            lbl = self._slots[s]["label"]
                            frm = self._slots[s]["frame"]
                            lbl.configure(image=img, text="")
                            lbl._ctk_image = img
                            if c and c in SLOT_COLORS:
                                frm.configure(border_color=c, border_width=SLOT_COLORS[c])
                            else:
                                frm.configure(border_color="#1e1e1e", border_width=1)
                            if s == 0:
                                self._on_yolo(c)
                        finally:
                            self._pending[s] = False

                    try:
                        self._slots[current_slot]["frame"].after(0, _render)
                    except Exception:
                        self._pending[current_slot] = False

            except Exception as e:
                print(f"[ConectionServer] error procesando #{num}: {e}")

    def _yolo_loop(self, ak: str, num: int):
        try:
            from Core.L_Yolo import YoloPoseProcessor
            yolo = YoloPoseProcessor()
        except Exception:
            return

        while self._activo:
            bgr = None
            with self._lock:
                if ak not in self._clients:
                    break
                info = self._clients[ak]
                if info["yolo_latest"] is not None:
                    bgr = info["yolo_latest"]
                    info["yolo_latest"] = None

            if bgr is None:
                threading.Event().wait(0.01)
                continue

            if not yolo.activo:
                with self._lock:
                    if ak in self._clients:
                        self._clients[ak]["yolo_color"] = None
                threading.Event().wait(0.05)
                continue

            try:
                yolo.procesar(bgr, es_bgr=True)
                color = yolo.last_color
            except Exception:
                color = None

            with self._lock:
                if ak in self._clients:
                    self._clients[ak]["yolo_color"] = color
