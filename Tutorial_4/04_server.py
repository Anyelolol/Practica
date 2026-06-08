import socket
import threading
import struct
import pickle
import tkinter as tk
from PIL import Image, ImageTk
import subprocess
import atexit
import platform
import os
from o4_audio import AudioPanel, make_audio_button
from o4_yolo  import YoloPoseProcessor

HOST = 'localhost'
PORT = 8888
MAX_CONNECTIONS = 4
RULE_NAME = "CamaraServer_Temp_8888"

clients = {}
clients_lock = threading.Lock()
conexion_counter = 0

Server_Socket = None
Servidor_Activo = False
primary_addr = None
serial_activo = False

yolo = YoloPoseProcessor()
yolo._activo = True



def is_admin():
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        return os.geteuid() == 0


def open_port():
    if platform.system() == "Windows":
        subprocess.run([
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={RULE_NAME}", "dir=in", "action=allow",
            "protocol=TCP", f"localport={PORT}", "profile=private,domain"
        ], capture_output=True)
    else:
        subprocess.run([
            "pkexec", "firewall-cmd",
            f"--add-port={PORT}/tcp", "--temporary"
        ], capture_output=True)
    log(f"- Puerto {PORT} abierto en firewall")


def close_port():
    if platform.system() == "Windows":
        subprocess.run([
            "netsh", "advfirewall", "firewall", "delete", "rule",
            f"name={RULE_NAME}"
        ], capture_output=True)
    else:
        subprocess.Popen(
            ["pkexec", "firewall-cmd", f"--remove-port={PORT}/tcp"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


if platform.system() == "Windows":
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


def get_frames():
    return [FImagen, FImagen1, FImagen2, FImagen3]



PAD      = 3
CW_RATIO = 0.30   # ancho columna derecha
BS       = 45     # botones siempre 45x45
BG       = 5

_current_w = 0
_current_h = 0


def relayout(w, h, force=False):
    global _current_w, _current_h
    if not force and w == _current_w and h == _current_h:
        return
    _current_w, _current_h = w, h

    cw  = int(w * CW_RATIO)        # ancho columna derecha
    vw  = w - cw - PAD             # ancho zona video
    cx  = w - cw                   # x inicio columna derecha

    small_h = int(h * 0.26)
    large_h = h - small_h - PAD * 3
    large_w = vw - PAD * 2

    small_w = (vw - PAD * 4) // 3
    sy      = PAD + large_h + PAD

    FImagen.place(x=PAD, y=PAD, width=large_w, height=large_h)
    LImagen.place(x=0, y=0, width=large_w - 2, height=large_h - 2)

    sx0 = PAD
    sx1 = PAD + small_w + PAD
    sx2 = PAD + (small_w + PAD) * 2

    FImagen1.place(x=sx0, y=sy, width=small_w, height=small_h)
    LImagen1.place(x=0, y=0, width=small_w - 2, height=small_h - 2)

    FImagen2.place(x=sx1, y=sy, width=small_w, height=small_h)
    LImagen2.place(x=0, y=0, width=small_w - 2, height=small_h - 2)

    FImagen3.place(x=sx2, y=sy, width=small_w, height=small_h)
    LImagen3.place(x=0, y=0, width=small_w - 2, height=small_h - 2)

    cmd_rows  = 3                                  # 8 botones en 3 cols = 3 filas
    cmd_bh    = 28
    cmd_block = cmd_rows * (cmd_bh + BG)
    bottom_h  = BS + PAD + cmd_block + 20 + 34 + PAD * 4
    log_h     = max(60, h - bottom_h - PAD)

    bw   = (cw - PAD - BG * 2) // 3
    bh   = 28
    rows = -(-len(CMD_BTNS) // 3)   # ceil div

    cmd_y  = h - rows * (bh + BG) - PAD
    by     = cmd_y - BS - BG
    esty   = by - 20 - BG
    ey     = esty - 34 - BG
    log_h  = max(40, ey - PAD - BG)

    Log_Text.place(x=cx, y=PAD, width=cw - PAD, height=log_h)
    Entry_Mensaje.place(x=cx, y=ey, width=cw - PAD, height=34)
    EstadoLabel.place(x=cx, y=esty, width=cw - PAD, height=20)

    Start_Button.place(x=cx,              y=by, width=BS, height=BS)
    Btn_Audio.place(x=cx + (BS + BG),     y=by, width=BS, height=BS)
    SERIAL_BTN.place(x=cx + (BS + BG)*2,  y=by, width=BS, height=BS)
    MANDO.place(x=cx + (BS + BG)*3,       y=by, width=BS, height=BS)
    BTN_CONFIG.place(x=cx + (BS + BG)*4,   y=by, width=BS, height=BS)
    BTN_TECLADO.place(x=cx + (BS + BG)*5,  y=by, width=BS, height=BS)

    for i, btn in enumerate(CMD_BTNS):
        if serial_activo:
            col = i % 3
            row = i // 3
            bx  = cx + col * (bw + BG)
            btn.place(x=bx, y=cmd_y + row * (bh + BG), width=bw, height=bh)
        else:
            btn.place_forget()

    global SLOT_DIMS
    SLOT_DIMS = [
        (large_w, large_h),
        (small_w, small_h),
        (small_w, small_h),
        (small_w, small_h),
    ]


def on_resize(event):
    if event.widget is ventana:
        relayout(event.width, event.height)



SLOT_DIMS = [(820, 461), (268, 151), (268, 151), (268, 151)]


def assign_slot(ak):
    global primary_addr
    used = {info["slot"] for info in clients.values()}
    if primary_addr is None:
        primary_addr = ak
        return 0
    for s in range(1, 4):
        if s not in used:
            return s
    return -1


def swap_to_primary(slot_index):
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
        clients[target_key]["slot"] = 0
        if old_primary and old_primary in clients:
            clients[old_primary]["slot"] = slot_index
        primary_addr = target_key


def resize_cover(frame_array, slot):
    fw, fh = SLOT_DIMS[slot]
    im = Image.fromarray(frame_array)
    iw, ih = im.size
    scale = max(fw / iw, fh / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - fw) // 2
    top  = (nh - fh) // 2
    return im.crop((left, top, left + fw, top + fh))


def set_slot_border(slot, color):
    frames = get_frames()
    if 0 <= slot < len(frames):
        thickness = {"#e74c3c": 4, "#f39c12": 3, "#27ae60": 2}.get(color, 1)
        frames[slot].config(highlightbackground=color, highlightthickness=thickness)


def render_frame(slot, pil_img, color):
    labels = get_labels()
    frames = get_frames()
    lbl = labels[slot]
    frm = frames[slot]

    # Calcular grosor del borde para ajustar el Label
    thickness = 0
    if color:
        thickness = {"#e74c3c": 4, "#f39c12": 3, "#27ae60": 2}.get(color, 1)
        frm.config(highlightbackground=color, highlightthickness=thickness)
    else:
        frm.config(highlightbackground="#1e1e1e", highlightthickness=1)
        thickness = 1

    # El Label debe quedar DENTRO del borde: dejar margen igual al grosor
    m = thickness
    fw = frm.winfo_width()
    fh = frm.winfo_height()
    lw = max(1, fw - m * 2)
    lh = max(1, fh - m * 2)

    photo = ImageTk.PhotoImage(image=pil_img)
    lbl.configure(image=photo, text="", compound="center", bg="#000")
    lbl.image = photo
    lbl.place(x=m, y=m, width=lw, height=lh)



def recibir_video(conn, addr):
    global conexion_counter, primary_addr

    ak = addr_key(addr)
    with clients_lock:
        conexion_counter += 1
        num = conexion_counter
        slot = assign_slot(ak)
        clients[ak] = {"conn": conn, "slot": slot, "cam_id": "?", "num_conexion": num}

    log(f"- Conexión #{num} desde {addr} slot {slot}")

    buf = b""
    hdr_size = struct.calcsize("Q")

    while Servidor_Activo:
        try:
            while len(buf) < hdr_size:
                chunk = conn.recv(4096)
                if not chunk:
                    raise ConnectionResetError
                buf += chunk

            msg_size = struct.unpack("Q", buf[:hdr_size])[0]
            buf = buf[hdr_size:]

            while len(buf) < msg_size:
                chunk = conn.recv(4096)
                if not chunk:
                    raise ConnectionResetError
                buf += chunk

            raw = buf[:msg_size]
            buf = buf[msg_size:]

            payload = pickle.loads(raw)
            if isinstance(payload, tuple) and len(payload) == 2:
                cam_id, frame = payload
            else:
                cam_id = "?"
                frame = payload

            with clients_lock:
                if ak in clients:
                    clients[ak]["cam_id"] = str(cam_id)
                    current_slot = clients[ak]["slot"]
                else:
                    break

            if 0 <= current_slot < 4:
                frame = yolo.procesar(frame, es_bgr=True)
                color = yolo.last_color if yolo.activo else None
                im = resize_cover(frame, current_slot)
                ventana.after(0, render_frame, current_slot, im, color)

        except Exception as e:
            log(f"- Stream #{num} terminado ({addr}): {e}")
            break

    with clients_lock:
        freed_slot = clients.get(ak, {}).get("slot", -1)
        clients.pop(ak, None)
        if primary_addr == ak:
            primary_addr = None
            remaining = sorted(clients.items(), key=lambda x: x[1]["slot"])
            if remaining:
                next_ak, next_info = remaining[0]
                next_info["slot"] = 0
                primary_addr = next_ak

    def clear_slot(s):
        lbs = get_labels()
        frs = get_frames()
        if 0 <= s < len(lbs):
            lbs[s].configure(image="", text="", bg="#1e1e1e")
            lbs[s].image = None
        if 0 <= s < len(frs):
            frs[s].config(highlightbackground="#1e1e1e", highlightthickness=1)

    if freed_slot >= 0:
        ventana.after(0, clear_slot, freed_slot)

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
                threading.Thread(target=recibir_video, args=(conn, addr), daemon=True).start()
            except:
                break
    except Exception as e:
        log(f"- Error servidor: {e}")



def _broadcast(msg: str):
    encoded = msg.encode("utf-8")
    with clients_lock:
        conns = [(ak, info["conn"]) for ak, info in clients.items()]
    for ak, conn in conns:
        try:
            conn.sendall(encoded)
        except:
            with clients_lock:
                clients.pop(ak, None)


def enviar_mensaje_al_cliente(event=None):
    texto = Entry_Mensaje.get().strip()
    if not texto:
        return
    Entry_Mensaje.delete(0, tk.END)
    _broadcast(f"< {texto}")
    log(f"> {texto}")



def cmd_send(cmd: str):
    _broadcast(f"SERIAL:{cmd}")
    log(f"> {cmd.strip()}")



def toggle_serial():
    global serial_activo
    serial_activo = not serial_activo
    if serial_activo:
        SERIAL_BTN.config(bg="#e74c3c")
        _broadcast("SERIAL:ON")
        log("- Serial ACTIVADO")
    else:
        SERIAL_BTN.config(bg="#2e2e2e")
        _broadcast("SERIAL:OFF")
        log("- Serial DESACTIVADO")
    relayout(_current_w, _current_h, force=True)



def toggle_servidor():
    global Servidor_Activo, Server_Socket, primary_addr, conexion_counter

    if not Servidor_Activo:
        Servidor_Activo = True
        conexion_counter = 0
        if platform.system() == "Windows" and not is_admin():
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
        for frm in get_frames():
            frm.config(highlightbackground="#1e1e1e", highlightthickness=1)
        Start_Button.config(text="🔴", bg="#2ecc71", font=("Arial", 16, "bold"))
        EstadoLabel.config(text="Servidor detenido")
        log("- Servidor detenido")

        global serial_activo
        if serial_activo:
            serial_activo = False
            SERIAL_BTN.config(bg="#2e2e2e")


def on_close():
    global Servidor_Activo
    Servidor_Activo = False
    close_port()
    audio_panel.destroy()
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
ventana.resizable(True, True)
ventana.geometry("1280x720")
ventana.config(bg="black")
ventana.protocol("WM_DELETE_WINDOW", on_close)
ventana.bind("<Escape>", lambda e: ventana.attributes("-fullscreen", False))
ventana.bind("<F1>",     lambda e: ventana.attributes("-fullscreen", True))
ventana.bind("<Configure>", on_resize)

audio_panel = AudioPanel(master=ventana, role="server")


FImagen = tk.Frame(ventana, bg="#000", highlightbackground="#1e1e1e", highlightthickness=1)
LImagen = tk.Label(FImagen, background="#1e1e1e", anchor="center")
LImagen.place(x=0, y=0)

FImagen1 = tk.Frame(ventana, bg="#000", highlightbackground="#1e1e1e",
                    highlightthickness=1, cursor="hand2")
LImagen1 = tk.Label(FImagen1, background="#1e1e1e", anchor="center", cursor="hand2")
LImagen1.place(x=0, y=0)
FImagen1.bind("<Button-1>", lambda e: swap_to_primary(1))
LImagen1.bind("<Button-1>", lambda e: swap_to_primary(1))

FImagen2 = tk.Frame(ventana, bg="#000", highlightbackground="#1e1e1e",
                    highlightthickness=1, cursor="hand2")
LImagen2 = tk.Label(FImagen2, background="#1e1e1e", anchor="center", cursor="hand2")
LImagen2.place(x=0, y=0)
FImagen2.bind("<Button-1>", lambda e: swap_to_primary(2))
LImagen2.bind("<Button-1>", lambda e: swap_to_primary(2))

FImagen3 = tk.Frame(ventana, bg="#000", highlightbackground="#1e1e1e",
                    highlightthickness=1, cursor="hand2")
LImagen3 = tk.Label(FImagen3, background="#1e1e1e", anchor="center", cursor="hand2")
LImagen3.place(x=0, y=0)
FImagen3.bind("<Button-1>", lambda e: swap_to_primary(3))
LImagen3.bind("<Button-1>", lambda e: swap_to_primary(3))

Log_Text = tk.Text(ventana, bg="black", font=("Consolas", 10),
                   fg="#888888", state="disabled", relief="flat", bd=0)

Entry_Mensaje = tk.Entry(ventana, font=("Consolas", 12),
                          bg="#111111", fg="white", insertbackground="white",
                          relief="flat", bd=4)
Entry_Mensaje.bind("<Return>", enviar_mensaje_al_cliente)

EstadoLabel = tk.Label(ventana, text="Servidor detenido",
                       font=("Arial", 10), bg="black", fg="#888888")

Start_Button = tk.Button(ventana, text="🔴", command=toggle_servidor,
                          bg="#2ecc71", fg="white", font=("Arial", 16, "bold"),
                          relief="flat", cursor="hand2")

Btn_Audio = make_audio_button(ventana, audio_panel, x=0, y=0, width=BS, height=BS)

SERIAL_BTN = tk.Button(ventana, text="🔌", bg="#2e2e2e", fg="white",
                        font=("Arial", 16, "bold"), relief="flat",
                        cursor="hand2", command=toggle_serial)

MANDO = tk.Button(ventana, text="🛸", bg="#2e2e2e", fg="white",
                  font=("Arial", 16, "bold"), relief="flat", cursor="hand2")

BTN_CONFIG = tk.Button(ventana, text="⚙️", bg="#2e2e2e", fg="white",
                       font=("Arial", 16, "bold"), relief="flat", cursor="hand2")

BTN_TECLADO = tk.Button(ventana, text="⌨️", bg="#2e2e2e", fg="white",
                        font=("Arial", 16, "bold"), relief="flat", cursor="hand2")

CMD_BTNS = [
    tk.Button(ventana, text="Abortar", bg="#922b21", fg="white",
              font=("Consolas", 9, "bold"), relief="flat", cursor="hand2",
              command=lambda: cmd_send("a\r")),
    tk.Button(ventana, text="Move 0",  bg="#1a5276", fg="white",
              font=("Consolas", 9, "bold"), relief="flat", cursor="hand2",
              command=lambda: cmd_send("move 0\r")),
    tk.Button(ventana, text="Home",    bg="#0b5345", fg="white",
              font=("Consolas", 9, "bold"), relief="flat", cursor="hand2",
              command=lambda: cmd_send("home\r")),
]

if platform.system() == "Windows" and not is_admin():
    log("- No estas como Administrador")

ventana.mainloop()