#!/usr/bin/env python3

# Standard library imports
import glob
import importlib
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import stat
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkFont
import webbrowser
import zipfile

from io import BytesIO
from tkinter import messagebox, ttk
# ---------------------------------

name_App = "Xovi extensions manager"
# ----------------------------------

# Initializing the folder for the user config stored on the PC
path_Config = os.path.join(os.path.expanduser("~"), ".config", f"{name_App.replace(' ', '_').lower()}")
os.makedirs(path_Config, exist_ok=True)
# -----------------------------------------------------------------------------------------------------


# Basic resource path, in memory only
# Destroyed after application restart (works also in packaged .app/.exe files)
path_Resource = getattr(sys, "_MEIPASS", os.path.abspath("."))
# ----------------------------------------------------------------------------


# Installing dependencies from requirements.txt
dependencies = ["paramiko", "requests"]

for package in dependencies:
    try:
        importlib.import_module(package)
    except ImportError:
        print(f"Installing {package}…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", package])
# -----------------------------------------------------------------------------------------


# External library imports
import paramiko
import requests
# ------------------------


# Settings
stop_Event = threading.Event()

file_Config = os.path.join(path_Config, "config.json")
file_Translations = os.path.join(path_Resource, "translations.json")

path_Extensions = os.path.join(path_Config, "Extensions") # Aktuální složka projektu (kdybych potřeboval) -> path_Extensions = os.path.dirname(os.path.abspath(__file__))

ignored_LOAD_Main_Folder = "base/" # Ignored rows with base in update_Extension() and get_List_Extensions()
ignored_LOAD_RCC_File = False      # Ignored rows with *rcc in update_Extension()

ignored_Delete_File = ["hashtab"]    # Ignored folders in delete_Extension()
ignored_Delete_Folder = ["disabled"] # Ignored folders in delete_Extension()

ignored_GITHUB_Folders = ["images", "docs", "test"] # Ignored folders from Github in get_List_Version()

path_Xovi_Extensions = f"/home/root/xovi/exthome/qt-resource-rebuilder/"

url_Github_Page = "https://github.com/PepikVaio/reMarkable_Xovi_Extensions_Manager"
url_Repositories_Json = "https://raw.githubusercontent.com/PepikVaio/reMarkable_Xovi_Extensions_Manager/main/repositories.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Variables default
window_Loading = None
window_Log = None
window_Overlay = None
# -------------------

# Classes
class TextSpinner:
    def __init__(self, label, text_provider, debug=False, interval=100):
        self.label = label
        self.text_provider = text_provider
        self.frames = ["🐞", "🐛", "🪲", "🦋", "🪰", "🐝", "🪳"] if debug else ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.running = False
        self._after_id = None
        self.interval = interval

    def start(self):
        if not self.running:
            self.running = True
            self._animate(0)

    def stop(self):
        if self.running:
            self.running = False
            if self._after_id:
                self.label.after_cancel(self._after_id)
                self._after_id = None
            self.label.config(text="")

    def _animate(self, i):
        if self.running:
            frame = self.frames[i % len(self.frames)]
            self.label.config(text=f"{self.text_provider()} {frame}")
            self._after_id = self.label.after(self.interval, self._animate, i + 1)

    def update_text(self, new_text_provider):
        self.text_provider = new_text_provider if callable(new_text_provider) else lambda: new_text_provider
        self.label.config(text=self.text_provider() + self.frames[0])

class WindowLoading(tk.Toplevel):
    def __init__(self, parent, text="", width=300, height=100, title="", delay_ms=10):
        super().__init__(parent)

        # Change title
        title = tr["WindowLoading_Title_01"]

        # Hide the window during setup
        self.geometry(f"1x1+10000+10000")
        self.withdraw()

        # Basic window setup
        self.title(title)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.transient(parent)

        # Calculate center position
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2 - width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2 - height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Add content
        self.label = ttk.Label(self, text="", justify="center", anchor="center")
        self.label.pack(expand=True, fill="both", pady=20)

        provider = text if callable(text) else lambda: text
        self.spinner = TextSpinner(self.label, text_provider=provider)
        self.spinner.start()

        # Show the fully prepared window after delay
        self.after(delay_ms, self._show_window)

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.update_idletasks()

    def close(self):
        self.destroy()

    def focus_Gain(self):
        self.attributes("-topmost", True)
        self.lift()

    def focus_Loss(self):
        self.attributes("-topmost", False)

class WindowLog(tk.Toplevel):
    def __init__(self, parent, width=480*2, height=560, title="", x_offset=30):
        super().__init__(parent)

        # Change title
        title = tr["WindowSSH_Title_01"]

        # Hide window during setup
        self.withdraw()

        self.parent = parent
        self.width = width
        self.height = height
        self.x_offset = x_offset

        # Basic window setup
        self.title(title)
        self.overrideredirect(False)
        self.resizable(True, True)
        self.transient(parent)

        # Create Text widget
        self.text = tk.Text(self, wrap="word", height=25, width=90)
        self.text.pack(fill="both", expand=True)

        # Scrollbar
        # scrollbar = tk.Scrollbar(self, command=self.text.yview)
        # self.text.configure(yscrollcommand=scrollbar.set)
        # scrollbar.pack(side="right", fill="y")

        # Calculate position
        x = parent.winfo_rootx() + parent.winfo_width() + x_offset
        y = parent.winfo_y()
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Show the fully prepared window
        self.deiconify()

    def insert_Text(self, msg):
        self.parent.after(0, lambda: (self.text.insert("end", msg + "\n"), self.text.see("end")))

    def close(self):
        self.destroy()

