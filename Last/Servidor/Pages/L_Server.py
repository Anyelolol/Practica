import customtkinter as ctk
import subprocess
import threading
import secrets
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config.L_Conection import ConectionServer, get_local_ip
from Config.L_login import AuthServer
from Config import L_Conection as _conn_mod
from Core.L_Audio import AudioServer
from Core.L_Serial import SerialPanel
from Core.L_mando import MandoPanel

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG      = "#111111"
PANEL   = "#1a1a1a"
BORDER  = "#2a2a2a"
FONT    = ("Consolas", 25, "bold")

W, H    = 1280, 720
SIDE_W  = 65
SIDE_X  = W - SIDE_W - 5
PAD     = 5

MAIN_X  = PAD
MAIN_Y  = PAD
MAIN_W  = SIDE_X - PAD * 2
MAIN_H  = H - PAD * 2 - 150
THUMB_Y = MAIN_Y + MAIN_H + PAD
THUMB_H = H - THUMB_Y - PAD
THUMB_W = 240

ventana = ctk.CTk()
ventana.title("Servidor")
ventana.geometry(f"{W}x{H}")
ventana.configure(fg_color=BG)
ventana.resizable(False, False)

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
_servidor_activo = [False]
modo_tool        = [False]


def _log(msg: str):
    def _do():
        T_LogBash.configure(state="normal")
        T_LogBash.insert("end", msg + "\n")
        T_LogBash.see("end")
        T_LogBash.configure(state="disabled")
    try:
        ventana.after(0, _do)
    except Exception:
        pass


