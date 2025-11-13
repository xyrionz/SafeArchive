#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import sys
import tkinter as tk
import customtkinter as ctk
from .widgets import Combobox, Switch
from ..configs import config


def _set_window_icon(window, ico_name="gear.ico", png_name="gear.png"):
    """Platform-safe icon setter. Looks for icons relative to this file's directory.
    - On Windows: uses .ico via iconbitmap
    - On other platforms: prefers .png via iconphoto, with a Pillow fallback to convert .ico
    If no icon files are available, it silently skips setting the icon.
    """
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # assets are located at project_root/assets/ICO/
        ico_path = os.path.normpath(os.path.join(base_dir, "..", "..", "assets", "ICO", ico_name))
        png_path = os.path.normpath(os.path.join(base_dir, "..", "..", "assets", "ICO", png_name))

        # Windows: .ico works with iconbitmap
        if sys.platform.startswith("win"):
            if os.path.exists(ico_path):
                try:
                    window.iconbitmap(ico_path)
                except Exception as e:
                    print("_set_window_icon: iconbitmap failed on Windows:", e)
        else:
            # Non-Windows: prefer PNG via iconphoto
            if os.path.exists(png_path):
                try:
                    window.iconphoto(False, tk.PhotoImage(file=png_path))
                except Exception as e:
                    print("_set_window_icon: iconphoto failed with PNG:", e)
            elif os.path.exists(ico_path):
                # Try converting ICO -> PhotoImage via Pillow
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(ico_path)
                    window.iconphoto(False, ImageTk.PhotoImage(img))
                except Exception as pil_e:
                    print("_set_window_icon: PIL conversion of ICO -> PNG failed:", pil_e)
                    print("_set_window_icon: Consider converting %s -> %s" % (ico_path, png_path))
            # else: skip quietly
    except Exception as exc:
        print("_set_window_icon: unexpected error:", exc)


