"""数据写盘在独立线程；同步事务结果不变，慢IO期间仅服务界面与窗口消息。"""
from __future__ import annotations
import threading
import gc
import tkinter as tk
import weakref

BUSY_SUFFIX=' · 保存中'
# 常规落盘约十几毫秒，先等至一帧左右，避免短保存触发整窗保护和中间绘制。
# 超过此预算仍服务Tk消息；不提前提交结果，也不减少持久化步骤。
FAST_SAVE_SECONDS=.040


def waiting(owner):
    return getattr(owner,'_storage_waiting',False) is True


def defer_close(owner):
    if waiting(owner):
        owner._close_after_storage=True
        return True
    return False


def _protect_input(owner):
    if not hasattr(owner,'_storage_guard_tag'):
        owner._storage_guard_tag='StorageGuard'+str(owner.winfo_id())
        owner._storage_guard_widgets=weakref.WeakSet()
        def intercept(event):
            return 'break' if getattr(owner,'_storage_input_blocked',False) else None
        for pattern in ('<KeyPress>','<KeyRelease>','<ButtonPress>','<ButtonRelease>','<MouseWheel>'):
            owner.bind_class(owner._storage_guard_tag,pattern,intercept)
    stack=[owner]
    while stack:
        widget=stack.pop()
        try:
            stack.extend(widget.winfo_children())
            if widget not in owner._storage_guard_widgets:
                widget.bindtags((owner._storage_guard_tag,*widget.bindtags()))
                owner._storage_guard_widgets.add(widget)
        except tk.TclError:pass
    if not getattr(owner,'_storage_input_blocked',False):
        owner._storage_input_blocked=True
        owner._storage_previous_cursor=owner.cget('cursor')
        owner._storage_previous_title=owner.title()
        owner.configure(cursor='watch')
        owner.title(owner._storage_previous_title+BUSY_SUFFIX)


def _release_input(owner):
    owner._storage_release_id=None
    if waiting(owner):
        owner._storage_release_id=owner.after(20,lambda:_release_input(owner))
        return
    if not owner.winfo_exists():return
    if getattr(owner,'_storage_input_blocked',False):
        owner._storage_input_blocked=False
        owner.configure(cursor=owner._storage_previous_cursor)
        owner.title(owner._storage_previous_title)
    if getattr(owner,'_close_after_storage',False):
        owner._close_after_storage=False
        owner.after_idle(owner._on_close)


def save_with_events(owner, save, progress):
    """仅写纯数据，直到完成才返回；不把未持久化候选提前交给调用者。"""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('保存协调器必须由Tk主线程调用')
    if waiting(owner):return False
    event=threading.Event();result=[];errors=[]
    automatic_gc=gc.isenabled()
    if automatic_gc:gc.disable()
    owner._storage_waiting=True
    def write():
        try:result.append(save(progress))
        except BaseException as error:errors.append(error)
        finally:event.set()
    writer=threading.Thread(target=write,name='xiaoyuan-save',daemon=False)
    writer.start()
    responsive=False
    try:
        if not event.wait(FAST_SAVE_SECONDS):
            responsive=True;_protect_input(owner)
            while not event.is_set():
                # 输入已由首个bindtag拦截；业务时钟和新事务另由waiting守卫延后。
                owner.update_idletasks();owner.update();event.wait(.004)
        writer.join()
        if errors:raise errors[0]
        return result[0]
    finally:
        owner._storage_waiting=False
        if automatic_gc:gc.enable()
        if responsive and owner.winfo_exists() and getattr(owner,'_storage_release_id',None) is None:
            # 调用者先更新内存成绩及完整反馈，随后空闲时才解除输入和保存提示。
            owner._storage_release_id=owner.after_idle(lambda:_release_input(owner))
