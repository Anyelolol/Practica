import cv2
import numpy as np
import threading
import time
import os
from datetime import datetime

RESOLUTION_OUT = (960, 540)
TARGET_FPS = 3
FRAME_INTERVAL = 1.0 / TARGET_FPS
OUTPUT_DIR = "registros_video"


class CameraRecorder:
    """
    Grabadora de cámara para telemetría.
    - Entrada: cualquier índice de cámara (0, 1, 2...)
    - Salida: 960x540 @ 3 FPS, color básico, archivo AVI (MJPEG)
    """

    def __init__(self, cam_index=0, output_dir=OUTPUT_DIR, fps=TARGET_FPS,
                 resolution=RESOLUTION_OUT):
        self.cam_index = cam_index
        self.output_dir = output_dir
        self.fps = fps
        self.resolution = resolution

        self._activo = False
        self._hilo = None
        self._writer = None
        self._cap = None
        self._out_path = None
        self._frames = 0
        self._start_ts = None

        os.makedirs(self.output_dir, exist_ok=True)

    def start(self, suffix=""):
        if self._activo:
            return self._out_path

        self._cap = cv2.VideoCapture(self.cam_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara {self.cam_index}")

        # Forzar resolución de entrada cercana a la deseada para mejor calidad
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._out_path = os.path.join(
            self.output_dir,
            f"camara_{ts}{suffix}.avi"
        )

        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        self._writer = cv2.VideoWriter(
            self._out_path, fourcc, self.fps, self.resolution, isColor=True
        )

        if not self._writer.isOpened():
            self._cap.release()
            raise RuntimeError("No se pudo crear el archivo de video")

        self._activo = True
        self._frames = 0
        self._start_ts = time.time()

        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

        print(f"[CameraRecorder] Grabando: {self._out_path}")
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

        resultado = {
            "path": self._out_path,
            "frames": self._frames,
            "duracion_s": round(duracion, 1),
            "fps": self.fps,
            "resolucion": self.resolution,
            "tamanio_mb": tamanio,
        }
        self._out_path = None
        return resultado

    def is_recording(self):
        return self._activo

    def read_frame(self):
        """Lee un frame para preview (no graba)."""
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                return cv2.resize(frame, self.resolution, interpolation=cv2.INTER_AREA)
        return None

    def _bucle(self):
        while self._activo:
            t0 = time.time()

            ret, frame = self._cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Procesamiento
            frame = cv2.resize(frame, self.resolution, interpolation=cv2.INTER_AREA)
            frame = np.ascontiguousarray(frame, dtype=np.uint8)

            # Color básico: denoise + cuantización 6-bit
            frame = cv2.GaussianBlur(frame, (3, 3), 0.5)
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
            frame = cv2.filter2D(frame, -1, kernel)
            frame = (frame // 4) * 4
            frame = np.ascontiguousarray(frame, dtype=np.uint8)

            self._writer.write(frame)
            self._frames += 1

            elapsed = time.time() - t0
            sleep_t = FRAME_INTERVAL - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)