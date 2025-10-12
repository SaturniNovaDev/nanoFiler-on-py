"""Main module from nanoFiler in Python."""

from ctypes import windll
import tkinter as tk
import os
import string
import time
import threading
from typing import TypedDict, Union, Optional, Callable
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


class FileMetadata(TypedDict):
    """Metadata for File objects with timestamps."""

    created: str
    modified: str


class DirMetadata(TypedDict):
    """Standard metadata for successful directory scans with timestamps."""

    count_subdirs: int
    count_files: int
    created: str
    modified: str


class DirErrorMetadata(TypedDict):
    """Error metadata for failed directory scans."""

    error: str


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
        metadata: FileMetadata,  # Now includes timestamps
        size: int,
        mimetype: str,
        content: str = "",
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
        metadata: Union[
            DirMetadata, DirErrorMetadata
        ],  # Now includes timestamps on success
        subdirs: dict[int, str],
        files: dict[int, File],
    ):
        self.path = path
        self.metadata = metadata
        self.subdirs = subdirs
        self.files = files


# Global cache for Dir objects (path -> Dir)
cache: dict[str, Dir] = {}

# Global for current directory
current_dir: Optional[Dir] = None

# Focus and refresh management
is_focused: bool = True
refresh_timer_id: Optional[str] = None  # Timer ID for root.after

# Live refreshing to keep the file explorer updated
FOCUSED_REFRESH_MS = 10000  # 10 seconds
UNFOCUSED_REFRESH_MS = 90000  # 1.5 minutes


status_bar_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
status_bar_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
status_bar_frame.grid_propagate(False)

status_label = tk.Label(status_bar_frame, anchor="w", font=("Consolas", 11))
status_label.pack(side=tk.LEFT, padx=10, pady=2)


def update_status_bar() -> None:
    """UI function to update the status bar to show the current path and dir info."""
    current_path = path_explorer_entry.get()
    if current_dir and "error" not in current_dir.metadata:
        counts = current_dir.metadata
        dir_info = f" | {counts['count_subdirs']} dirs, {counts['count_files']} files"
    else:
        dir_info = ""
    status_text = f"Current Path: {current_path}{dir_info} | Version: {__version__}"
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
        ".ps1",
        ".rtf",
        ".git",
    }
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"}

    if extension in text_extensions:
        return "text/plain"
    elif extension in image_extensions:
        return "image"
    else:
        return "unknown"


def scan_dir(path: str) -> Dir:
    """Synchronous scan to create a Dir object (with timestamps). Called from thread."""
    subdirs: dict[int, str] = {}
    files: dict[int, File] = {}
    metadata: Union[
        DirMetadata, DirErrorMetadata
    ]  # Declare outside: always defined, union type
    try:
        # Get dir-level timestamps first
        dir_stat = os.stat(path)
        dir_created = time.ctime(dir_stat.st_birthtime)
        dir_modified = time.ctime(dir_stat.st_mtime)

        with os.scandir(path) as it:
            subdir_idx: int = 0
            file_idx: int = 0
            for entry in it:
                if entry.is_dir():
                    subdirs[subdir_idx] = entry.name
                    subdir_idx += 1
                elif entry.is_file():
                    stat = entry.stat()
                    file_path = os.path.join(path, entry.name)
                    size = stat.st_size
                    mimetype = get_mimetype(entry.name)
                    file_metadata: FileMetadata = {
                        "created": time.ctime(stat.st_birthtime),
                        "modified": time.ctime(stat.st_mtime),
                    }
                    files[file_idx] = File(
                        path=file_path,
                        metadata=file_metadata,
                        size=size,
                        mimetype=mimetype,
                        content="",
                    )
                    file_idx += 1
        # Assign after successful scan (type checker infers DirMetadata)
        metadata = {
            "count_subdirs": len(subdirs),
            "count_files": len(files),
            "created": dir_created,
            "modified": dir_modified,
        }
    except Exception as e:
        # On error, reset to empty state and set error metadata (infers DirErrorMetadata)
        subdirs = {}
        files = {}
        metadata = {"error": str(e)}
    return Dir(path=path, metadata=metadata, subdirs=subdirs, files=files)