class WindowOverlay(tk.Toplevel):
    def __init__(self, parent, alpha=0.3, bg_color="grey"):
        super().__init__(parent)

        # Hide the window during setup
        self.withdraw()

        # Basic window setup
        self.overrideredirect(True)
        self.attributes("-alpha", alpha)
        self.configure(bg=bg_color)
        self.transient(parent)

        # Calculate and set geometry
        parent.update_idletasks()
        title_bar_height = parent.winfo_rooty() - parent.winfo_y()
        self.geometry(f"{parent.winfo_width()}x{parent.winfo_height()}"f"+{parent.winfo_x()}+{parent.winfo_y() + title_bar_height}")

        # Show the fully prepared window
        self.deiconify()

    def close(self):
        self.destroy()

    def focus_Gain(self):
        self.attributes("-topmost", True)
        self.lift()

    def focus_Loss(self):
        self.attributes("-topmost", False)
# ----------------------------------------------------------------------------------------------------------------------------------


# Functions
def clear_Screen():
    global id_Trace

    # Disconect trace if exist
    if id_Trace:
        ssh_Version.trace_remove("write", id_Trace)
        id_Trace = None

    # Delete all widgets
    for widget in root.winfo_children():
        if not isinstance(widget, tk.Menu):
            widget.destroy()

def clear_DropDown(state=None):
    version_Var.set('')
    combo.config(values=[])

    if state:
        combo.config(state=state)

def close_Window_Info():
    window_Loading.close()
    window_Overlay.close()

def connect_To_reMarkable():
    while True:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ssh_Ipaddress.get(), username=ssh_Username.get(), password=ssh_Password.get(), timeout=10)
            sftp = ssh.open_sftp()

            return ssh, sftp

        except Exception as e:
            window_Overlay.focus_Loss()
            window_Loading.focus_Loss()

            result = messagebox.askretrycancel(tr["askretrycancel_Title_01"], tr["askretrycancel_Msg_01"].format(ip=ssh_Ipaddress.get(), error=e), parent=root)

            window_Overlay.focus_Gain()
            window_Loading.focus_Gain()
            
            if not result:
                root.after(100, close_Window_Info)
                return None, None

def create_Checkboxes(modules_Frame, list_Eextensions, file_status=None):
    for folder_Name, files in list_Eextensions.items():
        if folder_Name:
            ttk.Label(modules_Frame, text=folder_Name, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(5, 0))
        for file_Name in files:
            key = f"{folder_Name}/{file_Name}" if folder_Name else file_Name

            # Inicializace variable for checkboxes
            var_Checkbox[key] = tk.BooleanVar(value=file_status.get(key, False) if file_status else False)

            # Create empty checkboxes
            chk = ttk.Checkbutton(modules_Frame, text=file_Name, variable=var_Checkbox[key])
            chk.pack(anchor="w", padx=20, pady=1)

def create_Menu():
    global menu_App, menu_Settings, menu_Bar, menu_Language

    # Create menu
    menu_Bar = tk.Menu(root)
    # ----------------------

    # Settings menu
    menu_Settings = tk.Menu(menu_Bar, tearoff=0)

    # Settings language
    menu_Language = tk.Menu(menu_Settings, tearoff=0)
    menu_Language.add_radiobutton(label=tr["menu_Language_en"], variable=translate_Language, value="en", command=lambda: (manage_Json_Data("save_settings"), restart_App("change_Language")))
    menu_Language.add_radiobutton(label=tr["menu_Language_cs"], variable=translate_Language, value="cs", command=lambda: (manage_Json_Data("save_settings"), restart_App("change_Language")))

    menu_Settings.add_checkbutton(label=tr["menu_Show_Log"], variable=show_Log, command=lambda: manage_Json_Data("save_settings"))
    menu_Settings.add_cascade(label=tr["menu_Change_Language"], menu=menu_Language)
    menu_Settings.add_separator()
    menu_Settings.add_command(label=tr["menu_Reset_Settings"], command=lambda: manage_Json_Data("delete"))
    menu_Bar.add_cascade(label=tr["menu_Settings"], menu=menu_Settings)
    # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Application menu
    menu_App = tk.Menu(menu_Bar, tearoff=0)
    menu_App.add_command(label=tr["menu_About"], command=lambda: messagebox.showinfo("About", tr["menu_About_Text"], parent=root))
    menu_App.add_separator()
    menu_App.add_command(label="GitHub", command=lambda: webbrowser.open(url_Github_Page))
    menu_Bar.add_cascade(label=tr["menu_App"], menu=menu_App)
    # ----------------------------------------------------------------------------------------------------------------------------

    # Set menu
    root.config(menu=menu_Bar)
    # ------------------------

