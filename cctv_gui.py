#!/usr/bin/env python3
"""Secure GUI for interacting with home CCTV systems."""

from __future__ import annotations

import argparse
import threading
from dataclasses import dataclass
from typing import Optional
from urllib import error

from cctv import (
    DEFAULT_SNAPSHOT_PATH,
    DEFAULT_STATUS_PATH,
    SwannClient,
    SwannConfig,
    render_content,
    parse_channel,
    parse_port,
    parse_timeout,
)


@dataclass(frozen=True)
class GUIConnectionInput:
    host: str
    username: str = ""
    password: str = ""
    port: str = ""
    https: bool = True
    timeout: str = "10"


def _normalize_optional(value: str) -> Optional[str]:
    cleaned = value.strip()
    return cleaned or None


def build_config_from_input(params: GUIConnectionInput) -> SwannConfig:
    host = params.host.strip()
    if not host:
        raise ValueError("Host is required")
    port = parse_port(params.port) if params.port.strip() else None
    timeout = parse_timeout(params.timeout.strip())
    return SwannConfig(
        host,
        _normalize_optional(params.username),
        _normalize_optional(params.password),
        port,
        params.https,
        timeout,
    )


def format_request_output(content: bytes, content_type: Optional[str]) -> str:
    is_binary, rendered = render_content(content, content_type)
    if is_binary:
        binary_content = rendered if isinstance(rendered, bytes) else content
        return binary_content.hex()
    return str(rendered)


def parse_channel_from_input(value: str) -> int:
    return parse_channel(value.strip())


def perform_formatted_request(client: SwannClient, path: str, method: str, accept: str) -> str:
    content, content_type = client.request_response(path=path, method=method, accept=accept)
    return format_request_output(content, content_type)


