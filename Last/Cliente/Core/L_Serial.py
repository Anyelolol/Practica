import glob
import platform
import threading
import time
import customtkinter as ctk

try:
    import serial
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False

PANEL  = "#1e1e1e"
FG     = "white"
FG_DIM = "#3e3e3e"
FONT   = ("Consolas", 28, "bold")

BAUD   = 9600

COMANDOS = [
    ("pcplc", b"Run pcplc\r", "#0e6655"),
    ("ppnb",  b"Run ppnb\r",  "#6c3483"),
    ("Abort",   b"a\r",         "#922b21"),
    ("Coff",      b"coff\r",      "#784212"),
    ("Move0",    b"move 0\r",    "#1a5276"),
    ("🏠",        b"home\r",      "#0b5345"),
    ("Open",      b"open\r",      "#424949"),
    ("Close",     b"close\r",     "#17202a"),
]


def _listar_puertos() -> list[str]:
    if platform.system() == "Windows":
        return [f"COM{i}" for i in range(1, 21)]
    return sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")) or ["/dev/ttyUSB0"]


class SerialPanel:

    def __init__(self, tool_frame: ctk.CTkFrame):
        self.tool_frame  = tool_frame
        self._port: "serial.Serial | None" = None
        self._cmd_ts: dict = {}
        self._lock       = threading.Lock()
        self._frame      = None
        self._combo_port = None
        self._lbl_status = None
        self._btn_toggle = None
        self._connected  = False

    def build(self):
        self._frame = ctk.CTkFrame(self.tool_frame, fg_color="transparent")
        f = self._frame

        puertos = _listar_puertos()
        self._combo_port = ctk.CTkComboBox(
            f, values=puertos, width=250, height=50,
            fg_color=PANEL, border_color=PANEL,
            button_color=PANEL, button_hover_color="#2a2a2a",
            font=FONT, text_color=FG,
            dropdown_font=FONT, dropdown_fg_color=PANEL,
            dropdown_text_color=FG, dropdown_hover_color="#2a2a2a",
            state="readonly")
        self._combo_port.set(puertos[0] if puertos else "")
        self._combo_port.place(x=5, y=5)

        ctk.CTkButton(
            f, text="↺", width=50, height=50,
            fg_color=PANEL, border_color=PANEL, border_width=2,
            font=FONT, text_color=FG, corner_radius=5,
            command=self._refresh_ports
        ).place(x=260, y=5)

        self._btn_toggle = ctk.CTkButton(
            f, text="conectar", width=150, height=50,
            fg_color=PANEL, border_color=PANEL, border_width=2,
            font=FONT, text_color=FG, corner_radius=5,
            command=self._toggle_conexion)
        self._btn_toggle.place(x=315, y=5)

        self._lbl_status = ctk.CTkLabel(
            f, text="offline", height=50,
            font=FONT, text_color=FG_DIM, fg_color="transparent")
        self._lbl_status.place(x=470, y=5)

        for i, (label, cmd_bytes, color) in enumerate(COMANDOS):
            fila = i // 4
            col  = i % 4
            ctk.CTkButton(
                f, text=label,
                fg_color=color, hover_color=color,
                border_color=PANEL, border_width=2,
                font=FONT, text_color=FG, corner_radius=5,
                command=lambda c=cmd_bytes: self._enviar(c)
            ).place(x=5 + col * 145, y=60 + fila * 55)

    def show(self):
        if self._frame:
            self._frame.place(x=0, y=0, relwidth=1, relheight=1)

    def hide(self):
        if self._frame:
            self._frame.place_forget()

    def toggle(self):
        if self._frame is None:
            return
        if bool(self._frame.place_info()):
            self.hide()
        else:
            self.show()

    def manejar_remoto(self, cmd: str):
        if cmd in ("ON", "OFF"):
            return
        cmd = cmd.strip()
        ahora = time.time()
        with self._lock:
            if ahora - self._cmd_ts.get(cmd, 0) < 0.3:
                return
            self._cmd_ts[cmd] = ahora
        self._enviar(cmd.encode("utf-8") + b"\r")

    def is_open(self) -> bool:
        return self._port is not None and self._port.is_open

    def close(self):
        if self.is_open():
            self._port.close()

    def _after(self, fn):
        try:
            self.tool_frame.after(0, fn)
        except Exception:
            pass

    def _set_status(self, text: str, color: str):
        def _do():
            if self._lbl_status and self._lbl_status.winfo_exists():
                self._lbl_status.configure(text=text, text_color=color)
        self._after(_do)

    def _refresh_ports(self):
        puertos = _listar_puertos()
        self._combo_port.configure(values=puertos)
        if puertos:
            self._combo_port.set(puertos[0])
        self._set_status(f"{len(puertos)} puertos", FG_DIM)

    def _toggle_conexion(self):
        if self.is_open():
            self._desconectar()
        else:
            self._conectar()

    def _conectar(self):
        if not SERIAL_OK:
            self._set_status("instalar pyserial", "#e74c3c")
            return
        puerto = self._combo_port.get().strip()
        if not puerto:
            self._set_status("sin puerto", "#e74c3c")
            return
        try:
            self._port = serial.Serial(
                port=puerto, baudrate=BAUD,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False, rtscts=False, dsrdtr=False,
            )
            time.sleep(1)
            self._port.write(b"speed 20\r")
            self._port.flush()
            time.sleep(1)
            self._port.write(b"speedl 20\r")
            self._port.flush()
            time.sleep(1)
            self._port.write(b"home\r")
            self._port.flush()
            self._set_status("conectado", "#2ecc71")
            time.sleep(0.7) 
            self._set_status("home", "#2ecc71")
            self._after(lambda: self._btn_toggle.configure(text="desconectar", text_color="#e74c3c"))
        except Exception as e:
            self._set_status(f"error: {e}", "#e74c3c")

    def _desconectar(self):
        if self.is_open():
            self._port.close()
        self._port = None
        self._set_status("desconectado", FG_DIM)
        self._after(lambda: self._btn_toggle.configure(text="conectar", text_color=FG))

    def _enviar(self, cmd_bytes: bytes):
        self.send_raw(cmd_bytes)

    def send_raw(self, cmd_bytes: bytes):
        if not self.is_open():
            self._set_status(f"sin puerto", "#e74c3c")
            return
        try:
            self._port.write(cmd_bytes)
            self._port.flush()
            self._set_status(f"→ {cmd_bytes.decode('utf-8', errors='ignore').strip()}", FG_DIM)
        except Exception as e:
            self._set_status(f"error: {e}", "#e74c3c")
