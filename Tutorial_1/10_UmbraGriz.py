import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
import imutils
import cv2

ventana = tk.Tk()
ventana.title("UFo_to")
ventana.resizable(0, 0)
ventana.geometry("1070x450")


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



def Urgb():
    global imagen_camara
    valor = int(numUmbra.get())
    gray = cv2.cvtColor(imagen_camara, cv2.COLOR_RGB2GRAY)
    ret, thresh1 = cv2.threshold(gray, valor, 255, cv2.THRESH_BINARY)
    umbral = Image.fromarray(thresh1)
    umbral = ImageTk.PhotoImage(image=umbral)
    ImgUmbra.config(image=umbral)
    ImgUmbra.image = umbral

numUmbra = tk.Spinbox(ventana, from_=0,to=255)
numUmbra.place(x=800, y=331, width=42, height=23)

BCamara = tk.Button(ventana, text="On", command=camara)
BCamara.place(x=80, y=330, width=90, height=23)
BCapturar = tk.Button(ventana, text="Capturar", command=Capturar)
BCapturar.place(x=220, y=330, width=91, height=23)
Umbra = tk.Button(ventana, text="RGB", command=Urgb)
Umbra.place(x=840, y=420, width=80, height=23)

LImagen = tk.Label(ventana, background="white")
LImagen.place(x=50, y=50, width=300, height=240)
LImagenROI = tk.Label(ventana, background="white")
LImagenROI.place(x=390, y=50, width=300, height=240)
ImgUmbra = tk.Label(ventana, background="white")
ImgUmbra.place(x=730, y=50, width=300, height=240)


ventana.mainloop()
