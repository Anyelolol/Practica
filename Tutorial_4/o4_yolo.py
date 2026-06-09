import threading
import tkinter as tk
import numpy as np
import cv2
import time

_yolo_disponible = False
try:
    from ultralytics import YOLO as _YOLO

    _yolo_disponible = True
except ImportError:
    pass

MODEL_PATH = "yolo11n-pose.pt"

UMBRAL_ROJO = 170
UMBRAL_NARANJA = 70

_COLOR_HOLD_FRAMES = 4


def _color_altura(altura_px):
    if altura_px is None:
        return None
    if altura_px >= UMBRAL_ROJO:
        return "#e74c3c"  # Rojo: Muy cerca
    if altura_px >= UMBRAL_NARANJA:
        return "#f39c12"  # Naranja: Precaución
    return "#27ae60"  # Verde: Distancia segura


def _grosor_altura(altura_px):
    if altura_px is None:
        return 1
    if altura_px >= UMBRAL_ROJO:
        return 5  # Margen de 5 píxeles para Rojo
    if altura_px >= UMBRAL_NARANJA:
        return 3  # Margen de 3 píxeles para Naranja
    return 1  # Margen de 1 píxel para Verde


class YoloPoseProcessor:
    def __init__(self):
        self._model = None
        self._activo = True
        self._listo = False
        self._lock = threading.Lock()
        self._last_color: str | None = None

        # Suavizado anti-parpadeo
        self._color_history: list[str | None] = []
        self._stable_color: str | None = None

        threading.Thread(target=self._cargar_modelo, daemon=True).start()

    def _cargar_modelo(self):
        if not _yolo_disponible:
            print("[YOLO] ultralytics no instalado")
            return
        try:
            model = _YOLO(MODEL_PATH)
            with self._lock:
                self._model = model
                self._listo = True
            print("[YOLO] Modelo cargado con éxito")
        except Exception as e:
            print(f"[YOLO] Error al cargar el modelo: {e}")

    @property
    def activo(self):
        return self._activo

    @property
    def listo(self):
        return self._listo

    @property
    def last_color(self):
        return self._last_color

    def toggle(self):
        self._activo = not self._activo
        if not self._activo:
            self._last_color = None
            self._stable_color = None
            self._color_history.clear()
        return self._activo

    def procesar(self, frame: np.ndarray, es_bgr: bool = True) -> np.ndarray:
        if not self._activo or not self._listo:
            self._last_color = None
            return frame

        with self._lock:
            model = self._model
        if model is None:
            return frame

        bgr = frame if es_bgr else cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        try:
            t0 = time.time()
            results = model(bgr, conf=0.5, verbose=False)
            dt_ms = (time.time() - t0) * 1000

            bgr, raw_color = self._analizar(bgr, results)
            self._last_color = self._smooth_color(raw_color)
            print(f"[YOLO Perf] Inferencia: {dt_ms:.1f} ms | Color detectado: {raw_color}")

        except Exception as e:
            print(f"[YOLO] Error inferencia: {e}")
            self._last_color = None
            return frame

        return bgr if es_bgr else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def _smooth_color(self, raw: str | None) -> str | None:
        self._color_history.append(raw)
        if len(self._color_history) > _COLOR_HOLD_FRAMES:
            self._color_history.pop(0)

        votes: dict[str, int] = {}
        for c in self._color_history:
            if c is not None:
                votes[c] = votes.get(c, 0) + 1

        if not votes:
            self._stable_color = None
            return None

        winner = max(votes, key=lambda c: votes[c])
        if votes[winner] >= max(2, _COLOR_HOLD_FRAMES // 2):
            self._stable_color = winner

        return self._stable_color

    def _obtener_altura(self, bbox):
        x1, y1, x2, y2 = bbox
        altura = int(abs(y2 - y1))
        return max(1, altura)

    def _analizar(self, frame, results):
        max_altura = 0
        detectado = False

        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.xyxy.cpu().numpy()

            for bbox in boxes:
                detectado = True
                altura_px = self._obtener_altura(bbox)
                # Buscamos la caja más alta (la persona más cercana)
                if altura_px > max_altura:
                    max_altura = altura_px

        if not detectado:
            return frame, None
        print(f"[YOLO BBox Debug] Altura detectada: {max_altura}px / 240px")

        color_hex = _color_altura(max_altura)
        return frame, color_hex


def make_yolo_button(parent: tk.Misc, processor: YoloPoseProcessor,
                     x: int, y: int,
                     width: int = 37, height: int = 37) -> tk.Button:
    def _toggle():
        activo = processor.toggle()
        btn.config(bg="#8e44ad" if activo else "#2e2e2e")

    btn = tk.Button(
        parent,
        text="🤖",
        bg="#2e2e2e",
        fg="white",
        font=("Arial", 16, "bold"),
        relief="flat",
        cursor="hand2",
        command=_toggle,
    )
    btn.place(x=x, y=y, width=width, height=height)
    return btn