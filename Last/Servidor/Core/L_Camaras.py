import socket
import struct
import pickle
import threading
import numpy as np
import customtkinter as ctk
from PIL import Image

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    from Core.L_Yolo import YoloPoseProcessor
    YOLO_OK = True
except ImportError:
    YOLO_OK = False

PORT = 8888
MAX_CLIENTS = 4

SLOT_COLORS = {
    "#e74c3c": 5,
    "#f39c12": 3,
    "#27ae60": 1,
}


def _resize_cover(frame_bgr, w, h):
    ih, iw = frame_bgr.shape[:2]
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    left = (nw - w) // 2
    top = (nh - h) // 2
    cropped = resized[top:top + h, left:left + w]
    rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


class CamarasServer:
    def __init__(self, slots: list[dict], log_fn=None):
        self._slots = slots
        self._log = log_fn or (lambda msg: None)
        self._clients: dict = {}
        self._lock = threading.Lock()
        self._primary_addr: str | None = None
        self._counter = 0
        self._activo = False
        self._server_sock: socket.socket | None = None
        self._pending = [False] * MAX_CLIENTS
        self._yolo = YoloPoseProcessor() if YOLO_OK else None

    def iniciar(self):
        if self._activo:
            return
        self._activo = True
        threading.Thread(target=self._escuchar, daemon=True).start()

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
        for slot in self._slots:
            lbl = slot["label"]
            frm = slot["frame"]
            try:
                lbl.after(0, lambda l=lbl, f=frm: (
                    l.configure(image=None, text=""),
                    f.configure(border_color="#1e1e1e")
                ))
            except Exception:
                pass

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
                            self._log(f"rechazado (max {MAX_CLIENTS}): {addr}")
                            conn.close()
                            continue
                    self._log(f"cliente: {addr[0]}:{addr[1]}")
                    threading.Thread(
                        target=self._recibir,
                        args=(conn, addr),
                        daemon=True
                    ).start()
                except Exception:
                    break
        except Exception as e:
            self._log(f"error servidor: {e}")

    def _asignar_slot(self, ak: str) -> int:
        if self._primary_addr is not None and self._primary_addr not in self._clients:
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
        ak = f"{addr[0]}:{addr[1]}"
        conn.settimeout(5.0)

        with self._lock:
            self._counter += 1
            num = self._counter
            slot = self._asignar_slot(ak)
            self._clients[ak] = {
                "conn": conn,
                "slot": slot,
                "cam_id": "?",
                "num": num,
                "latest": None,
            }

        self._log(f"#{num} → slot {slot}")
        threading.Thread(target=self._procesar, args=(ak, num), daemon=True).start()

        buf = b""
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

                raw = buf[:msg_size]
                buf = buf[msg_size:]

                payload = pickle.loads(raw)
                if isinstance(payload, tuple) and len(payload) == 2:
                    cam_id, frame = payload
                else:
                    cam_id, frame = "?", payload

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
                    self._clients[ak]["latest"] = frame

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
                if freed >= 0 and not any(i["slot"] == freed for i in self._clients.values()):
                    slots_libres.append(freed)
            if self._primary_addr == ak:
                self._primary_addr = None
                remaining = sorted(self._clients.items(), key=lambda x: x[1]["slot"])
                if remaining:
                    next_ak, next_info = remaining[0]
                    old_s = next_info["slot"]
                    next_info["slot"] = 0
                    self._primary_addr = next_ak
                    if not any(i["slot"] == old_s for i in self._clients.values()):
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
        self._log(f"#{num} desconectado")

    def _procesar(self, ak: str, num: int):
        while self._activo:
            jpg_data = None
            current_slot = -1

            with self._lock:
                if ak not in self._clients:
                    break
                info = self._clients[ak]
                if info["latest"] is not None:
                    jpg_data = info["latest"]
                    info["latest"] = None
                    current_slot = info["slot"]

            if jpg_data is None:
                threading.Event().wait(0.01)
                continue

            if not CV2_OK or current_slot < 0 or current_slot >= len(self._slots):
                continue

            try:
                if isinstance(jpg_data, np.ndarray) and jpg_data.ndim == 3:
                    bgr = jpg_data
                else:
                    arr = np.frombuffer(bytes(jpg_data), dtype=np.uint8)
                    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if bgr is None:
                        continue

                color = None
                if self._yolo and self._yolo.activo:
                    bgr = self._yolo.procesar(bgr, es_bgr=True)
                    color = self._yolo.last_color

                slot_data = self._slots[current_slot]
                sw = slot_data["w"]
                sh = slot_data["h"]
                pil_img = _resize_cover(bgr, sw, sh)
                ctk_img = ctk.CTkImage(
                    light_image=pil_img, dark_image=pil_img,
                    size=(sw, sh)
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
                        finally:
                            self._pending[s] = False

                    try:
                        self._slots[current_slot]["frame"].after(0, _render)
                    except Exception:
                        self._pending[current_slot] = False

            except Exception as e:
                print(f"[CamarasServer] error procesando #{num}: {e}")