class Settings:
    """
    Create a toplevel widget containing a frame with settings.
    """
    def __init__(self, App):
        self.App = App
        self.create_settings_window()
        self.create_frame()
        self.display_appearance_mode_label()
        self.create_appearance_mode_combobox()
        self.display_color_theme_label()
        self.create_color_theme_combobox()
        self.display_storage_provider_label()
        self.create_storage_provider_combobox()
        self.display_compression_method_label()
        self.create_compression_method_combobox()
        self.display_compression_level_label()
        self.create_compression_level_combobox()
        self.display_keep_my_backups_label()
        self.create_keep_my_backups_combobox()
        self.create_encryption_switch()
        self.create_notifications_switch()


    def create_settings_window(self):
        self.settings_window = tk.Toplevel(self.App)
        self.settings_window.title("Settings")
        # Increased window size for better spacing (wider)
        self.settings_window.geometry("1000x320")

        # Platform-safe icon setting (looks for assets/ICO/gear.ico or gear.png)
        _set_window_icon(self.settings_window, ico_name="gear.ico", png_name="gear.png")

        self.settings_window.resizable(False, False)  # Disable minimize/maximize buttons
        self.settings_window.configure(background=self.get_window_background())


    def create_frame(self):
        # Widened frame to match increased window size
        self.frame = ctk.CTkFrame(master=self.settings_window, corner_radius=10, height=300, width=980)
        self.frame.place(x=8, y=8)


    def get_window_background(self):
        return "#242424" if config['appearance_mode'] == "dark" else "#ebebeb"


    def display_appearance_mode_label(self):
        appearance_mode_label = ctk.CTkLabel(master=self.frame, text="Appearance Mode:", font=('Helvetica', 15))
        appearance_mode_label.place(x=10, y=20)


    def create_appearance_mode_combobox(self):
        appearance_mode_combobox_var = ctk.StringVar(value=config['appearance_mode'])
        appearance_mode_options = ["dark", "light"]
        appearance_mode_combobox = ctk.CTkComboBox(
            master=self.frame,
            width=112,
            values=appearance_mode_options,
            command=lambda choice: Combobox(key='appearance_mode', choice=choice),
            variable=appearance_mode_combobox_var
        )

        appearance_mode_combobox.place(x=160, y=20)


    def display_color_theme_label(self):
        color_theme_label = ctk.CTkLabel(master=self.frame, text="Color Theme:", font=('Helvetica', 15))
        color_theme_label.place(x=10, y=55)


    def create_color_theme_combobox(self):
        color_theme_combobox_var = ctk.StringVar(value=config['color_theme'])
        color_theme_options = ["blue", "green"]
        color_theme_combobox = ctk.CTkComboBox(
            master=self.frame,
            width=112,
            values=color_theme_options,
            command=lambda choice: Combobox(key='color_theme', choice=choice),
            variable=color_theme_combobox_var
        )

        color_theme_combobox.place(x=160, y=55)


    def display_storage_provider_label(self):
        storage_provider_label = ctk.CTkLabel(master=self.frame, text="Storage Provider:", font=('Helvetica', 15))
        storage_provider_label.place(x=10, y=90)


    def create_storage_provider_combobox(self):
        storage_provider_combobox_var = ctk.StringVar(value=config['storage_provider'])
        storage_provider_options = ["None", "Google Drive", "Dropbox", "FTP"]
        storage_provider_combobox = ctk.CTkComboBox(
            master=self.frame,
            width=112,
            values=storage_provider_options,
            command=lambda choice: Combobox(key='storage_provider', choice=choice),
            variable=storage_provider_combobox_var
        )

        storage_provider_combobox.place(x=160, y=90)


    def display_compression_method_label(self):
        compression_method_label = ctk.CTkLabel(master=self.frame, text="Compression Method:", font=('Helvetica', 15))
        compression_method_label.place(x=295, y=20)


    def create_compression_method_combobox(self):
        compression_method_combobox_var = ctk.StringVar(value=config['compression_method'])
        compression_method_options = ["ZIP_DEFLATED", "ZIP_STORED", "ZIP_LZMA", "ZIP_BZIP2"]
        compression_method_combobox = ctk.CTkComboBox(
            master=self.frame,
            width=130,
            values=compression_method_options,
            command=lambda choice: Combobox(key='compression_method', choice=choice),
            variable=compression_method_combobox_var
        )

        compression_method_combobox.place(x=465, y=20)


    def display_compression_level_label(self):
        compression_level_label = ctk.CTkLabel(master=self.frame, text="Compression Level:", font=('Helvetica', 15))
        compression_level_label.place(x=295, y=55)


    def create_compression_level_combobox(self):
        compression_level_combobox_var = ctk.StringVar(value=config['compression_level'])
        integers = list(range(1, 10))  # Create a list of integers
        compression_level_options = [str(i) for i in integers]
        compression_level_combobox = ctk.CTkComboBox(
            master=self.frame,
            width=130,
            values=compression_level_options,
            command=lambda choice: Combobox(key='compression_level', choice=choice),
            variable=compression_level_combobox_var
        )

        compression_level_combobox.place(x=465, y=55)

    def display_keep_my_backups_label(self):
        keep_my_backups_label = ctk.CTkLabel(master=self.frame, text="Keep my backups:", font=('Helvetica', 15))
        keep_my_backups_label.place(x=295, y=90)

    def create_keep_my_backups_combobox(self):
        backup_expiry_date_combobox_var = ctk.StringVar(value=config['backup_expiry_date'])
        backup_expiry_date_options = ["1 month", "3 months", "6 months", "9 months", "1 year", "Forever"]
        backup_expiry_date_combobox = ctk.CTkComboBox(
            master=self.frame,
            width=130,
            values=backup_expiry_date_options,
            command=lambda choice: Combobox(key='backup_expiry_date', choice=choice),
            variable=backup_expiry_date_combobox_var
        )

        backup_expiry_date_combobox.place(x=465, y=90)


    def create_encryption_switch(self):
        encryption_switch_var = ctk.StringVar(value="on" if config['encryption'] else "off")
        encryption_switch = ctk.CTkSwitch(
            master=self.frame,
            text="Encrypt Backups",
            font=('Helvetica', 15),
            command=lambda: Switch(key='encryption', switch_var=encryption_switch_var),
            variable=encryption_switch_var,
            onvalue="on",
            offvalue="off"
        )

        encryption_switch.place(x=295, y=130)


    def create_notifications_switch(self):
        notifications_switch_var = ctk.StringVar(value="on" if config['notifications'] else "off")
        notifications_switch = ctk.CTkSwitch(
            master=self.frame,
            text="Allow all system notifications",
            font=('Helvetica', 15),
            command=lambda: Switch(key='notifications', switch_var=notifications_switch_var),
            variable=notifications_switch_var,
            onvalue="on",
            offvalue="off"
        )

        notifications_switch.place(x=10, y=130)
