import customtkinter as ctk
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core.L_Audio import AudioPanel
from Core.L_Serial import SerialPanel
from Core.L_Camaras import CamarasPanel
from Pages.L_Client_min import ClienteMini

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ventana = ctk.CTk()
ventana.title("Cliente")
ventana.geometry("1280x720")
ventana.configure(fg_color="black")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _volver_a_principal():
    pass

def ir_a_mini():
    mini.mostrar()

L_Token = ctk.CTkLabel(ventana, width=65, height=50, text="Token", font=("Consolas", 25, "bold"), fg_color="#000", text_color="white")
L_Token.place(x=700, y=5)

E_Token = ctk.CTkEntry(ventana, width=150, height=50, font=("Consolas", 25, "bold"), fg_color="#000")
E_Token.place(x=790, y=5)

L_IP = ctk.CTkLabel(ventana, width=35, height=50, text="IP", font=("Consolas", 25, "bold"), fg_color="#000", text_color="white")
L_IP.place(x=960, y=5)

E_IP = ctk.CTkEntry(ventana, width=270, height=50, font=("Consolas", 25, "bold"), fg_color="#000")
E_IP.place(x=1005, y=5)

F_Tool = ctk.CTkFrame(ventana, width=585, height=170, fg_color="#1e1e1e", border_color="#1e1e1e", border_width=2)
F_Tool.place(x=690, y=120)

def _abrir_serial():
    audio.hide()
    serial.toggle()

serial = SerialPanel(F_Tool)
serial.build()

B_Serial = ctk.CTkButton(ventana, width=50, height=50, text="🔌", fg_color="#000", command=_abrir_serial, font=("Consolas", 25, "bold"), corner_radius=5, border_color="#1e1e1e", border_width=2)
B_Serial.place(x=690, y=60)

def _abrir_audio():
    serial.hide()
    audio.toggle()

audio = AudioPanel(F_Tool, role="client")
audio.build()

B_Audio = ctk.CTkButton(ventana, width=50, height=50, text="🎤", fg_color="#000", command=_abrir_audio, font=("Consolas", 25, "bold"), corner_radius=5, border_color="#1e1e1e", border_width=2)
B_Audio.place(x=750, y=60)

B_Mini = ctk.CTkButton(ventana, width=50, height=50, text="->", fg_color="#000", font=("Consolas", 25, "bold"), corner_radius=5, border_color="#1e1e1e", border_width=2, command=ir_a_mini)
B_Mini.place(x=810, y=60)

F_Scroll = ctk.CTkScrollableFrame(ventana, width=660, height=695, fg_color="black", scrollbar_button_color="#1e1e1e", border_color="#1e1e1e", border_width=2)
F_Scroll.place(x=5, y=5)

_serial_cmd_ts: dict = {}

def _on_serial(cmd: str):
    cmd = cmd.strip()
    if cmd in ("ON", "OFF"):
        _log(f"[serial] {cmd}")
        return
    ahora = time.time()
    if ahora - _serial_cmd_ts.get(cmd, 0) < 0.3:
        return
    _serial_cmd_ts[cmd] = ahora
    serial.send_raw(cmd.encode("utf-8") + b"\r")
    _log(f"[serial→hw] {cmd}")

def _on_msg(msg: str):
    _log(f"[srv] {msg}")

def _log(text: str):
    def _do():
        T_LogBash.configure(state="normal")
        T_LogBash.insert("end", text + "\n")
        T_LogBash.see("end")
        T_LogBash.configure(state="disabled")
    try:
        ventana.after(0, _do)
    except Exception:
        pass
    try:
        mini.log(text)
    except Exception:
        pass

camaras = CamarasPanel(
    scroll_frame = F_Scroll,
    get_ip_fn    = lambda: E_IP.get().strip(),
    get_port_fn  = lambda: 8888,
    on_serial_fn = _on_serial,
    on_msg_fn    = _on_msg,
)

L_Estado = ctk.CTkLabel(ventana, width=190, height=50, anchor="center", font=("Consolas", 25, "bold"), text="offline", text_color="#3e3e3e", cursor="hand2")
L_Estado.place(x=1085, y=60)

camaras.set_status_label(L_Estado)

_conectado = False
def _toggle_conectar():
    global _conectado
    if not _conectado:
        camaras.conectar()
        B_Conectar.configure(text="desconectar")
        _conectado = True
    else:
        camaras.desconectar()
        B_Conectar.configure(text="conectar")
        _conectado = False

B_Camaras = ctk.CTkButton(ventana, width=50, height=50, text="📷", fg_color="#000", font=("Consolas", 25, "bold"), command=camaras.detectar, corner_radius=5, border_color="#1e1e1e", border_width=2)
B_Camaras.place(x=870, y=60)

B_Conectar = ctk.CTkButton(ventana, width=150, height=50, text="conectar", fg_color="#000", font=("Consolas", 25, "bold"), corner_radius=5, border_color="#1e1e1e", border_width=2, command=_toggle_conectar)
B_Conectar.place(x=930, y=60)

T_LogBash = ctk.CTkTextbox(ventana, width=585, height=365, font=("Consolas", 25, "bold"), fg_color="#1e1e1e", state="disabled")
T_LogBash.place(x=690, y=295)

def _enviar_bash(event=None):
    import pickle, struct
    msg = E_Bash.get().strip()
    if not msg:
        return
    with camaras._streams_lock:
        streams = list(camaras._streams.values())
    if not streams:
        _log("[sin conexion]")
        return
    try:
        data   = pickle.dumps(("MSG", msg))
        header = struct.pack("Q", len(data))
        streams[0]._conn.sock.sendall(header + data)
        _log(f"[cli→srv] {msg}")
        E_Bash.delete(0, "end")
    except Exception as e:
        _log(f"[error envio] {e}")

E_Bash = ctk.CTkEntry(ventana, width=475, height=50, font=("Consolas", 25, "bold"), fg_color="#1e1e1e")
E_Bash.place(x=690, y=665)
E_Bash.bind("<Return>", _enviar_bash)

B_Log = ctk.CTkButton(ventana, width=50, height=50, text="📄", fg_color="#000", font=("Consolas", 25, "bold"), corner_radius=5, border_color="#1e1e1e", border_width=2)
B_Log.place(x=1170, y=665)

B_Carpeta = ctk.CTkButton(ventana, width=50, height=50, text="📁", fg_color="#000", font=("Consolas", 25, "bold"), corner_radius=5, border_color="#1e1e1e", border_width=2)
B_Carpeta.place(x=1225, y=665)

def _mini_abort():
    serial.send_raw(b"a\r")
    _log("[serial→hw] a (mini)")

def _mini_home():
    serial.send_raw(b"home\r")
    _log("[serial→hw] home (mini)")

mini = ClienteMini(
    parent             = ventana,
    camaras            = camaras,
    audio              = audio,
    serial             = serial,
    ir_a_principal_fn  = _volver_a_principal,
    log_fn             = _log,
    on_abort_fn        = _mini_abort,
    on_home_fn         = _mini_home,
)

ventana.mainloop()
