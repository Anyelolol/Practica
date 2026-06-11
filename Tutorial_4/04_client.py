import socket
import struct
import pickle
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import os
import serial
import platform
from o4_audio import AudioPanel, make_audio_button

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass

PORT_DEFAULT = 8888
BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2

TARGET_FPS = 15
FRAME_DELAY = 1.0 / TARGET_FPS
JPEG_QUALITY = 70


def detectar_camaras() -> list:
    disponibles = []
    if platform.system() == "Linux":
        import glob, subprocess as sp
        indices = []
        for d in sorted(glob.glob("/dev/video*")):
            try:
                idx = int(d.replace("/dev/video", ""))
            except:
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
    def __init__(self, cam_index, ip, port, preview_label, log_fn, on_error_fn, app):
        self.cam_index = cam_index
        self.ip = ip
        self.port = port
        self.preview_label = preview_label
        self.log = log_fn
        self.on_error = on_error_fn
        self.app = app
        self.sock = None
        self.captura = None
        self.activo = False

    def iniciar(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
        except Exception as e:
            self.log(f"[Cam {self.cam_index}] Error TCP: {e}")
            self.on_error(self.cam_index)
            return False

        self.captura = cv2.VideoCapture(self.cam_index, BACKEND)
        if not self.captura.isOpened():
            self.log(f"[Cam {self.cam_index}] No se pudo abrir")
            self.sock.close()
            self.on_error(self.cam_index)
            return False

        self._frame_queue = queue.Queue(maxsize=1)
        self.activo = True
        threading.Thread(target=self._capturar, daemon=True).start()
        threading.Thread(target=self._enviar, daemon=True).start()
        threading.Thread(target=self._recibir_msgs, daemon=True).start()
        self.log(f"[Cam {self.cam_index}] Transmitiendo a {self.ip}:{self.port}")
        return True

    def detener(self):
        self.activo = False
        if self.captura:
            self.captura.release()
            self.captura = None
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def _capturar(self):
        _preview_pending = False
        try:
            while self.activo:
                t0 = time.time()
                ret, frame = self.captura.read()
                if not ret or frame is None:
                    continue

                small = cv2.resize(frame, (426, 240))

                if not _preview_pending:
                    rgb_prev = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                    def do_preview(arr=rgb_prev):
                        nonlocal _preview_pending
                        self._set_preview(arr)
                        _preview_pending = False

                    _preview_pending = True
                    self.preview_label.after(0, do_preview)

                ok, jpg_buf = cv2.imencode(
                    '.jpg', small,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if not ok:
                    continue

                try:
                    self._frame_queue.put_nowait(jpg_buf)
                except queue.Full:
                    try:
                        self._frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self._frame_queue.put_nowait(jpg_buf)

                elapsed = time.time() - t0
                if elapsed < FRAME_DELAY:
                    time.sleep(FRAME_DELAY - elapsed)

        except Exception as e:
            if self.activo:
                self.log(f"[Cam {self.cam_index}] Error captura: {e}")
        finally:
            if self.captura:
                self.captura.release()
            try:
                self._frame_queue.put_nowait(None)
            except queue.Full:
                pass

    def _enviar(self):
        try:
            while self.activo:
                try:
                    jpg_buf = self._frame_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if jpg_buf is None:
                    break

                data = pickle.dumps((self.cam_index, jpg_buf))
                header = struct.pack("Q", len(data))
                self.sock.sendall(header + data)

        except Exception as e:
            if self.activo:
                self.log(f"[Cam {self.cam_index}] Error envío: {e}")
                self.on_error(self.cam_index)

    def _recibir_msgs(self):
        data_buffer = ""
        while self.activo:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                data_buffer += data.decode("utf-8")
                while "\n" in data_buffer:
                    line, data_buffer = data_buffer.split("\n", 1)
                    msg = line.strip()
                    if not msg:
                        continue
                    if msg.startswith("SERIAL:"):
                        cmd = msg[7:]
                        self.app.manejar_serial(cmd, self.cam_index)
                    else:
                        self.log(f"[Servidor] {msg}")
            except:
                break

    def _set_preview(self, rgb_array):
        im = Image.fromarray(rgb_array)
        img = ImageTk.PhotoImage(image=im)
        self.preview_label.configure(image=img, text="")
        self.preview_label.image = img


class ClienteCamara:
    BORDER_SEL = "#00e676"  # Verde brillante al seleccionar
    BORDER_NOSEL = "#2a2a2a"  # Gris oscuro

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Cliente - Control y Matriz Dinámica")
        self.master.geometry("1280x780")
        self.master.resizable(False, False)
        self.master.config(bg="#0a0a0a")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.camaras: list = []
        self.streams: dict = {}
        self.preview_slots: list = []
        self.local_preview_activo = False

        self.serial_port = serial.Serial()
        self._serial_cmd_ts: dict = {}
        self._streams_lock = threading.Lock()

        self._build_ui()

        self.audio_panel = AudioPanel(
            master=self.master,
            role="client",
            get_remote_ip=lambda: self.entry_ip.get().strip()
        )
        make_audio_button(self.master, self.audio_panel,
                          x=1060, y=390, width=180, height=30)

    def _build_ui(self):
        panel_bg = "#141414"
        fg_color = "white"
        font_btn = ("Consolas", 10, "bold")
        font_small = ("Consolas", 9, "bold")

        # --- CONTENEDOR SCROLLABLE PARA CÁMARAS DINÁMICAS ---
        self.canvas_camaras = tk.Canvas(self.master, bg="#0a0a0a", highlightthickness=0)
        self.scrollbar_v = ttk.Scrollbar(self.master, orient="vertical", command=self.canvas_camaras.yview)
        self.scroll_frame = tk.Frame(self.canvas_camaras, bg="#0a0a0a")

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas_camaras.configure(scrollregion=self.canvas_camaras.bbox("all"))
        )
        self.canvas_camaras.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas_camaras.configure(yscrollcommand=self.scrollbar_v.set)

        # Ubicación del contenedor scrollable (Cubre todo el flanco izquierdo de la UI)
        self.canvas_camaras.place(x=10, y=10, width=900, height=730)
        self.scrollbar_v.place(x=915, y=10, width=15, height=730)

        # Enlace del scroll general con la rueda del ratón
        self.master.bind_all("<MouseWheel>", self._on_mousewheel)
        self.master.bind_all("<Button-4>", self._on_mousewheel)
        self.master.bind_all("<Button-5>", self._on_mousewheel)

        # Mensaje flotante inicial de estado en el scroll_frame vacío
        self.lbl_inicial = tk.Label(self.scroll_frame,
                                    text="Presiona 'Detectar Cámaras' para iniciar la matriz de video...",
                                    bg="#0a0a0a", fg="#444", font=("Consolas", 11, "italic"))
        self.lbl_inicial.pack(pady=300, padx=180)

        # --- PANEL DE CONTROL DERECHO ---
        RX = 940
        RW = 330
        PAD = 6

        tk.Label(self.master, text="SERVIDOR", bg="#0a0a0a", fg="#555",
                 font=("Consolas", 9, "bold")).place(x=RX, y=10)

        frm_conn = tk.Frame(self.master, bg=panel_bg)
        frm_conn.place(x=RX, y=28, width=RW, height=32)

        self.entry_ip = tk.Entry(frm_conn, font=("Consolas", 11),
                                 bg="#1a1a1a", fg=fg_color, insertbackground=fg_color,
                                 relief="flat", bd=3, width=13)
        self.entry_ip.insert(0, "127.0.0.1")
        self.entry_ip.pack(side="left", padx=(0, PAD))

        self.entry_port = tk.Entry(frm_conn, font=("Consolas", 11),
                                   bg="#1a1a1a", fg=fg_color, insertbackground=fg_color,
                                   relief="flat", bd=3, width=5)
        self.entry_port.insert(0, str(PORT_DEFAULT))
        self.entry_port.pack(side="left")

        self.btn_detectar = tk.Button(
            self.master, text="🔍 Detectar Cámaras", bg="#6c3483", fg=fg_color,
            font=font_btn, relief="flat", cursor="hand2",
            command=self.detectar_y_mostrar)
        self.btn_detectar.place(x=RX, y=68, width=RW, height=30)

        self.btn_conectar = tk.Button(
            self.master, text="▶ Conectar", bg="#1e8449", fg=fg_color,
            font=font_btn, relief="flat", cursor="hand2",
            state=tk.DISABLED, command=self.conectar_todo)
        self.btn_conectar.place(x=RX, y=106, width=(RW - PAD) // 2, height=30)

        self.btn_desconectar = tk.Button(
            self.master, text="⏹ Desconectar", bg="#922b21", fg=fg_color,
            font=font_btn, relief="flat", cursor="hand2",
            state=tk.DISABLED, command=self.desconectar_todo)
        self.btn_desconectar.place(x=RX + (RW - PAD) // 2 + PAD, y=106,
                                   width=(RW - PAD) // 2, height=30)

        tk.Frame(self.master, bg="#222").place(x=RX, y=144, width=RW, height=1)

        tk.Label(self.master, text="SERIAL", bg="#0a0a0a", fg="#555",
                 font=("Consolas", 9, "bold")).place(x=RX, y=152)

        frm_serial = tk.Frame(self.master, bg="#0a0a0a")
        frm_serial.place(x=RX, y=170, width=RW, height=30)

        if platform.system() == "Windows":
            serial_ports = [f"COM{i}" for i in range(1, 21)]
            serial_default = "COM5"
        else:
            import glob
            serial_ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")) or ["/dev/ttyUSB0"]
            serial_default = serial_ports[0]

        self.combo_com = ttk.Combobox(frm_serial, state="readonly",
                                      values=serial_ports,
                                      font=("Consolas", 10), width=14)
        self.combo_com.set(serial_default)
        self.combo_com.pack(side="left", padx=(0, PAD))

        tk.Button(frm_serial, text="Conectar", bg="#1a5276", fg=fg_color,
                  font=font_small, relief="flat", cursor="hand2",
                  command=self.conectar_serial).pack(side="left", padx=(0, PAD))
        tk.Button(frm_serial, text="Desconectar", bg="#641e16", fg=fg_color,
                  font=font_small, relief="flat", cursor="hand2",
                  command=self.desconectar_serial).pack(side="left")

        self.lbl_serial_estado = tk.Label(
            self.master, text="⬤ DESCONECTADO",
            font=("Consolas", 9, "bold"), bg="#0a0a0a", fg="#e74c3c")
        self.lbl_serial_estado.place(x=RX, y=206, width=RW, height=18)

        tk.Frame(self.master, bg="#222").place(x=RX, y=230, width=RW, height=1)

        tk.Label(self.master, text="CONTROL MANUAL", bg="#0a0a0a", fg="#555",
                 font=("Consolas", 9, "bold")).place(x=RX, y=238)

        BW = (RW - PAD * 2) // 3
        BH = 28
        comandos = [
            ("Run pcplc", b"Run pcplc\r", 0, 0, "#0e6655"),
            ("Run ppnb", b"Run ppnb\r", 1, 0, "#6c3483"),
            ("Abortar", b"a\r", 2, 0, "#922b21"),
            ("Coff", b"coff\r", 0, 1, "#784212"),
            ("Move 0", b"move 0\r", 1, 1, "#1a5276"),
            ("Home", b"home\r", 2, 1, "#0b5345"),
            ("Open", b"open\r", 0, 2, "#424949"),
            ("Close", b"close\r", 1, 2, "#17202a"),
        ]
        for texto, cmd_bytes, col, row, color in comandos:
            bx = RX + col * (BW + PAD)
            by = 258 + row * (BH + PAD)
            tk.Button(self.master, text=texto, bg=color, fg=fg_color,
                      font=font_small, relief="flat", cursor="hand2",
                      command=lambda c=cmd_bytes: self._serial_send(c)
                      ).place(x=bx, y=by, width=BW, height=BH)

        tk.Frame(self.master, bg="#222").place(x=RX, y=362, width=RW, height=1)

        self.log_text = tk.Text(self.master, bg="#0d0d0d", fg="#777777",
                                font=("Consolas", 9), relief="flat", bd=0)
        self.log_text.place(x=RX, y=430, width=RW, height=340)

        self.log("Sistema Iniciado.")

    def _on_mousewheel(self, event):
        if platform.system() == "Windows":
            self.canvas_camaras.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif platform.system() == "Darwin":
            self.canvas_camaras.yview_scroll(int(-1 * event.delta), "units")
        else:
            if event.num == 4:
                self.canvas_camaras.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas_camaras.yview_scroll(1, "units")

    def get_seleccionadas(self) -> list:
        return [s["cam_idx"] for s in self.preview_slots if s["selected"] and s["cam_idx"] is not None]

    def _toggle_seleccion_slot(self, slot_idx):
        slot = self.preview_slots[slot_idx]
        if slot["cam_idx"] is None:
            return

        if slot["selected"]:
            slot["selected"] = False
            slot["outer"].config(bg=self.BORDER_NOSEL)
        else:
            slot["selected"] = True
            slot["outer"].config(bg=self.BORDER_SEL)

        if self.btn_desconectar.cget("state") == tk.NORMAL:
            self.actualizar_streams_en_tiempo_real()

    def actualizar_streams_en_tiempo_real(self):
        ip = self.entry_ip.get().strip()
        port = int(self.entry_port.get().strip())
        target_cams = self.get_seleccionadas()

        with self._streams_lock:
            cams_actuales = list(self.streams.keys())
        for c in cams_actuales:
            if c not in target_cams:
                with self._streams_lock:
                    s = self.streams.pop(c, None)
                if s:
                    s.detener()

        for slot_data in self.preview_slots:
            idx = slot_data["cam_idx"]
            if idx is None or idx not in target_cams:
                continue

            lbl = slot_data["label"]
            with self._streams_lock:
                s = self.streams.get(idx)

            if s:
                s.preview_label = lbl
            else:
                lbl.config(image="", text=f"Conectando Cam {idx}remoto...")

                def _iniciar_stream_async(cam_id=idx, target_lbl=lbl):
                    time.sleep(0.2)
                    if self.btn_desconectar.cget("state") != tk.NORMAL:
                        return
                    if cam_id not in self.get_seleccionadas():
                        return
                    s_new = StreamCamara(cam_id, ip, port, target_lbl, self.log, self._on_error, self)
                    if s_new.iniciar():
                        with self._streams_lock:
                            if self.btn_desconectar.cget("state") == tk.NORMAL and cam_id in self.get_seleccionadas():
                                self.streams[cam_id] = s_new
                            else:
                                s_new.detener()
                    else:
                        target_lbl.config(image="", text=f"Error Red Cam {cam_id}")

                threading.Thread(target=_iniciar_stream_async, daemon=True).start()

    def _bucle_preview_local(self, cam_idx, lbl):
        time.sleep(0.1)
        if not self.local_preview_activo:
            return
        cap = cv2.VideoCapture(cam_idx, BACKEND)
        if not cap.isOpened():
            lbl.after(0, lambda: lbl.config(text=f"Error Disp Cam {cam_idx}"))
            return
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        while self.local_preview_activo:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue
            small = cv2.resize(frame, (426, 240))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(rgb)
            photo = ImageTk.PhotoImage(image=im)

            def update_lbl(p=photo, l=lbl):
                if self.local_preview_activo:
                    l.config(image=p, text="")
                    l.image = p

            lbl.after(0, update_lbl)
            time.sleep(0.04)
        cap.release()

    def conectar_serial(self):
        try:
            if not self.serial_port.is_open:
                self.serial_port.port = self.combo_com.get()
                self.serial_port.baudrate = 9600
                self.serial_port.bytesize = serial.EIGHTBITS
                self.serial_port.parity = serial.PARITY_NONE
                self.serial_port.stopbits = serial.STOPBITS_ONE
                self.serial_port.timeout = 1
                self.serial_port.xonxoff = False
                self.serial_port.rtscts = False
                self.serial_port.dsrdtr = False
                self.serial_port.open()
                self.lbl_serial_estado.config(text="⬤ CONECTADO", fg="#2ecc71")
                self.log(f"Serial {self.serial_port.port} conectado")
                messagebox.showinfo(message="Puerto Conectado")
        except Exception as e:
            messagebox.showerror("Error Serial", str(e))
            self.lbl_serial_estado.config(text="⬤ DESCONECTADO", fg="#e74c3c")

    def desconectar_serial(self):
        if self.serial_port.is_open:
            self.serial_port.close()
            self.lbl_serial_estado.config(text="⬤ DESCONECTADO", fg="#e74c3c")
            self.log("Serial desconectado")
            messagebox.showinfo(message="Puerto Desconectado")

    def _serial_send(self, cmd_bytes: bytes):
        if self.serial_port.is_open:
            try:
                self.serial_port.write(cmd_bytes)
                self.serial_port.flush()
                print("ENVIADO RAW:", repr(cmd_bytes))
                self.log(f"Serial > {cmd_bytes.decode('utf-8', errors='ignore').strip()}")
            except Exception as e:
                self.log(f"Error serial: {e}")
        else:
            self.log(f"IGNORADO (serial cerrado): {cmd_bytes.decode('utf-8', errors='ignore').strip()}")

    def manejar_serial(self, cmd: str, cam_index: int):
        with self._streams_lock:
            if self.streams:
                primer_idx = min(self.streams.keys())
            else:
                primer_idx = None

        if cam_index != primer_idx:
            return

        if cmd == "ON":
            self.log("[Servidor: serial ON]")
            return
        if cmd == "OFF":
            self.log("[Servidor: serial OFF]")
            return
        cmd_limpio = cmd.strip()
        ahora = time.time()
        if ahora - self._serial_cmd_ts.get(cmd_limpio, 0) < 0.3:
            return
        self._serial_cmd_ts[cmd_limpio] = ahora
        self._serial_send(cmd_limpio.encode("utf-8") + b"\r")

    def detectar_y_mostrar(self):
        self.log("Detectando dispositivos de video activos en hardware...")
        self.btn_detectar.config(state=tk.DISABLED, text="Buscando...")
        self.master.update()
        threading.Thread(
            target=lambda: self.master.after(0, self._mostrar, detectar_camaras()),
            daemon=True
        ).start()

    def _mostrar(self, encontradas: list):
        self.camaras = encontradas
        self.btn_detectar.config(state=tk.NORMAL, text="🔍 Detectar Cámaras")

        # Apagar previsualizaciones previas y limpiar por completo el Frame de Scroll
        self.local_preview_activo = False
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.preview_slots.clear()

        if not encontradas:
            self.log("No se detectó ningún hardware de cámara.")
            self.lbl_inicial = tk.Label(self.scroll_frame, text="Sin cámaras detectadas en el sistema.",
                                        bg="#0a0a0a", fg="#922b21", font=("Consolas", 11, "bold"))
            self.lbl_inicial.pack(pady=300, padx=180)
            self.btn_conectar.config(state=tk.DISABLED)
            return

        self.btn_conectar.config(state=tk.NORMAL)
        self.log(f"Matriz configurada para {len(encontradas)} cámara(s). Inicializando video directo...")

        # Construir dinámicamente los frames en formato de cuadrícula de 2 columnas dentro del Scrollable Frame
        self.local_preview_activo = True
        panel_bg = "#141414"
        font_title = ("Consolas", 11, "bold")

        for idx_slot, cam_idx in enumerate(encontradas):
            fila = idx_slot // 2
            columna = idx_slot % 2

            # Contenedor rígido externo del slot (Borde indicador)
            outer = tk.Frame(self.scroll_frame, bg=self.BORDER_NOSEL, padx=3, pady=3, cursor="hand2",
                             width=434, height=250)
            outer.grid_propagate(False)
            outer.grid(row=fila, column=columna, padx=6, pady=6)

            lbl = tk.Label(outer, text=f"Inicializando Cam {cam_idx}...",
                           bg=panel_bg, fg="#555", font=font_title, anchor="center")
            lbl.pack(fill="both", expand=True)

            slot_data = {
                "outer": outer,
                "label": lbl,
                "cam_idx": cam_idx,
                "selected": False
            }
            self.preview_slots.append(slot_data)

            # Enlazar clics de selección
            outer.bind("<Button-1>", lambda e, s_idx=idx_slot: self._toggle_seleccion_slot(s_idx))
            lbl.bind("<Button-1>", lambda e, s_idx=idx_slot: self._toggle_seleccion_slot(s_idx))

            # Lanzar el hilo de renderizado individual
            threading.Thread(target=self._bucle_preview_local, args=(cam_idx, lbl), daemon=True).start()

        # Forzar reposicionamiento inicial del canvas
        self.canvas_camaras.yview_moveto(0)

    def conectar_todo(self):
        seleccionadas = self.get_seleccionadas()
        if not seleccionadas:
            messagebox.showwarning(
                "Sin selección",
                "Haz clic directo sobre cualquiera de las pantallas para marcar cuáles deseas transmitir remótamente."
            )
            return

        self.local_preview_activo = False

        # Ocultar visualmente la reproducción local de las cámaras que decidiste NO transmitir
        for slot in self.preview_slots:
            if not slot["selected"]:
                slot["label"].config(image="", text=f"Cam {slot['cam_idx']} en Espera (Local)")
                slot["label"].image = None

        self.btn_conectar.config(state=tk.DISABLED)
        self.btn_desconectar.config(state=tk.NORMAL)

        self.log(f"Iniciando sockets de red para: {seleccionadas}")
        self.actualizar_streams_en_tiempo_real()

    def desconectar_todo(self):
        with self._streams_lock:
            for s in self.streams.values():
                s.detener()
            self.streams.clear()

        self.btn_conectar.config(state=tk.NORMAL)
        self.btn_desconectar.config(state=tk.DISABLED)
        self.log("Sockets cerrados. Volviendo a video local total.")

        # Re-encender de golpe todas las cámaras en reproducción interna local
        self.local_preview_activo = True
        for slot in self.preview_slots:
            threading.Thread(target=self._bucle_preview_local, args=(slot["cam_idx"], slot["label"]),
                             daemon=True).start()

    def _on_error(self, idx):
        with self._streams_lock:
            self.streams.pop(idx, None)

        def _handle_err():
            for slot in self.preview_slots:
                if slot["cam_idx"] == idx:
                    slot["label"].config(image="", text=f"Fallo crítico Cam {idx}")
                    slot["label"].image = None

        self.master.after(0, _handle_err)

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def on_close(self):
        self.desconectar_todo()
        self.audio_panel.destroy()
        if self.serial_port.is_open:
            self.serial_port.close()
        self.master.destroy()


if __name__ == "__main__":
    ventana = tk.Tk()
    app = ClienteCamara(ventana)
    ventana.mainloop()