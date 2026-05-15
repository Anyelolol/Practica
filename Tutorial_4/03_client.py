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


os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass

PORT_DEFAULT = 8888
MAX_CAMARAS = 4
BACKEND = cv2.CAP_DSHOW


def detectar_camaras() -> list:
    disponibles = []
    for i in range(MAX_CAMARAS):
        cap = cv2.VideoCapture(i, BACKEND)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                disponibles.append(i)
        cap.release()
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

                # Dimensiones equilibradas
                small = cv2.resize(frame, (426, 240))
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                im = Image.fromarray(rgb)
                img = ImageTk.PhotoImage(image=im)
                self.preview_label.after(0, self._set_preview, img)

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

                # PASO DIRECTO: Si empieza con ARM:, se manda directo al serial
                if msg.startswith("ARM:"):
                    cmd = msg[4:]
                    self.app.manejar_comando_arm(cmd)
                else:
                    self.log(f"[Servidor] {msg}")
            except:
                break

    def _set_preview(self, img):
        self.preview_label.configure(image=img, text="")
        self.preview_label.image = img


class ClienteCamara:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Cliente - Emisor y Control Brazo")
        self.master.geometry("1366x768")
        self.master.resizable(False, False)
        self.master.config(bg="black")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.camaras: list = []
        self.streams: dict = {}


        self.serial_port = serial.Serial()
        self._arm_cmd_ts: dict = {}

        self._build_ui()

    def _build_ui(self):
        bg_color = "black"
        fg_color = "white"
        panel_bg = "#1e1e1e"
        font_title = ("Arial", 14, "bold")
        font_btn = ("Arial", 11, "bold")

        self.preview_labels = []
        coords = [(20, 20), (480, 20), (20, 290), (480, 290)]
        for i in range(MAX_CAMARAS):
            x, y = coords[i]
            lbl = tk.Label(self.master, text=f"Cámara {i + 1} Inactiva",
                           bg=panel_bg, fg="#555", font=font_title, anchor="center")
            lbl.place(x=x, y=y, width=440, height=250)
            self.preview_labels.append(lbl)

        rx = 950

        # TCP
        tk.Label(self.master, text="Conexión Servidor", bg=bg_color, fg=fg_color, font=font_title).place(x=rx, y=20)
        self.entry_ip = tk.Entry(self.master, font=("Arial", 12), width=15)
        self.entry_ip.insert(0, "127.0.0.1")
        self.entry_ip.place(x=rx, y=55)

        self.entry_port = tk.Entry(self.master, font=("Arial", 12), width=7)
        self.entry_port.insert(0, str(PORT_DEFAULT))
        self.entry_port.place(x=rx + 160, y=55)

        self.btn_detectar = tk.Button(self.master, text="🔍 Detectar Cámaras", bg="#8e44ad", fg=fg_color, font=font_btn,
                                      command=self.detectar_y_mostrar)
        self.btn_detectar.place(x=rx, y=95, width=380, height=35)

        self.btn_conectar = tk.Button(self.master, text="▶ Conectar", bg="#2ecc71", fg=fg_color, font=font_btn,
                                      state=tk.DISABLED, command=self.conectar_todo)
        self.btn_conectar.place(x=rx, y=140, width=185, height=35)

        self.btn_desconectar = tk.Button(self.master, text="⏹ Desconectar", bg="#e74c3c", fg=fg_color, font=font_btn,
                                         state=tk.DISABLED, command=self.desconectar_todo)
        self.btn_desconectar.place(x=rx + 195, y=140, width=185, height=35)

        tk.Label(self.master, text="Conexión Brazo (Serial)", bg=bg_color, fg=fg_color, font=font_title).place(x=rx,
                                                                                                               y=210)

        self.combo_com = ttk.Combobox(self.master, state="readonly", values=[f"COM{i}" for i in range(1, 21)],
                                      font=("Arial", 12))
        self.combo_com.set("COM5")
        self.combo_com.place(x=rx, y=245, width=90)

        tk.Button(self.master, text="Conectar", bg="#2980b9", fg=fg_color, font=font_btn,
                  command=self.conectar_serial).place(x=rx + 100, y=242, width=135, height=30)
        tk.Button(self.master, text="Desconectar", bg="#e74c3c", fg=fg_color, font=font_btn,
                  command=self.desconectar_serial).place(x=rx + 245, y=242, width=135, height=30)

        self.lbl_serial_estado = tk.Label(self.master, text="⬤ DESCONECTADO", font=("Arial", 11, "bold"), bg=bg_color,
                                          fg="#e74c3c")
        self.lbl_serial_estado.place(x=rx, y=285)

        tk.Label(self.master, text="Control Manual", bg=bg_color, fg=fg_color, font=font_title).place(x=rx, y=330)

        comandos = [
            ("Run pcplc", b"Run pcplc\r", rx, 365, "#16a085"),
            ("Run ppnb", b"Run ppnb\r", rx + 130, 365, "#8e44ad"),
            ("Abortar", b"a\r", rx + 260, 365, "#c0392b"),
            ("Coff", b"coff\r", rx, 405, "#d35400"),
            ("Move 0", b"move 0\r", rx + 130, 405, "#2471a3"),
            ("Home", b"home\r", rx + 260, 405, "#117a65"),
            ("Open", b"open\r", rx, 445, "#626567"),
            ("Close", b"close\r", rx + 130, 445, "#1a252f")
        ]

        for texto, cmd_bytes, bx, by, color in comandos:
            tk.Button(self.master, text=texto, bg=color, fg=fg_color, font=("Arial", 9, "bold"),
                      command=lambda c=cmd_bytes: self._serial_send(c)).place(x=bx, y=by, width=120, height=30)

        # LOGS
        self.log_text = tk.Text(self.master, bg=panel_bg, fg=fg_color, font=("Consolas", 10))
        self.log_text.place(x=rx, y=500, width=380, height=240)
        self.log("Sistema Iniciado.")

    def conectar_serial(self):
        try:
            if not self.serial_port.is_open:
                self.serial_port.port = self.combo_com.get()
                self.serial_port.baudrate = 9600
                self.serial_port.bytesize = serial.EIGHTBITS
                self.serial_port.parity = serial.PARITY_NONE
                self.serial_port.stopbits = serial.STOPBITS_ONE
                self.serial_port.timeout = 1

                # IMPORTANTISIMO SEGÚN TU V2
                self.serial_port.xonxoff = False
                self.serial_port.rtscts = False
                self.serial_port.dsrdtr = False

                self.serial_port.open()

                self.lbl_serial_estado.config(text="⬤ CONECTADO", fg="#2ecc71")
                self.log(f"Puerto Serial {self.serial_port.port} Conectado")
                messagebox.showinfo(message="Puerto Conectado")
        except Exception as e:
            messagebox.showerror("Error Serial", str(e))
            self.lbl_serial_estado.config(text="⬤ DESCONECTADO", fg="#e74c3c")

    def desconectar_serial(self):
        if self.serial_port.is_open:
            self.serial_port.close()
            self.lbl_serial_estado.config(text="⬤ DESCONECTADO", fg="#e74c3c")
            self.log("Puerto Serial Desconectado")
            messagebox.showinfo(message="Puerto Desconectado")

    def _serial_send(self, cmd_bytes: bytes):
        if self.serial_port.is_open:
            try:
                self.serial_port.write(cmd_bytes)
                self.log(f"Serial -> {cmd_bytes.decode('utf-8', errors='ignore').strip()}")
            except Exception as e:
                self.log(f"Error Enviando: {e}")
        else:
            self.log(f"IGNORADO (Serial cerrado): {cmd_bytes}")

    def manejar_comando_arm(self, cmd: str):
        ahora = time.time()
        if ahora - self._arm_cmd_ts.get(cmd, 0) < 0.3:
            return
        self._arm_cmd_ts[cmd] = ahora

        if cmd == "ON":
            self.log("[Modo ARM Activado en Servidor]")
            return
        if cmd == "OFF":
            self.log("[Modo ARM Desactivado en Servidor]")
            return

        comando_bytes = cmd.encode("utf-8") + b"\r"
        self._serial_send(comando_bytes)

    def detectar_y_mostrar(self):
        self.log("Buscando cámaras...")
        self.btn_detectar.config(state=tk.DISABLED, text="Buscando...")
        self.master.update()
        threading.Thread(target=lambda: self.master.after(0, self._mostrar, detectar_camaras()), daemon=True).start()

    def _mostrar(self, encontradas: list):
        self.camaras = encontradas
        self.btn_detectar.config(state=tk.NORMAL, text="🔍 Detectar Cámaras")

        for lbl in self.preview_labels:
            lbl.config(image="", text="Inactiva", bg="#1e1e1e")
            lbl.image = None

        if not encontradas:
            self.log("No se detectaron cámaras.")
            self.btn_conectar.config(state=tk.DISABLED)
            return

        self.btn_conectar.config(state=tk.NORMAL)
        self.log(f"Detectadas: {encontradas}")

        for i, idx in enumerate(encontradas):
            if i < len(self.preview_labels):
                self.preview_labels[i].config(text=f"Cámara {idx} (Lista)")

    def conectar_todo(self):
        if not self.camaras:
            return
        ip = self.entry_ip.get().strip()
        port = int(self.entry_port.get().strip())

        self.btn_conectar.config(state=tk.DISABLED)
        self.btn_desconectar.config(state=tk.NORMAL)

        for i, idx in enumerate(self.camaras):
            if i < len(self.preview_labels):
                lbl = self.preview_labels[i]
                s = StreamCamara(idx, ip, port, lbl, self.log, self._on_error, self)
                if s.iniciar():
                    self.streams[idx] = s

    def desconectar_todo(self):
        for s in self.streams.values():
            s.detener()
        self.streams.clear()
        for i, lbl in enumerate(self.preview_labels):
            lbl.config(image="", text=f"Inactiva")
            lbl.image = None
        self.btn_conectar.config(state=tk.NORMAL)
        self.btn_desconectar.config(state=tk.DISABLED)
        self.log("Cámaras desconectadas.")

    def _on_error(self, idx):
        self.streams.pop(idx, None)
        if not self.streams:
            self.master.after(0, lambda: self.btn_conectar.config(state=tk.NORMAL))
            self.master.after(0, lambda: self.btn_desconectar.config(state=tk.DISABLED))

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def on_close(self):
        self.desconectar_todo()
        if self.serial_port.is_open:
            self.serial_port.close()
        self.master.destroy()


if __name__ == "__main__":
    ventana = tk.Tk()
    app = ClienteCamara(ventana)
    ventana.mainloop()