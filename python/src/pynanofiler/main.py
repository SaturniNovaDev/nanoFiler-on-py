"""Main module from nanoFiler in Python."""

from ctypes import windll
import tkinter as tk
import os
import string
import typing
from tkinter import messagebox as msgbox, ttk
from PIL import Image, ImageTk
from __init__ import __version__

root = tk.Tk()
root.title("NanoFiler" + __version__)
root.geometry("900x700")

root.grid_rowconfigure(0, weight=15)
root.grid_rowconfigure(1, weight=85)
root.grid_columnconfigure(0, weight=15)
root.grid_columnconfigure(1, weight=85)
windll.shcore.SetProcessDpiAwareness(1)


class File:
    """File representation with metadata, size, mimetype, and content.

    Mimetype is declared early to help with file handling decisions.
    For example, we cannot display images as text, so we need to know the mimetype
    before attempting to read the content.
    Content is loaded on demand for efficiency.
    """

    def __init__(
        self,
        path: str,
        metadata: dict[str, typing.Any],
        size: int,
        mimetype: str,
        content: str = "",  # Empty by default; load on demand
    ):
        self.path = path
        self.metadata = metadata
        self.size = size
        self.content = content
        self.mimetype = mimetype


class Dir:
    """Directory representation with metadata, subdirs, and files."""

    def __init__(
        self,
        path: str,
        metadata: dict[str, typing.Any],
        subdirs: dict[int, str],
        files: dict[int, File],
    ):
        self.path = path
        self.metadata = metadata
        self.subdirs = subdirs
        self.files = files


# --- Status Bar (simplified, removed unused indexing progress) ---
status_bar_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
status_bar_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
status_bar_frame.grid_propagate(False)

status_label = tk.Label(status_bar_frame, anchor="w", font=("Consolas", 11))
status_label.pack(side=tk.LEFT, padx=10, pady=2)


def update_status_bar():
    current_path = path_explorer_entry.get()
    status_text = f"Current Path: {current_path} | " f"Version: {__version__}"
    status_label.config(text=status_text)
    root.after(200, update_status_bar)


def get_mimetype(file_name: str) -> str:
    """Simple mimetype detection based on file extension."""
    extension = os.path.splitext(file_name)[1].lower()
    text_extensions = {
        ".txt",
        ".md",
        ".py",
        ".log",
        ".json",
        ".xml",
        ".csv",
        ".ini",
        ".css",
        ".html",
        ".js",
        ".yaml",
        ".yml",
        ".bat",
        ".cmd",
        ".sh",
        ".rtf",
    }
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"}

    if extension in text_extensions:
        return "text/plain"
    elif extension in image_extensions:
        return "image"
    else:
        return "unknown"


def get_dir_object(path: str) -> Dir:
    """Return a Dir object for the given path."""
    subdirs = {}
    files = {}
    metadata = {}
    try:
        with os.scandir(path) as it:
            subdir_idx = 0
            file_idx = 0
            for entry in it:
                if entry.is_dir():
                    subdirs[subdir_idx] = entry.name
                    subdir_idx += 1
                elif entry.is_file():
                    file_path = os.path.join(path, entry.name)
                    size = entry.stat().st_size
                    mimetype = get_mimetype(entry.name)
                    files[file_idx] = File(
                        path=file_path,
                        metadata={},
                        size=size,
                        mimetype=mimetype,
                        content="",
                    )
                    file_idx += 1
        metadata = {"count_subdirs": len(subdirs), "count_files": len(files)}
    except Exception as e:
        metadata = {"error": str(e)}
    return Dir(path=path, metadata=metadata, subdirs=subdirs, files=files)


def get_windows_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path) and os.path.ismount(drive_path):
            drives.append(drive_path)
    return drives


def populate_listbox_from_dir(dir_obj: Dir, listbox: tk.Listbox):
    """Populate the listbox with contents from a Dir object."""
    listbox.delete(0, tk.END)
    if dir_obj.metadata.get("error"):
        listbox.insert(tk.END, f"Error: {dir_obj.metadata['error']}")
        return
    if not dir_obj.subdirs and not dir_obj.files:
        listbox.insert(tk.END, "No accessible folders or files found.")
        return
    for idx, subdir in dir_obj.subdirs.items():
        listbox.insert(tk.END, f"[DIR] {subdir}")
    for idx, file_obj in dir_obj.files.items():
        listbox.insert(tk.END, f"[FILE] {os.path.basename(file_obj.path)}")


