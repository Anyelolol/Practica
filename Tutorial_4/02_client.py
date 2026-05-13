import socket
import struct
import pickle
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2

PORT_DEFAULT = 8888

class ClienteCamara:

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("WCam — Cliente Emisor")
        self.master.geometry("520x620") 
        self.master.resizable(False, False)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.sock      = None
        self.conectado = False
        self.captura   = None
        self.indice_actual = 0 

        self._build_ui()

    def _build_ui(self):
        m = self.master

        # --- Conexión ---
        tk.Label(m, text="IP del servidor:").place(x=10, y=10)
        self.entry_ip = tk.Entry(m, width=18, font=("Arial", 10))
        self.entry_ip.insert(0, "127.0.0.1")
        self.entry_ip.place(x=120, y=10)

        tk.Label(m, text="Puerto:").place(x=260, y=10)
        self.entry_port = tk.Entry(m, width=7, font=("Arial", 10))
        self.entry_port.insert(0, str(PORT_DEFAULT))
        self.entry_port.place(x=310, y=10)

        # --- Control de Cámara con Botón ---
        tk.Label(m, text="Cámara actual:").place(x=10, y=40)
        self.lbl_cam_info = tk.Label(m, text="ID: 0 (Frontal)", font=("Arial", 9, "bold"), fg="blue")
        self.lbl_cam_info.place(x=120, y=40)

        self.btn_switch = tk.Button(
            m, text="🔄 Cambiar Cámara", command=self.alternar_camara,
            bg="#3498db", fg="white", font=("Arial", 8, "bold")
        )
        self.btn_switch.place(x=230, y=37, width=130, height=26)

        # --- Botones de Conexión ---
        self.btn_conectar = tk.Button(
            m, text="Conectar", command=self.conectar,
            bg="#27ae60", fg="white", font=("Arial", 9, "bold")
        )
        self.btn_conectar.place(x=390, y=7, width=100, height=26)

        self.btn_desconectar = tk.Button(
            m, text="Desconectar", command=self.desconectar,
            bg="#e74c3c", fg="white", font=("Arial", 9, "bold"), state=tk.DISABLED
        )
        self.btn_desconectar.place(x=390, y=37, width=100, height=26)

        # --- Estado ---
        self.lbl_estado = tk.Label(m, text="Estado: Desconectado", fg="red",
                                   font=("Arial", 9, "bold"))
        self.lbl_estado.place(x=10, y=75)

        # --- Vista de video local ---
        self.LImagen = tk.Label(m, background="#1a1a2e", relief="sunken")
        self.LImagen.place(x=10, y=105, width=500, height=360)

        # --- Log / mensajes del servidor ---
        tk.Label(m, text="Mensajes del servidor:", font=("Arial", 8)).place(x=10, y=475)
        self.log_text = tk.Text(m, height=6, width=64, font=("Consolas", 8))
        self.log_text.place(x=10, y=493)

    def alternar_camara(self):
        """ Cambia entre índice 0 y 1 """
        self.indice_actual = 1 if self.indice_actual == 0 else 0
        tipo = "Trasera" if self.indice_actual == 1 else "Frontal"
        self.lbl_cam_info.config(text=f"ID: {self.indice_actual} ({tipo})")
        
        # Si ya estamos transmitiendo, el hilo _transmitir_video 
        # detectará el cambio de self.indice_actual automáticamente.
        self.log(f"Cámara cambiada a: {tipo}")

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def conectar(self):
        ip   = self.entry_ip.get().strip()
        port = int(self.entry_port.get().strip())

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((ip, port))
            self.sock.settimeout(None)
            self.conectado = True
        except Exception as e:
            messagebox.showerror("Error de conexión", str(e))
            return

        self.log(f"Conectado a {ip}:{port}")
        self.lbl_estado.config(text=f"Estado: Transmitiendo a {ip}", fg="green")
        self.btn_conectar.config(state=tk.DISABLED)
        self.btn_desconectar.config(state=tk.NORMAL)

        threading.Thread(target=self._transmitir_video, daemon=True).start()
        threading.Thread(target=self._recibir_mensajes, daemon=True).start()

    def desconectar(self):
        self.conectado = False
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None

        self.LImagen.config(image="")
        self.LImagen.image = None
        self.lbl_estado.config(text="Estado: Desconectado", fg="red")
        self.btn_conectar.config(state=tk.NORMAL)
        self.btn_desconectar.config(state=tk.DISABLED)
        self.log("Desconectado del servidor")

    def _recibir_mensajes(self):
        while self.conectado:
            try:
                data = self.sock.recv(1024)
                if not data: break
                self.master.after(0, self.log, data.decode("utf-8"))
            except:
                break

    def _transmitir_video(self):
        # Iniciar cámara con el índice actual
        id_cam_local = self.indice_actual
        self.captura = cv2.VideoCapture(id_cam_local)

        try:
            while self.conectado:
                # Si el índice cambió por el botón, reiniciamos captura
                if id_cam_local != self.indice_actual:
                    self.captura.release()
                    id_cam_local = self.indice_actual
                    self.captura = cv2.VideoCapture(id_cam_local)

                ret, frame = self.captura.read()
                if not ret:
                    continue

                frame     = cv2.resize(frame, (320, 240))
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Actualizar vista local
                im  = Image.fromarray(rgb_frame)
                img = ImageTk.PhotoImage(image=im)
                self.LImagen.after(0, self._actualizar_imagen, img)

                # Enviar al servidor
                data         = pickle.dumps(rgb_frame)
                message_size = struct.pack("Q", len(data))
                self.sock.sendall(message_size + data)

        except Exception as e:
            if self.conectado:
                self.master.after(0, self.log, f"Transmisión detenida: {e}")
                self.master.after(0, self.desconectar)
        finally:
            if self.captura is not None:
                self.captura.release()

    def _actualizar_imagen(self, img):
        self.LImagen.configure(image=img)
        self.LImagen.image = img

    def on_close(self):
        self.desconectar()
        self.master.destroy()

if __name__ == "__main__":
    ventana = tk.Tk()
    app = ClienteCamara(ventana)
    ventana.mainloop()
