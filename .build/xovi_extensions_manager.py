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
path_Extensions = os.path.join(path_Config, "Extensions") # Aktuální složka projektu (kdybych potřeboval) -> path_Extensions = os.path.dirname(os.path.abspath(__file__))

ignored_LOAD_Main_Folder = "base/"                  # Ignored rows with base in update_Extension() and get_List_Extensions()
ignored_LOAD_RCC_File = False                       # Ignored rows with *rcc in update_Extension()
ignored_GITHUB_Folders = ["images", "docs", "test"] # Ignored folders from Github in get_List_Version()

path_Xovi_Extensions = f"/home/root/xovi/exthome/qt-resource-rebuilder/"
url_Repositories_Json = "https://raw.githubusercontent.com/PepikVaio/reMarkable_Xovi_Extensions_Manager/main/repositories.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Functions
def action_Buttons(name_Window):
    global button_Refresh, button_Home_Refresh

    if name_Window == "window_Main":
        if button_Refresh.cget("text") == "Refresh":
            version_Var.set('')
            combo.config(values=[])
            threading.Thread(target=download_Repositories, daemon=True).start()
        else:
            restart_Program()

    elif name_Window == "window_List_Extension":
        if button_Home_Refresh.cget("text") == "Home & Refresh":
            stop_Event.set(),
            show_Window_Main()
        else:
            restart_Program()

    elif name_Window == "window_Post_Upload":
        if button_Home_Refresh.cget("text") == "Home & Refresh":
            show_Window_Main()
        else:
            restart_Program()

def add_Dots(label, base_Text, interval=500, max_Dots=3, update_text_only=False):
    global running

    if not label.winfo_exists():
        return

    # Change text
    if update_text_only:
        label._base_Text = base_Text
        label.config(text=base_Text)
        return

    if not running:
        return

    # Cancel old animation
    if hasattr(label, "_after_id"):
        label.after_cancel(label._after_id)

    label._base_Text = base_Text
    counter = 0

    def _update():
        nonlocal counter
        if not running:
            return
        counter = (counter + 1) % (max_Dots + 1)
        label.config(text=label._base_Text + "." * counter + " " * (max_Dots - counter))
        label._after_id = label.after(interval, _update)

    _update()

def connect_To_reMarkable():
    while True:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ssh_Ipaddress.get(), username=ssh_Username.get(), password=ssh_Password.get(), timeout=10)
            sftp = ssh.open_sftp()

            return ssh, sftp

        except Exception as e:
            print(f"SSH/SFTP error: {e}")
            result = messagebox.askretrycancel("Connection error", f"Cannot connect to your reMarkable ({ssh_Ipaddress.get()}).\nError: {e}\n\nRetry?", parent=root)
            if not result:
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

def clear_Screen():
    for widget in root.winfo_children():
        widget.destroy()

