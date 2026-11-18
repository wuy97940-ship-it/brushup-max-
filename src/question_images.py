"""有界题干图缓存。后台仅解码 PIL；CTk/Tk 图像由主线程创建。"""
from __future__ import annotations
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from PIL import Image


class QuestionImages:
    def __init__(self, *, limit=12, max_bytes=36 * 1024 * 1024):
        self.limit, self.max_bytes = limit, max_bytes
        self._cache = OrderedDict()
        self._bytes = 0
        self._lock = RLock()
        self._pending = set()
        self._closed = False
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='题干图片预读')

    def read(self, path: Path):
        key = str(path)
        with self._lock:
            source = self._cache.get(key)
            if source is not None:
                self._cache.move_to_end(key)
                return source
        with Image.open(path) as original:
            source = original.convert('RGB')
        if source.width > 1200:
            source = source.resize((1200, max(1, round(source.height * 1200 / source.width))), Image.Resampling.LANCZOS)
        cost = source.width * source.height * 3
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            if cost <= self.max_bytes and not self._closed:
                self._cache[key] = source
                self._bytes += cost
                while len(self._cache) > self.limit or self._bytes > self.max_bytes:
                    _, old = self._cache.popitem(last=False)
                    self._bytes -= old.width * old.height * 3
        return source

    def prefetch(self, paths):
        for path in paths:
            key = str(path)
            with self._lock:
                if self._closed or key in self._cache or key in self._pending or len(self._pending) >= 6:
                    continue
                self._pending.add(key)
            self._worker.submit(self._prepare, path)

    def _prepare(self, path):
        try:
            if path.is_file():
                self.read(path)
        except (OSError, ValueError):
            pass
        finally:
            with self._lock:
                self._pending.discard(str(path))

    def close(self):
        with self._lock:
            self._closed = True
        self._worker.shutdown(wait=True, cancel_futures=True)
        with self._lock:
            self._cache.clear()
            self._bytes = 0

