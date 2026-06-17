import os
import threading
import numpy as np
import cv2
import time

_yolo_disponible = False
try:
    from ultralytics import YOLO as _YOLO
    _yolo_disponible = True
except ImportError:
    pass

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Models", "yolo11n-pose.pt")

UMBRAL_ROJO = 170
UMBRAL_NARANJA = 70
_COLOR_HOLD_FRAMES = 4


def _color_altura(altura_px):
    if altura_px is None:
        return None
    if altura_px >= UMBRAL_ROJO:
        return "#e74c3c"
    if altura_px >= UMBRAL_NARANJA:
        return "#f39c12"
    return "#27ae60"


class YoloPoseProcessor:
    def __init__(self):
        self._model = None
        self._activo = True
        self._listo = False
        self._lock = threading.Lock()
        self._last_color = None
        self._color_history = []
        self._stable_color = None
        threading.Thread(target=self._cargar_modelo, daemon=True).start()

    def _cargar_modelo(self):
        if not _yolo_disponible:
            return
        try:
            model = _YOLO(MODEL_PATH)
            with self._lock:
                self._model = model
                self._listo = True
        except Exception as e:
            pass

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

    def procesar(self, frame, es_bgr=True):
        if not self._activo or not self._listo:
            self._last_color = None
            return frame
        with self._lock:
            model = self._model
        if model is None:
            return frame
        bgr = frame if es_bgr else cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        try:
            results = model(bgr, conf=0.5, verbose=False)
            bgr, raw_color = self._analizar(bgr, results)
            self._last_color = self._smooth_color(raw_color)
        except Exception:
            self._last_color = None
            return frame
        return bgr if es_bgr else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def _smooth_color(self, raw):
        self._color_history.append(raw)
        if len(self._color_history) > _COLOR_HOLD_FRAMES:
            self._color_history.pop(0)
        votes = {}
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
                if altura_px > max_altura:
                    max_altura = altura_px
        if not detectado:
            return frame, None
        color_hex = _color_altura(max_altura)
        return frame, color_hex
