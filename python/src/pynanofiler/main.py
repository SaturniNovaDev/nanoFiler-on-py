"""Main module from nanoFiler in Python."""

from functools import partial  # For threading with instance methods
from ctypes import windll
import tkinter as tk
import os
import string
import time
import threading
from typing import TypedDict, Union, Optional, Callable, Tuple
from tkinter import messagebox as msgbox, ttk
from _tkinter import TclError
from PIL import Image, ImageTk
from __init__ import __version__


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
        metadata: Union[DirMetadata, DirErrorMetadata],
        subdirs: dict[int, str],
        files: dict[int, File],
    ):
        self.path = path
        self.metadata = metadata
        self.subdirs = subdirs
        self.files = files


class NanoFilerApp(tk.Tk):
    """Main application class encapsulating state and UI for NanoFiler."""

    def __init__(self):
        super().__init__()
        self.title("NanoFiler" + __version__)
        self.geometry("900x700")

        # Grid configuration
        self.grid_rowconfigure(0, weight=15)
        self.grid_rowconfigure(1, weight=85)
        self.grid_rowconfigure(2, weight=0)  # For status bar
        self.grid_columnconfigure(0, weight=15)
        self.grid_columnconfigure(1, weight=85)
        windll.shcore.SetProcessDpiAwareness(1)

        # Instance variables (replacing globals)
        self.cache: dict[str, Dir] = {}
        self.current_dir: Optional[Dir] = None
        self.is_focused: bool = True
        self.refresh_timer_id: Optional[str] = None  # Timer ID for self.after

        # Reference image variable to avoid garbage collection from destroying images
        self._current_image_tk: Optional[ImageTk.PhotoImage] = None

        # Text viewer label
        self.text_viewer_label: Optional[tk.Label] = None

        # Encoders list
        self.avail_encoders: list = ["utf-8", "utf-16", "utf-8-sig", "utf-16-le"]

        # Live refreshing constants
        self.focused_refresh_ms = 10000  # 10 seconds
        self.unfocused_refresh_ms = 90000  # 1.5 minutes

        # Set up UI and bindings
        self._setup_status_bar()
        self._setup_drives()
        self._setup_subdirs()
        self._setup_file_viewer()
        self._setup_path_explorer()
        self._setup_bindings()

        # Initialize
        self.update_status_bar()
        self.schedule_live_refresh()

    def _setup_status_bar(self) -> None:
        """Set up the status bar frame and label."""
        self.status_bar_frame = tk.Frame(self, bd=1, relief=tk.SUNKEN)
        self.status_bar_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_bar_frame.grid_propagate(False)

        self.status_label = tk.Label(
            self.status_bar_frame, anchor="w", font=("Consolas", 11)
        )
        self.status_label.pack(side=tk.LEFT, padx=10, pady=2)

        # Unused elements (kept for compatibility)
        self.scanning_label = tk.Label(self.status_bar_frame)
        self.scanning_progressbar = ttk.Progressbar(self.status_bar_frame)

    def _setup_drives(self) -> None:
        """Set up the drives frame and listbox."""
        self.drives_frame = tk.Frame(self, width=150, bd=2, relief=tk.SUNKEN)
        self.drives_frame.grid(row=0, column=0, sticky="nsew")
        self.drives_frame.grid_propagate(False)
        self.drives_label = tk.Label(
            self.drives_frame, text="DRIVES", font=("Arial", 12, "bold")
        )
        self.drives_label.pack(pady=5)
        self.drives_listbox = tk.Listbox(
            self.drives_frame, font=("Consolas", 14), height=10
        )
        self.drives_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Populate drives
        drives = self.get_windows_drives()
        for drive in drives:
            try:
                self.drives_listbox.insert(tk.END, drive)
            except TclError as e:
                msgbox.showerror(
                    "Error showing 1 or more drives",
                    f"Internal program error when using Tkinter library.\nExtended error: {e}.",
                )
            except MemoryError as e:
                msgbox.showerror(
                    "Error loading 1 or more drives",
                    f"Insufficient memory.\nExtended error: {e}.",
                )
        if not drives:
            self.drives_listbox.insert(tk.END)
            self.drives_listbox.config(state=tk.DISABLED)
            msgbox.showerror(
                "No drives found!",
                "No drives found! Check you have any storage devices connected and correctly mounted.",
            )
        self.drives_listbox.config(exportselection=False)

    def _setup_subdirs(self) -> None:
        """Set up the subdirs frame and listbox."""
        self.subdirs_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
        self.subdirs_frame.grid(row=1, column=0, sticky="nsew")
        self.subdirs_frame.grid_propagate(False)
        self.subdirs_frame.grid_rowconfigure(0, weight=0)
        self.subdirs_frame.grid_rowconfigure(1, weight=1)
        self.subdirs_frame.grid_columnconfigure(0, weight=1)
        self.subdirs_label = tk.Label(
            self.subdirs_frame, text="FOLDERS & FILES", font=("Arial", 12, "bold")
        )
        self.subdirs_label.grid(row=0, column=0, sticky="nsew", pady=5)
        self.subdirs_listbox = tk.Listbox(
            self.subdirs_frame, font=("Consolas", 14), height=20
        )
        self.subdirs_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.subdirs_scrollbar = tk.Scrollbar(self.subdirs_frame, orient=tk.VERTICAL)
        self.subdirs_scrollbar.grid(row=1, column=1, sticky="ns")
        self.subdirs_listbox.config(yscrollcommand=self.subdirs_scrollbar.set)
        self.subdirs_scrollbar.config(command=self.subdirs_listbox.yview)  # type: ignore
        self.subdirs_listbox.config(exportselection=False)
        self.subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
        self.subdirs_listbox.config(state=tk.DISABLED)

    def _setup_file_viewer(self) -> None:
        """Set up the file viewer frame."""
        self.file_viewer_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN)
        self.file_viewer_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        self.file_viewer_frame.grid_propagate(False)
        self.file_viewer_frame.grid_rowconfigure(0, weight=1)
        self.file_viewer_frame.grid_columnconfigure(0, weight=1)
        self.text_viewer_frame = tk.Frame(self.file_viewer_frame)
        self.text_viewer_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.text_viewer_label = tk.Label(
            self.text_viewer_frame, text="File Viewer", font=("Arial", 12, "bold")
        )
        self.text_viewer_label.pack()

    def _setup_path_explorer(self) -> None:
        """Set up the path explorer frame."""
        self.path_explorer_frame = tk.Frame(self, bd=2, relief=tk.RIDGE)
        self.path_explorer_frame.grid(
            row=0, column=1, sticky="new", padx=5, pady=(5, 0)
        )
        self.path_explorer_frame.grid_propagate(False)
        self.path_explorer_label = tk.Label(
            self.path_explorer_frame, text="Current Path:", font=("Arial", 10)
        )
        self.path_explorer_label.pack(side=tk.LEFT, padx=5)
        self.path_explorer_entry = tk.Entry(
            self.path_explorer_frame, font=("Consolas", 12), width=1
        )
        self.path_explorer_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.clear_entry_btn = tk.Button(
            self.path_explorer_frame, text="Clear", command=self.clear_path_entry
        )
        self.clear_entry_btn.pack(side=tk.LEFT, padx=5)

    def _setup_bindings(self) -> None:
        """Set up event bindings."""
        self.drives_listbox.bind("<<ListboxSelect>>", self.on_drive_select)
        self.path_explorer_entry.bind("<Return>", self.browse_to_path)
        self.bind("<FocusIn>", self.on_focus_in)
        self.bind("<FocusOut>", self.on_focus_out)
        # Initial state for subdirs
        self.subdirs_listbox.config(state=tk.DISABLED)
        self.subdirs_listbox.unbind("<<ListboxSelect>>")

    @staticmethod
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
        image_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".gif",
            ".tiff",
            ".svg",
        }

        if extension in text_extensions:
            return "text/plain"
        elif extension in image_extensions:
            return "image"
        else:
            return "unknown"

    @staticmethod
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
                        mimetype = NanoFilerApp.get_mimetype(entry.name)
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

    @staticmethod
    def get_windows_drives() -> list[str]:
        """Check if there are any storage devices mounted."""
        drives: list[str] = []
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path) and os.path.ismount(drive_path):
                drives.append(drive_path)
        return drives

    def async_get_dir(self, path: str, callback: Callable[[Dir], None]) -> None:
        """Asynchronously get Dir: check cache first, else scan in thread and callback."""
        if path in self.cache:
            # Instant from cache
            callback(self.cache[path])
            # Schedule background refresh to update cache
            threading.Thread(
                target=partial(self.scan_and_update_cache, path), daemon=True
            ).start()
        else:
            # Scan in background
            threading.Thread(
                target=partial(self.scan_and_callback, path, callback), daemon=True
            ).start()

    def scan_and_callback(self, path: str, callback: Callable[[Dir], None]) -> None:
        """Thread function: scan, cache, and callback on main thread."""
        dir_obj = self.scan_dir(path)
        self.cache[path] = dir_obj
        # Queue callback on main thread
        self.after(0, lambda: callback(dir_obj))

    def scan_and_update_cache(self, path: str) -> None:
        """Thread function: scan and update cache (no UI callback)."""
        dir_obj = self.scan_dir(path)
        self.cache[path] = dir_obj

    def schedule_live_refresh(self) -> None:
        """Schedule the next live refresh based on focus state."""
        if self.refresh_timer_id:
            self.after_cancel(self.refresh_timer_id)
        delay = (
            self.focused_refresh_ms if self.is_focused else self.unfocused_refresh_ms
        )
        self.refresh_timer_id = self.after(delay, self.perform_live_refresh)

    def perform_live_refresh(self) -> None:
        """Perform live refresh of current directory if set."""
        if self.current_dir and self.current_dir.path:
            path = self.current_dir.path
            # Async refresh: will update cache and UI via callback
            self.async_get_dir(path, self.update_ui_from_dir)
        # Reschedule next
        self.schedule_live_refresh()

    def on_focus_in(self, _event: tk.Event) -> None:
        """Handle window focus in: switch to faster refresh."""
        self.is_focused = True
        self.schedule_live_refresh()

    def on_focus_out(self, _event: tk.Event) -> None:
        """Handle window focus out: switch to slower refresh."""
        self.is_focused = False
        self.schedule_live_refresh()

    def update_ui_from_dir(self, dir_obj: Dir) -> None:
        """Callback to update UI with new Dir object (populate, bind, set current)."""
        self.current_dir = dir_obj
        self.subdirs_listbox.config(state=tk.NORMAL)
        self.populate_listbox_from_dir(dir_obj)
        # Re-bind for further selections (pass the new dir_obj)
        self.subdirs_listbox.bind(
            "<<ListboxSelect>>", lambda e: self.on_item_select(e, dir_obj)
        )
        self.subdirs_listbox.config(state=tk.NORMAL)

    def show_loading_state(self) -> None:
        """Show loading in listbox."""
        self.subdirs_listbox.config(state=tk.NORMAL)
        self.subdirs_listbox.delete(0, tk.END)
        self.subdirs_listbox.insert(tk.END, "Loading...")
        self.subdirs_listbox.config(state=tk.DISABLED)

    def populate_listbox_from_dir(self, dir_obj: Dir) -> None:
        """Populate the listbox with contents from a Dir object."""
        self.subdirs_listbox.delete(0, tk.END)
        if "error" in dir_obj.metadata:  # Check for error key in union type
            self.subdirs_listbox.insert(tk.END, f"Error: {dir_obj.metadata['error']}")
            return
        if not dir_obj.subdirs and not dir_obj.files:
            self.subdirs_listbox.insert(tk.END, "No accessible folders or files found.")
            return
        for _, subdir in dir_obj.subdirs.items():
            self.subdirs_listbox.insert(tk.END, f"[DIR] {subdir}")
        for _, file_obj in dir_obj.files.items():
            self.subdirs_listbox.insert(
                tk.END, f"[FILE] {os.path.basename(file_obj.path)}"
            )

    def on_drive_select(self, _event: tk.Event) -> None:
        """Handles item selection from the drive browsing listbox."""
        selected_indices: Tuple[int, ...] = self.drives_listbox.curselection()  # type: ignore
        if not selected_indices:
            return
        selected_index = selected_indices[0]  # type: ignore
        selected_drive = self.drives_listbox.get(selected_index)  # type: ignore
        self.update_path_explorer(selected_drive)  # type: ignore
        self.show_loading_state()
        self.drives_listbox.config(state=tk.DISABLED)
        self.drives_listbox.unbind("<<ListboxSelect>>")
        # Async load
        self.async_get_dir(selected_drive, self.update_ui_from_dir)  # type: ignore

    def on_item_select(self, _event: tk.Event, parent_dir_obj: Dir) -> None:
        """Handles item selection from the file browsing listbox."""
        selected_indices: Tuple[int, ...] = self.subdirs_listbox.curselection()  # type: ignore
        if not selected_indices:
            return
        selected_index = selected_indices[0]  # type: ignore
        selected_item = self.subdirs_listbox.get(selected_index)  # type: ignore
        if selected_item.startswith("[DIR] "):  # type: ignore
            selected_dir_name: str = selected_item[6:]  # type: ignore
            new_path = os.path.join(parent_dir_obj.path, selected_dir_name)  # type: ignore
            self.update_path_explorer(new_path)
            self.show_loading_state()
            # Async load new path
            self.async_get_dir(new_path, self.update_ui_from_dir)
        elif selected_item.startswith("[FILE] "):  # type: ignore
            selected_file_name = selected_item[7:]  # type: ignore
            for file_obj in parent_dir_obj.files.values():
                if os.path.basename(file_obj.path) == selected_file_name:
                    self.display_file(file_obj)
                    break

    def display_file(self, file_obj: File) -> None:
        """Display the file based on its mimetype."""
        # Clear existing content widgets (but label will be recreated in sub-methods)
        for widget in self.text_viewer_frame.winfo_children():
            if (
                widget != self.text_viewer_label
            ):  # Skip if label exists, but we'll recreate anyway
                widget.destroy()
        # If label was destroyed previously, recreate it (safe to call multiple times)
        if (
            hasattr(self, "text_viewer_label")
            and not self.text_viewer_label.winfo_exists()
        ):
            self.text_viewer_label = None  # Reset invalid ref
        self._create_viewer_label("File Viewer")  # Repack a default label

        if file_obj.mimetype == "text/plain":
            self.display_text_file(file_obj.path)
        elif file_obj.mimetype == "image":
            self.display_image_file(file_obj.path)
        else:
            self.display_unsupported_file(os.path.basename(file_obj.path))

    def _create_viewer_label(self, text: str) -> None:
        """Helper to create/repack the viewer label (avoids destruction issues)."""
        # Destroy existing label if invalid
        if hasattr(self, "text_viewer_label") and self.text_viewer_label.winfo_exists():
            self.text_viewer_label.destroy()
        self.text_viewer_label = tk.Label(
            self.text_viewer_frame, text=text, font=("Arial", 12, "bold")
        )
        self.text_viewer_label.pack()  # Repack at top

    def display_text_file(self, file_path: str) -> None:
        """Opens the specified file and displays its content, trying multiple
        encoders until successful."""

        # 1. Setup UI
        # Recreate label with file info
        self._create_viewer_label(f"Viewing Text File: {os.path.basename(file_path)}")
        text_viewer = tk.Text(self.text_viewer_frame, wrap=tk.WORD)
        text_viewer.pack(fill=tk.BOTH, expand=True)

        content_loaded = False
        last_error_message = ""  # To store the error if all fail

        # 2. Attempt to read with multiple encoders
        for encoder in self.avail_encoders:
            try:
                with open(file_path, "r", encoding=encoder) as file:
                    content = file.read()
                    text_viewer.insert(tk.END, content)
                    text_viewer.config(state=tk.DISABLED)
                    content_loaded = True
                    break

            except UnicodeDecodeError as e:
                # This is an expected failure for non-matching encoders, skip msgbox
                last_error_message = f"Decode failed with {encoder}: {e}"
                continue

            except PermissionError as e:
                # Specific handling for permission issues (fatal/non-recoverable)
                last_error_message = f"Error: Cannot read '{os.path.basename(file_path)}', Permission Denied: {e}."
                content_loaded = False
                # Show error box immediately since this is a critical system error
                msgbox.showerror("Permission Error!", last_error_message)
                break

            except Exception as e:
                # Catch all other file I/O errors (e.g., file not found, hardware failure)
                last_error_message = f"Error: Cannot read '{os.path.basename(file_path)}', Unknown I/O Error: {e}."
                content_loaded = False
                msgbox.showerror("Error reading file!", last_error_message)
                break

        # 3. Final error handling if no content was loaded after all attempts
        if not content_loaded:
            # Clear text_viewer from any partial attempts/messages before final message
            text_viewer.delete("1.0", tk.END)
            text_viewer.insert(
                tk.END,
                f"Could not decode file using any available encoder.\n{last_error_message}",
            )
            text_viewer.config(state=tk.DISABLED)

    def display_image_file(self, file_path: str) -> None:
        """Displays an image file using `ImageTk`."""
        # Recreate label first
        self._create_viewer_label(f"Viewing Image File: {os.path.basename(file_path)}")

        try:
            if file_path.lower().endswith(".svg"):
                png_data = cairosvg.svg2png(
                    url=file_path
                )  # Convert SVG to PNG if ".svg" detected in the file path
                img = Image.open(BytesIO(png_data))
            else:
                img = Image.open(file_path)
            img.thumbnail((600, 500))
            self._current_image_tk = ImageTk.PhotoImage(img)  # Store reference
            img_label = tk.Label(self.text_viewer_frame, image=self._current_image_tk)
            img_label.pack(fill=tk.BOTH, expand=True)
        except PermissionError as e:  # Handle permission for images too
            error_label = tk.Label(
                self.text_viewer_frame,
                text=f"Error: Cannot open image '{os.path.basename(file_path)}', {e}.",
                fg="red",
                font="Consolas",
            )
            error_label.pack(pady=20)
        except Exception as e:
            error_label = tk.Label(
                self.text_viewer_frame,
                text=f"Error displaying image: {e}",
                fg="red",
                font="Consolas",
            )
            error_label.pack()

    def display_unsupported_file(self, file_name: str) -> None:
        """Displays an error text for unsupported filetypes."""
        self._create_viewer_label(f"Unsupported File: {file_name}")
        message_label = tk.Label(
            self.text_viewer_frame,
            text=f"The selected file type is not supported for preview: {file_name}",
            fg="red",
            font="Consolas",
            wraplength=500,
        )
        message_label.pack(pady=20)

    def browse_to_path(self, _event: Optional[tk.Event] = None) -> None:
        """Checks if the entered path exists before getting the dir."""
        path = self.path_explorer_entry.get()
        if not path or not os.path.exists(path):
            msgbox.showerror("Invalid Path", "The specified path does not exist.")
            return
        if not os.path.isdir(path):
            msgbox.showerror(
                "Not a Directory", "The specified path is not a directory."
            )
            return
        self.show_loading_state()
        self.drives_listbox.config(state=tk.DISABLED)
        self.drives_listbox.unbind("<<ListboxSelect>>")
        # Async load
        self.async_get_dir(path, self.update_ui_from_dir)

    def clear_path_entry(self) -> None:
        """Clears the path explorer and resets the file browsing frames when
        the `clear` button is pressed."""
        self.current_dir = None
        self.path_explorer_entry.delete(0, tk.END)
        self.subdirs_listbox.delete(0, tk.END)
        self.subdirs_listbox.insert(tk.END, "Select a drive to view its contents.")
        self.subdirs_listbox.config(state=tk.DISABLED)
        self.drives_listbox.config(state=tk.NORMAL)
        self.drives_listbox.bind("<<ListboxSelect>>", self.on_drive_select)
        self.subdirs_listbox.unbind("<<ListboxSelect>>")

    def update_path_explorer(self, path: str) -> None:
        """Update the path explorer to show the current path. Called when a new
        location is selected."""
        self.path_explorer_entry.delete(0, tk.END)
        self.path_explorer_entry.insert(0, path)

    def update_status_bar(self) -> None:
        """UI function to update the status bar to show the current path and dir info."""
        current_path = self.path_explorer_entry.get()
        if self.current_dir and "error" not in self.current_dir.metadata:
            counts = self.current_dir.metadata
            dir_info = (
                f" | {counts['count_subdirs']} dirs, {counts['count_files']} files"
            )
        else:
            dir_info = ""
        status_text = f"Current Path: {current_path}{dir_info} | Version: {__version__}"
        self.status_label.config(text=status_text)
        self.after(200, self.update_status_bar)


# Run the application
if __name__ == "__main__":
    app = NanoFilerApp()
    app.mainloop()
