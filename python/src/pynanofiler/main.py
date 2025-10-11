import tkinter as tk, os, string, threading, queue
from tkinter import filedialog, messagebox as msgbox
from PIL import Image, ImageTk
from appinfo import version
from ctypes import windll

root = tk.Tk()
root.title("NanoFiler" + version)
root.geometry("900x700")

root.grid_rowconfigure(0, weight=15)
root.grid_rowconfigure(1, weight=85)
root.grid_columnconfigure(0, weight=15)
root.grid_columnconfigure(1, weight=85)

windll.shcore.SetProcessDpiAwareness(1)

indexed_subdirs = {}


def get_windows_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path) and os.path.ismount(drive_path):
            drives.append(drive_path)
    return drives


def get_folder_contents(drive, path=""):
    full_path = os.path.join(drive, path)
    try:
        subdirs = []
        files = []
        with os.scandir(full_path) as it:
            for entry in it:
                if entry.is_dir():
                    subdirs.append(entry.name)
                elif entry.is_file():
                    files.append(entry.name)
        return subdirs, files
    except PermissionError:
        return [], []
    except FileNotFoundError:
        return [], []


def index_subdirs_background(parent_path):
    """Scan subdirectories of each immediate subdir in parent_path in background."""
    try:
        with os.scandir(parent_path) as it:
            for entry in it:
                if entry.is_dir():
                    subdir_path = os.path.join(parent_path, entry.name)
                    threading.Thread(
                        target=index_single_subdir, args=(subdir_path,), daemon=True
                    ).start()
    except Exception:
        pass


def index_single_subdir(subdir_path):
    """Index immediate subdirs/files of subdir_path and store in indexed_subdirs."""
    try:
        subdirs, files = [], []
        with os.scandir(subdir_path) as it:
            for entry in it:
                if entry.is_dir():
                    subdirs.append(entry.name)
                elif entry.is_file():
                    files.append(entry.name)
        indexed_subdirs[subdir_path] = (subdirs, files)
    except Exception:
        indexed_subdirs[subdir_path] = ([], [])


def dismount_drive():
    # Re-enable drives listbox, disable subdirs listbox, clear path explorer
    drives_listbox.config(state=tk.NORMAL)
    subdirs_listbox.config(state=tk.DISABLED)
    subdirs_listbox.delete(0, tk.END)
    subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
    update_path_explorer("")
    # Unbind subdirs_listbox event
    subdirs_listbox.unbind("<<ListboxSelect>>")
    # Rebind drives_listbox event
    drives_listbox.bind("<<ListboxSelect>>", on_drive_select)


def on_drive_select(event):
    selected_indices = drives_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_drive = drives_listbox.get(selected_index)
    update_path_explorer(selected_drive)
    subdirs_listbox.config(state=tk.NORMAL)
    subdirs_listbox.delete(0, tk.END)
    subdirs, files = get_folder_contents(selected_drive)
    if not subdirs and not files:
        subdirs_listbox.insert(tk.END, "No accessible folders or files found.")
    else:
        for subdir in subdirs:
            subdirs_listbox.insert(tk.END, f"[DIR] {subdir}")
        for file in files:
            subdirs_listbox.insert(tk.END, f"[FILE] {file}")
        threading.Thread(
            target=index_subdirs_background, args=(selected_drive,), daemon=True
        ).start()
    subdirs_listbox.config(state=tk.NORMAL)
    # Disable drives listbox and unbind its event
    drives_listbox.config(state=tk.DISABLED)
    drives_listbox.unbind("<<ListboxSelect>>")
    # Bind subdirs_listbox event
    subdirs_listbox.bind("<<ListboxSelect>>", on_subdir_select)


def on_subdir_select(event):
    selected_indices = subdirs_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_item = subdirs_listbox.get(selected_index)
    if selected_item.startswith("[DIR] "):
        selected_dir = selected_item[6:]
        current_drive_indices = drives_listbox.curselection()
        # Find the currently selected drive (since drives_listbox is disabled, use stored path)
        current_path = path_explorer_entry.get()
        if current_path:
            new_path = os.path.join(current_path, selected_dir)
            update_path_explorer(new_path)
            subdirs_listbox.config(state=tk.NORMAL)
            subdirs_listbox.delete(0, tk.END)
            subdirs, files = get_folder_contents(current_path, selected_dir)
            if not subdirs and not files:
                subdirs_listbox.insert(tk.END, "No accessible folders or files found.")
            else:
                for subdir in subdirs:
                    subdirs_listbox.insert(tk.END, f"[DIR] {subdir}")
                for file in files:
                    subdirs_listbox.insert(tk.END, f"[FILE] {file}")
                threading.Thread(
                    target=index_subdirs_background, args=(new_path,), daemon=True
                ).start()
            subdirs_listbox.config(state=tk.NORMAL)
    elif selected_item.startswith("[FILE] "):
        selected_file = selected_item[7:]
        # You can call your file display logic here