def async_get_dir(path: str, callback: Callable[[Dir], None]) -> None:
    """Asynchronously get Dir: check cache first, else scan in thread and callback."""
    if path in cache:
        # Instant from cache
        callback(cache[path])
        # Schedule background refresh to update cache
        threading.Thread(
            target=scan_and_update_cache, args=(path,), daemon=True
        ).start()
    else:
        # Scan in background
        threading.Thread(
            target=scan_and_callback, args=(path, callback), daemon=True
        ).start()


def scan_and_callback(path: str, callback: Callable[[Dir], None]) -> None:
    """Thread function: scan, cache, and callback on main thread."""
    dir_obj = scan_dir(path)
    cache[path] = dir_obj
    # Queue callback on main thread
    root.after(0, lambda: callback(dir_obj))


def scan_and_update_cache(path: str) -> None:
    """Thread function: scan and update cache (no UI callback)."""
    dir_obj = scan_dir(path)
    cache[path] = dir_obj


def schedule_live_refresh() -> None:
    """Schedule the next live refresh based on focus state."""
    global refresh_timer_id
    if refresh_timer_id:
        root.after_cancel(refresh_timer_id)
    delay = FOCUSED_REFRESH_MS if is_focused else UNFOCUSED_REFRESH_MS
    refresh_timer_id = root.after(delay, perform_live_refresh)


def perform_live_refresh() -> None:
    """Perform live refresh of current directory if set."""
    global refresh_timer_id
    if current_dir and current_dir.path:
        path = current_dir.path
        # Async refresh: will update cache and UI via callback
        async_get_dir(path, lambda dir_obj: update_ui_from_dir(dir_obj))
    # Reschedule next
    schedule_live_refresh()


def on_focus_in(event) -> None:
    """Handle window focus in: switch to faster refresh."""
    global is_focused
    is_focused = True
    schedule_live_refresh()


def on_focus_out(event) -> None:
    """Handle window focus out: switch to slower refresh."""
    global is_focused
    is_focused = False
    schedule_live_refresh()


def update_ui_from_dir(dir_obj: Dir) -> None:
    """Callback to update UI with new Dir object (populate, bind, set current)."""
    global current_dir
    current_dir = dir_obj
    subdirs_listbox.config(state=tk.NORMAL)
    populate_listbox_from_dir(dir_obj, subdirs_listbox)
    # Re-bind for further selections (pass the new dir_obj)
    subdirs_listbox.bind("<<ListboxSelect>>", lambda e: on_item_select(e, dir_obj))
    subdirs_listbox.config(state=tk.NORMAL)


def show_loading_state() -> None:
    """Show loading in listbox."""
    subdirs_listbox.config(state=tk.NORMAL)
    subdirs_listbox.delete(0, tk.END)
    subdirs_listbox.insert(tk.END, "Loading...")
    subdirs_listbox.config(state=tk.DISABLED)


def get_windows_drives() -> list[str]:
    drives: list[str] = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path) and os.path.ismount(drive_path):
            drives.append(drive_path)
    return drives


def populate_listbox_from_dir(dir_obj: Dir, listbox: tk.Listbox) -> None:
    """Populate the listbox with contents from a Dir object."""
    listbox.delete(0, tk.END)
    if "error" in dir_obj.metadata:  # Check for error key in union type
        listbox.insert(tk.END, f"Error: {dir_obj.metadata['error']}")
        return
    if not dir_obj.subdirs and not dir_obj.files:
        listbox.insert(tk.END, "No accessible folders or files found.")
        return
    for idx, subdir in dir_obj.subdirs.items():
        listbox.insert(tk.END, f"[DIR] {subdir}")
    for idx, file_obj in dir_obj.files.items():
        listbox.insert(tk.END, f"[FILE] {os.path.basename(file_obj.path)}")


def on_drive_select(event) -> None:
    selected_indices = drives_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_drive = drives_listbox.get(selected_index)
    update_path_explorer(selected_drive)
    show_loading_state()
    drives_listbox.config(state=tk.DISABLED)
    drives_listbox.unbind("<<ListboxSelect>>")
    # Async load
    async_get_dir(selected_drive, lambda dir_obj: update_ui_from_dir(dir_obj))


