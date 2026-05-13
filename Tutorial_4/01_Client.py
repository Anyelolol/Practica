import socket
import tkinter as tk
from threading import Thread
import tkinter.messagebox as messagebox
import time

HOST = 'localhost'
PORT = 8888

class ClientGUI:

    def __init__(self, master):
        self.master = master
        self.master.title("Cliente")
        self.master.geometry("500x400")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.name = tk.StringVar()
        self.name.set("USUARIO1")
        self.connected = False

        self.receive_messages_text = tk.Text(self.master, height=10, width=50)
        self.receive_messages_text.place(x=10, y=10)

        self.messages_entry = tk.Entry(self.master, width=50)
        self.messages_entry.place(x=10, y=220)

        self.name_entry = tk.Entry(self.master, textvariable=self.name, width=50)
        self.name_entry.place(x=10, y=260)

        self.send_button = tk.Button(self.master, text="Enviar", command=self.send_message)
        self.send_button.place(x=10, y=300)

        self.connect_to_server()

    def connect_to_server(self):
        while True:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((HOST, PORT))
                self.connected = True
                self.socket.sendall(self.name.get().encode())
                Thread(target=self.receive_messages, daemon=True).start()
                break
            except Exception as e:
                print(e)
                self.connected = False
                time.sleep(5)

    def receive_messages(self):
        while self.connected:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                self.receive_messages_text.insert(tk.END, data.decode() + "\n")
                self.receive_messages_text.see(tk.END)
            except Exception as e:
                print(e)
                self.connected = False
                self.socket.close()
                break

    def send_message(self):
        message = self.messages_entry.get()
        if not self.connected:
            messagebox.showerror("Error", "No hay conexión con el servidor")
            return
        try:
            self.socket.send(message.encode())
            self.messages_entry.delete(0, tk.END)
        except:
            messagebox.showerror("Error", "La conexión se perdió")

    def on_close(self):
        self.connected = False
        try:
            self.socket.close()
        except:
            pass
        self.master.destroy()

if __name__ == "__main__":
    ventana = tk.Tk()
    client_GUI = ClientGUI(ventana)
    ventana.mainloop()
