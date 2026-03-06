"""Spotify-like main window for audio playback."""

from __future__ import annotations

import json
import random
from pathlib import Path
from tkinter import filedialog, colorchooser

import customtkinter as ctk
from matplotlib.colors import to_rgb, to_hex

from Lumina.audio_engine import AudioEngine

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


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {"accent": DEFAULT_ACCENT}


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

        self.audio = AudioEngine()
        self._updating_slider = False
        self._current_file: str = ""
        
        # Playlist
        self._playlist: list[Path] = []
        self._playlist_index: int = -1
        self._shuffle = False
        self._loop = False
        self._shuffle_order: list[int] = []

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

    def _on_vol_mousewheel(self, event) -> None:
        """Handle mouse wheel on volume slider."""
        if event.delta > 0:
            self._volume_up()
        elif event.delta < 0:
            self._volume_down()

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

    def _update_vol_icon(self, vol: float) -> None:
        if vol == 0:
            self.vol_label.configure(text="🔇")
        elif vol < 0.5:
            self.vol_label.configure(text="🔉")
        else:
            self.vol_label.configure(text="🔊")

    def _build_ui(self) -> None:
        self.configure(fg_color=BG_DARK)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === Sidebar ===
        self._sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG, width=280, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsw")
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
        ctk.CTkLabel(title_left, text="Audio Player", text_color=TEXT_MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        
        # Settings button
        self._settings_btn = ctk.CTkButton(title_row, text="⚙", width=36, height=36, fg_color="transparent", hover_color=CARD, text_color=TEXT_DIM, font=("Segoe UI", 18), command=self._open_settings)
        self._settings_btn.grid(row=0, column=1, sticky="e")

        # Add files button
        self._add_btn = ctk.CTkButton(self._sidebar, text="+ Add Files", fg_color=self._accent, hover_color=self._accent_hover, text_color=TEXT, font=("Segoe UI Semibold", 13), height=42, corner_radius=21, command=self._add_files)
        self._add_btn.grid(row=1, column=0, sticky="ew", padx=20, pady=(8, 16))
        
        # Library label
        ctk.CTkLabel(self._sidebar, text="Your Library", text_color=TEXT_MUTED, font=("Segoe UI Semibold", 12)).grid(row=2, column=0, sticky="w", padx=24, pady=(8, 8))

        # Playlist
        self._playlist_frame = ctk.CTkScrollableFrame(self._sidebar, fg_color="transparent", label_text="")
        self._playlist_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        
        # Shortcuts hint
        hint = ctk.CTkLabel(self._sidebar, text="Space: Play/Pause  |  ←→: Prev/Next", text_color=TEXT_MUTED, font=("Segoe UI", 9))
        hint.grid(row=4, column=0, sticky="s", pady=(0, 12))

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

        # === Album Art / Placeholder Area ===
        self._art_container = ctk.CTkFrame(main, fg_color=BG, corner_radius=16)
        self._art_container.grid(row=1, column=0, sticky="nsew", padx=32, pady=(8, 24))
        self._art_container.grid_columnconfigure(0, weight=1)
        self._art_container.grid_rowconfigure(0, weight=1)
        
        # Placeholder with music note
        self._art_label = ctk.CTkLabel(self._art_container, text="♪", text_color=TEXT_MUTED, font=("Segoe UI", 120))
        self._art_label.grid(row=0, column=0)

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
        btn_row = ctk.CTkFrame(center, fg_color="transparent")
        btn_row.grid(row=0, column=0)
        
        self.btn_shuffle = ctk.CTkButton(btn_row, text="🔀", width=40, height=40, fg_color="transparent", hover_color=CARD, text_color=TEXT_MUTED, font=("Segoe UI", 16), command=self._toggle_shuffle)
        self.btn_shuffle.pack(side="left", padx=4)
        
        self.btn_prev = ctk.CTkButton(btn_row, text="⏮", width=48, height=48, fg_color="transparent", hover_color=CARD, text_color=self._accent, font=("Segoe UI", 22), command=self._prev_track)
        self.btn_prev.pack(side="left", padx=4)
        
        self.btn_play = ctk.CTkButton(btn_row, text="▶", width=56, height=56, fg_color=self._accent, hover_color=self._accent_hover, text_color=BG_DARK, font=("Segoe UI", 24), corner_radius=28, command=self._toggle_play)
        self.btn_play.pack(side="left", padx=8)
        
        self.btn_next = ctk.CTkButton(btn_row, text="⏭", width=48, height=48, fg_color="transparent", hover_color=CARD, text_color=self._accent, font=("Segoe UI", 22), command=self._next_track)
        self.btn_next.pack(side="left", padx=4)
        
        self.btn_loop = ctk.CTkButton(btn_row, text="🔁", width=40, height=40, fg_color="transparent", hover_color=CARD, text_color=TEXT_MUTED, font=("Segoe UI", 16), command=self._toggle_loop)
        self.btn_loop.pack(side="left", padx=4)

        # Progress bar row
        prog_row = ctk.CTkFrame(center, fg_color="transparent")
        prog_row.grid(row=1, column=0, sticky="ew", padx=60, pady=(8, 16))
        prog_row.grid_columnconfigure(1, weight=1)
        
        self.lbl_time_current = ctk.CTkLabel(prog_row, text="0:00", text_color=TEXT_MUTED, font=("Segoe UI", 11), width=45)
        self.lbl_time_current.grid(row=0, column=0, sticky="w")
        
        self.slider = ctk.CTkSlider(prog_row, from_=0, to=1, number_of_steps=1000, height=6, button_length=14, button_color=TEXT, button_hover_color=self._accent, progress_color=TEXT_DIM, fg_color=CARD, command=self._on_slider)
        self.slider.grid(row=0, column=1, sticky="ew", padx=12)
        self.slider.set(0)
        
        self.lbl_time_total = ctk.CTkLabel(prog_row, text="0:00", text_color=TEXT_MUTED, font=("Segoe UI", 11), width=45)
        self.lbl_time_total.grid(row=0, column=2, sticky="e")

        # Right: Volume
        vol_frame = ctk.CTkFrame(now_playing, fg_color="transparent", width=180)
        vol_frame.grid(row=0, column=2, sticky="nse", padx=24, pady=24)
        vol_frame.grid_propagate(False)
        
        vol_inner = ctk.CTkFrame(vol_frame, fg_color="transparent")
        vol_inner.pack(expand=True, anchor="center")
        
        self.vol_label = ctk.CTkLabel(vol_inner, text="🔊", text_color=TEXT_DIM, font=("Segoe UI", 16))
        self.vol_label.pack(side="left", padx=(0, 10))
        
        self.vol_slider = ctk.CTkSlider(vol_inner, from_=0, to=1, number_of_steps=100, height=12, width=130, button_length=14, button_color=TEXT, button_hover_color=self._accent, progress_color=TEXT_DIM, fg_color=CARD, command=self._on_volume)
        self.vol_slider.pack(side="left")
        self.vol_slider.set(1.0)
        # Bind mouse wheel to volume slider
        self.vol_slider.bind("<MouseWheel>", self._on_vol_mousewheel)
        self.vol_slider.bind("<Button-4>", lambda e: self._volume_up())
        self.vol_slider.bind("<Button-5>", lambda e: self._volume_down())

    def _open_settings(self) -> None:
        """Open settings dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Settings")
        dialog.geometry("400x200")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=BG_DARK)
        
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 200) // 2
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
        
        # Close button
        ctk.CTkButton(dialog, text="Close", fg_color=CARD, hover_color=CARD_HOVER, text_color=TEXT, font=("Segoe UI", 13), height=40, width=120, command=dialog.destroy).pack(pady=20)

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
            filetypes=[("Audio files", "*.wav *.flac *.ogg"), ("All files", "*.*")]
        )
        if paths:
            for p in paths:
                path = Path(p)
                if path not in self._playlist:
                    self._playlist.append(path)
            self._refresh_playlist_ui()
            if self._shuffle:
                self._generate_shuffle_order()
        self.focus_set()

    def _refresh_playlist_ui(self) -> None:
        for widget in self._playlist_frame.winfo_children():
            widget.destroy()
        
        for i, path in enumerate(self._playlist):
            is_selected = i == self._playlist_index
            fg = self._accent if is_selected else "transparent"
            hover = self._accent_hover if is_selected else CARD_HOVER
            text_color = BG_DARK if is_selected else TEXT
            
            btn = ctk.CTkButton(self._playlist_frame, text=path.stem, fg_color=fg, hover_color=hover, text_color=text_color, font=("Segoe UI", 12), height=36, anchor="w", corner_radius=8, command=lambda idx=i: self._select_track(idx))
            btn.pack(fill="x", pady=1)

    def _select_track(self, index: int, auto_play: bool = True) -> None:
        if 0 <= index < len(self._playlist):
            # Stop current playback
            self.audio.stop()
            
            self._playlist_index = index
            path = self._playlist[index]
            
            if self.audio.open(path):
                self._current_file = str(path)
                self.track_label.configure(text=path.stem)
                self.np_title.configure(text=path.stem)
                self.np_artist.configure(text=path.suffix.upper()[1:])
                self._update_position_display()
                self._refresh_playlist_ui()
                
                if auto_play:
                    self.audio.play()
                    self.btn_play.configure(text="⏸")
                    self.artist_label.configure(text="Now Playing")
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


def _fmt(sec: float) -> str:
    m = int(sec) // 60
    s = int(sec) % 60
    return f"{m}:{s:02d}"


def run() -> None:
    app = MainWindow()
    app.mainloop()