def on_drive_select(event):
    selected_indices = drives_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_drive = drives_listbox.get(selected_index)
    update_path_explorer(selected_drive)
    dir_obj = get_dir_object(selected_drive)
    subdirs_listbox.config(state=tk.NORMAL)
    populate_listbox_from_dir(dir_obj, subdirs_listbox)
    subdirs_listbox.config(state=tk.NORMAL)
    drives_listbox.config(state=tk.DISABLED)
    drives_listbox.unbind("<<ListboxSelect>>")
    subdirs_listbox.bind("<<ListboxSelect>>", lambda e: on_item_select(e, dir_obj))


def on_item_select(event, parent_dir_obj: Dir):
    selected_indices = subdirs_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_item = subdirs_listbox.get(selected_index)
    if selected_item.startswith("[DIR] "):
        selected_dir_name = selected_item[6:]
        new_path = os.path.join(parent_dir_obj.path, selected_dir_name)
        update_path_explorer(new_path)
        dir_obj = get_dir_object(new_path)
        subdirs_listbox.config(state=tk.NORMAL)
        populate_listbox_from_dir(dir_obj, subdirs_listbox)
        subdirs_listbox.config(state=tk.NORMAL)
        # Rebind with the new dir_obj for further navigation
        subdirs_listbox.bind("<<ListboxSelect>>", lambda e: on_item_select(e, dir_obj))
    elif selected_item.startswith("[FILE] "):
        selected_file_name = selected_item[7:]
        for file_obj in parent_dir_obj.files.values():
            if os.path.basename(file_obj.path) == selected_file_name:
                display_file(file_obj)
                break


def display_file(file_obj: File):
    """Display the file based on its mimetype."""
    for widget in text_viewer_frame.winfo_children():
        widget.destroy()

    if file_obj.mimetype == "text/plain":
        display_text_file(file_obj.path)
    elif file_obj.mimetype == "image":
        display_image_file(file_obj.path)
    else:
        display_unsupported_file(os.path.basename(file_obj.path))


def display_text_file(file_path: str):
    text_viewer = tk.Text(text_viewer_frame, wrap=tk.WORD)
    text_viewer.pack(fill=tk.BOTH, expand=True)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            text_viewer.insert(tk.END, content)
            text_viewer.config(state=tk.DISABLED)
        text_viewer_label.config(
            text=f"Viewing Text File: {os.path.basename(file_path)}"
        )
    except Exception as e:
        text_viewer.insert(tk.END, f"Error reading file: {e}")
        text_viewer_label.config(text="")


def display_image_file(file_path: str):
    try:
        img = Image.open(file_path)
        # Thumbnail to fit viewer (adjust size dynamically if needed)
        img.thumbnail((600, 500))  # Approximate viewer size
        img_tk = ImageTk.PhotoImage(img)
        img_label = tk.Label(text_viewer_frame, image=img_tk)
        img_label.image = img_tk  # Keep reference
        img_label.pack(fill=tk.BOTH, expand=True)
        text_viewer_label.config(
            text=f"Viewing Image File: {os.path.basename(file_path)}"
        )
    except Exception as e:
        error_label = tk.Label(
            text_viewer_frame, text=f"Error displaying image: {e}", fg="red"
        )
        error_label.pack()


def display_unsupported_file(file_name: str):
    message_label = tk.Label(
        text_viewer_frame,
        text=f"The selected file type is not supported for preview: {file_name}",
        fg="red",
        wraplength=500,
    )
    message_label.pack(pady=20)


def browse_to_path(event=None):
    path = path_explorer_entry.get()
    if not path or not os.path.exists(path):
        msgbox.showerror("Invalid Path", "The specified path does not exist.")
        return
    if not os.path.isdir(path):
        msgbox.showerror("Not a Directory", "The specified path is not a directory.")
        return
    dir_obj = get_dir_object(path)
    subdirs_listbox.config(state=tk.NORMAL)
    populate_listbox_from_dir(dir_obj, subdirs_listbox)
    subdirs_listbox.config(state=tk.NORMAL)
    drives_listbox.config(state=tk.DISABLED)
    drives_listbox.unbind("<<ListboxSelect>>")
    subdirs_listbox.bind("<<ListboxSelect>>", lambda e: on_item_select(e, dir_obj))