def download_Extensions(version):
    def _download():
        global Author, version_Name, tmp_Folder, file_Extensions, name_Author, list_Eextensions, repo_Fullname

        # Input control
        if not version_Var.get().strip():
            root.after(0, lambda: messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_01"], parent=root))
            return
        if not ssh_Name.get().strip():
            root.after(0, lambda: messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_02"], parent=root))
            return
        if not ssh_Ipaddress.get().strip():
            root.after(0, lambda: messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_03"], parent=root))
            return
        if not ssh_Username.get().strip():
            root.after(0, lambda: messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_04"], parent=root))
            return
        if not ssh_Password.get().strip():
            root.after(0, lambda: messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_05"], parent=root))
            return

        # Everything is OK? -> Save config.json file
        manage_Json_Data("save")

        if " / " in version:
            Author, version_Name = version.split(" / ", 1)
        else:
            Author, version_Name = "", version

        tmp_Folder = os.path.join(path_Extensions, Author, version_Name)

        extracted_files = 0
        show_Window_Info(lambda: f"{tr['show_Window_Info_01']}\n{Author} / {version_Name}")

        try:
            # Find extensions
            version_Info = next((v for v in extension_Versions if v[0] == version), None)
            if not version_Info:
                root.after(0, lambda: messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_01"].format(version=version), parent=root))
                return

            repo_Fullname = version_Info[1]
            url_to_download = get_Urls([repo_Fullname])[0][0]

            # Download ZIP
            r = requests.get(url_to_download)
            r.raise_for_status()
            zip_Data = BytesIO(r.content)

            # Create folder
            if os.path.exists(tmp_Folder):
                shutil.rmtree(tmp_Folder)
            os.makedirs(tmp_Folder, exist_ok=True)

            # Unzip
            with zipfile.ZipFile(zip_Data) as zip_In:
                root_folder_in_zip = zip_In.infolist()[0].filename.split("/")[0]
                prefix = root_folder_in_zip + f"/{version_Name}/"
                for zip_Info in zip_In.infolist():
                    if zip_Info.filename.startswith(prefix):
                        arcname = os.path.relpath(zip_Info.filename, prefix)
                        if not arcname:
                            continue
                        target_path = os.path.join(tmp_Folder, arcname)
                        if zip_Info.is_dir():
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with zip_In.open(zip_Info) as source, open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                        extracted_files += 1

            if extracted_files == 0:
                root.after(0, lambda: messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_06"].format(author=Author, version=version_Name), parent=root))
                shutil.rmtree(tmp_Folder)
                return

            # Get list files and authors
            file_Extensions = get_File_Extensions(tmp_Folder)
            name_Author = get_Name_Author(tmp_Folder)
            list_Eextensions = get_List_Extensions(tmp_Folder)

            # Check files from reMarkable
            file_status = {}

            # Conect to reMarkable
            show_Window_Info(lambda: tr["show_Window_Info_06"], update_Text=True)
            ssh, sftp = connect_To_reMarkable()

            if not ssh:
                return

            try:
                if name_Author and file_Extensions:
                    remote_qmd = os.path.join(path_Xovi_Extensions, file_Extensions)
                    try:
                        with sftp.file(remote_qmd, 'r') as f:
                            lines = f.readlines()
                        prefix_len = len(name_Author) + 1
                        for line in lines:
                            stripped = line.strip()
                            if stripped.startswith("LOAD") or stripped.startswith("; LOAD"):
                                module_name = stripped.lstrip(";").strip()[5:].strip()
                                if module_name.startswith(name_Author + "/"):
                                    module_name = module_name[prefix_len:]
                                file_status[module_name] = not stripped.startswith(";")
                    except IOError:
                        file_status = {}
                else:
                    for folder_Name, files in list_Eextensions.items():
                        for file_Name in files:
                            key = f"{folder_Name}/{file_Name}" if folder_Name else file_Name
                            try:
                                sftp.stat(os.path.join(path_Xovi_Extensions, key))
                                file_status[key] = True
                            except IOError:
                                file_status[key] = False
            finally:
                sftp.close()
                ssh.close()

            root.after(0, lambda: show_Window_List_Extensions(tmp_Folder, file_status))

        except Exception as e:
            root.after(0, lambda e=e: messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_02"].format(error_msg=str(e)), parent=root))

    threading.Thread(target=_download, daemon=True).start()

def download_Repositories():
    global combo, status_Label, extension_Versions, list_Repositories

    status_Label.config(text=tr["status_Label_03"])
    show_Window_Info(tr["show_Window_Info_02"])

    try:
        # Version
        extension_Versions = get_List_Version()

        # Combo update
        list_Repositories = [v[0] for v in extension_Versions]
        combo.configure(values=list_Repositories)

        root.after(0, lambda: status_Label.config(text=tr["status_Label_02"]))
        combo.config(state="readonly")
        close_Window_Info()
        return

    except Exception as e:
        root.after(0, lambda: status_Label.config(text=tr["status_Label_01"]))
        root.after(0, lambda e=e: messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_02"].format(error_msg=str(e)), parent=root))

def get_File_Extensions(folder):
    qmd_Files = [f for f in os.listdir(folder) if f.endswith(".qmd")]
    if qmd_Files:
        return qmd_Files[0]
    else:
        messagebox.showwarning(tr["showwarning_Title_01"], tr["showwarning_Msg_07"], parent=root)
        return None

def get_List_Extensions(folder):
    global file_Extensions, name_Author

    extensions = {}

    # 1. name_Author not found -> add all .qmd files in folder
    if not name_Author:
        qmd_Files = [f for f in os.listdir(folder) if f.endswith(".qmd")]
        extensions[""] = qmd_Files
        return extensions

    # 2. name_Author found -> load all .qmd from file qmd (example zz_rmhacks.qmd)
    file_path = os.path.join(folder, file_Extensions)
    prefix_Len = len(name_Author) + 1 if name_Author else 0  # +1 for slash

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("LOAD"):
                continue

            module_Name = line[5:].strip()

            # Delete prefix author
            if module_Name.startswith(name_Author + "/"):
                module_Name = module_Name[prefix_Len:]

            # Ignore base/ a .rcc
            if module_Name.startswith(ignored_LOAD_Main_Folder) or module_Name.endswith(".rcc"):
                continue

            # Find name folder
            parts = module_Name.split("/")
            if len(parts) > 1:
                folder_Name = parts[0]
                file_Name = parts[-1]
            else:
                folder_Name = ""
                file_Name = parts[0]

            # Save to dictionary by folder
            extensions.setdefault(folder_Name, []).append(file_Name)

    return extensions

def get_List_Repository(url_Repositories_Json):
    try:
        r = requests.get(url_Repositories_Json, headers=HEADERS)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_03"].format(error_msg=str(e)), parent=root)
        return []

def get_List_Version():
    result = []

    repo_Data = get_List_Repository(url_Repositories_Json)
    if not repo_Data:
        return result

    repos_Version = repo_Data.get("version", [])
    repos_Name = repo_Data.get("name", [])

    # Find via VERSION
    for full_Repo in repos_Version:
        try:
            author, repo = full_Repo.split("/")
            folder_Api_Url = f"https://api.github.com/repos/{author}/{repo}/contents"
            r = requests.get(folder_Api_Url, headers=HEADERS)
            r.raise_for_status()
            data = r.json()

            for item in data:
                name = item["name"]
                if item["type"] != "dir" or name.startswith("."):
                    continue

                full_Name = f"{author} / {name}"
                folder_r = requests.get(f"{folder_Api_Url}/{name}", headers=HEADERS)
                if folder_r.status_code != 200:
                    continue

                folder_Data = folder_r.json()
                qmd_Files = [f["name"] for f in folder_Data if f["type"] == "file" and f["name"].endswith(".qmd")]
                if not qmd_Files:
                    continue

                file_Url = f"https://raw.githubusercontent.com/{author}/{repo}/master/{name}/{qmd_Files[0]}"
                file_R = requests.get(file_Url, headers=HEADERS)
                if file_R.status_code != 200:
                    continue

                content = file_R.text
                versions = re.findall(r'^VERSION\s+([^\s]+)', content, re.MULTILINE)
                if any(v.startswith(ssh_Version.get().strip()) for v in versions):
                    result.append((full_Name, full_Repo))

        except Exception as e:
            messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_04"].format(repo=full_Repo, error_msg=str(e)), parent=root)

    # Find via Name
    for full_Repo in repos_Name:
        try:
            author, repo = full_Repo.split("/")
            folder_Api_Url = f"https://api.github.com/repos/{author}/{repo}/contents"
            r = requests.get(folder_Api_Url, headers=HEADERS)
            r.raise_for_status()
            data = r.json()

            for item in data:
                name = item["name"]
                if item["type"] != "dir" or name.startswith(".") or name in ignored_GITHUB_Folders:
                    continue

                if ssh_Version.get().strip() in name:
                    full_Name = f"{author} / {name}"
                    result.append((full_Name, full_Repo))

        except Exception as e:
            messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_05"].format(repo=full_Repo, error_msg=str(e)), parent=root)

    return result

def get_Name_Author(folder):
    subfolders = [item for item in os.listdir(folder) if os.path.isdir(os.path.join(folder, item))]
    if subfolders:
        return subfolders[0]
    else:
        return None

def get_Urls(name_Repository):
    url_Zip = []
    url_Web = []

    for repository in name_Repository:
        try:
            r = requests.get(f"https://api.github.com/repos/{repository}", headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            default_Branch = data.get("default_branch", "main")
        except Exception:
            default_Branch = "main"

        zip_url = f"https://github.com/{repository}/archive/refs/heads/{default_Branch}.zip"
        web_url = f"https://github.com/{repository}"

        url_Zip.append(zip_url)
        url_Web.append(web_url)

    return url_Zip, url_Web

def get_Translation_Dict(lang):
    global TRANSLATIONS

    return TRANSLATIONS.get(lang, TRANSLATIONS.get("en", {}))

def change_Focus(focus_type):
    global window_Overlay, window_Loading

    if window_Overlay and window_Overlay.winfo_exists() and window_Loading and window_Loading.winfo_exists():
        if focus_type == "in":
            window_Overlay.focus_Gain()
            window_Loading.focus_Gain()
            window_Loading.after(200, lambda: window_Loading.focus_force())

        if focus_type == "out":
            window_Overlay.focus_Loss()
            window_Loading.focus_Loss()

def change_Language():
    global menu_Bar, menu_Settings, menu_Language, menu_App

    dictionary_Menu = {
        menu_Bar: ["menu_Settings", "menu_App"],
        menu_Settings: ["menu_Show_Log", "menu_Change_Language", None, "menu_Reset_Settings"],
        menu_Language: ["menu_Language_en", "menu_Language_cs"],
        menu_App: ["menu_About"]
    }

    lang = translate_Language.get()
    tr = get_Translation_Dict(lang)
    # -----------------------------

    for menu_obj, keys in dictionary_Menu.items():
        for idx, key in enumerate(keys):
            if key is not None:
                menu_obj.entryconfig(idx, label=tr[key])

def change_Version(*args):
    version = ssh_Version.get().strip()

    if version != last_Version:
        status_Label.config(text=tr["status_Label_03"])
        combo.config(state="disabled")
    else:
        status_Label.config(text=tr["status_Label_02"])
        combo.config(state="readonly")

def check_Input_Version():
    global last_Version

    version = ssh_Version.get().strip()

    if version == last_Version:
        return

    pattern = r'^(?:[0-9]\.[0-9]{2}|[0-9]\.[0-9]{2}\.[0-9]\.[0-9]|[0-9]\.[0-9]{2}\.[0-9]\.[0-9]{2})$'
    if version and not re.match(pattern, version):
        messagebox.showerror(tr["showerror_Title_02"], tr["showerror_Msg_06"], parent=root)
        return

    if last_Version:
        result = messagebox.askyesno(tr["askyesno_Title_01"], tr["askyesno_Msg_01"], parent=root)

        if result:
            clear_DropDown("readonly")
            manage_Extensions("delete", callback=lambda: threading.Thread(target=download_Repositories, daemon=True).start())

        else:
            clear_DropDown("readonly")
            threading.Thread(target=download_Repositories, daemon=True).start()

    else:
        clear_DropDown()
        threading.Thread(target=download_Repositories).start()

    last_Version = version

def interaction_Text(action):
    cursors_Mouse = [
        "arrow", "based_arrow_down", "based_arrow_up", "boat", "bogosity", "bottom_left_corner",
        "bottom_right_corner", "bottom_side", "bottom_tee", "box_spiral", "center_ptr", "circle",
        "clock", "coffee_mug", "cross", "cross_reverse", "crosshair", "diamond_cross",
        "dot", "dotbox", "double_arrow", "draft_large", "draft_small", "draped_box",
        "exchange", "fleur", "gobbler", "gumby", "hand1", "hand2",
        "heart", "icon", "iron_cross", "left_ptr", "left_side", "left_tee",
        "leftbutton", "ll_angle", "lr_angle", "man", "middlebutton", "mouse",
        "pencil", "pirate", "plus", "question_arrow", "right_ptr", "right_side",
        "right_tee", "rightbutton", "rtl_logo", "sailboat", "sb_down_arrow", "sb_h_double_arrow",
        "sb_left_arrow", "sb_right_arrow", "sb_up_arrow", "sb_v_double_arrow", "shuttle", "sizing",
        "spider", "spraycan", "star", "target", "tcross", "top_left_arrow",
        "top_left_corner", "top_right_corner", "top_side", "top_tee", "trek", "ul_angle",
        "umbrella", "ur_angle", "watch", "xterm", "X_cursor"
    ]

    def handler(event):
        if action == "open_Link":
            text = event.widget.cget("text")
            url = text.split()[-1]
            webbrowser.open(url)        
        
        elif action == "enter":
            status_Label.config(cursor=random.choice(cursors_Mouse))
            current_font = tkFont.Font(font=status_Label.cget("font"))
            current_font.configure(underline=True)
            status_Label.config(font=current_font)
        
        elif action == "leave":
            current_font = tkFont.Font(font=status_Label.cget("font"))
            current_font.configure(underline=False)
            status_Label.config(font=current_font)

    return handler

def launch_Xovi(action):
    def worker():
        global window_Log

        # Close previous log window if exists
        if window_Log:
            try:
                window_Log.destroy()
            except Exception:
                pass
            window_Log = None

        # Create log window
        config_Data = manage_Json_Data("load")

        # Pokud je log povolen, vytvoř okno
        if config_Data.get("Settings", {}).get("log", False):
            window_Log = WindowLog(root)
        else:
            window_Log = None

        try:
            # Connect to reMarkable
            show_Window_Info(lambda: tr["show_Window_Info_06"])
            ssh, sftp = connect_To_reMarkable()

            if not ssh:
                if window_Log: window_Log.insert_Text("[ERROR] SSH connection failed.")
                return

            if window_Log: window_Log.insert_Text("[OK] Connected to reMarkable")
            sftp.close()

            if action == "debug":
                show_Window_Info("🐞 Loading debug mode")
                spinner = TextSpinner(label_Warning, lambda: "WARNING - IS DEBUG MODE!", debug=True, interval=750)

                def start_Debug():
                    root.after(0, close_Window_Info)
                    spinner.start()

                root.after(20000, start_Debug)

            if action == "start":
                show_Window_Info("Loading Xochitl")

            # Stop previous debug mode
            if window_Log: window_Log.insert_Text("[CMD] pkill -f 'xovi/debug'")
            ssh.exec_command("PID=$(ps | grep '[x]ochitl' | awk '{print $1}'); [ -n \"$PID\" ] && kill $PID")
            time.sleep(0.5)

            # Run chosen xovi command
            cmd = f"xovi/{action}"
            if window_Log: window_Log.insert_Text(f"[CMD] {cmd}")

            stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)

            for line in iter(stdout.readline, ""):
                line = line.rstrip()
                if line:
                    if window_Log: window_Log.insert_Text(line)

            err = stderr.read().decode().strip()
            ssh.close()

            if err:
                if window_Log: window_Log.insert_Text("[ERROR] " + err)
                root.after(0, lambda: messagebox.showerror("SSH Error", f"Error running xovi/{action}:\n{err}", parent=root))
            # else:
                # if window_Log: window_Log.insert_Text("[DONE] No errors.")

        except Exception as e:
            if window_Log: window_Log.insert_Text(f"[EXCEPTION] {e}")
            root.after(0, lambda: messagebox.showerror("SSH Error", f"Cannot launch xovi/{action}:\n{e}", parent=root))

        if action == "start":
            time.sleep(10)
            root.after(0, root.destroy)

    threading.Thread(target=worker, daemon=True).start()

def manage_Extensions(action, callback=None):
    def _worker():
        if action == "delete":
            try:
                show_Window_Info(lambda: tr["show_Window_Info_06"])
                ssh, sftp = connect_To_reMarkable()
                if not ssh:
                    return

                show_Window_Info(tr["show_Window_Info_03"], update_Text=True)

                def _delete_recursive(path):
                    for entry in sftp.listdir_attr(path):
                        full_path = os.path.join(path, entry.filename)
                        if any(k.lower() in entry.filename.lower() for k in ignored_Delete_Folder + ignored_Delete_File):                        
                            continue
                        if stat.S_ISDIR(entry.st_mode):
                            _delete_recursive(full_path)
                            try: sftp.rmdir(full_path)
                            except: pass
                        else:
                            try: sftp.remove(full_path)
                            except: pass

                _delete_recursive(path_Xovi_Extensions)

            except Exception as e:
                messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_07"].format(error_msg=str(e)), parent=root)
                return

            finally:
                for conn in (sftp, ssh):
                    try: conn.close()
                    except: pass
            if callback:
                root.after(0, callback)

        elif action == "update":
            global var_Checkbox, state_Checkbox, file_Extensions, name_Author, current_Folder

            # Save the current state of the checkboxes
            state_Checkbox = {k: v.get() for k, v in var_Checkbox.items()}

            files_Install = None
            files_Uninstall = None
            selected = [k for k, var in var_Checkbox.items() if var.get()]

            if not selected:
                response = messagebox.askokcancel(tr["askokcancel_Title_01"], tr["askokcancel_Msg_01"], parent=root)

                if not response:
                    return
                selected = []

            try:
                if name_Author:
                    file_path = os.path.join(current_Folder, file_Extensions)

                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    new_Lines = []
                    prefix_Len = len(name_Author) + 1

                    for line in lines:
                        if stop_Event.is_set():
                            print("Upload interrupted during file edit.")
                            return

                        stripped = line.strip()
                        if stripped.startswith("LOAD") or stripped.startswith("; LOAD"):

                            # Remove semicolon, spaces and LOAD
                            module_Name = stripped.lstrip("; ").strip()[5:].strip()
                            
                            # Delete prefix author
                            if module_Name.startswith(name_Author + "/"):
                                module_Name = module_Name[prefix_Len:]

                            key = module_Name

                            # Ignore base/ a .rcc
                            if key.startswith(ignored_LOAD_Main_Folder) or (not ignored_LOAD_RCC_File and key.endswith(".rcc")):
                                new_Lines.append(line)
                                continue

                            # Set row based on whether module is selected
                            if key in selected:
                                line = f"LOAD {name_Author}/{key}\n"
                            else:
                                line = f"; LOAD {name_Author}/{key}\n"

                        new_Lines.append(line)

                    # Overwrite the file
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(new_Lines)

                    files_Install = glob.glob(os.path.join(current_Folder, "*"))

                else:
                    all_Files = []
                    for folder_Name, files in get_List_Extensions(current_Folder).items():
                        if stop_Event.is_set():
                            return
                        for f in files:
                            key = f"{folder_Name}/{f}" if folder_Name else f
                            all_Files.append((key, os.path.join(current_Folder, f)))

                    files_Install = [path for key, path in all_Files if key in selected and os.path.exists(path)]
                    files_Uninstall = [key for key, _ in all_Files if key not in selected]

                if stop_Event.is_set():
                    return

                # Conect to reMarkable
                show_Window_Info(lambda: tr["show_Window_Info_06"])
                ssh, sftp = connect_To_reMarkable()

                if not ssh:
                    return

                try:
                    ssh.exec_command(f"mkdir -p {path_Xovi_Extensions}")

                    if not selected:
                        show_Window_Info(tr["show_Window_Info_04"], update_Text=True)

                    else:
                        show_Window_Info(tr["show_Window_Info_05"], update_Text=True)

                    # Upload files
                    for f in files_Install or []:
                        if stop_Event.is_set() or not os.path.exists(f):
                            continue
                        stack = [(f, os.path.join(path_Xovi_Extensions, os.path.basename(f)))]
                        while stack:
                            l, r = stack.pop()
                            if os.path.isdir(l):
                                try: sftp.mkdir(r)
                                except: pass
                                stack.extend((os.path.join(l, i), os.path.join(r, i)) for i in os.listdir(l))
                            else:
                                sftp.put(l, r)

                    # Remove files
                    for key in files_Uninstall or []:
                        if stop_Event.is_set(): break
                        r = os.path.join(path_Xovi_Extensions, key)
                        try:
                            sftp.remove(r)
                        except:
                            stack = [r]
                            while stack:
                                p = stack.pop()
                                try:
                                    entries = sftp.listdir_attr(p)
                                    for e in entries:
                                        cp = os.path.join(p, e.filename)
                                        if stat.S_ISDIR(e.st_mode): stack.append(cp)
                                        else: sftp.remove(cp)
                                    sftp.rmdir(p)
                                except:
                                    try: sftp.remove(p)
                                    except: pass

                finally:
                    sftp.close()
                    ssh.close()

            finally:
                stop_Event.clear()
                root.after(0, show_Window_Post_Upload)

    threading.Thread(target=_worker, daemon=True).start()

def manage_Json_Data(action=None, name=None):
    global last_Selected, show_Log, translate_Language, TRANSLATIONS, tr

    config_Default = {
        "last_selected": "Config 1",
        "Configs": [
            {"name": "Config 1", "version": "", "ipaddress": "", "username": "root", "password": ""},
            {"name": "Config 2", "version": "", "ipaddress": "", "username": "root", "password": ""},
            {"name": "Config 3", "version": "", "ipaddress": "", "username": "root", "password": ""},
        ],
        "Settings": {
            "translate": "en",
            "log": True
        }
    }

    # File not exist? -> Create
    if not os.path.exists(file_Config):
        try:
            with open(file_Config, "w", encoding="utf-8") as f:
                json.dump(config_Default, f, indent=2)
            print(f"{file_Config} not found, created default config.")

        except Exception as e:
            messagebox.showerror(tr["showerror_Title_01"], tr["showerror_Msg_08"].format(error_msg=str(e)), parent=root)
            return

    # File exist? -> Go ahead
    try:
        with open(file_Config, "r+", encoding="utf-8") as f:
            config_Data = json.load(f)

            if action == "load":
                if not name:
                    name = config_Data.get("last_selected")

                # Find configuration by name
                configs = config_Data.get("Configs", [])
                cfg = next((c for c in configs if c.get("name") == name), None)
                # -------------------------------------------------------------

                # Load the values
                ssh_Name.set(cfg.get("name", ""))
                ssh_Version.set(cfg.get("version", ""))
                ssh_Ipaddress.set(cfg.get("ipaddress", ""))
                ssh_Username.set(cfg.get("username", "root"))
                ssh_Password.set(cfg.get("password", ""))
                # -------------------------------------------

                # Find the configuration by last_Selected
                settings = config_Data.get("Settings", {})
                # ----------------------------------------

                # Setting Tkinter variables based on loaded JSON
                translate_Language.set(settings.get("translate", "en"))
                show_Log.set(settings.get("log", True))
                # -----------------------------------------------------

                # Load translations
                if os.path.exists(file_Translations):
                    with open(file_Translations, "r", encoding="utf-8") as tf:
                        TRANSLATIONS = json.load(tf)
                else:
                    TRANSLATIONS = {}
                # ------------------------------------------------------------

                # Set current translation dictionary
                lang = translate_Language.get()
                tr = TRANSLATIONS.get(lang, TRANSLATIONS.get("en", {}))
                # -----------------------------------------------------

                # Update the values
                last_Selected = name

                return config_Data

            elif action == "save":
                # Find the configuration by last_Selected
                configs = config_Data.get("Configs", [])

                # Update last_Selected
                cfg = next(c for c in configs if c.get("name") == last_Selected)
                
                # Update the values
                config_Data["last_selected"] = ssh_Name.get()
                cfg.update({
                    "name": ssh_Name.get(),
                    "password": ssh_Password.get(),
                    "version": ssh_Version.get(),
                    "ipaddress": ssh_Ipaddress.get(),
                    "username": ssh_Username.get()
                })

            elif action == "save_settings":
                # Find the configuration by last_Selected
                settings = config_Data.get("Settings", {})

                # Update the values
                settings.update({
                    "translate": translate_Language.get(),
                    "log": show_Log.get()
                })

                # Ulož zpět do hlavního configu
                config_Data["Settings"] = settings

            elif action == "delete":
                os.remove(file_Config)
                restart_App("delete_File_Config")

            else:
                raise ValueError("Undefined action.")

            # Save json file
            if action != "load" and action != "delete_File_Config":
                f.seek(0)
                f.truncate()
                json.dump(config_Data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Error managing config.json ({action}): {e}")

def show_Window_Info(text, update_Text=False):
    global window_Overlay, window_Loading

    if 'window_Overlay' not in globals() or window_Overlay is None or not window_Overlay.winfo_exists():
        window_Overlay = WindowOverlay(root)

    if 'window_Loading' not in globals() or window_Loading is None or not window_Loading.winfo_exists():
        window_Loading = WindowLoading(window_Overlay, text=text)

    if update_Text and hasattr(window_Loading, "spinner") and window_Loading.spinner.running:
        window_Loading.spinner.update_text(text)
        return

    provider = text if callable(text) else lambda: text
    window_Loading.spinner.update_text(provider)

def show_Window_List_Extensions(folder, file_status=None):
    global list_Eextensions, state_Checkbox, current_Folder, var_Checkbox, status_Label

    # Initializing variables
    var_Checkbox = {}
    state_Checkbox = {}
    list_Eextensions = {}
    current_Folder = folder
    # ---------------------

    # Funkctions
    clear_Screen()
    list_Eextensions = get_List_Extensions(folder)
    # --------------------------------------------

    # Note - Title
    ttk.Label(root, text=tr["note_Title_01"]).pack(pady=(15, 0))
    ttk.Label(root, text=tr["note_Title_02"], font=("Arial", 12), foreground="gray").pack(pady=5)
    # ------------------------------------------------------------------------------------------

    # Note - Extensions
    status_Label = ttk.Label(root, text = f"🌐 {get_Urls([repo_Fullname])[1][0]}")
    status_Label.pack(pady=10)
    status_Label.bind("<Button-1>", interaction_Text("open_Link"))
    status_Label.bind("<Enter>", interaction_Text("enter"))
    status_Label.bind("<Leave>", interaction_Text("leave"))

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=5)

    canvas = tk.Canvas(frame)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")

    canvas.configure(yscrollcommand=scrollbar.set)

    modules_Frame = ttk.Frame(canvas)
    modules_Frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    canvas.create_window((0, 0), window=modules_Frame, anchor="nw")
    # --------------------------------------------------------------------------------------------

    # Buttons - Home / Apply selected changes / Exit
    frame = ttk.Frame(root)
    frame.pack(pady=10)

    ttk.Button(frame, text=tr["button_Home"], command=lambda: show_Window_Main()).pack(side="left", padx=5)
    ttk.Button(frame, text=tr["button_Apply_Changes"], command=lambda: manage_Extensions("update")).pack(side="left", padx=5)
    ttk.Button(frame, text=tr["button_Exit"], command=root.destroy).pack(side="left", padx=5)
    # -----------------------------------------------------------------------------------------------------------------------

    # Funkctions
    create_Checkboxes(modules_Frame, list_Eextensions, file_status)
    # -------------------------------------------------------------

def show_Window_Main():
    global status_Label, combo, last_Version, version_Var, ssh_Name, ssh_Version, ssh_Ipaddress, ssh_Username, ssh_Password, translate_Language, show_Log, list_Repositories, id_Trace

    # Variables for settings
    if 'version_Var' not in globals(): version_Var = tk.StringVar()
    if 'ssh_Name' not in globals(): ssh_Name = tk.StringVar()
    if 'ssh_Version' not in globals(): ssh_Version = tk.StringVar()
    if 'ssh_Ipaddress' not in globals(): ssh_Ipaddress = tk.StringVar()
    if 'ssh_Username' not in globals(): ssh_Username = tk.StringVar()
    if 'ssh_Password' not in globals(): ssh_Password = tk.StringVar()
    if 'translate_Language' not in globals(): translate_Language = tk.StringVar(value="en")
    if 'show_Log' not in globals(): show_Log = tk.BooleanVar(value=False)
    if 'list_Repositories' not in globals(): list_Repositories = []
    if 'id_Trace' not in globals(): id_Trace = None
    # -------------------------------------------------------------------------------------

    # Disconect old trace, if exist
    if hasattr(ssh_Version, "_id_Trace"): ssh_Version.trace_remove("write", ssh_Version._id_Trace)
    # --------------------------------------------------------------------------------------------

    # Funkctions
    clear_Screen()
    data = manage_Json_Data("load")
    # -----------------------------

    # Note - Title
    ttk.Label(root, text=tr["note_Title_03"]).pack(pady=(15, 0))
    ttk.Label(root, text="💡 Menu / Settings / General / Software", font=("Arial", 12), foreground="gray").pack(pady=5)
    # -----------------------------------------------------------------------------------------------------------------

    # Note - Status bar
    status_Label = ttk.Label(root, text=tr["status_Label_03"])
    status_Label.pack(pady=10)
    # -----------------------------------------------------------

    # Dropdown - Extensions
    combo = ttk.Combobox(root, textvariable=version_Var, values=list_Repositories, state="readonly")
    combo.pack()
    # ----------------------------------------------------------------------------------------------

    # Note - SSH login
    ttk.Label(root, text=tr["note_Title_04"]).pack(pady=(20, 0))
    ttk.Label(root, text="💡 Menu / Settings / Help / Copyrights and licenses", font=("Arial", 12), foreground="gray").pack(pady=(5, 10))
    # -----------------------------------------------------------------------------------------------------------------------------------

    # Buttons - Config
    frame = ttk.Frame(root)
    frame.pack(pady=10)
    # ---------------------

    for cfg in data["Configs"]:
        ttk.Button(frame, text=cfg["name"], command=lambda c=cfg: manage_Json_Data("load", c["name"])).pack(side="left", padx=5, pady=(0,5))
    # --------------------------------------------------------------------------------------------------------------------------------------

    # Textfield - Config
    frame = ttk.Frame(root)
    frame.pack(fill="x", padx=20)
    # ---------------------------

    # Name
    name_Frame = ttk.Frame(frame)
    name_Frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
    ttk.Label(name_Frame, text=tr["label_Name"]).pack(anchor="w")
    ttk.Entry(name_Frame, textvariable=ssh_Name).pack(fill="x")
    # --------------------------------------------------------------

    # Version
    last_Version = ssh_Version.get()

    version_Frame = ttk.Frame(frame)
    version_Frame.pack(side="left", fill="x", expand=True)
    ttk.Label(version_Frame, text=tr["label_Version"]).pack(anchor="w")

    entry_Version = ttk.Entry(version_Frame, textvariable=ssh_Version)
    entry_Version.pack(fill="x")

    entry_Version.bind("<Return>", lambda event: check_Input_Version())
    entry_Version.bind("<KP_Enter>", lambda event: check_Input_Version())
    entry_Version.bind("<FocusOut>", lambda event: check_Input_Version())

    id_Trace = ssh_Version.trace_add("write", lambda *args: change_Version(*args))
    # ----------------------------------------------------------------------------

    # IP address
    ttk.Label(root, text=tr["label_IP_Address"]).pack(anchor="w", padx=20, pady=(10, 0))
    ttk.Entry(root, textvariable=ssh_Ipaddress).pack(fill="x", padx=20)
    # ----------------------------------------------------------------------------------

    # Username
    ttk.Label(root, text=tr["label_Username"]).pack(anchor="w", padx=20, pady=(10, 0))
    ttk.Entry(root, textvariable=ssh_Username).pack(fill="x", padx=20)
    # --------------------------------------------------------------------------------

    # Password
    ttk.Label(root, text=tr["label_Password"]).pack(anchor="w", padx=20, pady=(10, 0))
    ttk.Entry(root, textvariable=ssh_Password, show="*").pack(fill="x", padx=20)
    # --------------------------------------------------------------------------------

    # Buttons - Refresh / Save config & Download / Exit
    frame = ttk.Frame(root)
    frame.pack(pady=(50, 0))

    ttk.Button(frame, text=tr["button_Refresh"], command=lambda: (clear_DropDown(), threading.Thread(target=download_Repositories, daemon=True).start())).pack(side="left", padx=5)
    ttk.Button(frame, text=tr["button_Save_Download"], command=lambda: [stop_Event.clear(), download_Extensions(version_Var.get())]).pack(side="left", padx=5)
    ttk.Button(frame, text=tr["button_Exit"], command=root.destroy).pack(side="left", padx=5)
    # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Funkctions
    if ssh_Version.get().strip() and not list_Repositories:
        threading.Thread(target=download_Repositories, daemon=True).start()
    # ---------------------------------------------------------------------

def show_Window_Post_Upload():
    global label_Warning

    # Functions
    clear_Screen()
    # ------------

    # Note - Title
    ttk.Label(root, text=tr["note_Title_05"]).pack(pady=(15, 0))
    # --------------------------------------------------------------------

    # Note - Info
    ttk.Label(root, text=tr["note_Title_06"], font=("Arial", 12), foreground="gray", wraplength=250).pack(pady=(20, 0))
    ttk.Label(root, text=tr["note_Title_07"], font=("Arial", 12), foreground="gray", wraplength=250).pack(pady=(10, 0))
    # ----------------------------------------------------------------------------------------------------------------

    # Note - Separator
    ttk.Label(root, text="*************************************************").pack(pady=(20, 0))
    # ------------------------------------------------------------------------------------------

    # Note - Debug mode
    ttk.Label(root, text=tr["note_Title_08"]).pack(pady=(10, 0))
    ttk.Label(root, text=tr["note_Title_09"]).pack(pady=(10, 0))
    ttk.Label(root, text=tr["note_Title_10"], font=("Arial", 12), foreground="gray", wraplength=250).pack(pady=5)
    # ----------------------------------------------------------------------------------------------------------

    # Buttons - Debug / Reastart reMarkable & Exit
    frame = ttk.Frame(root)
    frame.pack(pady=(10, 0))
    
    ttk.Button(frame, text=tr["button_Debug"], command=lambda: launch_Xovi("debug")).pack(side="left", padx=5)
    ttk.Button(frame, text=tr["button_Launch_Xovi"], command=lambda: launch_Xovi("start")).pack(side="left", padx=5)
    # --------------------------------------------------------------------------------------------------------------

    # Note - Separator
    ttk.Label(root, text="*************************************************").pack(pady=(15, 20))
    # -------------------------------------------------------------------------------------------

    # Note - WARNING!
    label_Warning = ttk.Label(root, text=tr["note_Title_11"], font=("Arial", 18, "bold"), foreground="black", wraplength=300)
    label_Warning.pack(pady=5)

    ttk.Label(root, text=tr["note_Title_12"], font=("Arial", 12), foreground="red", wraplength=300, justify="center").pack(pady=5)
    # --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Buttons - Home / Exit
    frame = ttk.Frame(root)
    frame.pack(pady=(50, 0))

    ttk.Button(frame, text=tr["button_Home"], command=lambda: show_Window_Main()).pack(side="left", padx=5)
    ttk.Button(frame, text=tr["button_Exit"], command=root.destroy).pack(side="left", padx=5)
    # -----------------------------------------------------------------------------------------------------

def restart_App(action):
    if action == "change_Language":
        answer = messagebox.askyesno(tr["askyesno_Title_02"], tr["askyesno_Msg_02"], parent=root)

    if action == "delete_File_Config":
        answer = messagebox.askyesno(tr["askyesno_Title_03"], tr["askyesno_Msg_03"], parent=root)

    if answer:
        python = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        subprocess.Popen([python, script] + args)
        sys.exit(0)

# -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Main window
root = tk.Tk()
root.title(name_App)
window_Width = 480
window_Height = 560

# Position window
screen_Width = root.winfo_screenwidth()
screen_Height = root.winfo_screenheight()
x = (screen_Width // 2) - (window_Width // 2)
y = (screen_Height // 2) - (window_Height // 2)
root.geometry(f"{window_Width}x{window_Height}+{x}+{y}")

root.bind("<FocusIn>", lambda e: change_Focus("in"))
root.bind("<FocusOut>", lambda e: change_Focus("out"))

show_Window_Main()
create_Menu()

root.mainloop()
# ------------------------------------------------------
