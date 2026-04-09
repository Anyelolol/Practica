import tkinter as tk
from tkinter import *
from tkinter import ttk

from PIL import Image, ImageTk
import imutils
import cv2

ventana = tk.Tk()
ventana.title("UFo_to")
ventana.resizable(0, 0)
ventana.geometry("1320x800")


def camara():
    global Captura
    Captura = cv2.VideoCapture(0)
    iniciar()


def iniciar():
    global Captura
    if Captura is not None:
        BCapturar.place(x=250,y=330,width=91,height=23)
        ret, frame = Captura.read()
        if ret == True:
            frame = imutils.resize(frame, width=241)
            ImagenCamara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(ImagenCamara)
            img = ImageTk.PhotoImage(image=im)
            LImagen.config(image=img)
            LImagen.image = img
            LImagen.after(10, iniciar)
        else:
            LImagen.image = ""
            Captura.release()

def Capturar():
    global valor, Captura, CapturaG, frame_actual, CapturaRGB
    camara = Captura
    return_value, image = camara.read()
    frame = imutils.resize(image, width=301)
    frame = imutils.resize(frame, width=221)
    frame_actual = frame.copy()
    CapturaG = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    CapturaRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(CapturaRGB)
    img = ImageTk.PhotoImage(image=im)
    imG = Image.fromarray(CapturaG)
    imgG = ImageTk.PhotoImage(image=imG)
    GImagenROI.config(image=imgG)
    GImagenROI.image = imgG
    LImagenRecorte.config(image=img)
    LImagenRecorte.image = img


def rgb():
    global img_aux, bin_imagen, img_mask
    minimos = (int(SRedI.get()), int(SGreenI.get()), int(SBlueI.get()))
    maximos = (int(SRedD.get()), int(SGreenD.get()), int(SBlueD.get()))
    img_mask = cv2.inRange(ImgRec, minimos, maximos)
    img_aux = img_mask.copy()
    img_mask_pil = Image.fromarray(img_mask)
    img_mask_tk = ImageTk.PhotoImage(image=img_mask_pil)
    LImagenManchas.config(image=img_mask_tk)
    LImagenManchas.image = img_mask_tk
    _, bin_imagen = cv2.threshold(img_mask, 0, 255, cv2.THRESH_BINARY_INV)


