"""
Shared UI widgets and helpers (pure Python, no KV) so the app is easy to
reason about and test.
"""
import os

from kivy.metrics import dp, sp
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex

# ---------------------------------------------------------------- palette ---
PRIMARY = "#2563EB"
PRIMARY_DARK = "#1D4ED8"
BG = "#F4F6FA"
CARD_BG = "#FFFFFF"
TEXT = "#111827"
TEXT_MUTED = "#6B7280"
EXPENSE = "#DC2626"
INCOME = "#16A34A"
WARN = "#D97706"
BORDER = "#E5E7EB"

FONT_NAME = None  # resolved by register_app_font()


def register_app_font(project_root: str):
    """Register a CJK-capable font so Chinese text does not render as boxes."""
    global FONT_NAME
    from kivy.core.text import LabelBase

    candidates = [
        os.path.join(project_root, "assets", "fonts", "app.ttf"),
        os.path.join(project_root, "assets", "fonts", "app.otf"),
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansSC-Regular.otf",
        "/system/fonts/DroidSansFallback.ttf",
        "/system/fonts/DroidSansFallbackFull.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                LabelBase.register(name="AppFont", fn_regular=path)
                FONT_NAME = "AppFont"
                return FONT_NAME
            except Exception:
                continue
    return None


def rgba(hex_color: str, alpha: float = 1.0):
    r, g, b, *_ = get_color_from_hex(hex_color)
    return (r, g, b, alpha)


def lighten(hex_color: str, alpha: float = 0.12):
    return rgba(hex_color, alpha)


# ------------------------------------------------------------- primitives ---
class RoundedBox(BoxLayout):
    """BoxLayout with a rounded background."""

    def __init__(self, bg_color=CARD_BG, radius=dp(14), border_color=None, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_color = Color(*rgba(bg_color))
            self._bg_rect = RoundedRectangle(radius=[radius])
            self._border_color = None
            self._border = None
            if border_color:
                self._border_color = Color(*rgba(border_color))
                self._border = Line(width=dp(1))

        self.bind(pos=self._sync_canvas, size=self._sync_canvas)
        self._sync_canvas()

    def set_bg(self, hex_color):
        self._bg_color.rgba = rgba(hex_color)

    def _sync_canvas(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        if self._border is not None:
            self._border.rounded_rectangle = (
                self.x, self.y, self.width, self.height, dp(14)
            )


class AppLabel(Label):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_size", sp(15))
        kwargs.setdefault("color", rgba(TEXT))
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        if FONT_NAME:
            kwargs.setdefault("font_name", FONT_NAME)
        super().__init__(**kwargs)
        self.bind(size=lambda *a: setattr(self, "text_size", self.size))


class AppButton(Button):
    def __init__(self, text="", bg_color=PRIMARY, color="#FFFFFF", **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("color", rgba(color))
        kwargs.setdefault("font_size", sp(15))
        kwargs.setdefault("bold", True)
        if FONT_NAME:
            kwargs.setdefault("font_name", FONT_NAME)
        self._bg_hex = bg_color
        super().__init__(text=text, **kwargs)
        with self.canvas.before:
            self._btn_color = Color(*rgba(bg_color))
            self._btn_rect = RoundedRectangle(radius=[dp(10)])
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def _sync(self, *args):
        self._btn_rect.pos = self.pos
        self._btn_rect.size = self.size

    def set_bg(self, hex_color):
        self._bg_hex = hex_color
        self._btn_color.rgba = rgba(hex_color)


def primary_button(text, on_press=None, color=PRIMARY, **kwargs):
    btn = AppButton(text=text, bg_color=color, **kwargs)
    if on_press:
        btn.bind(on_press=lambda *_: on_press())
    return btn


def ghost_button(text, on_press=None, color=PRIMARY, **kwargs):
    kwargs.setdefault("size_hint_y", None)
    kwargs.setdefault("height", dp(46))
    btn = AppButton(text=text, bg_color="#FFFFFF", color=color, **kwargs)
    if on_press:
        btn.bind(on_press=lambda *_: on_press())
    return btn


class HeaderBar(RoundedBox):
    """Top bar with optional back button, title and right action."""

    def __init__(self, title, on_back=None, action_text=None, on_action=None,
                 bg_color=PRIMARY, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(58))
        kwargs.setdefault("padding", [dp(10), dp(8)])
        kwargs.setdefault("spacing", dp(8))
        super().__init__(bg_color=bg_color, radius=dp(0), **kwargs)

        if on_back:
            back = AppButton(text="返回", bg_color=bg_color, size_hint_x=None,
                             width=dp(62), height=dp(40))
            back.bind(on_press=lambda *_: on_back())
            self.add_widget(back)

        self.title_label = AppLabel(text=title, bold=True, font_size=sp(19),
                                    color="#FFFFFF")
        self.add_widget(self.title_label)

        if action_text and on_action:
            act = AppButton(text=action_text, bg_color=bg_color,
                            size_hint_x=None, width=dp(76), height=dp(40))
            act.bind(on_press=lambda *_: on_action())
            self.add_widget(act)


class Field(BoxLayout):
    """Label + TextInput."""

    def __init__(self, label, hint="", text="", multiline=False,
                 input_filter=None, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(72))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)

        self.add_widget(AppLabel(text=label, font_size=sp(13),
                                 color=TEXT_MUTED, size_hint_y=None, height=dp(20)))
        ti_kwargs = dict(
            text=text, hint_text=hint, multiline=multiline, font_size=sp(16),
            background_normal="", background_active="",
            background_color=rgba("#EEF1F6"),
            foreground_color=rgba(TEXT),
            cursor_color=rgba(PRIMARY),
            padding=[dp(12), dp(10)], size_hint_y=None,
            height=dp(46) if not multiline else dp(88),
        )
        if input_filter:
            ti_kwargs["input_filter"] = input_filter
        if FONT_NAME:
            ti_kwargs["font_name"] = FONT_NAME
        self.input = TextInput(**ti_kwargs)
        self.add_widget(self.input)

    @property
    def text(self):
        return self.input.text.strip()

    @text.setter
    def text(self, value):
        self.input.text = value


class Choice(BoxLayout):
    """Label + Spinner."""

    def __init__(self, label, values, text=None, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(72))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)

        self.add_widget(AppLabel(text=label, font_size=sp(13),
                                 color=TEXT_MUTED, size_hint_y=None, height=dp(20)))
        sp_kwargs = dict(
            values=values, text=text or (values[0] if values else ""),
            font_size=sp(16), background_normal="",
            background_color=rgba("#EEF1F6"), color=rgba(TEXT),
            size_hint_y=None, height=dp(46),
        )
        if FONT_NAME:
            sp_kwargs["font_name"] = FONT_NAME
        self.spinner = Spinner(**sp_kwargs)
        self.add_widget(self.spinner)

    @property
    def text(self):
        return self.spinner.text

    @text.setter
    def text(self, value):
        self.spinner.text = value


class Segmented(BoxLayout):
    """Simple segmented control."""

    def __init__(self, options, selected=None, on_change=None, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(40))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        self.options = options
        self.on_change = on_change
        self.buttons = {}
        for opt in options:
            btn = AppButton(text=opt, bg_color=PRIMARY if opt == selected else "#E5E7EB",
                            color="#FFFFFF" if opt == selected else TEXT,
                            height=dp(40), font_size=sp(14))
            btn.bind(on_press=lambda b, o=opt: self.select(o))
            self.buttons[opt] = btn
            self.add_widget(btn)
        self.selected = selected or (options[0] if options else None)

    def select(self, option):
        self.selected = option
        for opt, btn in self.buttons.items():
            active = opt == option
            btn.set_bg(PRIMARY if active else "#E5E7EB")
            btn.color = rgba("#FFFFFF") if active else rgba(TEXT)
        if self.on_change:
            self.on_change(option)


class Divider(BoxLayout):
    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(1))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*rgba(BORDER))
            self._rect = RoundedRectangle(radius=[])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class ListRow(RoundedBox):
    """A generic list row: color badge + title/subtitle + right-aligned value."""

    def __init__(self, title, subtitle="", value="", value_color=TEXT,
                 badge_text="", badge_color=PRIMARY, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(66))
        kwargs.setdefault("padding", [dp(12), dp(8)])
        kwargs.setdefault("spacing", dp(12))
        super().__init__(bg_color=CARD_BG, **kwargs)

        if badge_text:
            badge = RoundedBox(bg_color=badge_color, radius=dp(10),
                               size_hint=(None, None), size=(dp(38), dp(38)),
                               pos_hint={"center_y": 0.5})
            badge.add_widget(AppLabel(text=badge_text, halign="center",
                                      color="#FFFFFF", bold=True, font_size=sp(16)))
            self.add_widget(badge)

        mid = BoxLayout(orientation="vertical", spacing=dp(2))
        mid.add_widget(AppLabel(text=title, bold=True, font_size=sp(15)))
        if subtitle:
            mid.add_widget(AppLabel(text=subtitle, font_size=sp(12),
                                    color=TEXT_MUTED))
        self.add_widget(mid)

        if value:
            self.add_widget(AppLabel(text=value, bold=True, font_size=sp(15),
                                     color=value_color, halign="right",
                                     size_hint_x=None, width=dp(110)))


