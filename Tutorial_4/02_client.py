import socket
import struct
import pickle
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import os

# Silenciar logs de OpenCV ANTES de cualquier uso
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    pass

PORT_DEFAULT  = 8888
MAX_CAMARAS   = 4        # pocas búsquedas = menos warnings
BACKEND       = cv2.CAP_DSHOW   # un solo backend para todas las cámaras


def detectar_camaras() -> list:
    """
    Detecta cámaras reales usando CAP_DSHOW (un solo backend).
    Devuelve lista de índices enteros válidos.
    """
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
    """Una cámara = una conexión TCP independiente al servidor."""

    def __init__(self, cam_index, ip, port, preview_label, log_fn, on_error_fn):
        self.cam_index     = cam_index
        self.ip            = ip
        self.port          = port
        self.preview_label = preview_label
        self.log           = log_fn
        self.on_error      = on_error_fn
        self.sock          = None
        self.captura       = None
        self.activo        = False

    def iniciar(self) -> bool:
        # 1) Conectar TCP
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)
        except Exception as e:
            self.log(f"[Cam {self.cam_index}] Error TCP: {e}")
            self.on_error(self.cam_index)
            return False

        # 2) Abrir cámara — mismo backend que en detección
        self.captura = cv2.VideoCapture(self.cam_index, BACKEND)
        if not self.captura.isOpened():
            self.log(f"[Cam {self.cam_index}] No se pudo abrir")
            self.sock.close()
            self.on_error(self.cam_index)
            return False

        self.activo = True
        threading.Thread(target=self._transmitir,    daemon=True).start()
        threading.Thread(target=self._recibir_msgs,  daemon=True).start()
        self.log(f"[Cam {self.cam_index}] Activa (DSHOW) → {self.ip}:{self.port}")
        return True

    def detener(self):
        self.activo = False
        if self.captura:
            self.captura.release()
            self.captura = None
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None

    def _transmitir(self):
        try:
            while self.activo:
                ret, frame = self.captura.read()
                if not ret or frame is None:
                    continue

                small = cv2.resize(frame, (320, 240))
                rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                # Preview local
                im  = Image.fromarray(rgb)
                img = ImageTk.PhotoImage(image=im)
                self.preview_label.after(0, self._set_preview, img)

                # Enviar (cam_index, frame) al servidor
                data   = pickle.dumps((self.cam_index, rgb))
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
                if not data: break
                self.log(f"[Srv→{self.cam_index}] {data.decode('utf-8')}")
            except: break

    def _set_preview(self, img):
        self.preview_label.configure(image=img)
        self.preview_label.image = img

