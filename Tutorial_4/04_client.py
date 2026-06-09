import socket
import struct
import pickle
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import os
import serial
from o4_audio import AudioPanel, make_audio_button

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass

PORT_DEFAULT = 8888
MAX_CAMARAS = 4
import platform
BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2


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
            indices = list(range(MAX_CAMARAS))
    else:
        indices = list(range(MAX_CAMARAS))

    for i in indices:
        if len(disponibles) >= MAX_CAMARAS:
            break
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

        self.activo = True
        threading.Thread(target=self._transmitir, daemon=True).start()
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

    def _transmitir(self):
        try:
            while self.activo:
                ret, frame = self.captura.read()
                if not ret or frame is None:
                    continue
                small = cv2.resize(frame, (426, 240))
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                # Mandar numpy array — PhotoImage se crea en main thread
                self.preview_label.after(0, self._set_preview, rgb.copy())
                data = pickle.dumps((self.cam_index, rgb))
                header = struct.pack("Q", len(data))
                self.sock.sendall(header + data)
        except Exception as e:
            if self.activo:
                self.log(f"[Cam {self.cam_index}] Detenida: {e}")
                self.on_error(self.cam_index)
        finally:
            if self.captura:
                self.captura.release()

    def _recibir_msgs(self):
        while self.activo:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                msg = data.decode("utf-8").strip()
                if msg.startswith("SERIAL:"):
                    cmd = msg[7:]
                    self.app.manejar_serial(cmd)
                else:
                    self.log(f"[Servidor] {msg}")
            except:
                break

    def _set_preview(self, rgb_array):
        # PhotoImage creado en main thread — thread-safe
        im = Image.fromarray(rgb_array)
        img = ImageTk.PhotoImage(image=im)
        self.preview_label.configure(image=img, text="")
        self.preview_label.image = img


class ClienteCamara:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Cliente - Emisor y Control")
        self.master.geometry("1280x720")
        self.master.resizable(False, False)
        self.master.config(bg="#0a0a0a")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.camaras: list = []
        self.streams: dict = {}

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
        font_title = ("Consolas", 12, "bold")
        font_btn   = ("Consolas", 10, "bold")
        font_small = ("Consolas", 9, "bold")

        self.preview_labels = []
        coords = [(10, 10), (470, 10), (10, 280), (470, 280)]
        for i in range(MAX_CAMARAS):
            x, y = coords[i]
            lbl = tk.Label(self.master, text=f"Cam {i+1} Inactiva",
                           bg=panel_bg, fg="#444", font=font_title, anchor="center")
            lbl.place(x=x, y=y, width=450, height=258)
            self.preview_labels.append(lbl)

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
            self.master, text="🔍 Detectar Camaras", bg="#6c3483", fg=fg_color,
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
            ("Run ppnb",  b"Run ppnb\r",  1, 0, "#6c3483"),
            ("Abortar",   b"a\r",          2, 0, "#922b21"),
            ("Coff",      b"coff\r",       0, 1, "#784212"),
            ("Move 0",    b"move 0\r",     1, 1, "#1a5276"),
            ("Home",      b"home\r",       2, 1, "#0b5345"),
            ("Open",      b"open\r",       0, 2, "#424949"),
            ("Close",     b"close\r",      1, 2, "#17202a"),
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
        self.log_text.place(x=RX, y=430, width=RW, height=282)

        self.log("Sistema Iniciado.")

    def conectar_serial(self):
        try:
            if not self.serial_port.is_open:
                self.serial_port.port     = self.combo_com.get()
                self.serial_port.baudrate = 9600
                self.serial_port.bytesize = serial.EIGHTBITS
                self.serial_port.parity   = serial.PARITY_NONE
                self.serial_port.stopbits = serial.STOPBITS_ONE
                self.serial_port.timeout  = 1
                self.serial_port.xonxoff  = False
                self.serial_port.rtscts   = False
                self.serial_port.dsrdtr   = False
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
                self.log(f"Serial > {cmd_bytes.decode('utf-8', errors='ignore').strip()}")
            except Exception as e:
                self.log(f"Error serial: {e}")
        else:
            self.log(f"IGNORADO (serial cerrado): {cmd_bytes.decode('utf-8', errors='ignore').strip()}")

    def manejar_serial(self, cmd: str):
        if cmd == "ON":
            self.log("[Servidor: serial ON]")
            return
        if cmd == "OFF":
            self.log("[Servidor: serial OFF]")
            return

        ahora = time.time()
        if ahora - self._serial_cmd_ts.get(cmd, 0) < 0.3:
            return
        self._serial_cmd_ts[cmd] = ahora
        self._serial_send(cmd.encode("utf-8") + b"\r")

    def detectar_y_mostrar(self):
        self.log("Buscando camaras...")
        self.btn_detectar.config(state=tk.DISABLED, text="Buscando...")
        self.master.update()
        threading.Thread(
            target=lambda: self.master.after(0, self._mostrar, detectar_camaras()),
            daemon=True
        ).start()

    def _mostrar(self, encontradas: list):
        self.camaras = encontradas
        self.btn_detectar.config(state=tk.NORMAL, text="🔍 Detectar Camaras")

        for lbl in self.preview_labels:
            lbl.config(image="", text="Inactiva", bg="#141414")
            lbl.image = None

        if not encontradas:
            self.log("No se detectaron camaras.")
            self.btn_conectar.config(state=tk.DISABLED)
            return

        self.btn_conectar.config(state=tk.NORMAL)
        self.log(f"Detectadas: {encontradas}")

        for i, idx in enumerate(encontradas):
            if i < len(self.preview_labels):
                self.preview_labels[i].config(text=f"Camara {idx} (Lista)")

    def conectar_todo(self):
        if not self.camaras:
            return
        ip   = self.entry_ip.get().strip()
        port = int(self.entry_port.get().strip())

        self.btn_conectar.config(state=tk.DISABLED)
        self.btn_desconectar.config(state=tk.NORMAL)

        def _conectar_cam(i, idx):
            time.sleep(i * 0.3)  # escalonar para evitar race en VideoCapture
            lbl = self.preview_labels[i]
            s = StreamCamara(idx, ip, port, lbl, self.log, self._on_error, self)
            if s.iniciar():
                with self._streams_lock:
                    self.streams[idx] = s

        for i, idx in enumerate(self.camaras[:MAX_CAMARAS]):
            threading.Thread(target=_conectar_cam, args=(i, idx), daemon=True).start()

    def desconectar_todo(self):
        with self._streams_lock:
            for s in self.streams.values():
                s.detener()
            self.streams.clear()
        for i, lbl in enumerate(self.preview_labels):
            lbl.config(image="", text=f"Inactiva")
            lbl.image = None
        self.btn_conectar.config(state=tk.NORMAL)
        self.btn_desconectar.config(state=tk.DISABLED)
        self.log("Camaras desconectadas.")

    def _on_error(self, idx):
        with self._streams_lock:
            self.streams.pop(idx, None)
            empty = not self.streams
        if empty:
            self.master.after(0, lambda: self.btn_conectar.config(state=tk.NORMAL))
            self.master.after(0, lambda: self.btn_desconectar.config(state=tk.DISABLED))

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