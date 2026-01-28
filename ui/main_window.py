"""Spotify-like main window with WMP/Winamp-style visualization."""

from __future__ import annotations

import json
import random
from pathlib import Path
from tkinter import filedialog, colorchooser
import tkinter as tk

import customtkinter as ctk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap, to_rgb, to_hex

from Lumina.audio_engine import AudioEngine
from Lumina.visualizer import Visualizer

# Default colors
DEFAULT_ACCENT = "#1db954"
BG_DARK = "#0a0a0a"
BG = "#121212"
BG_LIGHT = "#181818"
SIDEBAR_BG = "#000000"
CARD = "#282828"
CARD_HOVER = "#3e3e3e"
TEXT = "#ffffff"
TEXT_DIM = "#b3b3b3"
TEXT_MUTED = "#727272"

# Settings file
SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings.json"

FFT_SIZE = 2048
VIZ_BARS_2D = 48
VIZ_BARS_3D = 20  # Fewer bars for 3D performance
VIZ_UPDATE_MS = 16  # ~60fps
CHUNK_LEN = FFT_SIZE


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {"accent": DEFAULT_ACCENT, "viz_3d": True}


def save_settings(settings: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
    except Exception:
        pass


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lumina")
        self.geometry("1200x800")
        self.minsize(900, 650)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        # Load settings
        self._settings = load_settings()
        self._accent = self._settings.get("accent", DEFAULT_ACCENT)
        self._accent_hover = self._lighten_color(self._accent, 0.15)
        self._viz_3d = self._settings.get("viz_3d", True)

        self.audio = AudioEngine()
        self.viz = Visualizer(fft_size=FFT_SIZE)
        self._viz_job: str | None = None
        self._updating_slider = False
        self._current_file: str = ""
        
        # Playlist
        self._playlist: list[Path] = []
        self._playlist_index: int = -1
        self._shuffle = False
        self._loop = False  # False=no loop, True=loop playlist
        self._shuffle_order: list[int] = []
        
        # Smooth animation state
        self._viz_bars = VIZ_BARS_3D if self._viz_3d else VIZ_BARS_2D
        self._display_heights = np.zeros(self._viz_bars, dtype=np.float32)
        self._peak_heights = np.zeros(self._viz_bars, dtype=np.float32)
        self._peak_decay = np.zeros(self._viz_bars, dtype=np.float32)
        
        # 3D view angle (preserved during playback)
        self._view_elev = 25
        self._view_azim = -50

        self._build_ui()
        self._bind_shortcuts()
        self._update_position_display()
        self.audio.set_position_callback(self._on_position)

    def _lighten_color(self, hex_color: str, amount: float) -> str:
        """Lighten a hex color by a percentage."""
        try:
            r, g, b = to_rgb(hex_color)
            r = min(1.0, r + amount)
            g = min(1.0, g + amount)
            b = min(1.0, b + amount)
            return to_hex((r, g, b))
        except Exception:
            return hex_color

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        self.bind("<space>", lambda e: self._toggle_play())
        self.bind("<Left>", lambda e: self._prev_track())
        self.bind("<Right>", lambda e: self._next_track())
        self.bind("<Up>", lambda e: self._volume_up())
        self.bind("<Down>", lambda e: self._volume_down())
        self.bind("<m>", lambda e: self._toggle_mute())
        self.bind("<M>", lambda e: self._toggle_mute())
        self.bind("<s>", lambda e: self._toggle_shuffle())
        self.bind("<S>", lambda e: self._toggle_shuffle())
        self.bind("<l>", lambda e: self._toggle_loop())
        self.bind("<L>", lambda e: self._toggle_loop())
        self.focus_set()

    def _volume_up(self) -> None:
        current = self.audio.get_volume()
        new_vol = min(1.0, current + 0.05)
        self.audio.set_volume(new_vol)
        self.vol_slider.set(new_vol)
        self._update_vol_icon(new_vol)

    def _volume_down(self) -> None:
        current = self.audio.get_volume()
        new_vol = max(0.0, current - 0.05)
        self.audio.set_volume(new_vol)
        self.vol_slider.set(new_vol)
        self._update_vol_icon(new_vol)

    def _toggle_mute(self) -> None:
        if not hasattr(self, '_pre_mute_vol'):
            self._pre_mute_vol = 1.0
        current = self.audio.get_volume()
        if current > 0:
            self._pre_mute_vol = current
            self.audio.set_volume(0)
            self.vol_slider.set(0)
            self._update_vol_icon(0)
        else:
            self.audio.set_volume(self._pre_mute_vol)
            self.vol_slider.set(self._pre_mute_vol)
            self._update_vol_icon(self._pre_mute_vol)

    def _update_vol_icon(self, v: float) -> None:
        if v == 0:
            self.vol_label.configure(text="🔇")
        elif v < 0.5:
            self.vol_label.configure(text="🔉")
        else:
            self.vol_label.configure(text="🔊")

    def _build_ui(self) -> None:
        self.configure(fg_color=BG_DARK)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === Left Sidebar ===
        self._sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, width=300, corner_radius=0)
        self._sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_columnconfigure(0, weight=1)
        self._sidebar.grid_rowconfigure(3, weight=1)
        
        # Logo/Title row with settings
        title_row = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 16))
        title_row.grid_columnconfigure(0, weight=1)
        
        title_left = ctk.CTkFrame(title_row, fg_color="transparent")
        title_left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_left, text="Lumina", text_color=TEXT, font=("Segoe UI Semibold", 26)).pack(anchor="w")
        ctk.CTkLabel(title_left, text="Audio Visualizer", text_color=TEXT_MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        
        # Settings button
        self._settings_btn = ctk.CTkButton(title_row, text="⚙", width=36, height=36, fg_color="transparent", hover_color=CARD, text_color=TEXT_DIM, font=("Segoe UI", 18), command=self._open_settings)
        self._settings_btn.grid(row=0, column=1, sticky="ne", pady=4)
        
        # Add files button
        btn_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        
        self._add_btn = ctk.CTkButton(btn_frame, text="+ Add Files", fg_color=self._accent, hover_color=self._accent_hover, text_color=BG_DARK, font=("Segoe UI Semibold", 13), height=36, command=self._add_files)
        self._add_btn.pack(fill="x", pady=(0, 8))
        
        # Shortcuts hint
        hint_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        hint_frame.pack(fill="x")
        ctk.CTkLabel(hint_frame, text="Space: Play  S: Shuffle  L: Loop", text_color=TEXT_MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=4)
        
        ctk.CTkLabel(btn_frame, text="PLAYLIST", text_color=TEXT_MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=8, pady=(8, 0))
        
        # Playlist area
        playlist_container = ctk.CTkFrame(self._sidebar, fg_color=BG_LIGHT, corner_radius=8)
        playlist_container.grid(row=3, column=0, sticky="nsew", padx=12, pady=(4, 12))
        playlist_container.grid_columnconfigure(0, weight=1)
        playlist_container.grid_rowconfigure(0, weight=1)
        
        # Scrollable playlist
        self._playlist_frame = ctk.CTkScrollableFrame(playlist_container, fg_color="transparent")
        self._playlist_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._playlist_frame.grid_columnconfigure(0, weight=1)
        
        self._playlist_buttons: list[ctk.CTkButton] = []

        # === Main Content ===
        main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Header with current track
        header = ctk.CTkFrame(main, fg_color="transparent", height=70)
        header.grid(row=0, column=0, sticky="ew", padx=32, pady=(20, 8))
        header.grid_propagate(False)
        
        self.track_label = ctk.CTkLabel(header, text="No track loaded", text_color=TEXT, font=("Segoe UI Semibold", 22))
        self.track_label.pack(anchor="w", pady=(8, 0))
        self.artist_label = ctk.CTkLabel(header, text="Add files to get started", text_color=TEXT_DIM, font=("Segoe UI", 14))
        self.artist_label.pack(anchor="w")

        # === Visualization Area ===
        self._viz_container = ctk.CTkFrame(main, fg_color=BG, corner_radius=16)
        self._viz_container.grid(row=1, column=0, sticky="nsew", padx=32, pady=(8, 24))
        self._viz_container.grid_columnconfigure(0, weight=1)
        self._viz_container.grid_rowconfigure(0, weight=1)

        self._create_visualizer()

        # === Bottom Now Playing Bar ===
        now_playing = ctk.CTkFrame(self, fg_color=BG_LIGHT, height=130, corner_radius=0)
        now_playing.grid(row=1, column=0, columnspan=2, sticky="sew")
        now_playing.grid_propagate(False)
        now_playing.grid_columnconfigure(1, weight=1)
        now_playing.grid_rowconfigure(0, weight=1)

        # Left: Track info
        info_frame = ctk.CTkFrame(now_playing, fg_color="transparent", width=280)
        info_frame.grid(row=0, column=0, sticky="nsw", padx=24, pady=24)
        info_frame.grid_propagate(False)
        
        self.np_title = ctk.CTkLabel(info_frame, text="", text_color=TEXT, font=("Segoe UI Semibold", 14), anchor="w")
        self.np_title.pack(anchor="w", pady=(20, 2))
        self.np_artist = ctk.CTkLabel(info_frame, text="", text_color=TEXT_DIM, font=("Segoe UI", 12), anchor="w")
        self.np_artist.pack(anchor="w")

        # Center: Transport controls
        center = ctk.CTkFrame(now_playing, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", pady=16)
        center.grid_rowconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=0)
        center.grid_columnconfigure(0, weight=1)
        
        # Buttons row
        btns = ctk.CTkFrame(center, fg_color="transparent")
        btns.grid(row=0, column=0, sticky="s", pady=(0, 8))
        
        # Shuffle button
        self.btn_shuffle = ctk.CTkButton(btns, text="🔀", width=40, height=40, fg_color="transparent", hover_color=CARD, text_color=TEXT_MUTED, font=("Segoe UI", 16), command=self._toggle_shuffle)
        self.btn_shuffle.pack(side="left", padx=4)
        
        self.btn_prev = ctk.CTkButton(btns, text="⏮", width=44, height=44, fg_color="transparent", hover_color=CARD, text_color=self._accent, font=("Segoe UI", 20), command=self._prev_track)
        self.btn_prev.pack(side="left", padx=8)
        
        self.btn_play = ctk.CTkButton(btns, text="▶", width=56, height=56, fg_color=self._accent, hover_color=self._accent_hover, text_color=BG_DARK, font=("Segoe UI", 22), corner_radius=28, command=self._toggle_play)
        self.btn_play.pack(side="left", padx=14)
        
        self.btn_next = ctk.CTkButton(btns, text="⏭", width=44, height=44, fg_color="transparent", hover_color=CARD, text_color=self._accent, font=("Segoe UI", 20), command=self._next_track)
        self.btn_next.pack(side="left", padx=8)
        
        # Loop button
        self.btn_loop = ctk.CTkButton(btns, text="🔁", width=40, height=40, fg_color="transparent", hover_color=CARD, text_color=TEXT_MUTED, font=("Segoe UI", 16), command=self._toggle_loop)
        self.btn_loop.pack(side="left", padx=4)
        
        # Progress row
        progress_frame = ctk.CTkFrame(center, fg_color="transparent")
        progress_frame.grid(row=1, column=0, sticky="sew", padx=10, pady=(0, 16))
        progress_frame.grid_columnconfigure(1, weight=1)
        
        self.lbl_time_current = ctk.CTkLabel(progress_frame, text="0:00", text_color=TEXT_DIM, font=("Segoe UI", 11), width=50)
        self.lbl_time_current.grid(row=0, column=0, padx=(0, 10))
        
        self.slider = ctk.CTkSlider(progress_frame, from_=0, to=1, number_of_steps=1000, height=6, button_length=14, button_color=TEXT, button_hover_color=self._accent, progress_color=TEXT, fg_color=CARD, width=450, command=self._on_slider)
        self.slider.grid(row=0, column=1, sticky="ew")
        self.slider.set(0)
        
        self.lbl_time_total = ctk.CTkLabel(progress_frame, text="0:00", text_color=TEXT_DIM, font=("Segoe UI", 11), width=50)
        self.lbl_time_total.grid(row=0, column=2, padx=(10, 0))

        # Right: Volume
        vol_frame = ctk.CTkFrame(now_playing, fg_color="transparent", width=200)
        vol_frame.grid(row=0, column=2, sticky="nse", padx=24, pady=24)
        vol_frame.grid_propagate(False)
        
        vol_inner = ctk.CTkFrame(vol_frame, fg_color="transparent")
        vol_inner.pack(expand=True, pady=30)
        
        self.vol_label = ctk.CTkLabel(vol_inner, text="🔊", text_color=TEXT_DIM, font=("Segoe UI", 16))
        self.vol_label.pack(side="left", padx=(0, 10))
        
        self.vol_slider = ctk.CTkSlider(vol_inner, from_=0, to=1, number_of_steps=100, height=5, width=130, button_length=12, button_color=TEXT, button_hover_color=self._accent, progress_color=TEXT_DIM, fg_color=CARD, command=self._on_volume)
        self.vol_slider.pack(side="left")
        self.vol_slider.set(1.0)

    def _create_visualizer(self) -> None:
        """Create the matplotlib visualizer (2D or 3D based on settings)."""
        # Clear existing
        for widget in self._viz_container.winfo_children():
            widget.destroy()
        
        self._viz_bars = VIZ_BARS_3D if self._viz_3d else VIZ_BARS_2D
        self._display_heights = np.zeros(self._viz_bars, dtype=np.float32)
        self._peak_heights = np.zeros(self._viz_bars, dtype=np.float32)
        self._peak_decay = np.zeros(self._viz_bars, dtype=np.float32)
        
        if self._viz_3d:
            self._fig = Figure(figsize=(10, 5), facecolor=BG, dpi=60)
            self._ax = self._fig.add_subplot(111, projection='3d')
        else:
            self._fig = Figure(figsize=(10, 4), facecolor=BG, dpi=80)
            self._ax = self._fig.add_subplot(111)
        
        self._setup_visualizer()
        
        viz_frame = tk.Frame(self._viz_container, bg=BG)
        viz_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._canvas = FigureCanvasTkAgg(self._fig, master=viz_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

    def _setup_visualizer(self) -> None:
        """Configure the visualizer based on mode."""
        self._ax.clear()
        self._ax.set_facecolor(BG)
        self._fig.patch.set_facecolor(BG)
        self._update_colormap()
        
        if self._viz_3d:
            # 3D setup
            self._ax.set_axis_off()
            self._ax.xaxis.pane.fill = False
            self._ax.yaxis.pane.fill = False
            self._ax.zaxis.pane.fill = False
            self._ax.xaxis.pane.set_edgecolor('none')
            self._ax.yaxis.pane.set_edgecolor('none')
            self._ax.zaxis.pane.set_edgecolor('none')
            self._ax.view_init(elev=self._view_elev, azim=self._view_azim)
            self._ax.set_xlim(-1, self._viz_bars + 1)
            self._ax.set_ylim(-0.5, 1.5)
            self._ax.set_zlim(-0.25, 1.1)
        else:
            # 2D setup
            self._ax.set_xlim(-0.5, self._viz_bars - 0.5)
            self._ax.set_ylim(-0.25, 1.15)
            self._ax.axis("off")
            
            # Main bars
            self._bars = self._ax.bar(
                range(self._viz_bars), [0.01] * self._viz_bars, 
                width=0.8, color=[self._cmap(0.3)] * self._viz_bars,
                edgecolor='none'
            )
            
            # Reflection bars
            self._reflections = self._ax.bar(
                range(self._viz_bars), [0.01] * self._viz_bars,
                width=0.8, color=[(*to_rgb(self._cmap(0.3)), 0.2)] * self._viz_bars,
                edgecolor='none', bottom=[-0.01] * self._viz_bars
            )
            
            # Peak indicators
            self._peaks = self._ax.bar(
                range(self._viz_bars), [0.015] * self._viz_bars,
                width=0.8, color='#ffffff', alpha=0.9,
                edgecolor='none', bottom=[0] * self._viz_bars
            )
        
        self._fig.tight_layout(pad=0)

    def _update_colormap(self) -> None:
        """Create colormap from accent color."""
        try:
            r, g, b = to_rgb(self._accent)
            colors = [
                (r * 0.3, g * 0.3, b * 0.3),
                (r * 0.6, g * 0.6, b * 0.6),
                self._accent,
                (min(1, r * 1.3), min(1, g * 1.3), min(1, b * 1.3)),
                (min(1, r * 1.5 + 0.2), min(1, g * 1.5 + 0.2), min(1, b * 1.5 + 0.2)),
            ]
            self._cmap = LinearSegmentedColormap.from_list('accent', colors)
        except Exception:
            self._cmap = LinearSegmentedColormap.from_list('default', ['#004400', '#00ff00', '#ffff00'])

    def _open_settings(self) -> None:
        """Open settings dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("400x280")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=BG_DARK)
        
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 280) // 2
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(dialog, text="Settings", text_color=TEXT, font=("Segoe UI Semibold", 20)).pack(pady=(24, 16))
        
        # Theme color section
        color_frame = ctk.CTkFrame(dialog, fg_color=BG_LIGHT, corner_radius=12)
        color_frame.pack(fill="x", padx=24, pady=8)
        
        color_inner = ctk.CTkFrame(color_frame, fg_color="transparent")
        color_inner.pack(fill="x", padx=16, pady=12)
        
        color_row = ctk.CTkFrame(color_inner, fg_color="transparent")
        color_row.pack(fill="x")
        
        ctk.CTkLabel(color_row, text="Theme Color", text_color=TEXT, font=("Segoe UI", 13)).pack(side="left")
        
        self._color_preview = ctk.CTkFrame(color_row, fg_color=self._accent, width=32, height=32, corner_radius=6)
        self._color_preview.pack(side="right")
        
        ctk.CTkButton(color_row, text="Change", fg_color=CARD, hover_color=CARD_HOVER, text_color=TEXT, font=("Segoe UI", 11), height=32, width=80, command=lambda: self._pick_color(dialog)).pack(side="right", padx=8)
        
        # Visualizer mode section
        viz_frame = ctk.CTkFrame(dialog, fg_color=BG_LIGHT, corner_radius=12)
        viz_frame.pack(fill="x", padx=24, pady=8)
        
        viz_inner = ctk.CTkFrame(viz_frame, fg_color="transparent")
        viz_inner.pack(fill="x", padx=16, pady=12)
        
        viz_row = ctk.CTkFrame(viz_inner, fg_color="transparent")
        viz_row.pack(fill="x")
        
        ctk.CTkLabel(viz_row, text="Visualizer Mode", text_color=TEXT, font=("Segoe UI", 13)).pack(side="left")
        
        self._viz_switch = ctk.CTkSwitch(viz_row, text="3D", onvalue=True, offvalue=False, command=lambda: self._toggle_viz_mode(dialog), fg_color=CARD, progress_color=self._accent, button_color=TEXT)
        self._viz_switch.pack(side="right")
        if self._viz_3d:
            self._viz_switch.select()
        
        ctk.CTkLabel(viz_inner, text="2D mode is faster, 3D mode looks better", text_color=TEXT_MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
        
        # Close button
        ctk.CTkButton(dialog, text="Close", fg_color=CARD, hover_color=CARD_HOVER, text_color=TEXT, font=("Segoe UI", 13), height=40, width=120, command=dialog.destroy).pack(pady=20)

    def _toggle_viz_mode(self, dialog: ctk.CTkToplevel | None = None) -> None:
        """Toggle between 2D and 3D visualizer."""
        self._viz_3d = not self._viz_3d
        self._settings["viz_3d"] = self._viz_3d
        save_settings(self._settings)
        
        # Stop current viz and recreate
        self._stop_visualizer()
        self._create_visualizer()
        
        # Restart if playing
        if self.audio.is_playing():
            self._start_viz()

    def _pick_color(self, dialog: ctk.CTkToplevel) -> None:
        """Open color picker."""
        color = colorchooser.askcolor(color=self._accent, title="Choose Theme Color")
        if color[1]:
            self._apply_color(color[1], dialog)

    def _apply_color(self, color: str, dialog: ctk.CTkToplevel | None = None) -> None:
        """Apply new accent color."""
        self._accent = color
        self._accent_hover = self._lighten_color(color, 0.15)
        
        self._settings["accent"] = color
        save_settings(self._settings)
        
        # Update UI elements
        self._add_btn.configure(fg_color=self._accent, hover_color=self._accent_hover)
        self.slider.configure(button_hover_color=self._accent)
        self.vol_slider.configure(button_hover_color=self._accent)
        self.btn_play.configure(fg_color=self._accent, hover_color=self._accent_hover)
        self.btn_prev.configure(text_color=self._accent)
        self.btn_next.configure(text_color=self._accent)
        
        # Update shuffle/loop if active
        if self._shuffle:
            self.btn_shuffle.configure(text_color=self._accent)
        if self._loop:
            self.btn_loop.configure(text_color=self._accent)
        
        self._update_colormap()
        
        if dialog and hasattr(self, '_color_preview'):
            self._color_preview.configure(fg_color=color)
        
        self._refresh_playlist_ui()

    def _toggle_shuffle(self) -> None:
        """Toggle shuffle mode."""
        self._shuffle = not self._shuffle
        if self._shuffle:
            self.btn_shuffle.configure(text_color=self._accent)
            self._generate_shuffle_order()
        else:
            self.btn_shuffle.configure(text_color=TEXT_MUTED)
            self._shuffle_order = []
        self.focus_set()

    def _toggle_loop(self) -> None:
        """Toggle loop mode."""
        self._loop = not self._loop
        if self._loop:
            self.btn_loop.configure(text_color=self._accent)
        else:
            self.btn_loop.configure(text_color=TEXT_MUTED)
        self.focus_set()

    def _generate_shuffle_order(self) -> None:
        """Generate a random shuffle order for the playlist."""
        if not self._playlist:
            self._shuffle_order = []
            return
        self._shuffle_order = list(range(len(self._playlist)))
        random.shuffle(self._shuffle_order)
        # Move current track to front if playing
        if self._playlist_index >= 0 and self._playlist_index in self._shuffle_order:
            self._shuffle_order.remove(self._playlist_index)
            self._shuffle_order.insert(0, self._playlist_index)

    def _get_next_track_index(self) -> int:
        """Get the next track index based on shuffle/loop settings."""
        if not self._playlist:
            return -1
        
        if self._shuffle and self._shuffle_order:
            try:
                current_shuffle_pos = self._shuffle_order.index(self._playlist_index)
                if current_shuffle_pos < len(self._shuffle_order) - 1:
                    return self._shuffle_order[current_shuffle_pos + 1]
                elif self._loop:
                    return self._shuffle_order[0]
            except ValueError:
                return self._shuffle_order[0] if self._shuffle_order else -1
        else:
            if self._playlist_index < len(self._playlist) - 1:
                return self._playlist_index + 1
            elif self._loop:
                return 0
        return -1

    def _get_prev_track_index(self) -> int:
        """Get the previous track index based on shuffle/loop settings."""
        if not self._playlist:
            return -1
        
        if self._shuffle and self._shuffle_order:
            try:
                current_shuffle_pos = self._shuffle_order.index(self._playlist_index)
                if current_shuffle_pos > 0:
                    return self._shuffle_order[current_shuffle_pos - 1]
                elif self._loop:
                    return self._shuffle_order[-1]
            except ValueError:
                return self._shuffle_order[0] if self._shuffle_order else -1
        else:
            if self._playlist_index > 0:
                return self._playlist_index - 1
            elif self._loop:
                return len(self._playlist) - 1
        return -1

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Add audio files",
            filetypes=[
                ("Audio Files", "*.wav *.flac *.ogg"),
                ("WAV", "*.wav"),
                ("FLAC", "*.flac"),
                ("OGG", "*.ogg"),
                ("All Files", "*.*"),
            ],
        )
        for p in paths:
            path = Path(p)
            if path not in self._playlist:
                self._playlist.append(path)
        self._refresh_playlist_ui()
        
        if self._playlist_index < 0 and self._playlist:
            self._select_track(0)
        
        if self._shuffle:
            self._generate_shuffle_order()
        
        self.focus_set()

    def _refresh_playlist_ui(self) -> None:
        for btn in self._playlist_buttons:
            btn.destroy()
        self._playlist_buttons.clear()
        
        for i, path in enumerate(self._playlist):
            is_current = (i == self._playlist_index)
            btn = ctk.CTkButton(
                self._playlist_frame,
                text=path.stem,
                fg_color=CARD if is_current else "transparent",
                hover_color=CARD_HOVER,
                text_color=self._accent if is_current else TEXT,
                font=("Segoe UI", 12),
                height=36,
                anchor="w",
                command=lambda idx=i: self._select_track(idx)
            )
            btn.grid(row=i, column=0, sticky="ew", pady=2)
            self._playlist_buttons.append(btn)

    def _stop_visualizer(self) -> None:
        """Stop the visualization loop."""
        if self._viz_job:
            self.after_cancel(self._viz_job)
            self._viz_job = None

    def _select_track(self, idx: int, auto_play: bool = False) -> None:
        if 0 <= idx < len(self._playlist):
            self._stop_visualizer()
            self.audio.stop()
            
            self._playlist_index = idx
            path = self._playlist[idx]
            if self.audio.open(str(path)):
                self._current_file = str(path)
                self.track_label.configure(text=path.stem)
                self.np_title.configure(text=path.stem)
                self.np_artist.configure(text=path.suffix.upper()[1:] + " Audio")
                
                self.viz = Visualizer(fft_size=FFT_SIZE)
                self._display_heights.fill(0)
                self._peak_heights.fill(0)
                self._peak_decay.fill(0)
                self._update_position_display()
                self._refresh_playlist_ui()
                
                if auto_play:
                    self.audio.play()
                    self.btn_play.configure(text="⏸")
                    self.artist_label.configure(text="Now Playing")
                    self._start_viz()
                else:
                    self.artist_label.configure(text="Ready to play")
        
        self.focus_set()

    def _prev_track(self) -> None:
        next_idx = self._get_prev_track_index()
        if next_idx >= 0:
            was_playing = self.audio.is_playing()
            self._select_track(next_idx, auto_play=was_playing)

    def _next_track(self) -> None:
        next_idx = self._get_next_track_index()
        if next_idx >= 0:
            was_playing = self.audio.is_playing()
            self._select_track(next_idx, auto_play=was_playing)

    def _toggle_play(self) -> None:
        if self.audio.is_playing():
            self.audio.pause()
            self.btn_play.configure(text="▶")
            self.artist_label.configure(text="Paused")
        else:
            if self._playlist_index < 0 and self._playlist:
                self._select_track(0)
            self.audio.play()
            self.btn_play.configure(text="⏸")
            self.artist_label.configure(text="Now Playing")
            self._start_viz()

    def _on_slider(self, v: float) -> None:
        if self._updating_slider:
            return
        dur = self.audio.duration_sec()
        if dur <= 0:
            return
        self.audio.seek(float(v) * dur)
        self.focus_set()

    def _on_volume(self, v: float) -> None:
        self.audio.set_volume(float(v))
        self._update_vol_icon(v)

    def _on_position(self, cur: float, dur: float) -> None:
        self.after(0, lambda: self._update_slider(cur, dur))

    def _update_slider(self, cur: float, dur: float) -> None:
        if dur > 0:
            self._updating_slider = True
            try:
                self.slider.set(cur / dur)
            finally:
                self._updating_slider = False
        self._update_position_display()
        
        # Auto-advance to next track when song ends
        if dur > 0 and cur >= dur - 0.1:
            next_idx = self._get_next_track_index()
            if next_idx >= 0:
                self.after(100, lambda: self._select_track(next_idx, auto_play=True))

    def _update_position_display(self) -> None:
        cur = self.audio.position_sec()
        dur = self.audio.duration_sec()
        self.lbl_time_current.configure(text=_fmt(cur))
        self.lbl_time_total.configure(text=_fmt(dur))
        if not self.audio.is_playing() and dur > 0:
            self._updating_slider = True
            try:
                self.slider.set(cur / dur)
            finally:
                self._updating_slider = False

    def _start_viz(self) -> None:
        if self._viz_job:
            self.after_cancel(self._viz_job)
        self._tick_viz()

    def _tick_viz(self) -> None:
        chunk = self.audio.get_pcm_chunk(CHUNK_LEN)
        if chunk is not None and len(chunk) >= FFT_SIZE:
            self.viz.push(chunk)
        
        target = self.viz.get_magnitudes(self._viz_bars)
        
        # Smooth animation
        attack = 0.5
        decay = 0.92
        for i in range(self._viz_bars):
            if target[i] > self._display_heights[i]:
                self._display_heights[i] = attack * target[i] + (1 - attack) * self._display_heights[i]
            else:
                self._display_heights[i] = decay * self._display_heights[i]
            
            if self._display_heights[i] > self._peak_heights[i]:
                self._peak_heights[i] = self._display_heights[i]
                self._peak_decay[i] = 0
            else:
                self._peak_decay[i] += 0.008
                self._peak_heights[i] = max(0, self._peak_heights[i] - self._peak_decay[i])
        
        if self._viz_3d:
            self._draw_3d()
        else:
            self._draw_2d()
        
        self._canvas.draw_idle()
        
        if self.audio.is_playing():
            self._viz_job = self.after(VIZ_UPDATE_MS, self._tick_viz)
        else:
            self._viz_job = None

    def _draw_3d(self) -> None:
        """Draw optimized 3D visualization while preserving user rotation."""
        # Save current view angle before clearing
        self._view_elev = self._ax.elev
        self._view_azim = self._ax.azim
        
        self._ax.clear()
        self._ax.set_facecolor(BG)
        self._ax.set_axis_off()
        
        # Restore view angle (preserves user rotation)
        self._ax.view_init(elev=self._view_elev, azim=self._view_azim)
        self._ax.set_xlim(-1, self._viz_bars + 1)
        self._ax.set_ylim(-0.5, 1.5)
        self._ax.set_zlim(-0.25, 1.1)
        
        for i in range(self._viz_bars):
            h = max(0.03, self._display_heights[i])
            color = self._cmap(min(1.0, h * 1.3))
            
            # Main bar
            self._ax.bar3d(i, 0, 0, 0.85, 0.6, h, color=color, alpha=0.95, shade=True, edgecolor='none')
            
            # Reflection/shadow (mirrored below, faded)
            ref_h = h * 0.3
            ref_color = to_rgb(color)
            self._ax.bar3d(i, 0, -ref_h - 0.02, 0.85, 0.6, ref_h, color=(*ref_color, 0.18), shade=False, edgecolor='none')

    def _draw_2d(self) -> None:
        """Draw fast 2D visualization."""
        for i, (bar, ref_bar, peak_bar, h, ph) in enumerate(
            zip(self._bars, self._reflections, self._peaks, self._display_heights, self._peak_heights)
        ):
            h_val = max(0.02, h)
            color = self._cmap(min(1.0, h * 1.3))
            
            bar.set_height(h_val)
            bar.set_color(color)
            
            ref_h = h_val * 0.3
            ref_bar.set_height(ref_h)
            ref_bar.set_y(-ref_h - 0.01)
            ref_color = to_rgb(color)
            ref_bar.set_color((*ref_color, 0.2))
            
            peak_bar.set_y(ph)


def _fmt(sec: float) -> str:
    m = int(sec) // 60
    s = int(sec) % 60
    return f"{m}:{s:02d}"


def run() -> None:
    app = MainWindow()
    app.mainloop()
