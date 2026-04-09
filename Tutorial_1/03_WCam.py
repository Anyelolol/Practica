import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
import imutils
import cv2

ventana = tk.Tk()
ventana.title("WCam")
ventana.geometry("400x370")
ventana.resizable(width=0, height=0)

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
            LImagen.after(1,camara)
        else:
            LImagen.image = ""
            captura.release()

BCamara = tk.Button(ventana, text="OnCamara", command=camara)
BCamara.place(x=150, y=330,width=90,height=23)

LImagen = tk.Label(ventana, background="white")
LImagen.place(x=50, y=50,width=300,height=240)
ventana.mainloop()
