#!/usr/bin/env python3
"""
Camera Recorder + GUI de prueba - Todo en uno
Optimizado para telemetria: 960x540 @ 3 FPS, color basico, archivo ligero
"""
import cv2
import numpy as np
import threading
import time
import os
import platform
import glob
import subprocess as sp
from datetime import datetime
from PIL import Image, ImageTk
import tkinter as tk

# ==========================================
# CONFIGURACION
# ==========================================
RESOLUTION_OUT = (960, 540)
TARGET_FPS = 3
FRAME_INTERVAL = 1.0 / TARGET_FPS
OUTPUT_DIR = "pruebas_camara"
DENOISE_KERNEL = (3, 3)

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"


# ==========================================
# DETECCION DE CAMARAS (copiado de tu cliente)
# ==========================================
def detectar_camaras() -> list:
    disponibles = []
    backend = cv2.CAP_V4L2

    if platform.system() == "Linux":
        indices = []
        for d in sorted(glob.glob("/dev/video*")):
            try:
                idx = int(d.replace("/dev/video", ""))
            except Exception:
                continue
            try:
                out = sp.check_output(
                    ["v4l2-ctl", "--device", d, "--info"],
                    stderr=sp.DEVNULL, timeout=2
                ).decode()
                if "loopback" in out.lower() or "virtual" in out.lower():
                    continue
            except Exception:
                pass
            indices.append(idx)
        if not indices:
            indices = list(range(8))
    else:
        indices = list(range(8))

    for i in indices:
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, frame = cap.read()
            if ret and frame is not None and frame.size > 0:
                disponibles.append(i)
        cap.release()
        time.sleep(0.05)
    return disponibles


