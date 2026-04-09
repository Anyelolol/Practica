import tkinter as tk
from tkinter import *
from tkinter import ttk

from PIL import Image, ImageTk
import imutils
import cv2
import numpy as np

ventana = tk.Tk()
ventana.title("UFo_to")
ventana.resizable(0, 0)
ventana.geometry("1320x630")
ventana.config(bg="#1e1e1e")

tracking_activo = False
capture = None
frame_actual = None
drawing = False
ix, iy = -1, -1
fx, fy = -1, -1
zoom_original = None
Captura = None
ImgRec = None
ImgRecGray = None
thresh1 = None
camera_active = False
modo_zoom = "color"
mascara_rgb_actual = None
click_x = None
click_y = None

def camara():
    global Captura, camera_active
    Captura = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not Captura.isOpened():
        Captura = cv2.VideoCapture(0)
    if Captura.isOpened():
        camera_active = True
        iniciar()


def iniciar():
    global Captura, camera_active, frame_global
    if Captura is not None and Captura.isOpened() and camera_active:
        BCapturar.place(x=215, y=305, width=91, height=23)
        BCapturar.config(state='active')
        BCamara.config(state='disabled')
        ret, frame = Captura.read()
        frame_global = frame.copy()
        if ret == True:
            frame = imutils.resize(frame, width=241)
            ImagenCamara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(ImagenCamara)
            img = ImageTk.PhotoImage(image=im)
            LImagen.config(image=img)
            LImagen.image = img
            LImagen.after(10, iniciar)
        else:
            LImagen.after(100, iniciar)
    if ImgRec is not None:
        info_figuras()

def Capturar():
    global Captura, CapturaG, frame_actual, CapturaRGB, LImagenRecorte, zoom_original, ImgRec, ImgRecGray
    if Captura is None or not Captura.isOpened():
        return
    return_value, image = Captura.read()
    if not return_value or image is None:
        return
    frame = imutils.resize(image, width=301)
    frame = imutils.resize(frame, width=221)
    CapturaG = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame_actual = CapturaG
    CapturaRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(CapturaRGB)
    img = ImageTk.PhotoImage(image=im)
    imG = Image.fromarray(CapturaG)
    imgG = ImageTk.PhotoImage(image=imG)
    GImagenROI.config(image=imgG)
    GImagenROI.image = imgG
    LImagenRecorte.config(image=img)
    LImagenRecorte.image = img
    zoom_original = None
    ImgRec = None
    ImgRecGray = None
    actualizar_zoom()


def rgb():
    global img_aux, bin_imagen, img_mask, ImgRec, mascara_rgb_actual, modo_zoom
    if ImgRec is None or ImgRec.size == 0:
        CajaTexto2.config(state="normal")
        CajaTexto2.delete(1.0, tk.END)
        CajaTexto2.config(state="disabled")
        return
    minimos = (int(SRedI.get()), int(SGreenI.get()), int(SBlueI.get()))
    maximos = (int(SRedD.get()), int(SGreenD.get()), int(SBlueD.get()))
    if len(ImgRec.shape) == 2:
        img_rgb = cv2.cvtColor(ImgRec, cv2.COLOR_GRAY2RGB)
    else:
        img_rgb = ImgRec.copy()
    img_mask = cv2.inRange(img_rgb, minimos, maximos)
    img_aux = img_mask.copy()
    resultado = img_rgb.copy()
    resultado[img_mask == 255] = [0, 0, 255]
    mascara_rgb_actual = resultado
    modo_zoom = "mascara_rgb"
    actualizar_zoom()
    img_mask_pil = Image.fromarray(img_mask)
    img_mask_tk = ImageTk.PhotoImage(image=img_mask_pil)
    LImagenManchas.config(image=img_mask_tk)
    LImagenManchas.image = img_mask_tk
    _, bin_imagen = cv2.threshold(img_mask, 0, 255, cv2.THRESH_BINARY_INV)
    CajaTexto2.config(state="normal")
    CajaTexto2.delete(1.0, tk.END)
    CajaTexto2.config(state="disabled")


