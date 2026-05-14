import tkinter as tk
from tkinter import filedialog, messagebox
import sounddevice as sd
import queue
import json
import threading
import time
import os
import csv
import subprocess
import sys
from datetime import datetime
from vosk import Model, KaldiRecognizer

LOG_FILE = "attendance_log.csv"
SETTINGS_FILE = "settings.json"

audio_queue = queue.Queue()
listening = False


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


MODEL_PATH = resource_path(".")
DEFAULT_ALARM = resource_path("mixkit-classic-alarm-995.wav")


def callback(indata, frames, time_info, status):
    audio_queue.put(bytes(indata))


def load_settings():
    default = {
        "keywords": "attendance, quiz, test, submission",
        "alarm": DEFAULT_ALARM,
        "alarm_on": True,
        "stealth": True,
        "theme": "dark"
    }

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                default.update(json.load(f))
        except:
            pass

    return default


def save_settings():
    data = {
        "keywords": keyword_entry.get(),
        "alarm": alarm_file_var.get(),
        "alarm_on": alarm_on_var.get(),
        "stealth": stealth_var.get(),
        "theme": theme_var.get()
    }

    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def popup(title, message):
    os.system(f'''osascript -e 'display notification "{message}" with title "{title}"' ''')


def get_output_device():
    try:
        return subprocess.check_output(["SwitchAudioSource", "-c"], text=True).strip().lower()
    except:
        return ""


def headphones_connected():
    device = get_output_device()
    words = ["airpods", "headphone", "headset", "earbuds", "earphones", "buds"]
    return any(word in device for word in words)


def play_alarm():
    alarm = alarm_file_var.get().strip()

    if not os.path.exists(alarm):
        alarm = DEFAULT_ALARM

    if not os.path.exists(alarm):
        messagebox.showerror("Error", "Alarm file not found.")
        return

    if stealth_var.get():
        if headphones_connected():
            os.system(f'afplay "{alarm}"')
        else:
            popup("Stealth Mode", "Keyword detected, but no headphones connected.")
    else:
        os.system(f'afplay "{alarm}"')


def log_detection(keyword, text):
    exists = os.path.exists(LOG_FILE)
    now = datetime.now()

    with open(LOG_FILE, "a", newline="") as file:
        writer = csv.writer(file)

        if not exists:
            writer.writerow(["Date", "Time", "Keyword", "Full Text"])

        writer.writerow([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            keyword,
            text
        ])


def listen_loop():
    global listening

    status_label.config(text="Loading speech model...", fg="orange")

    try:
        model = Model(MODEL_PATH)
        recognizer = KaldiRecognizer(model, 16000)
    except Exception as e:
        status_label.config(text="Model loading failed", fg="red")
        messagebox.showerror("Model Error", str(e))
        listening = False
        return

    status_label.config(text="Listening...", fg="green")

    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback
    ):
        while listening:
            data = audio_queue.get()

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower()

                if text:
                    heard_label.config(text=f"Heard: {text}")

                keywords = [
                    k.strip().lower()
                    for k in keyword_entry.get().split(",")
                    if k.strip()
                ]

                for keyword in keywords:
                    if keyword in text:
                        status_label.config(text=f"Detected: {keyword}", fg="red")
                        log_detection(keyword, text)
                        popup("Attendance Alarm", f"Detected: {keyword}")

                        if alarm_on_var.get():
                            play_alarm()

                        save_settings()
                        time.sleep(2)


def start():
    global listening

    if listening:
        return

    if not keyword_entry.get().strip():
        messagebox.showerror("Error", "Enter at least one keyword.")
        return

    save_settings()
    listening = True
    threading.Thread(target=listen_loop, daemon=True).start()


def stop():
    global listening
    listening = False
    status_label.config(text="Stopped", fg="gray")
    save_settings()


def choose_alarm():
    path = filedialog.askopenfilename(
        filetypes=[
            ("Audio files", "*.wav *.mp3 *.m4a *.aiff"),
            ("All files", "*.*")
        ]
    )

    if path:
        alarm_file_var.set(path)
        save_settings()


