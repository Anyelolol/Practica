import socket
import threading
import struct
import pickle
import tkinter as tk
from PIL import Image, ImageTk
import subprocess
import atexit

HOST = ''
PORT = 8888
MAX_CONNECTIONS = 1
RULE_NAME = "CamaraServerMs_Temp_8888"

connections = []


def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def open_port():
    subprocess.run([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={RULE_NAME}", "dir=in", "action=allow",
        "protocol=TCP", f"localport={PORT}", "profile=private,domain"
    ], capture_output=True)
    log(f"Puerto {PORT} abierto en firewall")

def close_port():
    subprocess.run([
        "netsh", "advfirewall", "firewall", "delete", "rule",
        f"name={RULE_NAME}"
    ], capture_output=True)

atexit.register(close_port)

def log(msg):
    Log_Text.insert(tk.END, msg + "\n")
    Log_Text.see(tk.END)


def recibir_video(conn, addr):
    """Lee frames enviados por el cliente y los muestra en el Label."""
    log(f"Stream iniciado desde {addr}")
    data = b""
    payload_size = struct.calcsize("Q")   # 8 bytes

    while True:
        try:
            # 1. Leer los 8 bytes del encabezado (tamaño del payload)
            while len(data) < payload_size:
                packet = conn.recv(4096)
                if not packet:
                    raise ConnectionResetError("Cliente desconectado")
                data += packet

            packed_size = data[:payload_size]
            data        = data[payload_size:]
            msg_size    = struct.unpack("Q", packed_size)[0]

            # 2. Leer el payload completo
            while len(data) < msg_size:
                packet = conn.recv(4096)
                if not packet:
                    raise ConnectionResetError("Cliente desconectado")
                data += packet

            frame_data = data[:msg_size]
            data       = data[msg_size:]

            # 3. Deserializar y mostrar en la GUI (hilo principal)
            frame = pickle.loads(frame_data)
            im    = Image.fromarray(frame)
            img   = ImageTk.PhotoImage(image=im)
            LImagen.after(0, _mostrar_frame, img)

        except Exception as e:
            log(f"Stream terminado ({addr}): {e}")
            break

    conn.close()
    if conn in connections:
        connections.remove(conn)
    log(f"Conexión cerrada con {addr}")

def _mostrar_frame(img):
    LImagen.configure(image=img)
    LImagen.image = img   # evitar garbage-collection


# ─── Envío de mensajes al cliente ─────────────────────────────────────────────

def enviar_mensaje(event=None):
    texto = Entry_Mensaje.get().strip()
    if not texto:
        return
    Entry_Mensaje.delete(0, tk.END)

    payload = f"[SERVIDOR]: {texto}".encode("utf-8")
    muertos = []
    for conn in connections:
        try:
            conn.sendall(payload)
        except:
            muertos.append(conn)

    for c in muertos:
        connections.remove(c)

    log(f"Yo → {texto}")


Server_Socket = None

def correr_servidor():
    global Server_Socket
    Server_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    Server_Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    Server_Socket.bind((HOST, PORT))
    Server_Socket.listen(MAX_CONNECTIONS)
    log(f"Escuchando en puerto {PORT}…")

    while True:
        try:
            conn, addr = Server_Socket.accept()
            connections.append(conn)
            log(f"Cliente conectado: {addr}")
            t = threading.Thread(target=recibir_video, args=(conn, addr), daemon=True)
            t.start()
        except Exception as e:
            log(f"Servidor detenido: {e}")
            break

def iniciar_servidor():
    if is_admin():
        open_port()
    else:
        log("AVISO: sin privilegios de Administrador — abre el puerto manualmente")

    threading.Thread(target=correr_servidor, daemon=True).start()
    Start_Button.config(state=tk.DISABLED)
    Stop_Button.config(state=tk.NORMAL)
    EstadoLabel.config(text="Servidor corriendo", fg="green")

def detener_servidor():
    global Server_Socket
    close_port()
    if Server_Socket:
        try:
            Server_Socket.close()
        except:
            pass
    Start_Button.config(state=tk.NORMAL)
    Stop_Button.config(state=tk.DISABLED)
    EstadoLabel.config(text="Servidor detenido", fg="red")
    LImagen.configure(image="")

def on_close():
    close_port()
    ventana.destroy()

ventana = tk.Tk()
ventana.title("WCam — Servidor")
ventana.geometry("500x640")
ventana.resizable(False, False)
ventana.protocol("WM_DELETE_WINDOW", on_close)

EstadoLabel = tk.Label(ventana, text="Servidor detenido", fg="red",
                       font=("Arial", 11, "bold"))
EstadoLabel.place(x=10, y=10)

# Vista de cámara
LImagen = tk.Label(ventana, background="black")
LImagen.place(x=10, y=40, width=480, height=360)

# Log
Log_Text = tk.Text(ventana, height=7, width=58, font=("Consolas", 8))
Log_Text.place(x=10, y=415)

# Mensaje al cliente
tk.Label(ventana, text="Mensaje al cliente:", font=("Arial", 9)).place(x=10, y=548)
Entry_Mensaje = tk.Entry(ventana, width=50, font=("Arial", 10))
Entry_Mensaje.place(x=10, y=568)
Entry_Mensaje.bind("<Return>", enviar_mensaje)

btn_enviar = tk.Button(ventana, text="Enviar", command=enviar_mensaje,
                       bg="#3498db", fg="white", font=("Arial", 9, "bold"))
btn_enviar.place(x=390, y=565, width=90, height=26)

# Botones de servidor
Start_Button = tk.Button(ventana, text="Iniciar servidor",
                         command=iniciar_servidor, bg="#2ecc71", fg="white",
                         font=("Arial", 10, "bold"))
Start_Button.place(x=10, y=600, width=150, height=30)

Stop_Button = tk.Button(ventana, text="Detener",
                        command=detener_servidor, bg="#e74c3c", fg="white",
                        font=("Arial", 10, "bold"), state=tk.DISABLED)
Stop_Button.place(x=170, y=600, width=120, height=30)

if not is_admin():
    Log_Text.insert(tk.END, "No estás como Administrador — firewall manual necesario\n")

ventana.mainloop()