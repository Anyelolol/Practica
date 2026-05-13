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
MAX_CONNECTIONS = 4
RULE_NAME = "CamaraServer_Temp_8888"

# Cada cliente: addr_str → { conn, slot, cam_id, num_conexion }
clients = {}
clients_lock = threading.Lock()
conexion_counter = 0   # contador global de conexiones (1-based)

Server_Socket = None
Servidor_Activo = False

# addr_str que está en el slot 0 (pantalla grande)
primary_addr = None

# Dimensiones por slot
SLOT_DIMS = [(966, 540), (320, 180), (320, 180), (320, 180)]


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
    Log_Text.config(state="normal")
    Log_Text.insert("end", msg + "\n")
    Log_Text.see("end")
    Log_Text.config(state="disabled")


def addr_key(addr):
    return f"{addr[0]}:{addr[1]}"

def get_labels():
    return [LImagen, LImagen1, LImagen2, LImagen3]


def get_buttons():
    return [Cam, Cam1, Cam2, Cam3]


def assign_slot(ak):
    """Asigna el primer slot libre. Slot 0 va al primero en conectarse."""
    global primary_addr
    used = {info["slot"] for info in clients.values()}
    if primary_addr is None:
        primary_addr = ak
        return 0
    for s in range(1, 4):
        if s not in used:
            return s
    return -1


def refresh_buttons():
    """Actualiza texto y color de los 4 botones de cámara."""
    with clients_lock:
        slot_map = {info["slot"]: info for info in clients.values()}
    btns = get_buttons()
    for i, btn in enumerate(btns):
        if i in slot_map:
            info = slot_map[i]
            label = f"C{info['num_conexion']}\nCam{info['cam_id']}"
            btn.config(text=label, bg="#27ae60",
                       font=("Arial", 7, "bold"), wraplength=35)
        else:
            btn.config(text=str(i + 1), bg="#2e2e2e",
                       font=("Arial", 16, "bold"), wraplength=0)


def swap_to_primary(slot_index):
    """Mueve la cámara del slot_index al slot 0, intercambiando con la primaria."""
    global primary_addr
    with clients_lock:
        target_key = None
        old_primary = primary_addr
        for ak, info in clients.items():
            if info["slot"] == slot_index:
                target_key = ak
                break
        if target_key is None or target_key == old_primary:
            return
        # Intercambiar slots
        clients[target_key]["slot"] = 0
        if old_primary and old_primary in clients:
            clients[old_primary]["slot"] = slot_index
        primary_addr = target_key
    ventana.after(0, refresh_buttons)


def resize_cover(frame_array, slot):
    """Escala y recorta el frame para llenar el slot exacto."""
    fw, fh = SLOT_DIMS[slot]
    im = Image.fromarray(frame_array)
    iw, ih = im.size
    scale = max(fw / iw, fh / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - fw) // 2
    top = (nh - fh) // 2
    return im.crop((left, top, left + fw, top + fh))


def render_frame(slot, pil_img, overlay_text):
    """Actualiza el label del slot con la imagen y texto de enumeración."""
    labels = get_labels()
    lbl = labels[slot]
    photo = ImageTk.PhotoImage(image=pil_img)
    lbl.configure(image=photo, text=overlay_text,
                  compound="center",
                  font=("Arial", 12, "bold"),
                  fg="white", bg="#000")
    lbl.image = photo

