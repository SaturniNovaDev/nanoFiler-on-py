import tkinter as tk, PIL as pillow, os, sys, string
from tkinter import Label
from PIL import Image, ImageTk
from appinfo import version
from ctypes import windll

# Setup Basic Window
root = tk.Tk()
root.title("NanoFiler" + version)
root.geometry("900x700")
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(0, weight=1)
label = Label(root, text="Hello, NanoFiler!")
label.grid(column=0, row=0)
windll.shcore.SetProcessDpiAwareness(1)

# BACKGROUND CODE LOGIC ---------


# Helper functions ------
def get_windows_drives():
    """Returns a list of mounted Windows drive letters (e.g., ['C:\\', 'D:\\'])."""
    drives = []
    # Iterate through 'C', 'D', 'E', etc.
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        # Check if the path exists and is a mount point
        if os.path.exists(drive_path) and os.path.ismount(drive_path):
            drives.append(drive_path)
    return drives


def get_folder_contents(path):
    """
    Returns lists of subdirectories and files within a given path.
    """
    subdirectories = []
    files = []
    try:
        # List all entries (files and folders)
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            # Use os.path.isdir/isfile to classify entries
            if os.path.isdir(full_path):
                subdirectories.append(entry)
            elif os.path.isfile(full_path):
                files.append(entry)

        # Sort directories first, then files
        subdirectories.sort()
        files.sort()

    except PermissionError:
        # Handle cases like "Access Denied" for system folders
        print(f"Permission denied for: {path}")
    except FileNotFoundError:
        print(f"Path not found: {path}")

    return subdirectories, files


# FRONTEND GUI BUILDING ---------

# Navigation Frame (Fixed width)
nav_frame = tk.Frame(root, width=150, bg="#EAEAEA")
nav_frame.grid(row=0, column=0, sticky="ns")  # Sticks North-South

# Content view Frame (Expands)
content_frame = tk.Frame(root, bg="#FFFFFF")
content_frame.grid(row=0, column=1, sticky="nsew")  # Sticks everywhere, fills column 1

# Configure the column where the content frame is placed to expand
root.grid_columnconfigure(1, weight=3)

# Configure the content frame itself to be responsive
content_frame.grid_columnconfigure(0, weight=1)
content_frame.grid_rowconfigure(0, weight=1)
content_frame.grid_rowconfigure(1, weight=0)

# Tree Viewer (Folder structure on the left of content frame)
tree_frame = tk.Frame(content_frame)
tree_frame.grid(row=0, column=0, sticky="nsew")

# Status Bar (at the bottom, fixed height)
status_bar = tk.Label(
    content_frame, text="Ready | 0 Items Selected", bd=1, relief=tk.SUNKEN, anchor="w"
)
status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")  # Spans across all columns


root.mainloop()
