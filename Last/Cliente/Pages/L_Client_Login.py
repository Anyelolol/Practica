import customtkinter as ctk
import subprocess
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ventana = ctk.CTk()
ventana.title("Login - Cliente")
ventana.geometry("480x540")
ventana.configure(fg_color="black")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ir_a_server():
    ventana.destroy()
    subprocess.Popen(["python", os.path.join(BASE_DIR, "L_Client.py")])

FImagen = ctk.CTkFrame(ventana, width=200, height=200, fg_color="#000", border_color="#1e1e1e", border_width=2)
FImagen.place(x=140, y=5)

L_Nombre = ctk.CTkLabel(ventana, width=65, height=65, text="Nombre",font=("Consolas", 25, "bold"), fg_color="#000", text_color="white")
L_Nombre.place(x=50, y=230)

E_Nombre= ctk.CTkEntry(ventana, width=280, height=65, font=("Consolas", 28, "bold"), fg_color="#000")
E_Nombre.place(x=150, y=230)


L_Contraseña = ctk.CTkLabel(ventana, width=65, height=65, text="Contraseña",font=("Consolas", 28, "bold"), fg_color="#000", text_color="white")
L_Contraseña.place(x=65, y=300)

E_Contraseña= ctk.CTkEntry(ventana, width=180, height=65, font=("Consolas", 28, "bold"), fg_color="#000")
E_Contraseña.place(x=240, y=300)

B_Conectar= ctk.CTkButton(ventana, width=200, height=50, text="Conectar", fg_color="#000",font=("Consolas", 28, "bold"), command=ir_a_server, border_color="#1e1e1e", border_width=2)
B_Conectar.place(x=140, y=430)

L_Error = ctk.CTkLabel(ventana, width=180, height=50, text="estado",font=("Consolas", 28, "bold"), fg_color="#000", text_color="#3e3e3e")
L_Error.place(x=95, y=490)

ventana.mainloop()