def recibir_video(conn, addr):
    global conexion_counter, primary_addr

    ak = addr_key(addr)
    with clients_lock:
        conexion_counter += 1
        num = conexion_counter
        slot = assign_slot(ak)
        clients[ak] = {
            "conn": conn,
            "slot": slot,
            "cam_id": "?",
            "num_conexion": num,
        }

    ventana.after(0, refresh_buttons)
    log(f"- Conexión #{num} desde {addr} → slot {slot}")

    buf = b""
    hdr_size = struct.calcsize("Q")

    while Servidor_Activo:
        try:
            # Leer header
            while len(buf) < hdr_size:
                chunk = conn.recv(4096)
                if not chunk:
                    raise ConnectionResetError
                buf += chunk

            msg_size = struct.unpack("Q", buf[:hdr_size])[0]
            buf = buf[hdr_size:]

            # Leer payload
            while len(buf) < msg_size:
                chunk = conn.recv(4096)
                if not chunk:
                    raise ConnectionResetError
                buf += chunk

            raw = buf[:msg_size]
            buf = buf[msg_size:]

            # Deserializar — esperamos (cam_index, frame_array)
            payload = pickle.loads(raw)
            if isinstance(payload, tuple) and len(payload) == 2:
                cam_id, frame = payload
            else:
                # compatibilidad: solo frame
                cam_id = "?"
                frame = payload

            # Actualizar cam_id en el registro
            with clients_lock:
                if ak in clients:
                    clients[ak]["cam_id"] = str(cam_id)
                    current_slot = clients[ak]["slot"]
                    current_num = clients[ak]["num_conexion"]
                else:
                    break

            if 0 <= current_slot < 4:
                im = resize_cover(frame, current_slot)
                overlay = f""
                ventana.after(0, render_frame, current_slot, im, overlay)
                # Refrescar botones cuando tengamos cam_id real
                ventana.after(0, refresh_buttons)

        except Exception as e:
            log(f"- Stream #{num} terminado ({addr}): {e}")
            break

    with clients_lock:
        freed_slot = clients.get(ak, {}).get("slot", -1)
        clients.pop(ak, None)
        if primary_addr == ak:
            primary_addr = None
            # Promover el cliente con slot más bajo al slot 0
            remaining = sorted(clients.items(), key=lambda x: x[1]["slot"])
            if remaining:
                next_ak, next_info = remaining[0]
                next_info["slot"] = 0
                primary_addr = next_ak

    def clear_slot(s):
        lbs = get_labels()
        if 0 <= s < len(lbs):
            lbs[s].configure(image="", text="", bg="#1e1e1e")
            lbs[s].image = None

    if freed_slot >= 0:
        ventana.after(0, clear_slot, freed_slot)
    ventana.after(0, refresh_buttons)

    try:
        conn.close()
    except:
        pass
    log(f"- Conexión #{num} cerrada")

def correr_servidor():
    global Server_Socket, Servidor_Activo
    try:
        Server_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        Server_Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        Server_Socket.bind((HOST, PORT))
        Server_Socket.listen(MAX_CONNECTIONS)
        log(f"- Escuchando en puerto {PORT}...")

        while Servidor_Activo:
            try:
                conn, addr = Server_Socket.accept()
                if not Servidor_Activo:
                    break
                with clients_lock:
                    if len(clients) >= MAX_CONNECTIONS:
                        log(f"- Rechazado (máx {MAX_CONNECTIONS}): {addr}")
                        conn.close()
                        continue
                log(f"- Cliente conectado: {addr}")
                threading.Thread(
                    target=recibir_video, args=(conn, addr), daemon=True
                ).start()
            except:
                break
    except Exception as e:
        log(f"- Error servidor: {e}")


def enviar_mensaje_al_cliente(event=None):
    texto = Entry_Mensaje.get().strip()
    if not texto:
        return
    Entry_Mensaje.delete(0, tk.END)
    encoded = f"< {texto}".encode("utf-8")
    with clients_lock:
        conns = [(ak, info["conn"]) for ak, info in clients.items()]
    for ak, conn in conns:
        try:
            conn.sendall(encoded)
        except:
            with clients_lock:
                clients.pop(ak, None)
    log(f"> {texto}")