class ProgressCard(RoundedBox):
    """Savings plan card with progress bar."""

    def __init__(self, name, current, target, color=INCOME, on_add=None, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(132))
        kwargs.setdefault("padding", dp(14))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(bg_color=CARD_BG, **kwargs)

        progress = 0 if target <= 0 else min(100.0, current / target * 100)

        top = BoxLayout(orientation="horizontal", spacing=dp(8),
                        size_hint_y=None, height=dp(26))
        top.add_widget(AppLabel(text=name, bold=True, font_size=sp(16)))
        top.add_widget(AppLabel(text=f"{progress:.0f}%", bold=True,
                                font_size=sp(15), color=rgba(color),
                                halign="right", size_hint_x=None, width=dp(60)))
        self.add_widget(top)

        bar_bg = RoundedBox(bg_color="#EEF1F6", radius=dp(6),
                            size_hint_y=None, height=dp(10))
        with bar_bg.canvas.before:
            Color(*rgba(color))
            self._bar = RoundedRectangle(radius=[dp(6)])
        self._bar.size = (0, dp(10))
        self._bar_pos = (bar_bg.x, bar_bg.y)
        bar_bg.bind(pos=lambda *a: self._sync_bar(bar_bg, progress),
                    size=lambda *a: self._sync_bar(bar_bg, progress))
        self._bar_bg = bar_bg
        self._progress = progress
        self.add_widget(bar_bg)

        bottom = BoxLayout(orientation="horizontal", spacing=dp(8),
                           size_hint_y=None, height=dp(24))
        bottom.add_widget(AppLabel(text=f"已存 ¥{current:,.2f}", font_size=sp(13),
                                   color=TEXT_MUTED))
        bottom.add_widget(AppLabel(text=f"目标 ¥{target:,.2f}", font_size=sp(13),
                                   color=TEXT_MUTED, halign="right"))
        self.add_widget(bottom)

        if on_add:
            add = AppButton(text="存入", bg_color=color, height=dp(38),
                            font_size=sp(14))
            add.bind(on_press=lambda *_: on_add())
            self.add_widget(add)

    def _sync_bar(self, bar_bg, progress):
        width = bar_bg.width * progress / 100.0
        self._bar.pos = (bar_bg.x, bar_bg.y)
        self._bar.size = (width, bar_bg.height)


