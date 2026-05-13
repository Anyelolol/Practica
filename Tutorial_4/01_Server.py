import socket
import threading
import tkinter as tk
import subprocess
import atexit

HOST = ''
PORT = 8888
MAX_CONNECTIONS = 2
RULE_NAME = "ChatServer_Temp_8888"

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
        f"name={RULE_NAME}",
        "dir=in", "action=allow",
        "protocol=TCP",
        f"localport={PORT}",
        "profile=private,domain"
    ], capture_output=True)
    log(f"Puerto {PORT} abierto en firewall")

def close_port():
    subprocess.run([
        "netsh", "advfirewall", "firewall", "delete", "rule",
        f"name={RULE_NAME}"
    ], capture_output=True)

atexit.register(close_port)

def log(mensaje):
    Log_Text.insert(tk.END, mensaje + "\n")
    Log_Text.see(tk.END)

def iniciar_Servidor():
    if not is_admin():
        log("Ejecutá el script como Administrador para abrir el firewall")
        return

    open_port()

    servidor_thread = threading.Thread(target=correr_Servidor)
    servidor_thread.start()

    Start_Button.config(state=tk.DISABLED)
    Stop_Button.config(state=tk.NORMAL)

    EstadoLabel.config(text="Servidor corriendo")

def detener_Servidor():
    global Server_Socket

    close_port()

    Server_Socket.close()

    Start_Button.config(state=tk.NORMAL)
    Stop_Button.config(state=tk.DISABLED)

    EstadoLabel.config(text="Servidor detenido")

def manejar_conexion(conn, addr, name):
    log(f"{name} conectado por {addr}")

    while True:
        try:
            data = conn.recv(1024)

            if not data:
                break

            mensaje = data.decode().strip()

            log(f"Datos recibidos de {name}: {mensaje}")

            conn.sendall(mensaje.encode())
        except:
            break

    conn.close()
    log(f"Conexión cerrada con {name}")

def correr_Servidor():
    global Server_Socket

    Server_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    Server_Socket.bind((HOST, PORT))

    Server_Socket.listen(MAX_CONNECTIONS)

    log(f"Servidor corriendo en puerto {PORT}")

    while True:
        try:
            conn, addr = Server_Socket.accept()

            connections.append(conn)

            data = conn.recv(1024)

            name = data.decode().strip()

            t = threading.Thread( target=manejar_conexion, args=(conn, addr, name))

            t.start()

        except:
            break

def enviar_Mensaje():
    mensaje = mensaje_Text.get("1.0", tk.END).strip()

    mensaje_Text.delete("1.0", tk.END)

    log(f"Mensaje enviado: {mensaje}")

    for conn in connections:
        try:
            conn.sendall(mensaje.encode())
        except:
            pass

def on_close():
    close_port()
    ventana.destroy()

ventana = tk.Tk()

ventana.title("Servidor")
ventana.geometry("500x500")
ventana.protocol("WM_DELETE_WINDOW", on_close)
EstadoLabel = tk.Label(ventana, text="Servidor detenido")
EstadoLabel.place(x=10, y=10)

Log_Text = tk.Text(ventana, height=10, width=50)
Log_Text.place(x=10, y=40)

Start_Button = tk.Button(
    ventana,
    text="Iniciar",
    command=iniciar_Servidor
)

Start_Button.place(x=10, y=230)

Stop_Button = tk.Button(
    ventana,
    text="Detener",
    command=detener_Servidor,
    state=tk.DISABLED
)

Stop_Button.place(x=100, y=230)

mensaje_Text = tk.Text(ventana, height=5, width=50)
mensaje_Text.place(x=10, y=280)

Enviar_Button = tk.Button(
    ventana,
    text="Enviar",
    command=enviar_Mensaje
)

Enviar_Button.place(x=10, y=400)

if not is_admin():
    Log_Text.insert(tk.END, "No estás como Administrador — el firewall no se podrá abrir\n")

ventana.mainloop()