import threading
import queue
import time
import platform
import customtkinter as ctk
from PIL import Image

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

from Config.L_Conection import Conection

PANEL    = "#1e1e1e"
FG       = "white"
FG_DIM   = "#3e3e3e"
FONT     = ("Consolas", 28, "bold")

TARGET_FPS   = 15
FRAME_DELAY  = 1.0 / TARGET_FPS
JPEG_QUALITY = 70
CAM_W        = 320
CAM_H        = 180
BACKEND      = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2


def detectar_camaras() -> list:
    if not CV2_OK:
        return []
    disponibles = []
    if platform.system() == "Linux":
        import glob
        import subprocess as sp
        indices = []
        for d in sorted(glob.glob("/dev/video*")):
            try:
                idx = int(d.replace("/dev/video", ""))
            except Exception:
                continue
            try:
                out = sp.check_output(
                    ["v4l2-ctl", "--device", d, "--info"],
                    stderr=sp.DEVNULL, timeout=2
                ).decode()
                if "loopback" in out.lower() or "virtual" in out.lower():
                    continue
            except Exception:
                pass
            indices.append(idx)
        if not indices:
            indices = list(range(8))
    else:
        indices = list(range(8))

    for i in indices:
        cap = cv2.VideoCapture(i, BACKEND)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                disponibles.append(i)
        cap.release()
        time.sleep(0.05)
    return disponibles


