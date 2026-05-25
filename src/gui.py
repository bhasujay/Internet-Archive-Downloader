import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import queue
import threading
import time
from urllib.parse import urlparse, unquote
import requests

from .utils import (
    DEFAULT_HEADERS,
    FileItem,
    build_download_url,
    fetch_directory_listing,
    format_bytes,
    parse_directory_listing,
    parse_item_id,
    sanitize_folder_name,
)


class MainWindow(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.item_id = ""
        self.item_title = ""
        self.download_url = ""
        self.file_rows: list[dict[str, object]] = []
        self.ui_queue: queue.Queue[tuple] = queue.Queue()
        self.queue_polling = False
        self.download_in_progress = False
        self.fetch_in_progress = False
        self.last_requested = ""
        self._fetch_debounce_id: str | None = None
        self.progress_total_bytes = 0
        self.progress_downloaded_bytes = 0
        self.download_start_time: float | None = None
        self.completed_files = 0
        self.total_files = 0
        self.create_widgets()

    def create_widgets(self):
        self.url_label = ctk.CTkLabel(self, text="Item URL or ID:")
        self.url_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 0))

        self.url_var = tk.StringVar()
        self.url_entry = ctk.CTkEntry(self, textvariable=self.url_var)
        self.url_entry.grid(row=1, column=0, sticky="ew", pady=4, padx=(8, 4))
        self.url_var.trace_add("write", self._on_url_change)
        self.url_entry.bind("<Return>", self._on_url_submit)
        self.url_entry.bind("<<Paste>>", self._on_url_paste)
        self.url_entry.bind("<Control-v>", self._on_url_paste)

        self.fetch_btn = ctk.CTkButton(self, text="Get Files", command=self.on_fetch_files)
        self.fetch_btn.grid(row=1, column=1, sticky="e", pady=4, padx=(4, 8))

        self.download_btn = ctk.CTkButton(
            self, text="Download Selected", command=self.on_download
        )
        self.download_btn.grid(row=2, column=1, sticky="e", pady=6, padx=8)
        self.download_btn.configure(state="disabled")

        self.status_var = tk.StringVar(value="")
        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var)
        self.status_label.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))

        self.welcome_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.welcome_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=8, pady=6)
        self.welcome_frame.columnconfigure(0, weight=1)
        self.welcome_frame.rowconfigure(0, weight=1)
        self.welcome_frame.rowconfigure(1, weight=0)
        self.welcome_frame.rowconfigure(2, weight=1)

        self.welcome_label = ctk.CTkLabel(self.welcome_frame, text="Paste an Internet Archive URL or ID above to get started", font=("Helvetica", 16))
        self.welcome_label.grid(row=0, column=0, sticky="s", pady=(0, 10))

        self.fetch_progress = ctk.CTkProgressBar(self.welcome_frame, mode="indeterminate", width=300)
        self.fetch_progress.grid(row=1, column=0, pady=(10, 0))
        self.fetch_progress.grid_remove()

        self.files_frame = ctk.CTkFrame(self)
        self.files_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=8, pady=6)
        self.files_frame.grid_remove()
        self.rowconfigure(3, weight=1)

        self.files_header_frame = ctk.CTkFrame(self.files_frame, fg_color="transparent")
        self.files_header_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.files_header_frame.columnconfigure(1, weight=1)

        self.files_title_label = ctk.CTkLabel(self.files_header_frame, text="Files")
        self.files_title_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(self.files_header_frame, textvariable=self.search_var, placeholder_text="Search files...", height=28)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=8)
        self.search_var.trace_add("write", self._on_search_change)

        self.select_all_btn = ctk.CTkButton(self.files_header_frame, text="Select All", width=80, command=self.on_select_all)
        self.select_all_btn.grid(row=0, column=2, sticky="e", padx=(0, 4))

        self.deselect_all_btn = ctk.CTkButton(self.files_header_frame, text="Deselect All", width=80, command=self.on_deselect_all)
        self.deselect_all_btn.grid(row=0, column=3, sticky="e")

        self.files_scroll = ctk.CTkScrollableFrame(self.files_frame)
        self.files_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.files_frame.rowconfigure(1, weight=1)
        self.files_frame.columnconfigure(0, weight=1)

        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self.progress_frame.grid_remove()

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Downloaded: 0 B")
        self.progress_label.grid(row=1, column=0, sticky="w", padx=8)

        self.speed_label = ctk.CTkLabel(self.progress_frame, text="Speed: 0 B/s")
        self.speed_label.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 8))

        self.progress_frame.columnconfigure(0, weight=1)

    def _on_url_submit(self, _event):
        self.on_fetch_files()

    def _on_url_paste(self, _event):
        # Cancel any pending debounce so we don't double-fetch
        if self._fetch_debounce_id is not None:
            self.master.after_cancel(self._fetch_debounce_id)
            self._fetch_debounce_id = None
        self.master.after(150, self.on_fetch_files)

    def _on_url_change(self, *_args):
        value = self.url_var.get().strip()
        if not value or self.fetch_in_progress:
            return
        if self._fetch_debounce_id is not None:
            self.master.after_cancel(self._fetch_debounce_id)
        self._fetch_debounce_id = self.master.after(500, self.on_fetch_files)

    def _on_search_change(self, *_args):
        query = self.search_var.get().lower()
        for row in self.file_rows:
            if query in row["item"].name.lower():
                row["frame"].grid()
            else:
                row["frame"].grid_remove()

    def _set_status(self, message: str):
        self.status_var.set(message)

    def on_select_all(self):
        for row in self.file_rows:
            row["var"].set(True)

    def on_deselect_all(self):
        for row in self.file_rows:
            row["var"].set(False)

    def on_download(self):
        if self.download_in_progress:
            return
        selected = [
            (index, row)
            for index, row in enumerate(self.file_rows)
            if row["var"].get()
        ]
        if not selected:
            messagebox.showwarning("Selection required", "Please select at least one file.")
            return
        destination = filedialog.askdirectory(title="Select download folder")
        if not destination:
            return
        folder_name = sanitize_folder_name(self.item_title or self.item_id)
        target_folder = os.path.join(destination, folder_name)
        os.makedirs(target_folder, exist_ok=True)
        self.download_btn.configure(state="disabled")
        self.fetch_btn.configure(state="disabled")
        self.download_in_progress = True
        thread = threading.Thread(
            target=self._download_worker, args=(selected, target_folder), daemon=True
        )
        thread.start()
        self._ensure_queue_processing()

    def on_fetch_files(self):
        if self.fetch_in_progress:
            return
        raw = self.url_var.get().strip()
        if not raw:
            messagebox.showwarning("Input required", "Please enter an Item URL or ID")
            return
        if raw == self.last_requested and self.file_rows:
            return
        self.last_requested = raw
        self.fetch_in_progress = True
        self.fetch_btn.configure(state="disabled")
        self.download_btn.configure(state="disabled")
        self._set_status("Fetching files...")
        self._clear_files()
        
        self.welcome_frame.grid()
        self.fetch_progress.grid()
        self.fetch_progress.start()
        self.welcome_label.configure(text="Fetching file list, please wait...")

        thread = threading.Thread(target=self._fetch_files_worker, args=(raw,), daemon=True)
        thread.start()
        self._ensure_queue_processing()

    def _fetch_files_worker(self, raw: str):
        try:
            item_id = parse_item_id(raw)
            download_url = build_download_url(item_id)
            html = fetch_directory_listing(download_url)
            title, files = parse_directory_listing(html, base_url=download_url)
            self.ui_queue.put(("files_loaded", item_id, download_url, title, files))
        except (requests.RequestException, ValueError) as exc:
            self.ui_queue.put(("files_error", str(exc)))

    def _download_worker(self, selected: list[tuple[int, dict]], target_folder: str):
        self.ui_queue.put(("download_started", len(selected)))
        max_workers = max(1, min(len(selected), 16))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    self._download_single,
                    index,
                    row["item"],
                    target_folder,
                )
                for index, row in selected
            ]
            for future in as_completed(futures):
                future.result()
        self.ui_queue.put(("download_complete",))

    def _download_single(self, index: int, item: FileItem, target_folder: str):
        self.ui_queue.put(("file_status", index, "Downloading"))
        parsed = urlparse(item.url)
        filename = unquote(os.path.basename(parsed.path) or item.name)
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        destination = os.path.join(target_folder, safe_filename)
        try:
            with requests.get(
                item.url, stream=True, timeout=30, headers=DEFAULT_HEADERS
            ) as response:
                response.raise_for_status()
                size_header = response.headers.get("Content-Length")
                if size_header and size_header.isdigit():
                    self.ui_queue.put(("total_bytes", int(size_header)))
                with open(destination, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        self.ui_queue.put(("progress", len(chunk)))
            self.ui_queue.put(("file_status", index, "Done"))
        except (requests.RequestException, OSError) as exc:
            self.ui_queue.put(("file_status", index, f"Failed: {exc}"))

    def _ensure_queue_processing(self):
        if self.queue_polling:
            return
        self.queue_polling = True
        self.master.after(100, self._process_queue)

    def _process_queue(self):
        while not self.ui_queue.empty():
            event = self.ui_queue.get()
            if not event:
                continue
            event_type = event[0]
            if event_type == "files_loaded":
                self.fetch_progress.stop()
                self.welcome_frame.grid_remove()
                _, item_id, download_url, title, files = event
                self.item_id = item_id
                self.download_url = download_url
                self.item_title = title
                self._render_files(title, files)
                self._fetch_debounce_id = None
                self.fetch_in_progress = False
                self._set_status(f"Found {len(files)} files.")
                self.fetch_btn.configure(state="normal")
                self.download_btn.configure(state="normal")
            elif event_type == "files_error":
                self.fetch_progress.stop()
                self.fetch_progress.grid_remove()
                self.welcome_label.configure(text="Error fetching files.")
                _, message = event
                self._fetch_debounce_id = None
                self.fetch_in_progress = False
                self._set_status(f"Error: {message}")
                self.fetch_btn.configure(state="normal")
                messagebox.showerror("Error", message)
            elif event_type == "download_started":
                _, total_files = event
                self.progress_total_bytes = 0
                self.progress_downloaded_bytes = 0
                self.download_start_time = time.time()
                self.completed_files = 0
                self.total_files = total_files
                self.progress_bar.set(0)
                self.progress_label.configure(text="Downloaded: 0 B")
                self.speed_label.configure(text="Speed: 0 B/s")
                self.progress_frame.grid()
            elif event_type == "total_bytes":
                _, size = event
                self.progress_total_bytes += size
            elif event_type == "progress":
                _, size = event
                self.progress_downloaded_bytes += size
                self._update_progress()
            elif event_type == "file_status":
                _, index, status = event
                if 0 <= index < len(self.file_rows):
                    self.file_rows[index]["status_label"].configure(text=status)
                if status.startswith("Done") or status.startswith("Failed"):
                    self.completed_files += 1
                    self._update_progress()
            elif event_type == "download_complete":
                self.download_in_progress = False
                self.fetch_btn.configure(state="normal")
                self.download_btn.configure(state="normal")
                messagebox.showinfo("Done", "Selected files downloaded.")
        if self.download_in_progress or self.fetch_in_progress or not self.ui_queue.empty():
            self.master.after(100, self._process_queue)
        else:
            self.queue_polling = False

    def _update_progress(self):
        downloaded = self.progress_downloaded_bytes
        total = self.progress_total_bytes
        if total > 0:
            progress = min(1.0, downloaded / total)
            self.progress_bar.set(progress)
            progress_text = f"Downloaded: {format_bytes(downloaded)} / {format_bytes(total)}"
        else:
            progress_text = f"Downloaded: {format_bytes(downloaded)}"
        file_text = f"{self.completed_files}/{self.total_files} files"
        self.progress_label.configure(text=f"{progress_text} ({file_text})")
        if self.download_start_time:
            elapsed = max(0.1, time.time() - self.download_start_time)
            speed = downloaded / elapsed
            self.speed_label.configure(text=f"Speed: {format_bytes(int(speed))}/s")

    def _render_files(self, title: str, files: list[FileItem]):
        self.files_title_label.configure(text=f"Files for {title}")
        for child in self.files_scroll.winfo_children():
            child.destroy()
        self.file_rows = []
        for index, item in enumerate(files):
            row_frame = ctk.CTkFrame(self.files_scroll)
            row_frame.grid(row=index, column=0, sticky="ew", padx=4, pady=2)
            row_frame.columnconfigure(0, weight=1)
            var = tk.BooleanVar(value=True)
            label_text = item.name
            if item.size_label:
                label_text = f"{item.name} ({item.size_label})"
            checkbox = ctk.CTkCheckBox(row_frame, text=label_text, variable=var)
            checkbox.grid(row=0, column=0, sticky="w", padx=4)
            status_label = ctk.CTkLabel(row_frame, text="Ready")
            status_label.grid(row=0, column=1, sticky="e", padx=6)
            self.file_rows.append(
                {"var": var, "item": item, "status_label": status_label, "frame": row_frame}
            )
        self.files_scroll.columnconfigure(0, weight=1)
        self.search_var.set("")
        self.files_frame.grid()
        self.download_btn.configure(state="normal")

    def _clear_files(self):
        for child in self.files_scroll.winfo_children():
            child.destroy()
        self.file_rows = []
        self.files_frame.grid_remove()
