import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
import imutils
import cv2

ventana = tk.Tk()
ventana.title("UFo_to")
ventana.resizable(0, 0)
ventana.geometry("1320x450")


def camara():
    global captura
    captura = cv2.VideoCapture(0)
    iniciar()


def iniciar():
    global captura
    if captura is not None:
        ret, frame = captura.read()
        if ret == True:
            frame = imutils.resize(frame, width=311)
            frame = imutils.resize(frame, width=241)
            imagen_camara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(imagen_camara)
            img = ImageTk.PhotoImage(image=im)
            LImagen.configure(image=img)
            LImagen.image = img
            LImagen.after(1, iniciar)
        else:
            LImagen.image = ""
            captura.release()


def Capturar():
    global captura, imagen_camara
    camara = captura
    return_value, image = camara.read()
    frame = imutils.resize(image, width=301)
    frame = imutils.resize(frame, width=221)
    imagen_camara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(imagen_camara)
    img = ImageTk.PhotoImage(image=im)
    LImagenROI.config(image=img)
    LImagenROI.image = img


def rgb():
    global imagen_camara, img_mask, bin_imagen

    frame = cv2.cvtColor(imagen_camara, cv2.COLOR_RGB2BGR)
    min = (int(SBlueI.get()), int(SGreenI.get()), int(SRedI.get()))
    max = (int(SBlueD.get()), int(SGreenD.get()), int(SRedD.get()))
    img_mask = cv2.inRange(frame, min, max)
    img_mask = Image.fromarray(img_mask)
    img_mask = ImageTk.PhotoImage(image=img_mask)
    ImgUmbra.configure(image=img_mask)
    ImgUmbra.image = img_mask
    bin_imagen = cv2.threshold(img_mask, 0, 255, cv2.THRESH_BINARY_INV)

def manchas():
    global img_mask, bin_imagen, img_aux
    num_pix = cv2.countNonZero( bin_imagen)
    porcentaje_manchas = 100 - (num_pix /  bin_imagen.size) * 100
    contornos, _ = cv2.findContours(img_aux, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
    num_formas = len(contornos)
    Cadena = f"Objetos: {num_formas}\n% negro: {round(porcentaje_manchas,2)}%"
    CajaT.config(state='normal')
    CajaT.insert('end')
    CajaT.insert('end', Cadena)
    CajaT.configure(state="disabled")

SRedI = tk.Scale(ventana, from_=0, to=255, orient='horizontal')
SRedI.place(x=760, y=300)
SRedD = tk.Scale(ventana, from_=0, to=255, orient='horizontal')
SRedD.set(255)
SRedD.place(x=900, y=300)
LRed = tk.Label(ventana, text="R")
LRed.place(x=870, y=320)


SGreenI = tk.Scale(ventana, from_=0, to=255, orient='horizontal')
SGreenI.place(x=760, y=340)
SGreenD = tk.Scale(ventana, from_=0, to=255, orient='horizontal')
SGreenD.set(255)
SGreenD.place(x=900, y=340)
LGreen = tk.Label(ventana, text="G")
LGreen.place(x=870, y=360)

SBlueI = tk.Scale(ventana, from_=0, to=255, orient='horizontal')
SBlueI.place(x=760, y=380)
SBlueD = tk.Scale(ventana, from_=0, to=255, orient='horizontal')
SBlueD.set(255)
SBlueD.place(x=900, y=380)
LBlue = tk.Label(ventana, text="B")
LBlue.place(x=870, y=400)

BCamara = tk.Button(ventana, text="On", command=camara)
BCamara.place(x=80, y=330, width=90, height=23)
BCapturar = tk.Button(ventana, text="Capturar", command=Capturar)
BCapturar.place(x=220, y=330, width=91, height=23)
Umbra = tk.Button(ventana, text="RGB", command=rgb)
Umbra.place(x=840, y=420, width=80, height=23)
Manchas = tk.Button(ventana, text="Manchas", command=manchas)
Manchas.place(x=1120, y=330, width=120, height=23)

LImagen = tk.Label(ventana, background="white")
LImagen.place(x=50, y=50, width=300, height=240)
LImagenROI = tk.Label(ventana, background="white")
LImagenROI.place(x=390, y=50, width=300, height=240)
ImgUmbra = tk.Label(ventana, background="white")
ImgUmbra.place(x=730, y=50, width=300, height=240)

CajaT = tk.Text(ventana, state="disabled")
CajaT.place(x=1055, y=50, width=225, height=220)

ventana.mainloop()