def open_log():
    if os.path.exists(LOG_FILE):
        os.system(f'open "{LOG_FILE}"')
    else:
        messagebox.showinfo("Log", "No log yet.")


def apply_theme():
    theme = theme_var.get()

    if theme == "dark":
        bg = "#2b2b2b"
        fg = "white"
        entry_bg = "#111111"
    else:
        bg = "#f2f2f2"
        fg = "black"
        entry_bg = "white"

    root.config(bg=bg)

    for widget in root.winfo_children():
        try:
            widget.config(bg=bg, fg=fg)
        except:
            pass

    keyword_entry.config(bg=entry_bg, fg=fg, insertbackground=fg)
    alarm_entry.config(bg=entry_bg, fg=fg, insertbackground=fg)

    save_settings()


settings = load_settings()

root = tk.Tk()
root.title("Attendance Alarm")
root.geometry("560x500")
root.resizable(False, False)

tk.Label(root, text="Attendance Alarm", font=("Arial", 25, "bold")).pack(pady=15)

tk.Label(root, text="Trigger words separated by commas:", font=("Arial", 12)).pack()

keyword_entry = tk.Entry(root, font=("Arial", 14), width=45)
keyword_entry.insert(0, settings["keywords"])
keyword_entry.pack(pady=10)

alarm_file_var = tk.StringVar(value=settings["alarm"])

frame = tk.Frame(root)
frame.pack(pady=5)

tk.Label(frame, text="Alarm:").pack(side=tk.LEFT)

alarm_entry = tk.Entry(frame, textvariable=alarm_file_var, width=40)
alarm_entry.pack(side=tk.LEFT, padx=5)

tk.Button(frame, text="Choose", command=choose_alarm).pack(side=tk.LEFT)

alarm_on_var = tk.BooleanVar(value=settings["alarm_on"])
stealth_var = tk.BooleanVar(value=settings["stealth"])
theme_var = tk.StringVar(value=settings["theme"])

tk.Checkbutton(
    root,
    text="Play alarm when detected",
    variable=alarm_on_var,
    command=save_settings
).pack(pady=4)

tk.Checkbutton(
    root,
    text="Stealth mode: play only if headphones/AirPods are connected",
    variable=stealth_var,
    command=save_settings
).pack(pady=4)

theme_frame = tk.Frame(root)
theme_frame.pack(pady=8)

tk.Label(theme_frame, text="Theme:").pack(side=tk.LEFT, padx=5)

tk.Radiobutton(
    theme_frame,
    text="Dark",
    variable=theme_var,
    value="dark",
    command=apply_theme
).pack(side=tk.LEFT)

tk.Radiobutton(
    theme_frame,
    text="Light",
    variable=theme_var,
    value="light",
    command=apply_theme
).pack(side=tk.LEFT)

buttons = tk.Frame(root)
buttons.pack(pady=15)

tk.Button(
    buttons,
    text="Start Listening",
    font=("Arial", 13, "bold"),
    width=16,
    command=start
).grid(row=0, column=0, padx=8)

tk.Button(
    buttons,
    text="Stop",
    font=("Arial", 13, "bold"),
    width=16,
    command=stop
).grid(row=0, column=1, padx=8)

tk.Button(root, text="Test Alarm", font=("Arial", 12), command=play_alarm).pack(pady=5)

tk.Button(root, text="Open Log", font=("Arial", 12), command=open_log).pack(pady=5)

status_label = tk.Label(root, text="Stopped", font=("Arial", 13), fg="gray")
status_label.pack(pady=12)

heard_label = tk.Label(root, text="Heard: -", font=("Arial", 11), wraplength=480)
heard_label.pack(pady=5)

tk.Label(root, text="Settings save automatically.", fg="gray").pack(side=tk.BOTTOM, pady=10)

apply_theme()

root.mainloop()

