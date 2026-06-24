import customtkinter as ctk
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config.L_login import LoginManager

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ventana = ctk.CTk()
ventana.title("Login - Cliente")
ventana.geometry("480x540")
ventana.configure(fg_color="black")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

login_mgr = LoginManager()


def ir_a_server():
    ventana.destroy()
    subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "L_Client.py")])


def _set_error(texto: str, color: str = "#e74c3c"):
    L_Error.configure(text=texto, text_color=color)


def _intentar_ingresar(event=None):
    usuario = E_Usuario.get().strip()
    clave   = E_Contraseña.get()

    ok, motivo = login_mgr.validar_credenciales(usuario, clave)
    if not ok:
        _set_error(motivo)
        return

    _set_error("ingresando…", "#2ecc71")
    ventana.after(300, ir_a_server)


FImagen = ctk.CTkFrame(ventana, width=200, height=200, fg_color="#000", border_color="#1e1e1e", border_width=2)
FImagen.place(x=140, y=5)

L_Usuario = ctk.CTkLabel(ventana, width=65, height=65, text="Usuario", font=("Consolas", 25, "bold"), fg_color="#000", text_color="white")
L_Usuario.place(x=50, y=230)

E_Usuario = ctk.CTkEntry(ventana, width=280, height=65, font=("Consolas", 22, "bold"), fg_color="#000")
E_Usuario.place(x=150, y=230)
E_Usuario.bind("<Return>", _intentar_ingresar)

L_Contraseña = ctk.CTkLabel(ventana, width=65, height=65, text="Contraseña", font=("Consolas", 28, "bold"), fg_color="#000", text_color="white")
L_Contraseña.place(x=65, y=300)

E_Contraseña = ctk.CTkEntry(ventana, width=180, height=65, font=("Consolas", 28, "bold"), fg_color="#000", show="*")
E_Contraseña.place(x=240, y=300)
E_Contraseña.bind("<Return>", _intentar_ingresar)

B_Ingresar = ctk.CTkButton(ventana, width=200, height=50, text="Ingresar", fg_color="#000", font=("Consolas", 28, "bold"), command=_intentar_ingresar, border_color="#1e1e1e", border_width=2)
B_Ingresar.place(x=140, y=430)

L_Error = ctk.CTkLabel(ventana, width=280, height=50, text="ingresá tu usuario y contraseña", font=("Consolas", 16, "bold"), fg_color="#000", text_color="#3e3e3e")
L_Error.place(x=95, y=490)

ventana.mainloop()