def download_Extensions(version):
    def _download():
        global Author, version_Name, tmp_Folder, running, file_Extensions, name_Author, list_Eextensions, repo_Fullname, status_Label, button_Refresh

        # Input control
        if not version_Var.get().strip():
            root.after(0, lambda: messagebox.showwarning("Warning", "Select author and software version of your reMarkable!", parent=root))
            return
        if not ssh_Name.get().strip():
            root.after(0, lambda: messagebox.showwarning("Warning", "Enter the name!", parent=root))
            return
        if not ssh_Ipaddress.get().strip():
            root.after(0, lambda: messagebox.showwarning("Warning", "Enter the ip address!", parent=root))
            return
        if not ssh_Username.get().strip():
            root.after(0, lambda: messagebox.showwarning("Warning", "Enter the username!", parent=root))
            return
        if not ssh_Password.get().strip():
            root.after(0, lambda: messagebox.showwarning("Warning", "Enter the password!", parent=root))
            return

        # Everything is OK? -> Save config.json file
        manage_Json_Data("save")

        if " / " in version:
            Author, version_Name = version.split(" / ", 1)
        else:
            Author, version_Name = "", version

        tmp_Folder = os.path.join(path_Extensions, Author, version_Name)

        running = True
        extracted_files = 0
        rename_Button(button_Refresh, "Restart")
        add_Dots(status_Label, f"⬇️ Downloading extensions {Author} / {version_Name}")

        try:
            # Find extensions
            version_Info = next((v for v in extension_Versions if v[0] == version), None)
            if not version_Info:
                root.after(0, lambda: messagebox.showerror("Error", f"Version {version} not found!", parent=root))
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
                root.after(0, lambda: messagebox.showwarning("Warning", f"No content found in folder '{Author} / {version_Name}'", parent=root))
                shutil.rmtree(tmp_Folder)
                return

            # Get list files and authors
            file_Extensions = get_File_Extensions(tmp_Folder)
            name_Author = get_Name_Author(tmp_Folder)
            list_Eextensions = get_List_Extensions(tmp_Folder)

            # Check files from reMarkable
            file_status = {}

            # Conect to reMarkable
            add_Dots(status_Label, f"🔌 Connecting to reMarkable at {ssh_Ipaddress.get()}", update_text_only=True)
            ssh, sftp = connect_To_reMarkable()
            if not ssh:
                running = False
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
            root.after(0, lambda e=e: messagebox.showerror("Error", str(e), parent=root))

        finally:
            running = False

    threading.Thread(target=_download, daemon=True).start()

def download_Repositories():
    global running, combo, status_Label, extension_Versions

    running = True
    add_Dots(status_Label, "⬇️ Loading repositories")

    try:
        # Version
        if not running: return
        extension_Versions = get_List_Version()

        # Combo update
        if not running: return
        combo.configure(values=[v[0] for v in extension_Versions])

        # End animation
        running = False
        root.after(0, lambda: status_Label.config(text="✅ Load complete"))

    except Exception as e:
        running = False
        root.after(0, lambda: status_Label.config(text="Failed to load repository list"))
        root.after(0, lambda e=e: messagebox.showerror("Error", str(e), parent=root))

def get_File_Extensions(folder):
    qmd_Files = [f for f in os.listdir(folder) if f.endswith(".qmd")]
    if qmd_Files:
        return qmd_Files[0]
    else:
        messagebox.showwarning("Warning", "No *qmd file found in the downloaded folder!", parent=root)
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
        messagebox.showerror("Error", f"Failed to load repository list:\n{e}", parent=root)
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
            messagebox.showerror("Error", f"Failed to load version list from {full_Repo}:\n{e}", parent=root)

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
            messagebox.showerror("Error", f"Failed to load repository {full_Repo}:\n{e}", parent=root)

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

def check_Input_Version():
    version = ssh_Version.get().strip()
    pattern = r'^(?:[0-9]\.[0-9]{2}|[0-9]\.[0-9]{2}\.[0-9]\.[0-9]|[0-9]\.[0-9]{2}\.[0-9]\.[0-9]{2})$'

    if version and not re.match(pattern, version):
        messagebox.showerror("Invalid version", "Allowed version formats are:\nempty field, x.xx, x.xx.x.x, x.xx.x.xx")
        return

    version_Var.set('')
    combo.config(values=[])
    threading.Thread(target=download_Repositories, daemon=True).start()

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
        global button_Home_Refresh

        try:
            if action == "debug":
                root.after(0, lambda: rename_Button(button_Home_Refresh, "Restart"))

            # Connect to reMarkable
            add_Dots(status_Label, f"🔌 Connecting to reMarkable at {ssh_Ipaddress.get()}")
            ssh, sftp = connect_To_reMarkable()
            if not ssh:
                return

            ssh.exec_command("pkill -f 'xovi/debug'")
            time.sleep(0.5)
            stdin, stdout, stderr = ssh.exec_command(f"xovi/{action}", get_pty=True)

            for line in iter(stdout.readline, ""):
                if line.strip():
                    print(line.strip())

            err = stderr.read().decode()
            ssh.close()

            if err:
                root.after(0, lambda: messagebox.showerror("SSH Error", f"Error running xovi/{action}:\n{err}", parent=root))

        except Exception as e:
            root.after(0, lambda: messagebox.showerror("SSH Error", f"Cannot launch xovi/{action}:\n{e}", parent=root))

        if action == "start":
            time.sleep(1)
            root.after(0, root.destroy)

    threading.Thread(target=worker, daemon=True).start()