def manchas():
    global bin_imagen, img_aux
    total_pixeles = bin_imagen.size
    pixeles_blancos = cv2.countNonZero(bin_imagen)
    porcentaje_area_negras = (pixeles_blancos / total_pixeles) * 100
    porcentaje_area_blancas = 100 - porcentaje_area_negras
    contornos, _ = cv2.findContours(img_aux, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    numero_manchas = len(contornos)
    Cadena = (f"Área con manchas: {round(porcentaje_area_negras, 2)}%\n"
              f"Área sin manchas: {round(porcentaje_area_blancas, 2)}%\n"
              f"Número de manchas: {numero_manchas}")

    CajaTexto2.config(state="normal")
    CajaTexto2.delete(1.0, tk.END)
    CajaTexto2.insert(1.0, Cadena)
    CajaTexto2.config(state="disabled")

def umbralizacion():
    global thresh1, mask
    valor = int(numeroUmbra.get())
    ret, thresh1 = cv2.threshold(CapturaG, valor, 255, cv2.THRESH_BINARY)
    Umbral = Image.fromarray(thresh1)
    Umbral = ImageTk.PhotoImage(image=Umbral)
    UImagen.configure(image = Umbral)
    UImagen.image = Umbral

    min = (valor, valor, valor)
    max = (255, 255, 255)
    mask = cv2.inRange(Captura, min, max)


def manchasG():
    global thresh1
    total_pixeles = thresh1.size
    pixeles_blancos = cv2.countNonZero(thresh1)
    porcentaje_area_blancas = (pixeles_blancos / total_pixeles) * 100
    porcentaje_area_negras = 100 - porcentaje_area_blancas
    contornos = cv2.findContours(thresh1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    numero_manchas = len(contornos)
    Cadena = (f"Área con manchas: {round(porcentaje_area_negras, 2)}%\n"
              f"Área sin manchas: {round(porcentaje_area_blancas, 2)}%\n"
              f"Número de manchas: {numero_manchas}")
    CajaTexto.configure(state="normal")
    CajaTexto.delete(1.0, tk.END)
    CajaTexto.insert(1.0, Cadena)
    CajaTexto.configure(state="disabled")

def mostrar_coordenadas(event):
    coordenadas['text']=f'x={event.x}, y={event.y}'

def recortar():
    global ImgRec
    Vx1 = int(x1.get())
    Vy1 = int(y1.get())
    Vx2 = int(x2.get())
    Vy2 = int(y2.get())
    ImgRec = frame_actual[Vy1:Vy2, Vx1:Vx2]
    Im = Image.fromarray(ImgRec)
    ImRec = ImageTk.PhotoImage(image=Im)
    LImagenROI.config(image=ImRec)
    LImagenROI.image = ImRec

BCamara = tk.Button(ventana, text="On", command=camara)
BCamara.place(x=60, y=330, width=90, height=23)
BCapturar = tk.Button(ventana, text="Capturar", command=Capturar)
BCapturar.place(x=250, y=330, width=91, height=23)
BManchas = tk.Button(ventana, text="RGB", command=rgb)
BManchas.place(x=760, y=640, width=100, height=23)
ManchasRGB = tk.Button(ventana, text="Manchas", command=manchas)
ManchasRGB.place(x=880, y=640, width=120, height=23)
BBinary = tk.Button(ventana, text="RGB_G", command=umbralizacion)
BBinary.place(x=800, y=310, width=90, height=23)
BManchasG = tk.Button(ventana, text="Manchas_G", command=manchasG)
BManchasG.place(x=1100, y=310, width=131, height=23)
BRecortar = tk.Button(ventana, text="Recortar", command=recortar)
BRecortar.place(x=155, y=700, width=80, height=23)

numeroUmbra = tk.Spinbox(ventana, from_=0,to=255)
numeroUmbra.place(x=900, y=310, width=42, height=22)
x1 = tk.Spinbox(ventana, from_=0,to=298)
x1.place(x=140, y=630, width=42, height=22)
y1 = tk.Spinbox(ventana, from_=0,to=239)
y1.place(x=240, y=630, width=42, height=22)
x2 = tk.Spinbox(ventana, from_=1,to=298)
x2.place(x=140, y=660, width=42, height=22)
y2 = tk.Spinbox(ventana, from_=1,to=239)
y2.place(x=240, y=660, width=42, height=22)

LRed = tk.Label(ventana, text="R")
LRed.place(x=530, y=640, width=21, height=16)
LGreen = tk.Label(ventana, text="G")
LGreen.place(x=530, y=680, width=21, height=16)
LBlue = tk.Label(ventana, text="B")
LBlue.place(x=530, y=720, width=21, height=16)

coordenadeasTitulo = tk.Label(ventana, text="Coordenadas")
coordenadeasTitulo.place(x=505, y=310)
coordenadas = tk.Label(ventana, text="")
coordenadas.place(x=495, y=330)

Lx1 = tk.Label(ventana, text="X1")
Lx1.place(x=120, y=630)
Ly1 = tk.Label(ventana, text="Y1")
Ly1.place(x=220, y=630)
Lx2 = tk.Label(ventana, text="X2")
Lx2.place(x=120, y=660)
Ly2 = tk.Label(ventana, text="Y2")
Ly2.place(x=220, y=660)

logo = tk.PhotoImage(file="logoUBB.png")
LogoUBB = ttk.Label(image=logo)
LogoUBB.place(x=1250, y =615)

LImagen = tk.Label(ventana, background="white")
LImagen.place(x=50, y=50, width=300, height=240)

LImagenROI = tk.Label(ventana, background="white")
LImagenROI.place(x=390, y=380, width=300, height=240)

GImagenROI = tk.Label(ventana, background="white")
GImagenROI.place(x=390, y=50, width=300, height=240)

UImagen = tk.Label(ventana, background="white")
UImagen.place(x=730, y=50, width=301, height=240)

LImagenManchas = tk.Label(ventana, background="white")
LImagenManchas.place(x=730, y=380, width=301, height=240)

LImagenRecorte = tk.Label(ventana, background="white")
LImagenRecorte.place(x=50,y=380, width=301, height=240)

CajaTexto = tk.Text(ventana, state="disabled")
CajaTexto.place(x=1055, y=50, width=225, height=220)
CajaTexto2 = tk.Text(ventana, state="disabled")
CajaTexto2.place(x=1055, y=380, width=225, height=220)

SRedI = tk.Scale(ventana, from_=1, to=255, orient='horizontal')
SRedI.place(x=400, y=620)
SRedD = tk.Scale(ventana, from_=1, to=255, orient='horizontal')
SRedD.set(255)
SRedD.place(x=580, y=620)

SGreenI = tk.Scale(ventana, from_=1, to=255, orient='horizontal')
SGreenI.place(x=400, y=660)
SGreenD = tk.Scale(ventana, from_=1, to=255, orient='horizontal')
SGreenD.set(255)
SGreenD.place(x=580, y=660)

SBlueI = tk.Scale(ventana, from_=1, to=255, orient='horizontal')
SBlueI.place(x=400, y=700)
SBlueD = tk.Scale(ventana, from_=1, to=255, orient='horizontal')
SBlueD.set(255)
SBlueD.place(x=580, y=700)

ventana.mainloop()