def _notificar(msg: str):
    try:
        import platform
        if platform.system() == "Linux":
            subprocess.Popen(["notify-send", "Castor Server", msg],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Windows":
            from win10toast import ToastNotifier
            ToastNotifier().show_toast("Castor Server", msg, duration=4, threaded=True)
    except Exception:
        pass


F_Main = ctk.CTkFrame(ventana, width=MAIN_W, height=MAIN_H,
                      fg_color=PANEL, bg_color="transparent",
                      border_color=BORDER, corner_radius=2, border_width=1)
F_Main.place(x=MAIN_X, y=MAIN_Y)
L_Main = ctk.CTkLabel(F_Main, anchor="center", text="", cursor="hand2",
                       width=MAIN_W, height=MAIN_H)
L_Main.place(x=0, y=0)

F_T1 = ctk.CTkFrame(ventana, width=THUMB_W, height=THUMB_H,
                    fg_color=PANEL, bg_color="transparent",
                    border_color=BORDER, corner_radius=2, border_width=1)
L_T1 = ctk.CTkLabel(F_T1, anchor="center", text="", cursor="hand2",
                     width=THUMB_W, height=THUMB_H)
L_T1.place(x=0, y=0)

F_T2 = ctk.CTkFrame(ventana, width=THUMB_W, height=THUMB_H,
                    fg_color=PANEL, bg_color="transparent",
                    border_color=BORDER, corner_radius=2, border_width=1)
L_T2 = ctk.CTkLabel(F_T2, anchor="center", text="", cursor="hand2",
                     width=THUMB_W, height=THUMB_H)
L_T2.place(x=0, y=0)

F_T3 = ctk.CTkFrame(ventana, width=THUMB_W, height=THUMB_H,
                    fg_color=PANEL, bg_color="transparent",
                    border_color=BORDER, corner_radius=2, border_width=1)
L_T3 = ctk.CTkLabel(F_T3, anchor="center", text="", cursor="hand2",
                     width=THUMB_W, height=THUMB_H)
L_T3.place(x=0, y=0)

SLOTS = [
    {"frame": F_Main, "label": L_Main, "w": MAIN_W, "h": MAIN_H},
    {"frame": F_T1,   "label": L_T1,   "w": THUMB_W, "h": THUMB_H},
    {"frame": F_T2,   "label": L_T2,   "w": THUMB_W, "h": THUMB_H},
    {"frame": F_T3,   "label": L_T3,   "w": THUMB_W, "h": THUMB_H},
]


def _relayout(n_clientes: int):
    ventana.after(0, lambda: _do_relayout(n_clientes))


def _do_relayout(n: int):
    F_Main.place_forget()
    F_T1.place_forget()
    F_T2.place_forget()
    F_T3.place_forget()

    if n == 0:
        return

    if n == 1:
        fw = MAIN_W
        fh = MAIN_H + THUMB_H + PAD
        F_Main.configure(width=fw, height=fh)
        L_Main.configure(width=fw, height=fh)
        SLOTS[0]["w"] = fw
        SLOTS[0]["h"] = fh
        F_Main.place(x=MAIN_X, y=MAIN_Y)

    elif n == 2:
        fw, fh = MAIN_W, MAIN_H
        F_Main.configure(width=fw, height=fh)
        L_Main.configure(width=fw, height=fh)
        SLOTS[0]["w"] = fw
        SLOTS[0]["h"] = fh
        F_Main.place(x=MAIN_X, y=MAIN_Y)

        F_T1.configure(width=THUMB_W, height=THUMB_H)
        L_T1.configure(width=THUMB_W, height=THUMB_H)
        SLOTS[1]["w"] = THUMB_W
        SLOTS[1]["h"] = THUMB_H
        F_T1.place(x=MAIN_X, y=THUMB_Y)

    elif n == 3:
        fw, fh = MAIN_W, MAIN_H
        F_Main.configure(width=fw, height=fh)
        L_Main.configure(width=fw, height=fh)
        SLOTS[0]["w"] = fw
        SLOTS[0]["h"] = fh
        F_Main.place(x=MAIN_X, y=MAIN_Y)

        for i, (frm, lbl) in enumerate([(F_T1, L_T1), (F_T2, L_T2)]):
            frm.configure(width=THUMB_W, height=THUMB_H)
            lbl.configure(width=THUMB_W, height=THUMB_H)
            SLOTS[i + 1]["w"] = THUMB_W
            SLOTS[i + 1]["h"] = THUMB_H
            frm.place(x=MAIN_X + i * (THUMB_W + PAD), y=THUMB_Y)

    else:
        fw, fh = MAIN_W, MAIN_H
        F_Main.configure(width=fw, height=fh)
        L_Main.configure(width=fw, height=fh)
        SLOTS[0]["w"] = fw
        SLOTS[0]["h"] = fh
        F_Main.place(x=MAIN_X, y=MAIN_Y)

        for i, (frm, lbl) in enumerate([(F_T1, L_T1), (F_T2, L_T2), (F_T3, L_T3)]):
            frm.configure(width=THUMB_W, height=THUMB_H)
            lbl.configure(width=THUMB_W, height=THUMB_H)
            SLOTS[i + 1]["w"] = THUMB_W
            SLOTS[i + 1]["h"] = THUMB_H
            frm.place(x=MAIN_X + i * (THUMB_W + PAD), y=THUMB_Y)



conexion: ConectionServer | None = None


def _swap(slot_idx: int):
    if conexion and _servidor_activo[0]:
        conexion.swap_primary(slot_idx)


L_T1.bind("<Button-1>", lambda e: _swap(1))
F_T1.bind("<Button-1>", lambda e: _swap(1))
L_T2.bind("<Button-1>", lambda e: _swap(2))
F_T2.bind("<Button-1>", lambda e: _swap(2))
L_T3.bind("<Button-1>", lambda e: _swap(3))
F_T3.bind("<Button-1>", lambda e: _swap(3))




_BG_RGB        = (0x11, 0x11, 0x11)
_VERDE_BG_RGB   = (0x00, 0x2b, 0x08)
_NARANJA_BG_RGB = (0x2b, 0x1a, 0x00)
_ROJO_BG_RGB    = (0x2b, 0x00, 0x00)
_ANCLAS_BG = [(-1, _BG_RGB), (0, _VERDE_BG_RGB), (1, _NARANJA_BG_RGB), (2, _ROJO_BG_RGB)]


def _bg_desde_nivel(nivel: float) -> str:
    if nivel <= _ANCLAS_BG[0][0]:
        rgb = _ANCLAS_BG[0][1]
    else:
        rgb = _ANCLAS_BG[-1][1]
        for (n0, rgb0), (n1, rgb1) in zip(_ANCLAS_BG, _ANCLAS_BG[1:]):
            if n0 <= nivel <= n1:
                t = (nivel - n0) / (n1 - n0)
                rgb = tuple(round(rgb0[k] + (rgb1[k] - rgb0[k]) * t) for k in range(3))
                break
    return "#%02x%02x%02x" % rgb


def _on_yolo(color: str | None, nivel: float = -1.0):
    bg = _bg_desde_nivel(nivel)
    ventana.after(0, lambda: ventana.configure(fg_color=bg))


def _encender_servidor():
    global conexion
    _servidor_activo[0] = True
    ventana.after(0, lambda: B_On.configure(fg_color="#27ae60", text="On"))
    conexion = ConectionServer(
        slots=SLOTS,
        log_fn=_log,
        on_layout_fn=_relayout,
        on_yolo_fn=_on_yolo,
    )
    conexion.iniciar()
    audio.iniciar()
    audio.build()
    _log(f"IP: {get_local_ip()}  puerto: 8888")
    _notificar("Servidor encendido")


def _apagar_servidor():
    global conexion
    _servidor_activo[0] = False
    ventana.after(0, lambda: B_On.configure(fg_color=PANEL, text="Off"))
    ventana.after(0, lambda: ventana.configure(fg_color=BG))
    if conexion:
        conexion.detener()
        conexion = None
    audio.destroy()
    _relayout(0)
    _log("servidor detenido")


def _toggle_on():
    if not _servidor_activo[0]:
        threading.Thread(target=_encender_servidor, daemon=True).start()
    else:
        threading.Thread(target=_apagar_servidor, daemon=True).start()


def ir_a_login():
    if _servidor_activo[0]:
        _apagar_servidor()
    auth.detener()
    _conn_mod.close_auth_port()
    ventana.destroy()
    subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "L_Server_login.py")])