def manage_Json_Data(action=None, name=None):
    global last_Selected

    default_Config = {
        "last_selected": "Config 1",
        "Configs": [
            {"name": "Config 1", "version": "", "ipaddress": "", "username": "root", "password": ""},
            {"name": "Config 2", "version": "", "ipaddress": "", "username": "root", "password": ""},
            {"name": "Config 3", "version": "", "ipaddress": "", "username": "root", "password": ""},
        ]
    }

    # File not exist? -> Create
    if not os.path.exists(file_Config):
        try:
            with open(file_Config, "w", encoding="utf-8") as f:
                json.dump(default_Config, f, indent=2)
            print(f"{file_Config} not found, created default config.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create default config:\n{e}", parent=root)
            return

    # File exist? -> Go ahead
    try:
        with open(file_Config, "r+", encoding="utf-8") as f:
            config_Data = json.load(f)

            if action == "load":
                if not name:
                    name = config_Data.get("last_selected")

                # Find the configuration by name
                configs = config_Data.get("Configs", [])
                cfg = next((c for c in configs if c.get("name") == name), None)

                # Load the values
                ssh_Name.set(cfg.get("name", ""))
                ssh_Version.set(cfg.get("version", ""))
                ssh_Ipaddress.set(cfg.get("ipaddress", ""))
                ssh_Username.set(cfg.get("username", "root"))
                ssh_Password.set(cfg.get("password", ""))

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

            else:
                raise ValueError("Undefined action. Use 'load' or 'save'.")

            # Save json file
            if action != "load":
                f.seek(0)
                f.truncate()
                json.dump(config_Data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Error managing config.json ({action}): {e}")

def rename_Button(button, new_Text):
    button.config(text=new_Text)

def restart_Program():
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def show_Window_List_Extensions(folder, file_status=None):
    global list_Eextensions, state_Checkbox, current_Folder, var_Checkbox, status_Label, button_Home_Refresh

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
    ttk.Label(root, text="Select extensions to install or uncheck to uninstall:").pack(pady=(15, 0))
    ttk.Label(root, text="💡 Required extensions are hidden to prevent accidental disablement", font=("Arial", 12), foreground="gray").pack(pady=5)
    # ---------------------------------------------------------------------------------------------------------------------------------------------

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

    # Buttons - Home & Refresh / Apply selected changes / Exit
    frame = ttk.Frame(root)
    frame.pack(pady=10)

    button_Home_Refresh = ttk.Button(frame, text="Home & Refresh", command=lambda: action_Buttons("window_List_Extension"))
    button_Home_Refresh.pack(side="left", padx=5)

    ttk.Button(frame, text="Apply selected changes", command=update_Extensions).pack(side="left", padx=5)
    ttk.Button(frame, text="Exit", command=root.destroy).pack(side="left", padx=5)
    # ------------------------------------------------------------------------------------------------------------------------

    # Funkctions
    create_Checkboxes(modules_Frame, list_Eextensions, file_status)
    # -------------------------------------------------------------

def show_Window_Main():
    global status_Label, version_Var, combo, ssh_Name, ssh_Version, ssh_Ipaddress, ssh_Username, ssh_Password, button_Refresh

    # Initializing variables
    version_Var = tk.StringVar()
    ssh_Name = tk.StringVar()
    ssh_Version = tk.StringVar()
    ssh_Ipaddress = tk.StringVar()
    ssh_Username = tk.StringVar()
    ssh_Password = tk.StringVar()
    # ----------------------------

    # Funkctions
    clear_Screen()
    data = manage_Json_Data("load")
    # -----------------------------

    # Note - Title
    ttk.Label(root, text="Select author and software version of your reMarkable:").pack(pady=(15, 0))
    ttk.Label(root, text="💡 Menu / Settings / General / Software", font=("Arial", 12), foreground="gray").pack(pady=5)
    # -----------------------------------------------------------------------------------------------------------------

    # Note - Status bar
    status_Label = ttk.Label(root, text="")
    status_Label.pack(pady=10)
    # -------------------------------------

    # Dropdown - Extensions
    combo = ttk.Combobox(root, textvariable=version_Var, state="readonly")
    combo.pack()
    # --------------------------------------------------------------------

    # Note - SSH login
    ttk.Label(root, text="Log in via SSH to your reMarkable:").pack(pady=(20, 0))
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
    ttk.Label(name_Frame, text="Name:").pack(anchor="w")
    ttk.Entry(name_Frame, textvariable=ssh_Name).pack(fill="x")
    # --------------------------------------------------------------

    # Version
    version_Frame = ttk.Frame(frame)
    version_Frame.pack(side="left", fill="x", expand=True)
    ttk.Label(version_Frame, text="Version:").pack(anchor="w")

    entry_Version = ttk.Entry(version_Frame, textvariable=ssh_Version)
    entry_Version.pack(fill="x")

    ssh_Version.trace_add("write", lambda *args: [globals().update(running=False), version_Var.set(''), combo.config(values=[]), status_Label.config(text="🔄 Please refresh repositories")])

    entry_Version.bind("<Return>", lambda event: check_Input_Version())
    entry_Version.bind("<KP_Enter>", lambda event: check_Input_Version())
    # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # IP address
    ttk.Label(root, text="IP address:").pack(anchor="w", padx=20, pady=(10, 0))
    ttk.Entry(root, textvariable=ssh_Ipaddress).pack(fill="x", padx=20)
    # -------------------------------------------------------------------------

    # Username
    ttk.Label(root, text="Username:").pack(anchor="w", padx=20, pady=(10, 0))
    ttk.Entry(root, textvariable=ssh_Username).pack(fill="x", padx=20)
    # -----------------------------------------------------------------------

    # Password
    ttk.Label(root, text="Password:").pack(anchor="w", padx=20, pady=(10, 0))
    ttk.Entry(root, textvariable=ssh_Password, show="*").pack(fill="x", padx=20)
    # --------------------------------------------------------------------------

    # Buttons - Refresh / Save config & Download / Exit
    frame = ttk.Frame(root)
    frame.pack(pady=(50, 0))

    button_Refresh = ttk.Button(frame, text="Refresh", command=lambda: action_Buttons("window_Main"))
    button_Refresh.pack(side="left", padx=5)

    ttk.Button(frame, text="Save config & Download", command=lambda: [stop_Event.clear(), download_Extensions(version_Var.get())]).pack(side="left", padx=5)
    ttk.Button(frame, text="Exit", command=root.destroy).pack(side="left", padx=5)
    # ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Funkctions
    if ssh_Version.get().strip():
        threading.Thread(target=download_Repositories, daemon=True).start()
    # ---------------------------------------------------------------------

def show_Window_Post_Upload():
    global button_Home_Refresh
    
    # Functions
    clear_Screen()
    # ------------

    # Note - Title
    ttk.Label(root, text="All selected extensions successfully uploaded!").pack(pady=(15, 0))
    # ---------------------------------------------------------------------------------------

    # Note - Info
    ttk.Label(root, text="💡 Try debug mode for the first time, this will allow you to test the extension and avoid restarting reMarkable in a loop.", font=("Arial", 12), foreground="gray", wraplength=250).pack(pady=(20, 0))
    ttk.Label(root, text="💡 After successfully testing the extension and confirming everything works fine, you can launch Xovi.", font=("Arial", 12), foreground="gray", wraplength=250).pack(pady=(10, 0))
    # --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Note - Separator
    ttk.Label(root, text="*************************************************").pack(pady=(20, 0))
    # ------------------------------------------------------------------------------------------

    # Note - Debug mode
    ttk.Label(root, text="1. Debug mode is used to test extensions safely!").pack(pady=(10, 0))
    ttk.Label(root, text="2. Everything working fine? Launch Xovi & Exit!").pack(pady=(10, 0))
    ttk.Label(root, text="💡 Using terminal? Press Ctrl+c to exit debug mode, then press 'Launch Xovi & Exit'.", font=("Arial", 12), foreground="gray", wraplength=250).pack(pady=5)
    # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Buttons - Debug / Reastart reMarkable & Exit
    frame = ttk.Frame(root)
    frame.pack(pady=(10, 0))
    
    ttk.Button(frame, text="Debug", command=lambda: launch_Xovi("debug")).pack(side="left", padx=5)
    ttk.Button(frame, text="Launch Xovi & Exit", command=lambda: launch_Xovi("start")).pack(side="left", padx=5)
    # ----------------------------------------------------------------------------------------------------------

    # Note - Separator
    ttk.Label(root, text="*************************************************").pack(pady=(15, 20))
    # -------------------------------------------------------------------------------------------

    # Note - WARNING!
    ttk.Label(root, text="WARNING!", font=("Arial", 20, "bold"), foreground="black", wraplength=250).pack(pady=5)
    ttk.Label(root, text="Never exit the application while in debug mode!\nAlways press 'Launch Xovi & Exit' to avoid errors!", font=("Arial", 12), foreground="red", wraplength=300).pack(pady=5)
    # --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Buttons - Home & Refresh / Exit
    frame = ttk.Frame(root)
    frame.pack(pady=(50, 0))

    button_Home_Refresh = ttk.Button(frame, text="Home & Refresh", command=lambda: action_Buttons("window_Post_Upload"))
    button_Home_Refresh.pack(side="left", padx=5)

    ttk.Button(frame, text="Exit", command=root.destroy).pack(side="left", padx=5)
    # ------------------------------------------------------------------------------------------------------------------

def update_Extensions():
    global var_Checkbox, state_Checkbox, file_Extensions, name_Author, current_Folder, running

    # Save the current state of the checkboxes
    state_Checkbox = {k: v.get() for k, v in var_Checkbox.items()}
    running = True

    def _worker():
        global running, button_Home_Refresh

        if stop_Event.is_set():
            running = False
            return

        files_Install = None
        files_Uninstall = None
        selected = [k for k, var in var_Checkbox.items() if var.get()]

        if not selected:
            response = messagebox.askokcancel("Warning", "No extensions selected. If you proceed, all extensions will be uninstalled. Do you want to continue?", parent=root)
            if not response:
                running = False
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
                running = False
                return

            # Conect to reMarkable
            root.after(0, lambda: rename_Button(button_Home_Refresh, "Restart"))
            add_Dots(status_Label, f"🔌 Connecting to reMarkable at {ssh_Ipaddress.get()}")
            ssh, sftp = connect_To_reMarkable()
            if not ssh:
                running = False
                return

            try:
                ssh.exec_command(f"mkdir -p {path_Xovi_Extensions}")

                if not selected:
                    add_Dots(status_Label, "🗑️ Deleting all extensions", update_text_only=True)
                else:
                    add_Dots(status_Label, "🔄 Updating extensions", update_text_only=True)

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
            running = False
            stop_Event.clear()
            root.after(0, show_Window_Post_Upload)

    threading.Thread(target=_worker, daemon=True).start()

# -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Main window
root = tk.Tk()
root.title(name_App)
window_Width = 480#475
window_Height = 560

# Position window
screen_Width = root.winfo_screenwidth()
screen_Height = root.winfo_screenheight()
x = (screen_Width // 2) - (window_Width // 2)
y = (screen_Height // 2) - (window_Height // 2)
root.geometry(f"{window_Width}x{window_Height}+{x}+{y}")

show_Window_Main()
root.mainloop()
# ------------------------------------------------------
