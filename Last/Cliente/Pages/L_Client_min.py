import customtkinter as ctk

PANEL  = "#1e1e1e"
FG_DIM = "#3e3e3e"


class ClienteMini:
    """
    Ventana reducida del cliente. Vive en el MISMO proceso que la ventana
    principal: no destruye ni reconecta nada. Al mostrarse, simplemente
    redirige el render de los streams de camara activos hacia sus propios
    labels, y al volver a la ventana principal los devuelve a sus slots
    originales en F_Scroll. Audio y serial siguen corriendo igual en
    segundo plano durante todo el cambio.
    """

    def __init__(self, parent: ctk.CTk, camaras, audio, serial,
                 ir_a_principal_fn, log_fn=None, on_abort_fn=None, on_home_fn=None):
        self.parent      = parent
        self.camaras     = camaras
        self.audio       = audio
        self.serial      = serial
        self._ir_a_principal = ir_a_principal_fn
        self._log_fn     = log_fn or (lambda msg: None)
        self._on_abort    = on_abort_fn
        self._on_home     = on_home_fn

        self._win: ctk.CTkToplevel | None = None
        self._cam_labels: list = []
        self._labels_originales: dict = {}

    def _build(self):
        win = ctk.CTkToplevel(self.parent)
        win.title("Cliente Mini")
        win.geometry("960x540")
        win.configure(fg_color="black")
        win.protocol("WM_DELETE_WINDOW", self._volver)

        for i in range(4):
            fila, col = divmod(i, 2)
            f = ctk.CTkFrame(win, width=320, height=180, fg_color=PANEL,
                              bg_color="transparent", border_color=PANEL,
                              corner_radius=2)
            f.place(x=5 + col * 325, y=5 + fila * 185)
            lbl = ctk.CTkLabel(f, anchor="center", text="", cursor="hand2",
                                width=320, height=180, text_color=FG_DIM)
            lbl.place(x=0, y=0)
            self._cam_labels.append(lbl)

        self.E_Bash = ctk.CTkEntry(win, width=300, height=50,
                                    font=("Consolas", 28, "bold"), fg_color="#000")
        self.E_Bash.place(x=655, y=485)

        self.T_LogBash = ctk.CTkTextbox(win, width=300, height=475,
                                         font=("Consolas", 16, "bold"), fg_color=PANEL,
                                         state="disabled")
        self.T_LogBash.place(x=655, y=5)

        self.T_LogRes = ctk.CTkTextbox(win, width=590, height=160,
                                        font=("Consolas", 16, "bold"), fg_color=PANEL)
        self.T_LogRes.place(x=5, y=375)

        B_Abortar = ctk.CTkButton(win, width=50, height=50, text="A", fg_color="red",
                                   font=("Consolas", 28, "bold"), corner_radius=5,
                                   border_color=PANEL, border_width=2,
                                   command=self._abortar)
        B_Abortar.place(x=600, y=485)

        B_Home = ctk.CTkButton(win, width=50, height=50, text="🏠", fg_color="#000",
                                font=("Consolas", 28, "bold"), corner_radius=5,
                                border_color=PANEL, border_width=2,
                                command=self._home)
        B_Home.place(x=600, y=430)

        B_Volver = ctk.CTkButton(win, width=50, height=50, text="<-", fg_color="#000",
                                  font=("Consolas", 28, "bold"), corner_radius=5,
                                  border_color=PANEL, border_width=2,
                                  command=self._volver)
        B_Volver.place(x=600, y=375)

        self._win = win

    def log(self, text: str):
        def _do():
            if not (self._win and self._win.winfo_exists()):
                return
            self.T_LogBash.configure(state="normal")
            self.T_LogBash.insert("end", text + "\n")
            self.T_LogBash.see("end")
            self.T_LogBash.configure(state="disabled")
            self.T_LogRes.configure(state="normal")
            self.T_LogRes.insert("end", text + "\n")
            self.T_LogRes.see("end")
            self.T_LogRes.configure(state="disabled")
        try:
            self.parent.after(0, _do)
        except Exception:
            pass

    def _abortar(self):
        if self._on_abort:
            self._on_abort()

    def _home(self):
        if self._on_home:
            self._on_home()

    def _redirigir_streams_a_mini(self):
        with self.camaras._streams_lock:
            streams = list(self.camaras._streams.values())

        self._labels_originales.clear()
        for i, lbl in enumerate(self._cam_labels):
            if i < len(streams):
                stream = streams[i]
                self._labels_originales[stream.cam_index] = stream.label
                stream.label = lbl
            else:
                lbl.configure(image=None, text="sin señal")

    def _restaurar_streams_originales(self):
        with self.camaras._streams_lock:
            streams = {s.cam_index: s for s in self.camaras._streams.values()}
        for cam_idx, lbl_original in self._labels_originales.items():
            stream = streams.get(cam_idx)
            if stream:
                stream.label = lbl_original
        self._labels_originales.clear()

    def mostrar(self):
        if self._win is None or not self._win.winfo_exists():
            self._build()
        self._redirigir_streams_a_mini()
        self._win.deiconify()
        self._win.lift()
        self.parent.withdraw()

    def _volver(self):
        self._restaurar_streams_originales()
        if self._win and self._win.winfo_exists():
            self._win.withdraw()
        self.parent.deiconify()
        self.parent.lift()
        self._ir_a_principal()
