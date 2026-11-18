"""释放窗口自己的图片订阅、缩放订阅和延迟回调，避免缓存持有已关闭控件。"""
from __future__ import annotations

import tkinter as tk
import ctypes
import gc
import time
from threading import current_thread, main_thread
from ctypes import wintypes
import customtkinter as ctk
from customtkinter.windows.widgets.scaling import CTkScalingBaseClass

_gc_owners = 0
_gc_was_enabled = False


class GuiGarbageCollector:
    """Tk字体、变量、图片的循环引用必须在主线程回收，不能由图片线程触发析构。"""
    def __init__(self):
        global _gc_owners, _gc_was_enabled
        if current_thread() is not main_thread():
            raise RuntimeError("界面回收器必须由主线程创建。")
        if _gc_owners == 0:
            _gc_was_enabled = gc.isenabled()
            gc.disable()
        _gc_owners += 1
        self.owner = None
        self.timer = None
        self.closed = False
        self.young_cycles=0

    def start(self, owner):
        self.owner = owner
        self.timer = owner.after(1500, self._collect)

    def _collect(self):
        self.timer = None
        if self.closed:
            return
        if getattr(self.owner,'_storage_waiting',False):
            self.timer=self.owner.after(1500,self._collect)
            return
        # 高频回收年轻代；完整扫描等待操作间隙，仍只在Tk主线程执行。
        gc.collect(1)
        self.young_cycles+=1
        if self.young_cycles>=20 and time.monotonic()-getattr(self.owner,'_last_interaction_at',0)>=.5:
            gc.collect(2)
            self.young_cycles=0
        self.timer = self.owner.after(1500, self._collect)

    def close(self):
        global _gc_owners
        if self.closed:
            return
        self.closed = True
        if self.timer:
            try:
                self.owner.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        # 调用前图片线程已停止；析构始终在主线程执行。
        gc.collect()
        _gc_owners -= 1
        if _gc_owners == 0 and _gc_was_enabled:
            gc.enable()
        self.owner = None


def release_resources(widget):
    if isinstance(widget, ctk.CTkTextbox):
        text = getattr(widget, '_textbox', None)
        if text is not None and text.winfo_exists():
            # 先解除原生Text指向滚动条的回调，再释放滚动条及其Canvas。
            text.configure(xscrollcommand='', yscrollcommand='')
    children = list(widget.winfo_children())
    commands = set(getattr(widget, "_tclCommands", None) or ())
    for child in children:
        release_resources(child)
    # CTkLabel.destroy在当前运行库没有解除CTkImage订阅；先置空会走正式解除路径。
    if isinstance(widget, ctk.CTkLabel) and isinstance(getattr(widget, "_image", None), ctk.CTkImage):
        widget.configure(image=None)
    if isinstance(widget, tk.Menu) and isinstance(widget, CTkScalingBaseClass):
        CTkScalingBaseClass.destroy(widget)
    # tkinter销毁会删除回调命令，但不取消after队列中的定时事件。
    for identifier in widget.tk.call("after", "info"):
        try:
            script = widget.tk.call("after", "info", identifier)[0]
            if str(script).split()[0] in commands:
                widget.after_cancel(identifier)
        except (tk.TclError, IndexError):
            pass


class ManagedWindow(ctk.CTkToplevel):
    def _windows_set_titlebar_color(self, color_mode):
        # CTk的原方法在窗口构造中调用全局update，重入销毁/创建队列。
        # 延后设置原生标题栏颜色，避免构造未完成时处理其它窗口事件。
        self.after(15, lambda: self._apply_titlebar_color(color_mode))

    def _apply_titlebar_color(self, color_mode):
        if getattr(self, "_destroy_scheduled", False) or not self.winfo_exists():
            return
        user = ctypes.windll.user32
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        native = user.GetParent(self.winfo_id())
        value = ctypes.c_int(int(color_mode.lower() == "dark"))
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        dwm.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwm(native, 20, ctypes.byref(value), ctypes.sizeof(value))

    def destroy(self):
        if not self.winfo_exists() or getattr(self, "_destroy_scheduled", False):
            return
        if getattr(self.master, "_closing_app", False):
            self._finish_destroy()
            return
        # Windows Tk在同一事件中销毁原生顶层窗口、随后进入CTk构造器的
        # update_idletasks可能访问已释放的窗口。先隐藏，下一次事件循环统一释放。
        self._destroy_scheduled = True
        self.withdraw()
        self.after(0, self._finish_destroy)

    def _finish_destroy(self):
        if not self.winfo_exists():
            return
        release_resources(self)
        super().destroy()
