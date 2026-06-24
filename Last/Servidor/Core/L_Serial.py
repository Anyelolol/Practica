import customtkinter as ctk

PANEL  = "#1e1e1e"
FG     = "white"
FG_DIM = "#3e3e3e"

COMANDOS = [
    ("pcplc", "Run pcplc", "#0e6655"),
    ("ppnb",  "Run ppnb",  "#6c3483"),
    ("Abort", "a",         "#922b21"),
    ("🏠",     "home",      "#0b5345"),
]


class SerialPanel:
    """
    Panel de control remoto del servidor.
    No abre puerto serie propio: solo envia comandos por red al
    Cliente, que es quien tiene el puerto serie real conectado al brazo.
    """

    def __init__(self, tool_frame: ctk.CTkFrame, enviar_fn=None):
        self.tool_frame = tool_frame
        self.enviar_fn  = enviar_fn or (lambda cmd: None)
        self._frame      = None
        self._lbl_status = None

    def build(self):
        self._frame = ctk.CTkFrame(self.tool_frame, fg_color="transparent")
        f = self._frame
        FNT = ("Consolas", 13, "bold")

        self._lbl_status = ctk.CTkLabel(
            f, text="listo", height=28,
            font=FNT, text_color=FG_DIM, fg_color="transparent")
        self._lbl_status.place(x=4, y=4)

        for i, (label, cmd, color) in enumerate(COMANDOS):
            fila = i // 2
            col  = i % 2
            ctk.CTkButton(
                f, text=label,
                fg_color=color, hover_color=color,
                border_color=PANEL, border_width=2,
                font=FNT, text_color=FG, corner_radius=4,
                width=94, height=28,
                command=lambda c=cmd: self._enviar(c)
            ).place(x=4 + col * 99, y=36 + fila * 33)

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

    def _enviar(self, cmd: str):
        self.enviar_fn(cmd)
        self._set_status(f"→ {cmd}", FG_DIM)