def manchas():
    global bin_imagen, img_aux

    if bin_imagen is None:
        CajaTexto2.config(state="normal")
        CajaTexto2.delete(1.0, tk.END)
        CajaTexto2.config(state="disabled")
        return

    total_pixeles = bin_imagen.size
    pixeles_blancos = cv2.countNonZero(bin_imagen)

    porcentaje_area_negras = (pixeles_blancos / total_pixeles) * 100
    porcentaje_area_blancas = 100 - porcentaje_area_negras
    contornos_blancos, _ = cv2.findContours(bin_imagen, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    numero_manchas_blancas = len(contornos_blancos)
    imagen_invertida = cv2.bitwise_not(bin_imagen)
    contornos_negras, _ = cv2.findContours(imagen_invertida, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    numero_manchas_negras = len(contornos_negras)

    Cadena = (
        f"Área con manchas negras: {round(porcentaje_area_negras, 2)}%\n"
        f"Área sin manchas: {round(porcentaje_area_blancas, 2)}%\n"
        f"Manchas negras: {numero_manchas_blancas}, blancas: {numero_manchas_negras}"
    )

    CajaTexto2.config(state="normal")
    CajaTexto2.delete(1.0, tk.END)
    CajaTexto2.insert(1.0, Cadena)
    CajaTexto2.config(state="disabled")

def umbralizacion():
    global thresh1, ImgRecGray
    if ImgRecGray is None or ImgRecGray.size == 0:
        CajaTexto.config(state="normal")
        CajaTexto.delete(1.0, tk.END)
        CajaTexto.config(state="disabled")
        return
    valor = int(numeroUmbra.get())
    ret, thresh1 = cv2.threshold(ImgRecGray, valor, 255, cv2.THRESH_BINARY)
    Umbral = Image.fromarray(thresh1)
    Umbral = ImageTk.PhotoImage(image=Umbral)
    UImagen.configure(image=Umbral)
    UImagen.image = Umbral
    actualizar_zoom()
    CajaTexto.config(state="normal")
    CajaTexto.delete(1.0, tk.END)
    CajaTexto.config(state="disabled")


def manchasG():
    global thresh1

    if thresh1 is None or thresh1.size == 0:
        CajaTexto.config(state="normal")
        CajaTexto.delete(1.0, tk.END)
        CajaTexto.config(state="disabled")
        return

    total_pixeles = thresh1.size
    pixeles_blancos = cv2.countNonZero(thresh1)

    porcentaje_area_blancas = (pixeles_blancos / total_pixeles) * 100
    porcentaje_area_negras = 100 - porcentaje_area_blancas
    contornos_blancos, _ = cv2.findContours(thresh1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    numero_manchas_blancas = len(contornos_blancos)
    imagen_invertida = cv2.bitwise_not(thresh1)
    contornos_negras, _ = cv2.findContours(imagen_invertida, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    numero_manchas_negras = len(contornos_negras)

    Cadena = (
        f"Área con manchas negras: {round(porcentaje_area_negras, 2)}%\n"
        f"Área sin manchas: {round(porcentaje_area_blancas, 2)}%\n"
        f"Manchas blancas: {numero_manchas_blancas}, negras: {numero_manchas_negras}"
    )

    CajaTexto.config(state="normal")
    CajaTexto.delete(1.0, tk.END)
    CajaTexto.insert(1.0, Cadena)
    CajaTexto.config(state="disabled")

def click_mouse(event):
    global ix, iy, drawing
    drawing = True
    ix, iy = event.x, event.y
    Coordenadas['text'] = f'x = {event.x}, y = {event.y}'


def mover_mouse(event):
    global fx, fy
    if drawing:
        fx, fy = event.x, event.y
        Coordenadas['text'] = f'x = {event.x}, y = {event.y}'


def soltar_mouse(event):
    global Roi_1, drawing, fx, fy, frame_actual, ImgRec, ImgRecGray
    global zoom_original, CapturaG, CapturaRGB, modo_zoom

    drawing = False
    fx, fy = event.x, event.y

    if frame_actual is None or CapturaG is None or CapturaRGB is None:
        return

    label_w = LImagenRecorte.winfo_width()
    label_h = LImagenRecorte.winfo_height()

    img_w_display = LImagenRecorte.image.width()
    img_h_display = LImagenRecorte.image.height()

    offset_x = (label_w - img_w_display) // 2
    offset_y = (label_h - img_h_display) // 2

    x1 = ix - offset_x
    y1 = iy - offset_y
    x2 = fx - offset_x
    y2 = fy - offset_y

    x1 = max(0, min(x1, img_w_display))
    x2 = max(0, min(x2, img_w_display))
    y1 = max(0, min(y1, img_h_display))
    y2 = max(0, min(y2, img_h_display))

    x1, x2 = sorted([x1, x2])
    y1, y2 = sorted([y1, y2])

    if x1 == x2 or y1 == y2:
        return

    scale_x = frame_actual.shape[1] / img_w_display
    scale_y = frame_actual.shape[0] / img_h_display

    x1 = int(x1 * scale_x)
    x2 = int(x2 * scale_x)
    y1 = int(y1 * scale_y)
    y2 = int(y2 * scale_y)

    ImgRecGray = frame_actual[y1:y2, x1:x2]
    ImgRec = CapturaRGB[y1:y2, x1:x2]

    if ImgRecGray.size == 0:
        return

    ImG = Image.fromarray(ImgRecGray)
    ImgG = ImageTk.PhotoImage(image=ImG)
    GImagenROI.configure(image=ImgG)
    GImagenROI.image = ImgG

    if ImgRec.size != 0:
        Im = Image.fromarray(ImgRec)
        ImRec = ImageTk.PhotoImage(image=Im)
        LImagenROI.config(image=ImRec)
        LImagenROI.image = ImRec

        zoom_original = ImgRec.copy()
        modo_zoom = "color"
        actualizar_zoom()


def click_pixel_zoom(event):
    global zoom_original, modo_zoom

    if zoom_original is None or zoom_original.size == 0:
        return

    if modo_zoom != "color":
        return

    label_w = LImagenZoom.winfo_width()
    label_h = LImagenZoom.winfo_height()

    img_w_display = LImagenZoom.image.width()
    img_h_display = LImagenZoom.image.height()

    offset_x = (label_w - img_w_display) // 2
    offset_y = (label_h - img_h_display) // 2

    x = event.x - offset_x
    y = event.y - offset_y

    x = max(0, min(x, img_w_display - 1))
    y = max(0, min(y, img_h_display - 1))

    height, width = zoom_original.shape[:2]
    scale_x = width / img_w_display
    scale_y = height / img_h_display

    orig_x = int(x * scale_x)
    orig_y = int(y * scale_y)

    orig_x = max(0, min(orig_x, width - 1))
    orig_y = max(0, min(orig_y, height - 1))

    if len(zoom_original.shape) == 3:
        pixel_color = zoom_original[orig_y, orig_x]
        r, g, b = int(pixel_color[0]), int(pixel_color[1]), int(pixel_color[2])
    else:
        val = int(zoom_original[orig_y, orig_x])
        r = g = b = val

    rango = 35
    r_min = max(0, r - rango)
    r_max = min(255, r + rango)
    g_min = max(0, g - rango)
    g_max = min(255, g + rango)
    b_min = max(0, b - rango)
    b_max = min(255, b + rango)
    SRedI.set(r_min)
    SRedD.set(r_max)
    SGreenI.set(g_min)
    SGreenD.set(g_max)
    SBlueI.set(b_min)
    SBlueD.set(b_max)
    Coordenadas['text'] = f'x={orig_x}, y={orig_y} | RGB=({r},{g},{b})'

    rgb()

def info_figuras():
    global frame_global, click_x, click_y

    if frame_global is None:
        return

    frame = imutils.resize(frame_global, width=300)
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    minimos = (int(SRedI.get()), int(SGreenI.get()), int(SBlueI.get()))
    maximos = (int(SRedD.get()), int(SGreenD.get()), int(SBlueD.get()))

    mask = cv2.inRange(img, minimos, maximos)

    kernel = np.ones((3,3), np.uint8)
    mask = cv2.erode(mask, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=2)

    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contornos) == 0:

        if tracking_activo:
            return
        else:
            im = Image.fromarray(img)
            imgtk = ImageTk.PhotoImage(image=im)
            LImagenResultado.config(image=imgtk)
            LImagenResultado.image = imgtk

            Coordenadas['text'] = "Sin detección"
            return

    img_dibujar = img.copy()

    contorno_seleccionado = max(contornos, key=cv2.contourArea)

    x, y, w, h = cv2.boundingRect(contorno_seleccionado)
    area = cv2.contourArea(contorno_seleccionado)

    cx = int(x + w / 2)
    cy = int(y + h / 2)

    cv2.rectangle(img_dibujar, (x, y), (x+w, y+h), (0,0,255), 2)
    cv2.circle(img_dibujar, (cx, cy), 5, (0,255,0), -1)

    im = Image.fromarray(img_dibujar)
    imgtk = ImageTk.PhotoImage(image=im)

    LImagenResultado.config(image=imgtk)
    LImagenResultado.image = imgtk

    texto = (
        f"Área: {round(area,2)} px\n"
        f"Centro: ({cx},{cy})"
    )

    CajaTexto3.config(state="normal")
    CajaTexto3.delete(1.0, tk.END)
    CajaTexto3.insert(1.0, texto)
    CajaTexto3.config(state="disabled")


def actualizar_zoom():
    global zoom_original, modo_zoom, mascara_rgb_actual, thresh1, ImgRec
    if modo_zoom == "color" and ImgRec is not None:
        imagen_a_mostrar = ImgRec
    elif modo_zoom == "mascara_rgb" and mascara_rgb_actual is not None:
        imagen_a_mostrar = mascara_rgb_actual
    elif modo_zoom == "umbral" and thresh1 is not None:
        imagen_a_mostrar = thresh1
    else:
        return
    if imagen_a_mostrar is None or imagen_a_mostrar.size == 0:
        return
    height, width = imagen_a_mostrar.shape[:2]
    new_height = int(height * 2.5)
    new_width = int(width * 2.5)
    if len(imagen_a_mostrar.shape) == 3:
        zoomed = cv2.resize(imagen_a_mostrar, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        if zoomed.shape[2] == 3:
            zoomed_rgb = zoomed
        else:
            zoomed_rgb = cv2.cvtColor(zoomed, cv2.COLOR_BGR2RGB)
    else:
        zoomed = cv2.resize(imagen_a_mostrar, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        zoomed_rgb = cv2.cvtColor(zoomed, cv2.COLOR_GRAY2RGB)
    zoomed_pil = Image.fromarray(zoomed_rgb)
    zoomed_pil.thumbnail((950, 200), Image.Resampling.LANCZOS)
    zoomed_tk = ImageTk.PhotoImage(image=zoomed_pil)
    LImagenZoom.config(image=zoomed_tk)
    LImagenZoom.image = zoomed_tk


def resetear_vista():
    global modo_zoom
    modo_zoom = "color"
    actualizar_zoom()


def cerrar_camara():
    global Captura, camera_active
    camera_active = False
    if Captura is not None:
        Captura.release()
    ventana.quit()
    ventana.destroy()

def toggle_tracking():
    global tracking_activo

    tracking_activo = not tracking_activo

    if tracking_activo:
        BToggle.config(bg="white", fg="black", text="ON")
    else:
        BToggle.config(bg="#3e3e3e", fg="white", text="OFF")

BToggle = tk.Button(ventana, text="OFF", command=toggle_tracking, bg="#3e3e3e", fg="white")
BToggle.place(x=480, y=570, width=40, height=23)

logo = tk.PhotoImage(file="logoUBB.png")
LogoUBB = ttk.Label(image=logo)
LogoUBB.place(x=5, y=5)

fondo1 = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
fondo1.place(x=5, y=100, width=1310, height=200)
fondo2 = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
fondo2.place(x=5, y=365, width=1310, height=200)

LImagen = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagen.place(x=5, y=100, width=300, height=200)

LImagenRecorte = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenRecorte.place(x=335, y=100, width=300, height=200)

GImagenROI = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
GImagenROI.place(x=690, y=100, width=300, height=200)

LImagenROI = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenROI.config(state="disabled")

UImagen = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
UImagen.place(x=1000, y=100, width=300, height=200)

LImagenZoom = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenZoom.place(x=335, y=365, width=300, height=200)

LImagenManchas = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenManchas.place(x=690, y=365, width=301, height=200)

LImagenResultado = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenResultado.place(x=1000, y=365, width=300, height=200)

LRed = tk.Label(ventana, text="R")
LRed.place(x=153, y=400, width=21, height=16)
LGreen = tk.Label(ventana, text="G")
LGreen.place(x=153, y=430, width=21, height=16)
LBlue = tk.Label(ventana, text="B")
LBlue.place(x=153, y=460, width=21, height=16)

SRedI = tk.Scale(ventana, from_=0, to=255, orient='horizontal', bg="#3e3e3e", fg="white")
SRedI.place(x=15, y=390)
SRedD = tk.Scale(ventana, from_=0, to=255, orient='horizontal', bg="#3e3e3e", fg="white")
SRedD.set(255)
SRedD.place(x=210, y=390)

SGreenI = tk.Scale(ventana, from_=0, to=255, orient='horizontal', bg="#3e3e3e", fg="white")
SGreenI.place(x=15, y=430)
SGreenD = tk.Scale(ventana, from_=0, to=255, orient='horizontal', bg="#3e3e3e", fg="white")
SGreenD.set(255)
SGreenD.place(x=210, y=430)

SBlueI = tk.Scale(ventana, from_=0, to=255, orient='horizontal', bg="#3e3e3e", fg="white")
SBlueI.place(x=15, y=470)
SBlueD = tk.Scale(ventana, from_=0, to=255, orient='horizontal', bg="#3e3e3e", fg="white")
SBlueD.set(255)
SBlueD.place(x=210, y=470)

LImagenRecorte.bind("<Button-1>", click_mouse)
LImagenRecorte.bind("<B1-Motion>", mover_mouse)
LImagenRecorte.bind("<ButtonRelease-1>", soltar_mouse)
LImagenZoom.bind("<Button-1>", click_pixel_zoom)

CajaTexto = tk.Text(ventana, state="disabled", height=3, width=40)
CajaTexto.place(x=1000, y=305, width=315, height=50)

CajaTexto2 = tk.Text(ventana, state="disabled", height=3, width=30)
CajaTexto2.place(x=680, y=570, width=315, height=50)

CajaTexto3 = tk.Text(ventana, state="disabled", height=3, width=30)
CajaTexto3.place(x=1000, y=570, width=315, height=50)


BCamara = tk.Button(ventana, text="On", command=camara)
BCamara.place(x=5, y=305, width=90, height=23)
BCapturar = tk.Button(ventana, text="Capturar", command=Capturar, bg="#2e2e2e", fg="white")
BCapturar.config(state='disabled')

Coordenadas = tk.Label(ventana, text="", bg="#1e1e1e", fg="white")
Coordenadas.place(x=440, y=305)

LabelCoordenadasFig = tk.Label(ventana, text="", bg="#1e1e1e", fg="white")
LabelCoordenadasFig.place(x=610, y=600)


BBinary = tk.Button(ventana, text="RGB_G", command=umbralizacion, bg="#3e3e3e", fg="white")
BBinary.place(x=665, y=305, width=90, height=23)

numeroUmbra = tk.Spinbox(ventana, from_=0, to=255)
numeroUmbra.place(x=760, y=305, width=42, height=22)
numeroUmbra.delete(0, tk.END)
numeroUmbra.insert(0, "128")

BManchasG = tk.Button(ventana, text="Manchas_G", command=manchasG, bg="#3e3e3e", fg="white")
BManchasG.place(x=865, y=305, width=131, height=23)

BManchas = tk.Button(ventana, text="RGB", command=rgb, bg="#3e3e3e", fg="white")
BManchas.place(x=50, y=530, width=100, height=23)

ManchasRGB = tk.Button(ventana, text="Manchas", command=manchas, bg="#3e3e3e", fg="white")
ManchasRGB.place(x=555, y=570, width=120, height=23)

btn_reset = tk.Button(ventana, text="Reset_RGB", command=resetear_vista, bg="#3e3e3e", fg="white")
btn_reset.place(x=180, y=530, width=100, height=23)

ventana.protocol("WM_DELETE_WINDOW", cerrar_camara)

ventana.mainloop()