class PendingCard(RoundedBox):
    """Auto-detected transaction waiting for confirmation."""

    def __init__(self, amount, kind, merchant, source, category, account,
                 confidence, on_confirm, on_reject, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(150))
        kwargs.setdefault("padding", dp(14))
        kwargs.setdefault("spacing", dp(6))
        super().__init__(bg_color="#FFFBEB", border_color=WARN, **kwargs)

        sign = "-" if kind == "expense" else "+"
        color = EXPENSE if kind == "expense" else INCOME
        self.add_widget(AppLabel(
            text=f"待确认：检测到{'支出' if kind == 'expense' else '收入'} {sign}¥{amount:,.2f}",
            bold=True, font_size=sp(15), color=rgba(color)))
        self.add_widget(AppLabel(
            text=f"商户/备注：{merchant or '未识别'}", font_size=sp(13),
            color=TEXT_MUTED))
        self.add_widget(AppLabel(
            text=f"来源：{source}  ·  分类：{category}  ·  账户：{account}",
            font_size=sp(12), color=TEXT_MUTED))
        self.add_widget(AppLabel(
            text=f"置信度 {confidence:.0%}", font_size=sp(12), color=TEXT_MUTED))

        actions = BoxLayout(orientation="horizontal", spacing=dp(10),
                            size_hint_y=None, height=dp(40))
        reject = AppButton(text="忽略", bg_color="#E5E7EB", color=TEXT,
                           font_size=sp(14))
        reject.bind(on_press=lambda *_: on_reject())
        confirm = AppButton(text="确认记账", bg_color=PRIMARY, font_size=sp(14))
        confirm.bind(on_press=lambda *_: on_confirm())
        actions.add_widget(reject)
        actions.add_widget(confirm)
        self.add_widget(actions)


class EmptyHint(AppLabel):
    def __init__(self, text="暂无数据", **kwargs):
        kwargs.setdefault("font_size", sp(13))
        kwargs.setdefault("color", TEXT_MUTED)
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(48))
        super().__init__(text=text, **kwargs)


def scroll_column():
    """Return (scrollview, inner_box) ready for dynamic content."""
    from kivy.uix.scrollview import ScrollView

    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, bar_width=dp(3))
    inner = BoxLayout(orientation="vertical", size_hint_y=None,
                      spacing=dp(10), padding=[dp(12), dp(12), dp(12), dp(24)])
    inner.bind(minimum_height=inner.setter("height"))
    scroll.add_widget(inner)
    return scroll, inner


def toast(message, title="提示"):
    popup = Popup(title=title, size_hint=(0.85, 0.35),
                  content=AppLabel(text=message, halign="center"))
    popup.open()
    return popup


def text_prompt(title, label, on_submit, hint="", initial=""):
    """Simple modal text prompt."""
    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    field = Field(label=label, hint=hint, text=initial, input_filter="float")
    content.add_widget(field)

    popup = Popup(title=title, size_hint=(0.9, 0.45), content=content,
                  auto_dismiss=True)

    row = BoxLayout(orientation="horizontal", spacing=dp(10),
                    size_hint_y=None, height=dp(44))
    cancel = AppButton(text="取消", bg_color="#E5E7EB", color=TEXT)
    cancel.bind(on_press=lambda *_: popup.dismiss())
    ok = AppButton(text="确定")
    ok.bind(on_press=lambda *_: (on_submit(field.text), popup.dismiss()))
    row.add_widget(cancel)
    row.add_widget(ok)
    content.add_widget(row)
    popup.open()
    return popup