# ==========================================
# GRABADORA OPTIMIZADA
# ==========================================
class CameraRecorder:
    def __init__(self, cam_index=0, output_dir=OUTPUT_DIR, fps=TARGET_FPS,
                 resolution=RESOLUTION_OUT, escala_grises=False):
        self.cam_index = cam_index
        self.output_dir = output_dir
        self.fps = fps
        self.resolution = resolution
        self.escala_grises = escala_grises

        self._activo = False
        self._hilo = None
        self._writer = None
        self._cap = None
        self._out_path = None
        self._frames = 0
        self._start_ts = None

    def start(self, suffix=""):
        if self._activo:
            return self._out_path

        self._cap = cv2.VideoCapture(self.cam_index, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la camara {self.cam_index}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        modo = "bw" if self.escala_grises else "color"
        self._out_path = os.path.join(
            self.output_dir,
            f"cam_{ts}_{modo}{suffix}.avi"
        )

        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        is_color = not self.escala_grises

        self._writer = cv2.VideoWriter(
            self._out_path, fourcc, self.fps, self.resolution, isColor=is_color
        )

        if not self._writer.isOpened():
            self._cap.release()
            raise RuntimeError("No se pudo crear el archivo de video")

        self._activo = True
        self._frames = 0
        self._start_ts = time.time()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

        print(f"[Recorder] Grabando: {self._out_path} | Modo: {modo}")
        return self._out_path

    def stop(self):
        if not self._activo:
            return None

        self._activo = False
        if self._hilo:
            self._hilo.join(timeout=3.0)

        if self._writer:
            self._writer.release()
            self._writer = None
        if self._cap:
            self._cap.release()
            self._cap = None

        duracion = self._frames / self.fps if self.fps else 0
        tamanio = 0
        if self._out_path and os.path.exists(self._out_path):
            tamanio = round(os.path.getsize(self._out_path) / (1024 * 1024), 2)

        return {
            "path": self._out_path,
            "frames": self._frames,
            "duracion_s": round(duracion, 1),
            "fps": self.fps,
            "resolucion": self.resolution,
            "tamanio_mb": tamanio,
            "escala_grises": self.escala_grises,
        }

    def is_recording(self):
        return self._activo

    def _procesar_frame(self, frame):
        """Pipeline de optimizacion."""
        # 1. Resize a salida
        frame = cv2.resize(frame, self.resolution, interpolation=cv2.INTER_AREA)

        # 2. Denoise ligero (elimina ruido del sensor que consume bits)
        frame = cv2.GaussianBlur(frame, DENOISE_KERNEL, 0.5)

        # 3. Sharpen para recuperar bordes
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        frame = cv2.filter2D(frame, -1, kernel)

        # 4. Cuantizacion 6-bit (color basico)
        frame = (frame // 4) * 4

        # 5. Escala de grises si aplica (reduce tamano ~30-50%)
        if self.escala_grises:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        return frame

    def _bucle(self):
        while self._activo:
            t0 = time.time()

            ret, frame = self._cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            frame = self._procesar_frame(frame)
            self._writer.write(frame)
            self._frames += 1

            elapsed = time.time() - t0
            sleep_t = FRAME_INTERVAL - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)


# ==========================================
# GUI DE PRUEBA
# ==========================================
class PruebaCompleta:
    def __init__(self, master):
        self.master = master
        self.master.title("Camera Recorder - Prueba Integrada")
        self.master.geometry("1000x700")
        self.master.config(bg="#0a0a0a")
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.recorder = None
        self._preview_activo = True
        self._cap_preview = None

        self._build_ui()
        self._detectar()

    def _build_ui(self):
        self.lbl_preview = tk.Label(self.master, bg="#000", text="Esperando camara...",
                                    fg="#555", font=("Consolas", 14))
        self.lbl_preview.place(x=20, y=20, width=960, height=540)

        panel = tk.Frame(self.master, bg="#141414", width=280, height=660)
        panel.place(x=700, y=20)

        tk.Label(panel, text="CAMARA RECORDER", bg="#141414", fg="#888",
                 font=("Consolas", 12, "bold")).pack(pady=10)

        tk.Label(panel, text="Indice Camara:", bg="#141414", fg="#888",
                 font=("Consolas", 9)).pack()
        self.combo_cam = tk.StringVar(value="0")
        tk.Entry(panel, textvariable=self.combo_cam, font=("Consolas", 12),
                 width=5, bg="#1a1a1a", fg="white", insertbackground="white",
                 relief="flat", justify="center").pack(pady=2)

        # Escala de grises
        self.var_bw = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text="Escala de grises (menor tamano)",
                       variable=self.var_bw, bg="#141414", fg="#aaa",
                       selectcolor="#333", font=("Consolas", 9)).pack(pady=10)

        self.btn_record = tk.Button(
            panel, text="⏺ GRABAR", bg="#922b21", fg="white",
            font=("Consolas", 12, "bold"), relief="flat", cursor="hand2",
            command=self.toggle_grabacion)
        self.btn_record.pack(pady=15, padx=10, fill="x")

        self.lbl_estado = tk.Label(panel, text="SIN GRABAR", bg="#141414", fg="#777",
                                   font=("Consolas", 11, "bold"))
        self.lbl_estado.pack(pady=5)

        self.stats = tk.Label(panel, text="Esperando...", bg="#141414", fg="#aaa",
                              font=("Consolas", 9), justify="left")
        self.stats.pack(pady=10)

        self.consola = tk.Text(self.master, bg="#050505", fg="#00ff00",
                               font=("Consolas", 9), relief="flat", height=5)
        self.consola.place(x=20, y=570, width=660, height=80)
        self.log("Sistema listo.")

        tk.Button(panel, text="SALIR", bg="#333", fg="white",
                  font=("Consolas", 10), relief="flat", cursor="hand2",
                  command=self.on_close).pack(side="bottom", pady=10, padx=10, fill="x")

    def _detectar(self):
        self.log("Detectando camaras...")
        cams = detectar_camaras()
        if cams:
            self.combo_cam.set(str(cams[0]))
            self.log(f"Detectadas: {cams}")
            self._iniciar_preview(int(self.combo_cam.get()))
        else:
            self.log("⚠️  Ninguna camara detectada.")

    def _iniciar_preview(self, idx):
        if self._cap_preview:
            self._cap_preview.release()
        self._cap_preview = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if self._cap_preview.isOpened():
            self._cap_preview.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap_preview.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            threading.Thread(target=self._bucle_preview, daemon=True).start()

    def _bucle_preview(self):
        while self._preview_activo and self._cap_preview and self._cap_preview.isOpened():
            ret, frame = self._cap_preview.read()
            if ret and frame is not None:
                small = cv2.resize(frame, (960, 540), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                im = Image.fromarray(rgb)
                photo = ImageTk.PhotoImage(image=im)

                def up(p=photo):
                    self.lbl_preview.configure(image=p, text="")
                    self.lbl_preview.image = p

                self.master.after(0, up)
            time.sleep(0.033)

    def toggle_grabacion(self):
        if self.recorder and self.recorder.is_recording():
            info = self.recorder.stop()
            self.btn_record.config(text="⏺ GRABAR", bg="#922b21")
            self.lbl_estado.config(text="SIN GRABAR", fg="#777")
            self.log("DETENIDO")
            self.log(f"{info['tamanio_mb']} MB | {info['frames']} frames | {info['duracion_s']}s")
            self.stats.config(text=f"Ultimo: {info['tamanio_mb']} MB\n"
                                   f"Frames: {info['frames']}\n"
                                   f"Duracion: {info['duracion_s']}s\n"
                                   f"Modo: {'B/N' if info['escala_grises'] else 'Color'}")
            self.recorder = None
            # Volver a preview
            self._iniciar_preview(int(self.combo_cam.get()))
        else:
            try:
                idx = int(self.combo_cam.get())
                bw = self.var_bw.get()

                if self._cap_preview:
                    self._cap_preview.release()
                    self._cap_preview = None

                self.recorder = CameraRecorder(
                    cam_index=idx,
                    escala_grises=bw
                )
                path = self.recorder.start()
                self.btn_record.config(text="⏹ DETENER", bg="#1e8449")
                self.lbl_estado.config(text="🔴 GRABANDO", fg="#ff4444")
                self.log(f"GRABANDO: {path}")
            except Exception as e:
                self.log(f"ERROR: {e}")
                self._iniciar_preview(int(self.combo_cam.get()))

    def log(self, msg):
        self.consola.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.consola.see(tk.END)

    def on_close(self):
        self._preview_activo = False
        if self.recorder and self.recorder.is_recording():
            info = self.recorder.stop()
            self.log(f"Cierre: {info['path']}")
        if self._cap_preview:
            self._cap_preview.release()
        self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = PruebaCompleta(root)
    root.mainloop()
