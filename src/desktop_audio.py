"""程序独立音量、后台播放。设备调用排队，不阻塞 Tk 或进度保存。"""
from __future__ import annotations
import ctypes
import os
import json
from queue import Queue
import threading
import uuid
import store

TRACKS = {'hunting':'music/hunting_theme570.wav','success':'music/hunting_success570.wav','failure':'music/hunting_failure570.wav'}
TRACKS.update({name: 'music/hunting_' + name + '590.wav' for name in ('countdown','send','ultimate','correct','wrong','throw')})
THEMES = json.loads(store.resource_path('assets/music/themes590.json').read_text(encoding='utf-8'))['tracks']
SPIRIT_THEMES = {row['target']: row for row in THEMES}
TRACKS.update({row['track']: row['file'] for row in THEMES})

class GameAudio:
    def __init__(self):
        self._queue = Queue()
        self._alias = 'xyaudio' + uuid.uuid4().hex
        self.enabled = True
        self.volume = 50
        self.track = None
        self.last_error = None
        self.play_count = 0
        self.last_started = None
        self.status = {'mode': 'closed'}
        self._closed = False
        self._worker = threading.Thread(target=self._run, name='xiaoyuan-audio', daemon=True)
        self._worker.start()

    def configure(self, *, enabled, volume):
        self.enabled = bool(enabled)
        self.volume = max(0, min(100, int(volume)))
        self._put(('settings',self.enabled,self.volume))

    def play(self, track, *, loop=False):
        if track not in TRACKS: raise ValueError('音轨不存在')
        self.track = (track,bool(loop))
        self._put(('play',track,bool(loop)))

    def stop(self):
        self.track = None
        self._put(('stop',))

    def inspect(self):
        # MCI 别名由打开设备的线程持有，状态也必须在同一线程查询。
        self._put(('inspect',))

    def close(self):
        if not self._closed:
            self._put(('close',))
            self._closed = True
            self._worker.join(timeout=.5)

    def _put(self, message):
        if not self._closed: self._queue.put(message)

    def _run(self):
        if os.name != 'nt': return
        dll = ctypes.WinDLL('winmm')
        dll.mciSendStringW.argtypes = [ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p]
        dll.mciSendStringW.restype = ctypes.c_uint
        opened = False
        enabled, volume = True, 50
        wanted = None
        def command(value):
            error = dll.mciSendStringW(value,None,0,None)
            if error:
                self.last_error = int(error)
                raise OSError(error, '播放设备暂不可用')
        def stop():
            nonlocal opened
            if opened:
                dll.mciSendStringW('close '+self._alias,None,0,None)
                opened = False
            self.status = {'mode': 'closed'}
        def play():
            nonlocal opened
            stop()
            if not wanted or not enabled or volume == 0: return
            track, loop = wanted
            path = store.resource_path('assets/'+TRACKS[track])
            if not path.is_file():
                self.last_error = 'missing_track'
                raise OSError('音轨文件缺失')
            command(f'open "{path}" type mpegvideo alias {self._alias}')
            opened = True
            command(f'setaudio {self._alias} volume to {volume * 10}')
            command('play '+self._alias+(' repeat' if loop else ''))
            self.play_count += 1
            self.last_started = wanted
            self.last_error = None
        try:
            while True:
                message = self._queue.get()
                try:
                    if message[0] == 'close':
                        stop()
                        return
                    if message[0] == 'stop':
                        wanted = None
                        stop()
                    elif message[0] == 'inspect':
                        values = {}
                        for key in ('mode', 'volume'):
                            buffer = ctypes.create_unicode_buffer(64)
                            error = dll.mciSendStringW(f'status {self._alias} {key}', buffer, 64, None) if opened else 0
                            values[key] = buffer.value if opened else 'closed'
                            values[key + '_error'] = int(error)
                        self.status = values
                    elif message[0] == 'settings':
                        enabled, volume = message[1:]
                        if not enabled or volume == 0: stop()
                        elif opened: command(f'setaudio {self._alias} volume to {volume * 10}')
                        else: play()
                    elif message[0] == 'play':
                        if opened and wanted == message[1:] and message[2]:
                            continue
                        wanted = message[1:]
                        play()
                except OSError:
                    stop()
                finally:
                    self._queue.task_done()
        finally:
            stop()
