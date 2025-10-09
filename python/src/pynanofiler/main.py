import tkinter
from tkinter import Tk, Label
import PIL as pil
from PIL import Image, ImageTk
from appinfo import version
from ctypes import windll

root = Tk()
root.title("NanoFiler" + version)
root.geometry("900x700")
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(0, weight=1)
label = Label(root, text="Hello, NanoFiler!")
label.grid(column=0, row=0)
windll.shcore.SetProcessDpiAwareness(1)

root.mainloop()