class ClienteCamara:

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("WCam — Cliente Emisor")
        self.master.geometry("560x700")
        self.master.resizable(False, False)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.camaras:        list = []   # [index, ...]
        self.streams:        dict = {}   # index → StreamCamara
        self.preview_labels: dict = {}   # index → tk.Label
        self.cam_frames:     dict = {}   # index → tk.Frame

        self._build_ui()

    def _build_ui(self):
        m = self.master

        tk.Label(m, text="IP del servidor:").place(x=10, y=10)
        self.entry_ip = tk.Entry(m, width=18, font=("Arial", 10))
        self.entry_ip.insert(0, "127.0.0.1")
        self.entry_ip.place(x=120, y=10)

        tk.Label(m, text="Puerto:").place(x=260, y=10)
        self.entry_port = tk.Entry(m, width=7, font=("Arial", 10))
        self.entry_port.insert(0, str(PORT_DEFAULT))
        self.entry_port.place(x=310, y=10)

        self.btn_detectar = tk.Button(
            m, text="🔍 Detectar Cámaras", command=self.detectar_y_mostrar,
            bg="#8e44ad", fg="white", font=("Arial", 9, "bold"))
        self.btn_detectar.place(x=10, y=40, width=160, height=26)

        self.lbl_info = tk.Label(m, text="Cámaras: (sin detectar)",
                                 font=("Arial", 9), fg="#555")
        self.lbl_info.place(x=180, y=44)

        self.btn_conectar = tk.Button(
            m, text="▶ Conectar todo", command=self.conectar_todo,
            bg="#27ae60", fg="white", font=("Arial", 9, "bold"), state=tk.DISABLED)
        self.btn_conectar.place(x=390, y=7, width=155, height=26)

        self.btn_desconectar = tk.Button(
            m, text="⏹ Desconectar todo", command=self.desconectar_todo,
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), state=tk.DISABLED)
        self.btn_desconectar.place(x=390, y=37, width=155, height=26)

        self.lbl_estado = tk.Label(m, text="Estado: Desconectado",
                                   fg="red", font=("Arial", 9, "bold"))
        self.lbl_estado.place(x=10, y=75)

        # Área de previews
        self.canvas_area = tk.Canvas(m, bg="#111", highlightthickness=0)
        self.canvas_area.place(x=10, y=100, width=540, height=480)
        self.frame_prev = tk.Frame(self.canvas_area, bg="#111")
        self.canvas_area.create_window((0, 0), window=self.frame_prev, anchor="nw")

        # Log
        tk.Label(m, text="Log:", font=("Arial", 8)).place(x=10, y=585)
        self.log_text = tk.Text(m, height=5, width=68, font=("Consolas", 8))
        self.log_text.place(x=10, y=600)

    def detectar_y_mostrar(self):
        self.log("Detectando cámaras...")
        self.btn_detectar.config(state=tk.DISABLED, text="Buscando...")
        self.master.update()
        threading.Thread(target=lambda: self.master.after(
            0, self._mostrar, detectar_camaras()), daemon=True).start()

    def _mostrar(self, encontradas: list):
        self.camaras = encontradas
        self.btn_detectar.config(state=tk.NORMAL, text="🔍 Detectar Cámaras")

        for w in self.frame_prev.winfo_children():
            w.destroy()
        self.preview_labels.clear()
        self.cam_frames.clear()

        if not encontradas:
            self.lbl_info.config(text="No se encontraron cámaras", fg="red")
            self.btn_conectar.config(state=tk.DISABLED)
            self.log("Sin cámaras detectadas.")
            return

        self.lbl_info.config(
            text=f"Encontradas: {len(encontradas)} → índices {encontradas}",
            fg="#27ae60")

        cols = 2
        for i, idx in enumerate(encontradas):
            row, col = divmod(i, cols)
            frm = tk.Frame(self.frame_prev, bg="#222", relief="ridge", bd=2)
            frm.grid(row=row, column=col, padx=6, pady=6)
            self.cam_frames[idx] = frm

            tk.Label(frm, text=f"Cámara {idx}  [DSHOW]",
                     bg="#222", fg="white", font=("Arial", 9, "bold")).pack()

            lbl = tk.Label(frm, background="#1a1a2e", width=256, height=144)
            lbl.pack()
            self.preview_labels[idx] = lbl

            est = tk.Label(frm, text="● Inactiva",
                           bg="#222", fg="#e74c3c", font=("Arial", 8))
            est.pack()
            frm._estado = est

        self.frame_prev.update_idletasks()
        self.btn_conectar.config(state=tk.NORMAL)
        self.log(f"Listas: {encontradas}")

    def conectar_todo(self):
        if not self.camaras:
            messagebox.showwarning("Sin cámaras", "Primero detecta las cámaras.")
            return
        ip = self.entry_ip.get().strip()
        try:
            port = int(self.entry_port.get().strip())
        except ValueError:
            messagebox.showerror("Puerto inválido", "Debe ser un número.")
            return

        self.btn_conectar.config(state=tk.DISABLED)
        self.btn_desconectar.config(state=tk.NORMAL)
        self.lbl_estado.config(text=f"Transmitiendo → {ip}:{port}", fg="green")

        for idx in self.camaras:
            lbl = self.preview_labels.get(idx)
            if lbl is None:
                continue
            s = StreamCamara(idx, ip, port, lbl, self.log, self._on_error)
            if s.iniciar():
                self.streams[idx] = s
                frm = self.cam_frames.get(idx)
                if frm and hasattr(frm, "_estado"):
                    frm._estado.config(text="● Activa", fg="#27ae60")

    def desconectar_todo(self):
        for s in self.streams.values():
            s.detener()
        self.streams.clear()
        for idx, frm in self.cam_frames.items():
            if hasattr(frm, "_estado"):
                frm._estado.config(text="● Inactiva", fg="#e74c3c")
            lbl = self.preview_labels.get(idx)
            if lbl:
                lbl.config(image=""); lbl.image = None
        self.lbl_estado.config(text="Estado: Desconectado", fg="red")
        self.btn_conectar.config(state=tk.NORMAL)
        self.btn_desconectar.config(state=tk.DISABLED)
        self.log("Desconectado.")

    def _on_error(self, idx):
        def _ui():
            self.streams.pop(idx, None)
            frm = self.cam_frames.get(idx)
            if frm and hasattr(frm, "_estado"):
                frm._estado.config(text="● Error", fg="#e67e22")
            if not self.streams:
                self.lbl_estado.config(text="Estado: Desconectado", fg="red")
                self.btn_conectar.config(state=tk.NORMAL)
                self.btn_desconectar.config(state=tk.DISABLED)
        self.master.after(0, _ui)

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def on_close(self):
        self.desconectar_todo()
        self.master.destroy()


if __name__ == "__main__":
    ventana = tk.Tk()
    app = ClienteCamara(ventana)
    ventana.mainloop()
