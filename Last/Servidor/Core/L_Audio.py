import socket
import struct
import threading
import numpy as np
import customtkinter as ctk

try:
    import sounddevice as sd
    SD_OK = True
except ImportError:
    SD_OK = False

SAMPLE_RATE  = 44100
CHANNELS     = 1
DTYPE        = "int16"
CHUNK_FRAMES = 1024
AUDIO_PORT   = 9999
HEADER_FMT   = "!I"
HEADER_SIZE  = struct.calcsize(HEADER_FMT)

PANEL  = "#1e1e1e"
FG     = "white"
FG_DIM = "#3e3e3e"
FONT   = ("Consolas", 28, "bold")


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


class AudioServer:
    def __init__(self, parent_frame: ctk.CTkFrame):
        self.parent = parent_frame

        self._conn_send: socket.socket | None = None
        self._conn_recv: socket.socket | None = None
        self._server_sock: socket.socket | None = None
        self._active      = False
        self._muted_local = False
        self._stream_in   = None
        self._stream_out  = None
        self._mic_map: dict = {}
        self._out_map: dict = {}

        self._frame       = None
        self._combo_mic   = None
        self._combo_out   = None
        self._btn_mute    = None
        self._btn_disc    = None
        self._lbl_status  = None
        self._visible     = False

    def iniciar(self):
        threading.Thread(target=self._server_listen, daemon=True).start()

    def build(self):
        self._frame = ctk.CTkFrame(self.parent, fg_color="transparent")

        FNT  = ("Consolas", 13, "bold")
        W    = 193

        mics = _listar_microfonos()
        mic_names = [f"[{m['index']}] {m['name'][:16]}" for m in mics] or ["(sin mic)"]
        self._mic_map = {n: m["index"] for n, m in zip(mic_names, mics)}
        self._combo_mic = ctk.CTkComboBox(
            self._frame, values=mic_names, width=W, height=32,
            fg_color=PANEL, border_color=PANEL,
            button_color=PANEL, button_hover_color="#2a2a2a",
            font=FNT, text_color=FG,
            dropdown_font=FNT, dropdown_fg_color=PANEL,
            dropdown_text_color=FG, dropdown_hover_color="#2a2a2a",
            state="readonly")
        self._combo_mic.set(mic_names[0])
        self._combo_mic.place(x=4, y=4)

        outs = _listar_altavoces()
        out_names = [f"[{o['index']}] {o['name'][:16]}" for o in outs] or ["(sin salida)"]
        self._out_map = {n: o["index"] for n, o in zip(out_names, outs)}
        self._combo_out = ctk.CTkComboBox(
            self._frame, values=out_names, width=W, height=32,
            fg_color=PANEL, border_color=PANEL,
            button_color=PANEL, button_hover_color="#2a2a2a",
            font=FNT, text_color=FG,
            dropdown_font=FNT, dropdown_fg_color=PANEL,
            dropdown_text_color=FG, dropdown_hover_color="#2a2a2a",
            state="readonly")
        self._combo_out.set(out_names[0])
        self._combo_out.place(x=4, y=40)

        self._btn_mute = ctk.CTkButton(
            self._frame, text="🎤", width=32, height=32,
            fg_color=PANEL, border_color=PANEL, border_width=2,
            font=FNT, text_color=FG, corner_radius=4,
            command=self._toggle_mute)
        self._btn_mute.place(x=4, y=78)

        ctk.CTkButton(
            self._frame, text="↺", width=32, height=32,
            fg_color=PANEL, border_color=PANEL, border_width=2,
            font=FNT, text_color=FG, corner_radius=4,
            command=self._refresh_devs
        ).place(x=40, y=78)

        self._btn_disc = ctk.CTkButton(
            self._frame, text="cortar", width=113, height=32,
            fg_color=PANEL, border_color=PANEL, border_width=2,
            font=FNT, text_color="#e74c3c", corner_radius=4,
            state="disabled",
            command=self._disconnect)
        self._btn_disc.place(x=76, y=78)

        self._lbl_status = ctk.CTkLabel(
            self._frame, text="esperando…", height=28,
            font=FNT, text_color=FG_DIM, fg_color="transparent")
        self._lbl_status.place(x=4, y=114)

    def toggle(self):
        if self._frame is None:
            return
        self._visible = not self._visible
        if self._visible:
            self._frame.place(x=0, y=0, relwidth=1, relheight=1)
        else:
            self._frame.place_forget()

    def hide(self):
        if self._frame:
            self._frame.place_forget()
            self._visible = False

    def destroy(self):
        self._disconnect()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    def _set_status(self, text: str, color: str):
        def _do():
            if self._lbl_status and self._lbl_status.winfo_exists():
                self._lbl_status.configure(text=text, text_color=color)
        try:
            self._frame.after(0, _do)
        except Exception:
            pass

    def _refresh_devs(self):
        mics = _listar_microfonos()
        mic_names = [f"[{m['index']}] {m['name'][:20]}" for m in mics] or ["(sin mic)"]
        self._mic_map = {n: m["index"] for n, m in zip(mic_names, mics)}
        self._combo_mic.configure(values=mic_names)
        self._combo_mic.set(mic_names[0])

        outs = _listar_altavoces()
        out_names = [f"[{o['index']}] {o['name'][:20]}" for o in outs] or ["(sin salida)"]
        self._out_map = {n: o["index"] for n, o in zip(out_names, outs)}
        self._combo_out.configure(values=out_names)
        self._combo_out.set(out_names[0])
        self._set_status("actualizado", FG_DIM)

    def _toggle_mute(self):
        self._muted_local = not self._muted_local
        if self._muted_local:
            self._btn_mute.configure(text="🔇", text_color="#e74c3c")
        else:
            self._btn_mute.configure(text="🎤", text_color=FG)

    def _get_mic(self) -> int | None:
        if not SD_OK or not self._combo_mic:
            return None
        return self._mic_map.get(self._combo_mic.get())

    def _get_out(self) -> int | None:
        if not SD_OK or not self._combo_out:
            return None
        return self._out_map.get(self._combo_out.get())

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
        self._set_status("esperando…", FG_DIM)
        try:
            self._frame.after(0, lambda: self._btn_disc.configure(state="disabled"))
        except Exception:
            pass

    def _server_listen(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", AUDIO_PORT))
        srv.listen(4)
        self._server_sock = srv

        while True:
            try:
                conn, addr = srv.accept()
                role_byte = conn.recv(4)
                if role_byte == b"SEND":
                    self._conn_recv = conn
                elif role_byte == b"RECV":
                    self._conn_send = conn

                if self._conn_send and self._conn_recv:
                    self._active = True
                    self._set_status("conectado", "#2ecc71")
                    self._start_streams()
                    try:
                        self._frame.after(0, lambda: self._btn_disc.configure(state="normal"))
                    except Exception:
                        pass
            except Exception as e:
                self._set_status(f"error: {e}", "#e74c3c")
                break

    def _start_streams(self):
        mic_idx = self._get_mic()
        out_idx = self._get_out()

        def _input_cb(indata, frames, time_info, status):
            if not self._active or self._conn_send is None:
                return
            data = np.zeros_like(indata).tobytes() if self._muted_local else indata.tobytes()
            try:
                _send_chunk(self._conn_send, data)
            except Exception:
                pass

        try:
            self._stream_in = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS,
                dtype=DTYPE, blocksize=CHUNK_FRAMES,
                device=mic_idx, callback=_input_cb)
            self._stream_in.start()
        except Exception as e:
            self._set_status(f"error mic: {e}", "#e74c3c")

        threading.Thread(target=self._recv_play, args=(out_idx,), daemon=True).start()

    def _recv_play(self, out_idx):
        try:
            stream_out = sd.OutputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS,
                dtype=DTYPE, blocksize=CHUNK_FRAMES, device=out_idx)
            self._stream_out = stream_out
            stream_out.start()

            while self._active and self._conn_recv:
                data = _recv_chunk(self._conn_recv)
                if data is None:
                    break
                audio = np.frombuffer(data, dtype=DTYPE)
                try:
                    stream_out.write(audio)
                except Exception:
                    break

            stream_out.stop()
            stream_out.close()
        except Exception as e:
            self._set_status(f"error salida: {e}", "#e74c3c")

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
        self._stream_in = self._stream_out = None