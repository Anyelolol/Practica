import customtkinter as ctk
import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config.L_Conection import get_local_ip, is_admin, open_ports

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ventana = ctk.CTk()
ventana.title("Login - Servidor")
ventana.geometry("480x540")
ventana.configure(fg_color="black")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def ir_a_server():
    ventana.destroy()
    args = [sys.executable, os.path.join(BASE_DIR, "L_Server.py")]
    if platform_needs_admin() and not is_admin():
        if __import__("platform").system() == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{os.path.join(BASE_DIR, "L_Server.py")}"', None, 1
            )
            return
    subprocess.Popen(args)


def platform_needs_admin() -> bool:
    import platform
    return platform.system() in ("Windows", "Linux")


ip_local = get_local_ip()

FImagen = ctk.CTkFrame(ventana, width=200, height=200, fg_color="#000", border_color="#1e1e1e", border_width=2)
FImagen.place(x=140, y=5)

L_Usuario = ctk.CTkLabel(ventana, width=65, height=65, text="Usuario", font=("Consolas", 25, "bold"), fg_color="#000", text_color="white")
L_Usuario.place(x=50, y=230)

E_Usuario = ctk.CTkEntry(ventana, width=280, height=65, font=("Consolas", 28, "bold"), fg_color="#000")
E_Usuario.place(x=150, y=230)

L_Token = ctk.CTkLabel(ventana, width=65, height=65, text="Token", font=("Consolas", 28, "bold"), fg_color="#000", text_color="white")
L_Token.place(x=105, y=300)

E_Token = ctk.CTkEntry(ventana, width=180, height=65, font=("Consolas", 28, "bold"), fg_color="#000")
E_Token.place(x=200, y=300)

L_IP = ctk.CTkLabel(ventana, width=310, height=50, text=f"IP: {ip_local}", font=("Consolas", 28, "bold"), fg_color="#000", text_color="#3e3e3e")
L_IP.place(x=85, y=370)

B_Conectar = ctk.CTkButton(ventana, width=200, height=50, text="Conectar", fg_color="#000", font=("Consolas", 28, "bold"), command=ir_a_server, border_color="#1e1e1e", border_width=2)
B_Conectar.place(x=140, y=430)

L_Error = ctk.CTkLabel(ventana, width=180, height=50, text="estado", font=("Consolas", 28, "bold"), fg_color="#000", text_color="#3e3e3e")
L_Error.place(x=95, y=490)

ventana.mainloop()