def on_item_select(event, parent_dir_obj: Dir) -> None:
    selected_indices = subdirs_listbox.curselection()
    if not selected_indices:
        return
    selected_index = selected_indices[0]
    selected_item = subdirs_listbox.get(selected_index)
    if selected_item.startswith("[DIR] "):
        selected_dir_name = selected_item[6:]
        new_path = os.path.join(parent_dir_obj.path, selected_dir_name)
        update_path_explorer(new_path)
        show_loading_state()
        # Async load new path
        async_get_dir(new_path, lambda dir_obj: update_ui_from_dir(dir_obj))
    elif selected_item.startswith("[FILE] "):
        selected_file_name = selected_item[7:]
        for file_obj in parent_dir_obj.files.values():
            if os.path.basename(file_obj.path) == selected_file_name:
                display_file(file_obj)
                break


def display_file(file_obj: File) -> None:
    """Display the file based on its mimetype."""
    for widget in text_viewer_frame.winfo_children():
        widget.destroy()

    if file_obj.mimetype == "text/plain":
        display_text_file(file_obj.path)
    elif file_obj.mimetype == "image":
        display_image_file(file_obj.path)
    else:
        display_unsupported_file(os.path.basename(file_obj.path))


def display_text_file(file_path: str) -> None:
    text_viewer = tk.Text(text_viewer_frame, wrap=tk.WORD)
    text_viewer.pack(fill=tk.BOTH, expand=True)
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            text_viewer.insert(tk.END, content)
            text_viewer.config(state=tk.DISABLED)
        # Optionally show timestamps from metadata, but for now just filename
        text_viewer_label.config(
            text=f"Viewing Text File: {os.path.basename(file_path)}"
        )
    except Exception as e:
        text_viewer.insert(tk.END, f"Error reading file: {e}")
        text_viewer_label.config(text="")


def display_image_file(file_path: str) -> None:
    try:
        img = Image.open(file_path)
        img.thumbnail((600, 500))
        img_tk = ImageTk.PhotoImage(img)
        img_label = tk.Label(text_viewer_frame, image=img_tk)
        img_label.image = img_tk
        img_label.pack(fill=tk.BOTH, expand=True)
        text_viewer_label.config(
            text=f"Viewing Image File: {os.path.basename(file_path)}"
        )
    except Exception as e:
        error_label = tk.Label(
            text_viewer_frame, text=f"Error displaying image: {e}", fg="red"
        )
        error_label.pack()


def display_unsupported_file(file_name: str) -> None:
    message_label = tk.Label(
        text_viewer_frame,
        text=f"The selected file type is not supported for preview: {file_name}",
        fg="red",
        wraplength=500,
    )
    message_label.pack(pady=20)


def browse_to_path(event=None) -> None:
    """Checks if the entered path exists before getting the dir."""
    path = path_explorer_entry.get()
    if not path or not os.path.exists(path):
        msgbox.showerror("Invalid Path", "The specified path does not exist.")
        return
    if not os.path.isdir(path):
        msgbox.showerror("Not a Directory", "The specified path is not a directory.")
        return
    show_loading_state()
    drives_listbox.config(state=tk.DISABLED)
    drives_listbox.unbind("<<ListboxSelect>>")
    # Async load
    async_get_dir(path, lambda dir_obj: update_ui_from_dir(dir_obj))


def clear_path_entry() -> None:
    global current_dir
    current_dir = None
    path_explorer_entry.delete(0, tk.END)
    subdirs_listbox.delete(0, tk.END)
    subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
    subdirs_listbox.config(state=tk.DISABLED)
    drives_listbox.config(state=tk.NORMAL)
    drives_listbox.bind("<<ListboxSelect>>", on_drive_select)
    subdirs_listbox.unbind("<<ListboxSelect>>")


def update_path_explorer(path: str) -> None:
    """Update the path explorer to show the current path. Called when a new location is selected."""
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
subdirs_listbox.config(state=tk.DISABLED)
subdirs_listbox.unbind("<<ListboxSelect>>")
root.bind("<FocusIn>", on_focus_in)
root.bind("<FocusOut>", on_focus_out)

# End of UI setup

update_status_bar()
schedule_live_refresh()
root.mainloop()