def on_file_select(event):
    current_drive_indices = drives_listbox.curselection()
    if not current_drive_indices:
        return
    current_drive_index = current_drive_indices[0]
    current_drive = drives_listbox.get(current_drive_index)
    selected_indices = subdirs_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_item = subdirs_listbox.get(selected_index)
    if selected_item.startswith("[FILE] "):
        selected_file = selected_item[7:]
        file_extension = os.path.splitext(selected_file)[1].lower()
        if file_extension in [
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
        ]:
            display_text_file(os.path.join(current_drive, selected_file))
        elif file_extension in [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]:
            display_image_file(os.path.join(current_drive, selected_file))
        else:
            display_unsupported_file(selected_file)


def display_text_file(file_path):
    text_viewer = tk.Text(text_viewer_frame, wrap=tk.WORD)
    text_viewer.pack(fill=tk.BOTH, expand=True)
    text_viewer_label = tk.Label(text_viewer_frame, text="")
    text_viewer_label.pack()
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            text_viewer.delete(1.0, tk.END)
            text_viewer.insert(tk.END, content)
            text_viewer.config(state=tk.NORMAL)
            text_viewer_label.config(
                text=f"Viewing Text File: {os.path.basename(file_path)}"
            )
    except Exception as e:
        text_viewer.delete(1.0, tk.END)
        text_viewer.insert(tk.END, f"Error reading file: {e}")
        text_viewer.config(state=tk.DISABLED)
        text_viewer_label.config(text="")


def display_image_file(file_path):
    for widget in text_viewer_frame.winfo_children():
        widget.destroy()
    try:
        img = Image.open(file_path)
        img.thumbnail(
            (text_viewer_frame.winfo_width(), text_viewer_frame.winfo_height())
        )
        img_tk = ImageTk.PhotoImage(img)
        img_label = tk.Label(text_viewer_frame, image=img_tk)
        img_label.image = img_tk
        img_label.pack(fill=tk.BOTH, expand=True)
        img_label.config(text=f"Viewing Image File: {os.path.basename(file_path)}")
    except Exception as e:
        error_label = tk.Label(
            text_viewer_frame, text=f"Error displaying image: {e}", fg="red"
        )
        error_label.pack()


def display_unsupported_file(file_name):
    for widget in text_viewer_frame.winfo_children():
        widget.destroy()
    message_label = tk.Label(
        text_viewer_frame,
        text=f"The selected file type is not supported for preview: {file_name}",
        fg="red",
        wraplength=text_viewer_frame.winfo_width() - 20,
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
    subdirs_listbox.config(state=tk.NORMAL)
    subdirs_listbox.delete(0, tk.END)
    try:
        subdirs, files = get_folder_contents(path)
        if not subdirs and not files:
            subdirs_listbox.insert(tk.END, "No accessible folders or files found.")
        else:
            for subdir in subdirs:
                subdirs_listbox.insert(tk.END, f"[DIR] {subdir}")
            for file in files:
                subdirs_listbox.insert(tk.END, f"[FILE] {file}")
            threading.Thread(
                target=index_subdirs_background, args=(path,), daemon=True
            ).start()
        subdirs_listbox.config(state=tk.NORMAL)
        # Unbind drives_listbox, bind subdirs_listbox
        drives_listbox.config(state=tk.DISABLED)
        drives_listbox.unbind("<<ListboxSelect>>")
        subdirs_listbox.bind("<<ListboxSelect>>", on_subdir_select)
    except Exception as e:
        subdirs_listbox.insert(tk.END, f"Error: {e}")
        subdirs_listbox.config(state=tk.DISABLED)


def clear_path_entry():
    path_explorer_entry.delete(0, tk.END)
    subdirs_listbox.delete(0, tk.END)
    subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
    subdirs_listbox.config(state=tk.DISABLED)
    # Optionally, re-enable drives_listbox
    drives_listbox.config(state=tk.NORMAL)
    drives_listbox.bind("<<ListboxSelect>>", on_drive_select)
    subdirs_listbox.unbind("<<ListboxSelect>>")


def update_path_explorer(path):
    path_explorer_entry.delete(0, tk.END)
    path_explorer_entry.insert(0, path)


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
text_viewer_label.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)

path_explorer_frame = tk.Frame(root, bd=2, relief=tk.RIDGE)
path_explorer_frame.grid(row=0, column=1, sticky="new", padx=5, pady=(5, 0))
path_explorer_frame.grid_propagate(False)
path_explorer_label = tk.Label(
    path_explorer_frame, text="Current Path:", font=("Arial", 10)
)
path_explorer_label.pack(side=tk.LEFT, padx=5)
path_explorer_entry = tk.Entry(path_explorer_frame, font=("Consolas", 12), width=70)
path_explorer_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
path_explorer_entry.bind("<Return>", browse_to_path)
clear_entry_btn = tk.Button(path_explorer_frame, text="Clear", command=clear_path_entry)
clear_entry_btn.pack(side=tk.LEFT, padx=5)

# On startup, only drives_listbox is enabled and bound
drives_listbox.bind("<<ListboxSelect>>", on_drive_select)
subdirs_listbox.config(state=tk.DISABLED)
subdirs_listbox.unbind("<<ListboxSelect>>")

root.mainloop()