def toggle_servidor():
    global Servidor_Activo, Server_Socket, primary_addr, conexion_counter

    if not Servidor_Activo:
        Servidor_Activo = True
        conexion_counter = 0
        if not is_admin():
            log("- No eres Administrador")
        else:
            open_port()
        threading.Thread(target=correr_servidor, daemon=True).start()
        Start_Button.config(text="⭕", bg="#e74c3c")
        EstadoLabel.config(text="Servidor corriendo")
        log("- Servidor iniciado")
    else:
        Servidor_Activo = False
        close_port()
        try:
            Server_Socket.close()
        except:
            pass
        with clients_lock:
            for info in clients.values():
                try:
                    info["conn"].close()
                except:
                    pass
            clients.clear()
            primary_addr = None
        for lbl in get_labels():
            lbl.configure(image="", text="", bg="#1e1e1e")
            lbl.image = None
        refresh_buttons()
        Start_Button.config(text="🔴", bg="#2ecc71", font=("Arial", 16, "bold"))
        EstadoLabel.config(text="Servidor detenido")
        log("- Servidor detenido")


def on_close():
    global Servidor_Activo
    Servidor_Activo = False
    close_port()
    try:
        Server_Socket.close()
    except:
        pass
    with clients_lock:
        for info in clients.values():
            try:
                info["conn"].close()
            except:
                pass
    ventana.destroy()

ventana = tk.Tk()
ventana.title("Servidor - Vista de Camara")
ventana.geometry("1366x768")
ventana.resizable(False, False)
ventana.config(bg="black")
ventana.protocol("WM_DELETE_WINDOW", on_close)

EstadoLabel = tk.Label(ventana, text="Servidor detenido",
                       font=("Arial", 14, "bold"), bg="black", fg="white")
EstadoLabel.place(x=43, y=729, height=39)


LImagen = tk.Label(ventana, background="#1e1e1e", anchor="center")
LImagen.place(x=3, y=3, width=966, height=540)

LImagen1 = tk.Label(ventana, background="#1e1e1e", anchor="center")
LImagen1.place(x=3, y=546, width=320, height=180)

LImagen2 = tk.Label(ventana, background="#1e1e1e", anchor="center")
LImagen2.place(x=326, y=546, width=320, height=180)

LImagen3 = tk.Label(ventana, background="#1e1e1e", anchor="center")
LImagen3.place(x=649, y=546, width=320, height=180)

Cam = tk.Button(ventana, text="1", bg="#2e2e2e", fg="white",
                font=("Arial", 16, "bold"),
                command=lambda: swap_to_primary(0))
Cam.place(x=806, y=500, width=37, height=37)

Cam1 = tk.Button(ventana, text="2", bg="#2e2e2e", fg="white",
                 font=("Arial", 16, "bold"),
                 command=lambda: swap_to_primary(1))
Cam1.place(x=846, y=500, width=37, height=37)

Cam2 = tk.Button(ventana, text="3", bg="#2e2e2e", fg="white",
                 font=("Arial", 16, "bold"),
                 command=lambda: swap_to_primary(2))
Cam2.place(x=886, y=500, width=37, height=37)

Cam3 = tk.Button(ventana, text="4", bg="#2e2e2e", fg="white",
                 font=("Arial", 16, "bold"),
                 command=lambda: swap_to_primary(3))
Cam3.place(x=926, y=500, width=37, height=37)

Log_Text = tk.Text(ventana, bg="black", font=("Arial", 14, "bold"),
                   fg="white", state="disabled")
Log_Text.place(x=972, y=3, width=391, height=540)

Start_Button = tk.Button(ventana, text="🔴", command=toggle_servidor,
                         bg="#2ecc71", fg="white", font=("Arial", 16, "bold"))
Start_Button.place(x=3, y=729, width=37, height=37)

Entry_Mensaje = tk.Entry(ventana, font=("Arial", 14, "bold"),
                         bg="#1f1f1f", fg="white")
Entry_Mensaje.place(x=972, y=546, width=391, height=45)
Entry_Mensaje.bind("<Return>", enviar_mensaje_al_cliente)

if not is_admin():
    log("- No estas como Administrador")

ventana.mainloop()