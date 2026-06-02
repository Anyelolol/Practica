import socket
import threading
import tkinter as tk
from tkinter import ttk
import struct
import numpy as np

try:
    import sounddevice as sd
    SD_OK = True
except ImportError:
    SD_OK = False

SAMPLE_RATE   = 44100
CHANNELS      = 1
DTYPE         = "int16"
CHUNK_FRAMES  = 1024          # frames por bloque
AUDIO_PORT    = 9999          # puerto dedicado al audio (distinto del video)
HEADER_FMT    = "!I"          # 4 bytes: tamaño del chunk
HEADER_SIZE   = struct.calcsize(HEADER_FMT)


def _listar_microfonos() -> list[dict]:
    if not SD_OK:
        return []
    devs = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                devs.append({"index": i, "name": d["name"]})
    except Exception:
        pass
    return devs


def _listar_altavoces() -> list[dict]:
    if not SD_OK:
        return []
    devs = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                devs.append({"index": i, "name": d["name"]})
    except Exception:
        pass
    return devs


def _send_chunk(sock: socket.socket, data: bytes):
    header = struct.pack(HEADER_FMT, len(data))
    sock.sendall(header + data)


def _recv_chunk(sock: socket.socket) -> bytes | None:
    raw = b""
    while len(raw) < HEADER_SIZE:
        chunk = sock.recv(HEADER_SIZE - len(raw))
        if not chunk:
            return None
        raw += chunk
    size = struct.unpack(HEADER_FMT, raw)[0]
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