def run_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk
    except ModuleNotFoundError as exc:
        raise SystemExit("Tkinter is not available in this Python environment.") from exc

    class CCTVGUI:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("CCTV Secure Console")
            self.root.geometry("780x560")

            self.host_var = tk.StringVar()
            self.username_var = tk.StringVar()
            self.password_var = tk.StringVar()
            self.port_var = tk.StringVar()
            self.timeout_var = tk.StringVar(value="10")
            self.https_var = tk.BooleanVar(value=True)
            self.channel_var = tk.StringVar(value="1")
            self.snapshot_path_var = tk.StringVar(value=DEFAULT_SNAPSHOT_PATH)
            self.status_path_var = tk.StringVar(value=DEFAULT_STATUS_PATH)
            self.request_path_var = tk.StringVar(value=DEFAULT_STATUS_PATH)
            self.request_method_var = tk.StringVar(value="GET")
            self.request_accept_var = tk.StringVar(value="application/json")
            self._http_confirmed_fingerprint: Optional[tuple[str, str, str, str, str]] = None

            self._build_layout()

        def _build_layout(self) -> None:
            frame = ttk.Frame(self.root, padding=12)
            frame.pack(fill=tk.BOTH, expand=True)

            connection = ttk.LabelFrame(frame, text="Connection")
            connection.pack(fill=tk.X, pady=(0, 8))
            connection.columnconfigure(1, weight=1)

            ttk.Label(connection, text="Host").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(connection, textvariable=self.host_var).grid(row=0, column=1, sticky=tk.EW, padx=6, pady=4)

            ttk.Label(connection, text="Username").grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(connection, textvariable=self.username_var).grid(row=1, column=1, sticky=tk.EW, padx=6, pady=4)

            ttk.Label(connection, text="Password").grid(row=2, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(connection, textvariable=self.password_var, show="*").grid(row=2, column=1, sticky=tk.EW, padx=6, pady=4)

            ttk.Label(connection, text="Port").grid(row=0, column=2, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(connection, textvariable=self.port_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=6, pady=4)

            ttk.Label(connection, text="Timeout").grid(row=1, column=2, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(connection, textvariable=self.timeout_var, width=10).grid(row=1, column=3, sticky=tk.W, padx=6, pady=4)

            ttk.Checkbutton(connection, text="Use HTTPS (recommended)", variable=self.https_var).grid(
                row=2, column=2, columnspan=2, sticky=tk.W, padx=6, pady=4
            )

            actions = ttk.LabelFrame(frame, text="Actions")
            actions.pack(fill=tk.X, pady=(0, 8))
            actions.columnconfigure(1, weight=1)

            ttk.Label(actions, text="Channel").grid(row=0, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(actions, textvariable=self.channel_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=6, pady=4)
            ttk.Label(actions, text="Snapshot path").grid(row=0, column=2, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(actions, textvariable=self.snapshot_path_var).grid(row=0, column=3, sticky=tk.EW, padx=6, pady=4)
            ttk.Button(actions, text="Generate Snapshot URL", command=self.generate_snapshot_url).grid(
                row=0, column=4, sticky=tk.W, padx=6, pady=4
            )

            ttk.Label(actions, text="Status path").grid(row=1, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(actions, textvariable=self.status_path_var).grid(
                row=1, column=1, columnspan=3, sticky=tk.EW, padx=6, pady=4
            )
            ttk.Button(actions, text="Fetch Status", command=self.fetch_status).grid(row=1, column=4, sticky=tk.W, padx=6, pady=4)

            ttk.Label(actions, text="Request path").grid(row=2, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(actions, textvariable=self.request_path_var).grid(row=2, column=1, sticky=tk.EW, padx=6, pady=4)
            ttk.Label(actions, text="Method").grid(row=2, column=2, sticky=tk.W, padx=6, pady=4)
            method_combo = ttk.Combobox(
                actions,
                textvariable=self.request_method_var,
                width=8,
                values=("GET", "HEAD"),
                state="readonly",
            )
            method_combo.grid(row=2, column=3, sticky=tk.W, padx=6, pady=4)
            ttk.Button(actions, text="Send Request", command=self.send_request).grid(row=2, column=4, sticky=tk.W, padx=6, pady=4)

            ttk.Label(actions, text="Accept").grid(row=3, column=0, sticky=tk.W, padx=6, pady=4)
            ttk.Entry(actions, textvariable=self.request_accept_var).grid(
                row=3, column=1, columnspan=3, sticky=tk.EW, padx=6, pady=4
            )

            output_frame = ttk.LabelFrame(frame, text="Output")
            output_frame.pack(fill=tk.BOTH, expand=True)

            self.output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=16)
            self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        def _show_output(self, text: str, clear: bool = True) -> None:
            self.output.configure(state=tk.NORMAL)
            if clear:
                self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, text)
            if not text.endswith("\n"):
                self.output.insert(tk.END, "\n")
            self.output.configure(state=tk.DISABLED)

        def _build_client(self) -> SwannClient:
            if not self.https_var.get():
                fingerprint = (
                    self.host_var.get().strip(),
                    self.port_var.get().strip(),
                    self.timeout_var.get().strip(),
                    self.username_var.get().strip(),
                    self.password_var.get(),
                )
                if self._http_confirmed_fingerprint != fingerprint:
                    proceed = messagebox.askyesno(
                        title="Disable HTTPS?",
                        message="HTTPS is recommended for secure camera access. Continue with HTTP?",
                    )
                    if not proceed:
                        raise ValueError("HTTPS is required unless explicitly confirmed.")
                    self._http_confirmed_fingerprint = fingerprint
            else:
                self._http_confirmed_fingerprint = None
            config = build_config_from_input(
                GUIConnectionInput(
                    self.host_var.get(),
                    self.username_var.get(),
                    self.password_var.get(),
                    self.port_var.get(),
                    self.https_var.get(),
                    self.timeout_var.get(),
                )
            )
            return SwannClient(config)

        def _run_network_task(self, task) -> None:
            def worker() -> None:
                try:
                    result = task()
                    self.root.after(0, lambda: self._show_output(result))
                except error.HTTPError as exc:
                    message = f"HTTP error {exc.code}: {exc.reason}"
                    self.root.after(0, lambda msg=message: messagebox.showerror("HTTP error", msg))
                except error.URLError as exc:
                    message = f"Connection error: {exc.reason}"
                    self.root.after(0, lambda msg=message: messagebox.showerror("Connection error", msg))
                except Exception as exc:  # pragma: no cover
                    detail = str(exc).strip() or exc.__class__.__name__
                    message = f"Unexpected error: {detail}"
                    self.root.after(0, lambda msg=message: messagebox.showerror("Unexpected error", msg))

            threading.Thread(target=worker, daemon=True).start()

        def generate_snapshot_url(self) -> None:
            try:
                client = self._build_client()
                channel = parse_channel_from_input(self.channel_var.get())
                snapshot_url = client.snapshot_url(channel=channel, path=self.snapshot_path_var.get())
                self._show_output(snapshot_url)
            except (ValueError, argparse.ArgumentTypeError) as exc:
                messagebox.showerror("Invalid input", str(exc))

        def fetch_status(self) -> None:
            try:
                client = self._build_client()
                status_path = self.status_path_var.get()
                self._run_network_task(lambda: client.get_status(path=status_path))
            except (ValueError, argparse.ArgumentTypeError) as exc:
                messagebox.showerror("Invalid input", str(exc))

        def send_request(self) -> None:
            try:
                client = self._build_client()
                method = self.request_method_var.get().upper()
                request_path = self.request_path_var.get()
                request_accept = self.request_accept_var.get()

                def request_task() -> str:
                    return perform_formatted_request(client, request_path, method, request_accept)

                self._run_network_task(request_task)
            except (ValueError, argparse.ArgumentTypeError) as exc:
                messagebox.showerror("Invalid input", str(exc))

    root = tk.Tk()
    CCTVGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gui())