def clear_path_entry():
    path_explorer_entry.delete(0, tk.END)
    subdirs_listbox.delete(0, tk.END)
    subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
    subdirs_listbox.config(state=tk.DISABLED)
    drives_listbox.config(state=tk.NORMAL)
    drives_listbox.bind("<<ListboxSelect>>", on_drive_select)
    subdirs_listbox.unbind("<<ListboxSelect>>")


def update_path_explorer(path):
    path_explorer_entry.delete(0, tk.END)
    path_explorer_entry.insert(0, path)


# UI Setup
drives_frame = tk.Frame(root, width=150, bd=2, relief=tk.SUNKEN)
drives_frame.grid(row=0, column=0, sticky="nsew")
drives_frame.grid_propagate(False)
drives_label = tk.Label(drives_frame, text="DRIVES", font=("Arial", 12, "bold"))
drives_label.pack(pady=5)
drives_listbox = tk.Listbox(drives_frame, font=("Consolas", 14), height=10)
drives_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
drives = get_windows_drives()
for drive in drives:
    try:
        drives_listbox.insert(tk.END, drive)
    except Exception as e:
        error_label = tk.Label(
            drives_frame, text=f"Error loading drive {drive}: {e}", fg="red"
        )
        error_label.pack()
if not drives:
    drives_listbox.insert(
        tk.END,
        "No drives found! Check you have any storage devices connected and correctly mounted.",
    )
    drives_listbox.config(state=tk.DISABLED)
drives_listbox.config(exportselection=False)

subdirs_frame = tk.Frame(root, bd=2, relief=tk.SUNKEN)
subdirs_frame.grid(row=1, column=0, sticky="nsew")
subdirs_frame.grid_propagate(False)
subdirs_frame.grid_rowconfigure(0, weight=0)
subdirs_frame.grid_rowconfigure(1, weight=1)
subdirs_frame.grid_columnconfigure(0, weight=1)
subdirs_label = tk.Label(
    subdirs_frame, text="FOLDERS & FILES", font=("Arial", 12, "bold")
)
subdirs_label.grid(row=0, column=0, sticky="nsew", pady=5)
subdirs_listbox = tk.Listbox(subdirs_frame, font=("Consolas", 14), height=20)
subdirs_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
subdirs_scrollbar = tk.Scrollbar(subdirs_frame, orient=tk.VERTICAL)
subdirs_scrollbar.grid(row=1, column=1, sticky="ns")
subdirs_listbox.config(yscrollcommand=subdirs_scrollbar.set)
subdirs_scrollbar.config(command=subdirs_listbox.yview)
subdirs_listbox.config(exportselection=False)
subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
subdirs_listbox.config(state=tk.DISABLED)

drives_listbox.bind("<<ListboxSelect>>", on_drive_select)

file_viewer_frame = tk.Frame(root, bd=2, relief=tk.SUNKEN)
file_viewer_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
file_viewer_frame.grid_propagate(False)
file_viewer_frame.grid_rowconfigure(0, weight=1)
file_viewer_frame.grid_columnconfigure(0, weight=1)
text_viewer_frame = tk.Frame(file_viewer_frame)
text_viewer_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
text_viewer_label = tk.Label(
    text_viewer_frame, text="File Viewer", font=("Arial", 12, "bold")
)
text_viewer_label.pack()

path_explorer_frame = tk.Frame(root, bd=2, relief=tk.RIDGE)
path_explorer_frame.grid(row=0, column=1, sticky="new", padx=5, pady=(5, 0))
path_explorer_frame.grid_propagate(False)
path_explorer_label = tk.Label(
    path_explorer_frame, text="Current Path:", font=("Arial", 10)
)
path_explorer_label.pack(side=tk.LEFT, padx=5)
path_explorer_entry = tk.Entry(path_explorer_frame, font=("Consolas", 12), width=1)
path_explorer_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
path_explorer_entry.bind("<Return>", browse_to_path)
clear_entry_btn = tk.Button(path_explorer_frame, text="Clear", command=clear_path_entry)
clear_entry_btn.pack(side=tk.LEFT, padx=5)

# Initial setup
subdirs_listbox.config(state=tk.DISABLED)
subdirs_listbox.unbind("<<ListboxSelect>>")

update_status_bar()

root.mainloop()
