import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
import imutils
import cv2

ventana = tk.Tk()
ventana.title("TFoto")
ventana.geometry("740x370")

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
            ImagenCamara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(ImagenCamara)
            img = ImageTk.PhotoImage(image=im)
            LImagen.configure(image= img)
            LImagen.image = img
            LImagen.after(1,iniciar)
        else:
            LImagen.image = ""
            captura.release()

def Capturar():
    global captura
    camara = captura
    return_value, image = camara.read()
    frame = imutils.resize(image, width=301)
    frame = imutils.resize(frame, width=221)
    captura = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    im = Image.fromarray(captura)
    img = ImageTk.PhotoImage(image= im)
    LImagenROI.config(image= img)
    LImagenROI.image = img

BCamara = tk.Button(ventana, text="On", command= camara)
BCamara.place(x=150, y=330, width=90, height=23)

BCapturar = tk.Button(ventana, text="Capturar", command=Capturar)
BCapturar.place(x=500, y=330, width=91, height=23)

LImagen = tk.Label(ventana, background="white")
LImagen.place(x=50, y=50, width=300, height=240)

LImagenROI = tk.Label(ventana, background="white")
LImagenROI.place(x=390, y=50, width=300, height=240)

ventana.mainloop()