class StreamCamara:
    def __init__(self, cam_index, ip, port, label_ctk, on_error_fn,
                 on_serial_fn=None, on_msg_fn=None):
        self.cam_index    = cam_index
        self.label        = label_ctk
        self.on_error     = on_error_fn
        self.activo       = False
        self.captura      = None
        self._frame_queue = queue.Queue(maxsize=1)
        self._conn = Conection(
            cam_index    = cam_index,
            ip           = ip,
            port         = port,
            on_serial_fn = on_serial_fn,
            on_msg_fn    = on_msg_fn,
            on_error_fn  = lambda idx, e: self._on_conn_error(e),
        )

    def _on_conn_error(self, e):
        if self.activo and self.captura is not None:
            self.on_error(self.cam_index, e)

    def iniciar(self) -> bool:
        if not self._conn.conectar():
            return False
        self.captura = cv2.VideoCapture(self.cam_index, BACKEND)
        if not self.captura.isOpened():
            self._conn.desconectar()
            self.on_error(self.cam_index, "no se pudo abrir camara")
            return False
        self.activo = True
        threading.Thread(target=self._capturar, daemon=True).start()
        return True

    def detener(self):
        self.activo = False
        self._conn.desconectar()
        cap = self.captura
        self.captura = None
        if cap:
            try:
                cap.release()
            except Exception:
                pass

    def _capturar(self):
        _preview_pending = False
        try:
            while self.activo:
                t0 = time.time()
                ret, frame = self.captura.read()
                if not ret or frame is None:
                    continue

                small = cv2.resize(frame, (CAM_W, CAM_H))

                if not _preview_pending:
                    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                    def _do_preview(arr=rgb):
                        nonlocal _preview_pending
                        self._set_preview(arr)
                        _preview_pending = False

                    _preview_pending = True
                    self.label.after(0, _do_preview)

                ok, jpg_buf = cv2.imencode(
                    ".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
                    self._conn.push_frame(jpg_buf)

                elapsed = time.time() - t0
                if elapsed < FRAME_DELAY:
                    time.sleep(FRAME_DELAY - elapsed)

        except Exception as e:
            if self.activo:
                self.on_error(self.cam_index, f"captura: {e}")
        finally:
            cap = self.captura
            self.captura = None
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass

    def _set_preview(self, rgb_array):
        try:
            im    = Image.fromarray(rgb_array)
            photo = ctk.CTkImage(light_image=im, dark_image=im, size=(CAM_W, CAM_H))
            self.label.configure(image=photo, text="")
            self.label._photo = photo
        except Exception:
            pass


class CamarasPanel:
    def __init__(self, scroll_frame: ctk.CTkScrollableFrame, get_ip_fn, get_port_fn,
                 on_serial_fn=None, on_msg_fn=None):
        self.scroll_frame = scroll_frame
        self.get_ip       = get_ip_fn
        self.get_port     = get_port_fn
        self.on_serial_fn = on_serial_fn
        self.on_msg_fn    = on_msg_fn

        self._streams: dict  = {}
        self._streams_lock   = threading.Lock()
        self._stream_gen: dict = {}
        self._slots: list    = []
        self._transmitiendo  = False
        self._preview_activo = False
        self._preview_gen    = 0
        self._desconectando  = False
        self._lbl_status: ctk.CTkLabel | None = None

    def set_status_label(self, lbl: ctk.CTkLabel):
        self._lbl_status = lbl

    def detectar(self):
        self._set_status("buscando…", "#f39c12")
        threading.Thread(target=self._detectar_hilo, daemon=True).start()

    def _detectar_hilo(self):
        cams = detectar_camaras()
        self.scroll_frame.after(0, lambda: self._mostrar(cams))

    def _mostrar(self, encontradas: list):
        with self._streams_lock:
            streaming_idx = set(self._streams.keys())

        self._preview_gen += 1
        gen = self._preview_gen
        self._preview_activo = False
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self._slots.clear()

        if not encontradas:
            self._set_status("sin camaras", "#e74c3c")
            ctk.CTkLabel(
                self.scroll_frame, text="sin camaras detectadas",
                font=FONT, text_color=FG_DIM
            ).grid(row=0, column=0, padx=5, pady=5)
            return

        if streaming_idx:
            self._set_status(f"{len(encontradas)} cam(s), transmitiendo", "#2ecc71")
        else:
            self._set_status(f"{len(encontradas)} cam(s)", FG_DIM)
        self._preview_activo = True

        for idx_slot, cam_idx in enumerate(encontradas):
            fila    = idx_slot // 2
            columna = idx_slot % 2
            ya_streaming = cam_idx in streaming_idx

            outer = ctk.CTkFrame(
                self.scroll_frame,
                width=CAM_W + 10, height=CAM_H + 10,
                fg_color=PANEL, border_color=PANEL, border_width=2,
                corner_radius=5)
            outer.grid(row=fila, column=columna, padx=5, pady=5)
            outer.grid_propagate(False)

            lbl = ctk.CTkLabel(outer, text=f"cam {cam_idx}", font=FONT,
                               text_color=FG_DIM, image=None,
                               width=CAM_W, height=CAM_H)
            lbl.place(x=5, y=5)

            slot = {"outer": outer, "label": lbl,
                    "cam_idx": cam_idx, "selected": ya_streaming}
            self._slots.append(slot)

            outer.bind("<Button-1>", lambda e, s=idx_slot: self._toggle_slot(s))
            lbl.bind("<Button-1>",   lambda e, s=idx_slot: self._toggle_slot(s))

            if ya_streaming:
                outer.configure(border_color="#00e676")
                with self._streams_lock:
                    stream = self._streams.get(cam_idx)
                if stream:
                    stream.label = lbl
            else:
                threading.Thread(
                    target=self._preview_local,
                    args=(cam_idx, lbl, gen), daemon=True).start()

    def _preview_local(self, cam_idx, lbl, gen):
        time.sleep(0.1)
        if not self._preview_activo or gen != self._preview_gen:
            return
        cap = cv2.VideoCapture(cam_idx, BACKEND)
        if not cap.isOpened():
            lbl.after(0, lambda: lbl.configure(text=f"error cam {cam_idx}"))
            return
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        while self._preview_activo and gen == self._preview_gen:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue
            small = cv2.resize(frame, (CAM_W, CAM_H))
            rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            im    = Image.fromarray(rgb)
            photo = ctk.CTkImage(light_image=im, dark_image=im, size=(CAM_W, CAM_H))

            def _upd(p=photo, l=lbl):
                if gen == self._preview_gen:
                    l.configure(image=p, text="")
                    l._photo = p

            lbl.after(0, _upd)
            time.sleep(0.04)
        cap.release()

    def _toggle_slot(self, slot_idx):
        slot = self._slots[slot_idx]
        slot["selected"] = not slot["selected"]
        color = "#00e676" if slot["selected"] else PANEL
        slot["outer"].configure(border_color=color)

        if self._transmitiendo:
            self._actualizar_streams()

    def conectar(self):
        seleccionadas = [s["cam_idx"] for s in self._slots if s["selected"]]
        if not seleccionadas and self._slots:
            for slot in self._slots:
                slot["selected"] = True
                slot["outer"].configure(border_color="#00e676")
            seleccionadas = [s["cam_idx"] for s in self._slots]
        if not seleccionadas:
            self._set_status("sin camaras", "#e74c3c")
            return
        self._preview_activo = False
        self._transmitiendo  = True
        for slot in self._slots:
            if not slot["selected"]:
                slot["label"].configure(image=None, text=f"cam {slot['cam_idx']} en espera")
        self._actualizar_streams()
        self._set_status("transmitiendo", "#2ecc71")

    def desconectar(self):
        self._desconectando = True
        self._transmitiendo  = False
        with self._streams_lock:
            for s in self._streams.values():
                s.detener()
            self._streams.clear()
            for idx in self._stream_gen:
                self._stream_gen[idx] += 1
        self._desconectando = False
        self._set_status("desconectado", FG_DIM)
        self._preview_gen += 1
        gen = self._preview_gen
        self._preview_activo = True
        for slot in self._slots:
            slot["selected"] = False
            slot["outer"].configure(border_color=PANEL)
            threading.Thread(
                target=self._preview_local,
                args=(slot["cam_idx"], slot["label"], gen),
                daemon=True).start()

    def _actualizar_streams(self):
        ip   = self.get_ip()
        port = self.get_port()
        seleccionadas = {s["cam_idx"] for s in self._slots if s["selected"]}
        todas_idx     = {s["cam_idx"] for s in self._slots}

        with self._streams_lock:
            actuales = list(self._streams.keys())
            a_detener = []
            for c in actuales:
                if c not in seleccionadas:
                    s = self._streams.pop(c, None)
                    if s:
                        a_detener.append(s)
                    self._stream_gen[c] = self._stream_gen.get(c, 0) + 1

            for idx in todas_idx:
                if idx not in seleccionadas and idx not in self._streams:
                    self._stream_gen[idx] = self._stream_gen.get(idx, 0) + 1

            a_iniciar = []
            for slot in self._slots:
                idx = slot["cam_idx"]
                if idx not in seleccionadas:
                    continue
                if idx in self._streams:
                    continue
                self._stream_gen[idx] = self._stream_gen.get(idx, 0) + 1
                a_iniciar.append((idx, slot["label"], self._stream_gen[idx]))

        for s in a_detener:
            s.detener()

        for idx, lbl, gen in a_iniciar:
            lbl.configure(image=None, text=f"conectando cam {idx}…")

            def _iniciar(cam_id=idx, target_lbl=lbl, my_gen=gen):
                time.sleep(0.2)
                with self._streams_lock:
                    vigente = self._stream_gen.get(cam_id) == my_gen
                if not vigente:
                    return
                s = StreamCamara(
                    cam_id, ip, port, target_lbl,
                    on_error_fn  = self._on_error,
                    on_serial_fn = self.on_serial_fn,
                    on_msg_fn    = self.on_msg_fn,
                )
                ok = s.iniciar()
                with self._streams_lock:
                    vigente = self._stream_gen.get(cam_id) == my_gen
                if not vigente:
                    if ok:
                        s.detener()
                    return
                if ok:
                    with self._streams_lock:
                        self._streams[cam_id] = s
                else:
                    target_lbl.after(0, lambda: target_lbl.configure(
                        text=f"error cam {cam_id}"))

            threading.Thread(target=_iniciar, daemon=True).start()

    def _on_error(self, idx, msg=""):
        if self._desconectando:
            return
        with self._streams_lock:
            self._streams.pop(idx, None)
        for slot in self._slots:
            if slot["cam_idx"] == idx:
                slot["label"].after(0, lambda l=slot["label"]: l.configure(
                    image=None, text=f"fallo cam {idx}"))
        self._set_status(f"error cam {idx}: {msg}", "#e74c3c")

    def _set_status(self, text: str, color: str):
        if self._lbl_status and self._lbl_status.winfo_exists():
            try:
                self._lbl_status.after(0, lambda: self._lbl_status.configure(
                    text=text, text_color=color))
            except Exception:
                pass