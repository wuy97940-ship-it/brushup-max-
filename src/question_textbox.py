"""客观题文本保持固定滚动区域，避免反馈后延迟换行。"""
import customtkinter as ctk


class QuestionTextbox(ctk.CTkTextbox):
    """仅用于自动换行的题干/解析，保留原生 Text 的滚动范围更新。"""

    def __init__(self, *args, **kwargs):
        self._vertical_scroll_after = None
        self._vertical_scroll_range = None
        self._vertical_scroll_drawn = None
        super().__init__(*args, **kwargs)
        # 替换文字时Text会连续报告中间滚动范围；同一轮布局只绘制最终范围。
        self._textbox.configure(yscrollcommand=self._queue_vertical_scroll)
        self._check_if_scrollbars_needed()

    def _queue_vertical_scroll(self, first, last):
        self._vertical_scroll_range = (float(first), float(last))
        if self._vertical_scroll_after is None:
            self._vertical_scroll_after = self.after_idle(self._draw_vertical_scroll)

    def _draw_vertical_scroll(self):
        self._vertical_scroll_after = None
        bounds = self._vertical_scroll_range
        if bounds != self._vertical_scroll_drawn and self._y_scrollbar.winfo_exists():
            self._y_scrollbar.set(*bounds)
            self._vertical_scroll_drawn = bounds

    def destroy(self):
        if self._vertical_scroll_after is not None:
            self.after_cancel(self._vertical_scroll_after)
            self._vertical_scroll_after = None
        super().destroy()

    def _check_if_scrollbars_needed(self, event=None, continue_loop=False):
        # 固定纵向栏位；不启动父类的周期显隐检查。Text 的 yscrollcommand
        # 仍直接更新滚动条，长解析、滚轮和拖动均沿用原有实现。
        wanted = self._scrollbars_activated
        if self._hide_y_scrollbar == wanted or bool(self._y_scrollbar.winfo_manager()) != wanted:
            self._hide_y_scrollbar = not wanted
            self._create_grid_for_text_and_scrollbars(re_grid_y_scrollbar=True)
        if not self._hide_x_scrollbar:
            self._hide_x_scrollbar = True
            self._create_grid_for_text_and_scrollbars(re_grid_x_scrollbar=True)
