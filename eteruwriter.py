"""Type text into the currently focused Windows application, one character at a time.

Run with: python eteruwriter.py
"""

from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import messagebox, ttk


if not hasattr(ctypes, "windll"):
    raise SystemExit("This tool currently supports Windows only.")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_F12 = 0x7B
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
HOTKEY_ID = 1


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", INPUT_UNION)]


user32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = ctypes.c_uint


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


def send_key(vk: int = 0, scan: int = 0, flags: int = 0) -> None:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.union.ki = KEYBDINPUT(vk, scan, flags, 0, None)
    if user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError()


def type_character(character: str) -> None:
    if character == "\n":
        send_key(vk=VK_RETURN)
        send_key(vk=VK_RETURN, flags=KEYEVENTF_KEYUP)
        return
    if character == "\r":
        return
    # SendInput's Unicode mode takes UTF-16 code units, including surrogate pairs.
    encoded = character.encode("utf-16-le", errors="surrogatepass")
    for offset in range(0, len(encoded), 2):
        unit = int.from_bytes(encoded[offset : offset + 2], "little")
        send_key(scan=unit, flags=KEYEVENTF_UNICODE)
        send_key(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


class TypewriterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("醚键打字机 | eteruwriter")
        self.root.geometry("720x740")
        self.root.minsize(600, 620)
        self.running = False
        self.countdown = 0
        self.position = 0
        self.text = ""
        self.interval_ms = 80
        self.busy = False
        self.topmost_var = tk.BooleanVar(value=False)

        outer = ttk.Frame(root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="把文字放在这里", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(10, 8))
        ttk.Label(controls, text="每个字符间隔").pack(side="left")
        self.interval_var = tk.StringVar(value="80")
        ttk.Spinbox(controls, from_=10, to=2000, increment=10, width=7, textvariable=self.interval_var).pack(side="left", padx=6)
        ttk.Label(controls, text="毫秒").pack(side="left")
        ttk.Checkbutton(
            controls,
            text="窗口置顶",
            variable=self.topmost_var,
            command=self.set_topmost,
        ).pack(side="left", padx=(18, 0))
        self.start_button = ttk.Button(controls, text="开始输入（3 秒后）", command=self.start)
        self.start_button.pack(side="right")
        ttk.Label(outer, text="停止快捷键：Ctrl + Alt + F12", foreground="#555").pack(anchor="w", pady=(0, 8))

        self.editor = tk.Text(outer, wrap="word", undo=True, font=("Microsoft YaHei UI", 10))
        self.editor.pack(fill="both", expand=True, pady=(0, 12))

        self.status = tk.StringVar(value="将光标放到目标输入框，倒计时结束后开始输入。")
        ttk.Label(outer, textvariable=self.status, wraplength=530).pack(anchor="w", pady=(12, 0))

        self.hotkey_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_F12))
        if not self.hotkey_registered:
            self.start_button.state(["disabled"])
            self.status.set("停止快捷键注册失败。请关闭占用 Ctrl+Alt+F12 的程序后重新打开工具。")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def set_topmost(self) -> None:
        self.root.attributes("-topmost", self.topmost_var.get())

    def start(self) -> None:
        if not self.hotkey_registered:
            return
        if self.running or self.busy:
            return
        self.text = self.editor.get("1.0", "end-1c")
        if not self.text:
            messagebox.showinfo("没有文字", "请先在上方输入或粘贴文字。")
            return
        try:
            self.interval_ms = max(10, min(2000, int(self.interval_var.get())))
        except ValueError:
            messagebox.showerror("间隔无效", "请输入 10 到 2000 之间的毫秒数。")
            return
        self.busy = True
        self.countdown = 3
        self.start_button.state(["disabled"])
        self.status.set(f"{self.countdown} 秒后开始。请马上切换到目标输入框；按 Ctrl+Alt+F12 可停止。")
        self.root.iconify()
        self.root.after(1000, self.countdown_tick)

    def countdown_tick(self) -> None:
        if not self.busy:
            return
        self.countdown -= 1
        if self.countdown > 0:
            self.root.after(1000, self.countdown_tick)
            return
        self.running = True
        self.busy = False
        self.position = 0
        self.type_tick()

    def type_tick(self) -> None:
        if not self.running:
            return
        if self.position >= len(self.text):
            self.finish("输入完成。")
            return
        try:
            type_character(self.text[self.position])
        except OSError as error:
            self.finish(f"输入失败：{error}")
            return
        self.position += 1
        if self.position % 20 == 0 or self.position == len(self.text):
            self.status.set(f"正在输入：{self.position}/{len(self.text)} 字符。按 Ctrl+Alt+F12 可停止。")
        self.root.after(self.interval_ms, self.type_tick)

    def poll_hotkey(self) -> None:
        message = MSG()
        while user32.PeekMessageW(ctypes.byref(message), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
            if message.wParam == HOTKEY_ID:
                self.finish("已停止。")
        self.root.after(50, self.poll_hotkey)

    def finish(self, message: str) -> None:
        self.running = False
        self.busy = False
        self.start_button.state(["!disabled"])
        self.status.set(message)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def close(self) -> None:
        self.running = False
        self.busy = False
        user32.UnregisterHotKey(None, HOTKEY_ID)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = TypewriterApp(root)
    root.after(50, app.poll_hotkey)
    root.mainloop()


if __name__ == "__main__":
    main()