def toggle_tool():
    if not modo_tool[0]:
        T_LogBash.configure(width=450, height=85)
        T_LogBash.place(x=745, y=575)
        F_Tool.place_forget()
        modo_tool[0] = True
    else:
        T_LogBash.configure(width=245, height=85)
        T_LogBash.place(x=745, y=575)
        F_Tool.place(x=995, y=400)
        modo_tool[0] = False


def _abrir_serial():
    F_Tool.place(x=995, y=400)
    modo_tool[0] = False
    T_LogBash.configure(width=245, height=85)
    T_LogBash.place(x=745, y=575)
    audio.hide()
    mando.hide()
    serial.toggle()


def _abrir_audio():
    F_Tool.place(x=995, y=400)
    modo_tool[0] = False
    T_LogBash.configure(width=245, height=85)
    T_LogBash.place(x=745, y=575)
    serial.hide()
    mando.hide()
    audio.toggle()

def _abrir_mando():
    F_Tool.place(x=995, y=400)
    modo_tool[0] = False
    T_LogBash.configure(width=245, height=85)
    T_LogBash.place(x=745, y=575)
    audio.hide()
    serial.hide()
    mando.toggle()

B_Logout = ctk.CTkButton(ventana, width=SIDE_W, height=65, text="<-", font=FONT,
                          command=ir_a_login, fg_color=PANEL, border_color=BORDER, border_width=2)
B_Logout.place(x=SIDE_X, y=5)

B_On = ctk.CTkButton(ventana, width=SIDE_W, height=125, text="Off", font=FONT,
                      fg_color=PANEL, border_color=BORDER, border_width=2, command=_toggle_on)
B_On.place(x=SIDE_X, y=75)

B_Audio = ctk.CTkButton(ventana, width=SIDE_W, height=65, text="🎤", font=FONT,
                         fg_color=PANEL, border_color=BORDER, border_width=2, command=_abrir_audio)
B_Audio.place(x=SIDE_X, y=330)

B_Teclado = ctk.CTkButton(ventana, width=SIDE_W, height=65, text="⌨️", font=FONT,
                            fg_color=PANEL, border_color=BORDER, border_width=2)
B_Teclado.place(x=SIDE_X, y=400)

B_Mando = ctk.CTkButton(ventana, width=SIDE_W, height=65, text="🛸", font=FONT,
                          fg_color=PANEL, border_color=BORDER, border_width=2, command=_abrir_mando)
B_Mando.place(x=SIDE_X, y=470)

B_Serial = ctk.CTkButton(ventana, width=SIDE_W, height=65, text="🔌", font=FONT,
                           fg_color=PANEL, border_color=BORDER, border_width=2,
                           command=_abrir_serial)
B_Serial.place(x=SIDE_X, y=540)

B_Config = ctk.CTkButton(ventana, width=SIDE_W, height=65, text="⚙️", font=FONT,
                           fg_color=PANEL, border_color=BORDER, border_width=2, command=toggle_tool)
B_Config.place(x=SIDE_X, y=610)


def _enviar_bash(event=None):
    if conexion and _servidor_activo[0]:
        msg = E_Bash.get().strip()
        if msg:
            conexion.enviar_a_todos(msg)
            _log(f"[srv→cli] {msg}")
            E_Bash.delete(0, "end")

E_Bash = ctk.CTkEntry(ventana, width=450, height=50, font=FONT, fg_color=PANEL)
E_Bash.place(x=745, y=665)
E_Bash.bind("<Return>", _enviar_bash)

T_LogBash = ctk.CTkTextbox(ventana, width=245, height=85, font=FONT,
                             fg_color="transparent", border_color=BORDER,
                             border_width=2, state="disabled")
T_LogBash.place(x=745, y=575)

F_Tool = ctk.CTkFrame(ventana, width=205, height=260, fg_color="transparent",
                       border_color=BORDER, border_width=2)
F_Tool.place(x=995, y=400)


def _cerrar_ventana():
    if _servidor_activo[0]:
        _apagar_servidor()
    auth.detener()
    _conn_mod.close_auth_port()
    ventana.destroy()


ventana.protocol("WM_DELETE_WINDOW", _cerrar_ventana)

def _enviar_serial_remoto(cmd: str):
    if conexion and _servidor_activo[0]:
        conexion.enviar_serial(cmd)
        _log(f"[srv→cli] SERIAL:{cmd}")
    else:
        _log("[serial] servidor apagado, comando ignorado")

mando = MandoPanel(tool_frame=F_Tool, enviar_fn=_enviar_serial_remoto)
audio  = AudioServer(parent_frame=F_Tool)
serial = SerialPanel(tool_frame=F_Tool, enviar_fn=_enviar_serial_remoto)
serial.build()

ventana.mainloop()