class AudioPanel:
    def __init__(self, master: tk.Tk, role: str = "client",
                 get_remote_ip=None):
        self.master       = master
        self.role         = role          # "server" | "client"
        self.get_remote_ip = get_remote_ip

        # Estado de conexión
        self._conn_send: socket.socket | None = None   # socket de envío
        self._conn_recv: socket.socket | None = None   # socket de recepción
        self._server_sock: socket.socket | None = None
        self._active      = False

        # Estado de audio
        self._mic_index    = None
        self._out_index    = None
        self._muted_local  = False
        self._muted_remote = False   # solo visual / envía señal
        self._stream_in    = None
        self._stream_out   = None

        # Ventana flotante
        self._win: tk.Toplevel | None = None

        # Si es servidor, arranca el listener de inmediato
        if self.role == "server":
            threading.Thread(target=self._server_listen, daemon=True).start()

    def toggle_window(self):
        if self._win is None or not self._win.winfo_exists():
            self._build_window()
        else:
            if self._win.state() == "withdrawn":
                self._win.deiconify()
            else:
                self._win.withdraw()

    def destroy(self):
        self._disconnect()
        if self._win and self._win.winfo_exists():
            self._win.destroy()


    def _build_window(self):
        self._win = tk.Toplevel(self.master)
        self._win.title("🎤 Audio P2P")
        self._win.geometry("420x440")
        self._win.resizable(False, False)
        self._win.configure(bg="#0d0d0d")
        self._win.protocol("WM_DELETE_WINDOW", self._win.withdraw)

        BG      = "#0d0d0d"
        PANEL   = "#1a1a1a"
        ACCENT  = "#00b4d8"
        FG      = "#e0e0e0"
        FG_DIM  = "#666"
        F_TITLE = ("Consolas", 12, "bold")
        F_NORM  = ("Consolas", 10)
        F_BTN   = ("Consolas", 10, "bold")

        # ── Título ──
        tk.Label(self._win, text="◈  AUDIO  P2P",
                 bg=BG, fg=ACCENT, font=("Consolas", 14, "bold")).pack(pady=(14, 4))

        role_txt = "[ SERVIDOR ]" if self.role == "server" else "[ CLIENTE ]"
        tk.Label(self._win, text=role_txt, bg=BG, fg=FG_DIM, font=F_NORM).pack()

        sep = tk.Frame(self._win, bg=ACCENT, height=1)
        sep.pack(fill="x", padx=16, pady=8)

        if self.role == "client" and self.get_remote_ip is None:
            frm_ip = tk.Frame(self._win, bg=PANEL, padx=10, pady=6)
            frm_ip.pack(fill="x", padx=16, pady=(0, 6))
            tk.Label(frm_ip, text="IP remota:", bg=PANEL, fg=FG, font=F_NORM).pack(side="left")
            self._entry_ip = tk.Entry(frm_ip, font=F_NORM, width=16,
                                      bg="#111", fg=FG, insertbackground=FG,
                                      relief="flat", bd=4)
            self._entry_ip.insert(0, "127.0.0.1")
            self._entry_ip.pack(side="left", padx=8)
        else:
            self._entry_ip = None

        frm_mic = tk.LabelFrame(self._win, text=" 🎤 Micrófono ",
                                bg=PANEL, fg=ACCENT, font=F_NORM,
                                bd=1, relief="groove", padx=8, pady=6)
        frm_mic.pack(fill="x", padx=16, pady=4)

        mics = _listar_microfonos()
        mic_names = [f"[{m['index']}] {m['name'][:38]}" for m in mics] or ["(no hay micrófonos)"]
        self._mic_map = {n: m["index"] for n, m in zip(mic_names, mics)}

        self._combo_mic = ttk.Combobox(frm_mic, values=mic_names,
                                       state="readonly", font=F_NORM, width=38)
        if mic_names:
            self._combo_mic.current(0)
        self._combo_mic.pack(side="left")

        tk.Button(frm_mic, text="↺", bg="#222", fg=ACCENT, font=F_BTN,
                  relief="flat", bd=0, cursor="hand2",
                  command=self._refresh_mics).pack(side="left", padx=6)

        frm_out = tk.LabelFrame(self._win, text=" 🔊 Salida de audio ",
                                bg=PANEL, fg=ACCENT, font=F_NORM,
                                bd=1, relief="groove", padx=8, pady=6)
        frm_out.pack(fill="x", padx=16, pady=4)

        outs = _listar_altavoces()
        out_names = [f"[{o['index']}] {o['name'][:38]}" for o in outs] or ["(no hay salidas)"]
        self._out_map = {n: o["index"] for n, o in zip(out_names, outs)}

        self._combo_out = ttk.Combobox(frm_out, values=out_names,
                                       state="readonly", font=F_NORM, width=38)
        if out_names:
            self._combo_out.current(0)
        self._combo_out.pack()

        # ── Botones mute ──
        frm_mute = tk.Frame(self._win, bg=BG)
        frm_mute.pack(fill="x", padx=16, pady=6)

        self._btn_mute_local = tk.Button(
            frm_mute, text="🎤 Silenciarme", bg="#1a1a1a", fg=FG,
            font=F_BTN, relief="flat", bd=0, cursor="hand2", width=18,
            command=self._toggle_mute_local)
        self._btn_mute_local.pack(side="left", padx=(0, 8))

        # ── Estado / botón conectar ──
        sep2 = tk.Frame(self._win, bg="#333", height=1)
        sep2.pack(fill="x", padx=16, pady=6)

        self._lbl_status = tk.Label(self._win, text="⬤  Desconectado",
                                    bg=BG, fg="#e74c3c", font=F_NORM)
        self._lbl_status.pack()

        frm_btns = tk.Frame(self._win, bg=BG)
        frm_btns.pack(pady=8)

        self._btn_connect = tk.Button(
            frm_btns, text="▶  Conectar audio", bg="#0a3d4a", fg=ACCENT,
            font=F_BTN, relief="flat", bd=0, cursor="hand2",
            padx=14, pady=6,
            command=self._connect)
        self._btn_connect.pack(side="left", padx=6)

        self._btn_disconnect = tk.Button(
            frm_btns, text="⏹  Desconectar", bg="#2e0a0a", fg="#e74c3c",
            font=F_BTN, relief="flat", bd=0, cursor="hand2",
            padx=14, pady=6, state=tk.DISABLED,
            command=self._disconnect)
        self._btn_disconnect.pack(side="left", padx=6)

        self._log_txt = tk.Text(self._win, bg="#111", fg=FG_DIM,
                                font=("Consolas", 8), height=4, state="disabled",
                                relief="flat", bd=0)
        self._log_txt.pack(fill="x", padx=16, pady=(4, 12))

    def _log(self, msg: str):
        def _do():
            if self._log_txt and self._log_txt.winfo_exists():
                self._log_txt.config(state="normal")
                self._log_txt.insert("end", msg + "\n")
                self._log_txt.see("end")
                self._log_txt.config(state="disabled")
        if self._win and self._win.winfo_exists():
            self._win.after(0, _do)

    def _set_status(self, text: str, color: str):
        def _do():
            if self._lbl_status and self._lbl_status.winfo_exists():
                self._lbl_status.config(text=text, fg=color)
        if self._win and self._win.winfo_exists():
            self._win.after(0, _do)

    def _refresh_mics(self):
        mics = _listar_microfonos()
        names = [f"[{m['index']}] {m['name'][:38]}" for m in mics] or ["(no hay micrófonos)"]
        self._mic_map = {n: m["index"] for n, m in zip(names, mics)}
        self._combo_mic["values"] = names
        if names:
            self._combo_mic.current(0)
        self._log(f"Micrófonos actualizados: {len(mics)} encontrados")

    def _toggle_mute_local(self):
        self._muted_local = not self._muted_local
        if self._muted_local:
            self._btn_mute_local.config(text="🔇 Muteado", bg="#4a0000", fg="#e74c3c")
        else:
            self._btn_mute_local.config(text="🎤 Silenciarme", bg="#1a1a1a", fg="#e0e0e0")

    def _get_selected_mic(self) -> int | None:
        if not SD_OK:
            return None
        sel = self._combo_mic.get()
        return self._mic_map.get(sel)

    def _get_selected_out(self) -> int | None:
        if not SD_OK:
            return None
        sel = self._combo_out.get()
        return self._out_map.get(sel)

    def _connect(self):
        if not SD_OK:
            self._log("ERROR: instala sounddevice  →  pip install sounddevice")
            return
        if self._active:
            return

        if self.role == "client":
            ip = (self.get_remote_ip() if self.get_remote_ip
                  else self._entry_ip.get().strip())
            threading.Thread(target=self._client_connect, args=(ip,), daemon=True).start()
        else:
            # El servidor ya está escuchando; solo inicia streams de audio locales
            self._log("Esperando cliente de audio...")
            self._set_status("⬤  Esperando…", "#f39c12")

    def _disconnect(self):
        self._active = False
        self._stop_streams()
        for s in (self._conn_send, self._conn_recv):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self._conn_send = None
        self._conn_recv = None
        self._set_status("⬤  Desconectado", "#e74c3c")
        self._log("Audio desconectado.")
        if self._win and self._win.winfo_exists():
            self._win.after(0, lambda: self._btn_connect.config(state=tk.NORMAL))
            self._win.after(0, lambda: self._btn_disconnect.config(state=tk.DISABLED))

    def _server_listen(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", AUDIO_PORT))
        srv.listen(4)
        self._server_sock = srv
        self._log(f"Audio server escuchando en :{AUDIO_PORT}")

        while True:
            try:
                conn, addr = srv.accept()
                role_byte = conn.recv(4)
                if role_byte == b"SEND":
                    self._conn_recv = conn      # el cliente envía → nosotros recibimos
                    self._log(f"Canal RECV listo ({addr[0]})")
                elif role_byte == b"RECV":
                    self._conn_send = conn      # el cliente recibe → nosotros enviamos
                    self._log(f"Canal SEND listo ({addr[0]})")

                if self._conn_send and self._conn_recv:
                    self._active = True
                    self._set_status("⬤  Conectado", "#2ecc71")
                    self._start_streams()
                    if self._win and self._win.winfo_exists():
                        self._win.after(0, lambda: self._btn_connect.config(state=tk.DISABLED))
                        self._win.after(0, lambda: self._btn_disconnect.config(state=tk.NORMAL))
            except Exception as e:
                self._log(f"Audio server error: {e}")
                break

    def _client_connect(self, ip: str):
        try:
            self._set_status("⬤  Conectando…", "#f39c12")

            # Socket para ENVIAR audio (le dice SEND al servidor)
            s_send = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s_send.connect((ip, AUDIO_PORT))
            s_send.sendall(b"SEND")
            self._conn_send = s_send

            # Socket para RECIBIR audio (le dice RECV al servidor)
            s_recv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s_recv.connect((ip, AUDIO_PORT))
            s_recv.sendall(b"RECV")
            self._conn_recv = s_recv

            self._active = True
            self._set_status("⬤  Conectado", "#2ecc71")
            self._log(f"Audio conectado a {ip}:{AUDIO_PORT}")
            self._start_streams()

            if self._win and self._win.winfo_exists():
                self._win.after(0, lambda: self._btn_connect.config(state=tk.DISABLED))
                self._win.after(0, lambda: self._btn_disconnect.config(state=tk.NORMAL))

        except Exception as e:
            self._set_status("⬤  Error", "#e74c3c")
            self._log(f"Error al conectar audio: {e}")

    def _start_streams(self):
        mic_idx = self._get_selected_mic()
        out_idx = self._get_selected_out()

        def _input_callback(indata, frames, time_info, status):
            if not self._active or self._conn_send is None:
                return
            if self._muted_local:
                silence = np.zeros_like(indata)
                data = silence.tobytes()
            else:
                data = indata.tobytes()
            try:
                _send_chunk(self._conn_send, data)
            except Exception:
                pass

        try:
            self._stream_in = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=CHUNK_FRAMES,
                device=mic_idx,
                callback=_input_callback,
            )
            self._stream_in.start()
            self._log(f"Micrófono [{mic_idx}] activo")
        except Exception as e:
            self._log(f"Error stream entrada: {e}")

        threading.Thread(target=self._recv_and_play,
                         args=(out_idx,), daemon=True).start()

    def _recv_and_play(self, out_idx):
        try:
            stream_out = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=CHUNK_FRAMES,
                device=out_idx,
            )
            self._stream_out = stream_out
            stream_out.start()
            self._log(f"Salida [{out_idx}] activa")

            while self._active and self._conn_recv:
                data = _recv_chunk(self._conn_recv)
                if data is None:
                    break
                if self._muted_remote:
                    continue
                audio = np.frombuffer(data, dtype=DTYPE)
                try:
                    stream_out.write(audio)
                except Exception:
                    break

            stream_out.stop()
            stream_out.close()
        except Exception as e:
            self._log(f"Error stream salida: {e}")

        if self._active:
            self._disconnect()

    def _stop_streams(self):
        for s in (self._stream_in, self._stream_out):
            if s:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
        self._stream_in  = None
        self._stream_out = None


def make_audio_button(parent, audio_panel: AudioPanel,
                      x: int, y: int,
                      width: int = 50, height: int = 37) -> tk.Button:
    btn = tk.Button(
        parent,
        text="🎤",
        bg="#0a3d4a",
        fg="white",
        font=("Arial", 16, "bold"),
        relief="flat",
        cursor="hand2",
        command=audio_panel.toggle_window,
    )
    btn.place(x=x, y=y, width=width, height=height)
    return btn
