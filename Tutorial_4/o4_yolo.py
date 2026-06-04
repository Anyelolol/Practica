import tkinter as tk
from PIL import Image, ImageTk
import imutils
import cv2
import numpy as np
from ultralytics import YOLO

FOCAL_LENGTH = 600
ALTURA_PERSONA_REAL = 1.70

model = YOLO("yolo11n-pose.pt")

ventana = tk.Tk()
ventana.title("YOLO Pose - Detección de Distancia")
ventana.attributes("-zoomed", True)
ventana.resizable(width=1, height=1)

captura = None

def estimar_distancia(altura_pixels):
    if altura_pixels == 0:
        return None
    return round((ALTURA_PERSONA_REAL * FOCAL_LENGTH) / altura_pixels, 2)

def obtener_altura(keypoints, bbox):
    if keypoints is not None and len(keypoints) >= 16:
        nariz = keypoints[0]
        tobillo = keypoints[15]
        conf_n = nariz[2] if len(nariz) > 2 else 1.0
        conf_t = tobillo[2] if len(tobillo) > 2 else 1.0
        if conf_n > 0.5 and conf_t > 0.5:
            altura = abs(tobillo[1] - nariz[1])
            if altura > 20:
                return altura
    x1, y1, x2, y2 = bbox
    return abs(y2 - y1)

def dibujar_detecciones(frame, results):
    personas = 0
    for result in results:
        if result.boxes is None:
            continue
        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        kps_xy = result.keypoints.xy.cpu().numpy() if result.keypoints else None
        kps_conf = result.keypoints.conf.cpu().numpy() if result.keypoints else None

        for i, (bbox, conf) in enumerate(zip(boxes, confs)):
            personas += 1
            kps = None
            if kps_xy is not None and i < len(kps_xy):
                if kps_conf is not None:
                    kps = np.column_stack([kps_xy[i], kps_conf[i]])
                else:
                    kps = kps_xy[i]

            altura_px = obtener_altura(kps, bbox)
            distancia = estimar_distancia(altura_px)

            x1, y1, x2, y2 = map(int, bbox)

            if distancia is None:   color = (128, 128, 128)
            elif distancia < 1.5:   color = (0, 0, 255)
            elif distancia < 3.0:   color = (0, 165, 255)
            elif distancia < 5.0:   color = (0, 255, 255)
            else:                   color = (0, 255, 0)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            texto = f"P{personas}: {distancia}m" if distancia else f"P{personas}"
            (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
            cv2.putText(frame, texto, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            if kps is not None:
                for idx in [0, 5, 6, 11, 12, 15, 16]:
                    if idx < len(kps):
                        kp = kps[idx]
                        c = kp[2] if len(kp) > 2 else 1.0
                        if c > 0.5:
                            cv2.circle(frame, (int(kp[0]), int(kp[1])), 5, color, -1)

    return frame, personas

def iniciar():
    global captura
    if captura is not None:
        ret, frame = captura.read()
        if ret:
            results = model(frame, conf=0.5, verbose=False)
            frame, personas = dibujar_detecciones(frame, results)

            lbl_estado.config(text=f"Personas detectadas: {personas}")

            # Tamaño dinámico según el label
            ancho_label = LImagen.winfo_width()
            alto_label = LImagen.winfo_height()

            if ancho_label > 10 and alto_label > 10:
                frame_resized = cv2.resize(frame, (ancho_label, alto_label))
            else:
                frame_resized = imutils.resize(frame, width=800)

            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(frame_rgb)
            img = ImageTk.PhotoImage(image=im)
            LImagen.configure(image=img)
            LImagen.image = img

        LImagen.after(30, iniciar)

def camara():
    global captura
    if captura is None:
        captura = cv2.VideoCapture(1)
        if captura.isOpened():
            btn_camara.config(text="Detener")
            iniciar()
        else:
            lbl_estado.config(text="Error: no se pudo abrir la cámara")
    else:
        captura.release()
        captura = None
        btn_camara.config(text="OnCamara")
        LImagen.configure(image="")
        lbl_estado.config(text="Cámara detenida")

def al_cerrar():
    global captura
    if captura:
        captura.release()
    ventana.destroy()

# UI con pack para que sea responsive
frame_principal = tk.Frame(ventana, bg="black")
frame_principal.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

LImagen = tk.Label(frame_principal, background="black")
LImagen.pack(fill=tk.BOTH, expand=True)

frame_inferior = tk.Frame(ventana, bg="#1e1e1e", height=60)
frame_inferior.pack(fill=tk.X, side=tk.BOTTOM)
frame_inferior.pack_propagate(False)

lbl_estado = tk.Label(frame_inferior, text="Presiona OnCamara para iniciar",
                       font=("Arial", 11), fg="lightgray", bg="#1e1e1e")
lbl_estado.pack(side=tk.LEFT, padx=15)

colores_texto = "🟢 >5m   🟡 3-5m   🟠 1.5-3m   🔴 <1.5m"
tk.Label(frame_inferior, text=colores_texto, font=("Arial", 10),
         bg="#1e1e1e", fg="white").pack(side=tk.LEFT, padx=20)

btn_camara = tk.Button(frame_inferior, text="OnCamara", command=camara,
                        font=("Arial", 11), width=12, bg="#333", fg="white",
                        activebackground="#555", relief=tk.FLAT)
btn_camara.pack(side=tk.RIGHT, padx=15, pady=10)

ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
ventana.mainloop()