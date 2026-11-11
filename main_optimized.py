import math
import time
import tkinter as tk
from fractions import Fraction
from pathlib import Path
from tkinter import ttk


DIGITS = "0123456789ABCDEF"
SUPPORTED_BASES = (2, 8, 10, 16)
MAX_PRECISION = 64

UI_FONT = "Microsoft YaHei UI"
MONO_FONT = "Consolas"

FRAME_MS = 14          # 补间步长（约 60fps）
BG_BANDS = 96          # 背景渐变的分段数（复用同一批矩形，resize 只改坐标）
HOVER_MS = 200         # 悬停过渡
PRESS_MS = 90          # 按下过渡
RELEASE_MS = 200       # 抬起回弹
STATE_MS = 300         # 状态切换（插画 / 提示标签）
BANNER_MS = 360        # 结果横幅变色 + 闪光
SCROLL_MS = 280        # 滚轮惯性
INTRO_MS = 620         # 启动入场


# ---------------------------------------------------------------- 缓动与插值

def lerp(start, end, t):
    return start + (end - start) * t


def clamp01(t):
    return 0.0 if t < 0.0 else 1.0 if t > 1.0 else t


def ease_out_cubic(t):
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_out_quint(t):
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 5


def ease_in_out_cubic(t):
    t = clamp01(t)
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def ease_out_back(t, overshoot=1.4):
    """先略微越过终点再回位，用在按下抬起时更有“弹性”。"""
    t = clamp01(t)
    c3 = overshoot + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + overshoot * (t - 1.0) ** 2


def lerp_color(color_a, color_b, t):
    """#RRGGBB 线性插值，用于模拟 CSS 的颜色过渡。"""
    t = clamp01(t)
    try:
        ar, ag, ab = int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16)
        br, bg, bb = int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16)
    except (ValueError, IndexError):
        return color_b
    return "#{:02x}{:02x}{:02x}".format(
        round(lerp(ar, br, t)),
        round(lerp(ag, bg, t)),
        round(lerp(ab, bb, t)),
    )


def as_rgb(color, fallback):
    """把控件当前的 bg/fg 取成可插值的 #RRGGBB，异常时回退。"""
    if isinstance(color, str) and len(color) == 7 and color.startswith("#"):
        try:
            int(color[1:], 16)
        except ValueError:
            return fallback
        return color
    return fallback


class Ticker:
    """单定时器补间引擎。

    所有动画共用一个 after 循环，每帧按真实时间计算进度，
    因此偶尔的调度延迟不会让动画变慢或跳帧。
    """

    def __init__(self, root, interval_ms=FRAME_MS):
        self.root = root
        self.interval = max(1, int(interval_ms))
        self._tweens = {}
        self._after_id = None

    # ---- 对外接口
    def tween(self, key, duration_ms, step, easing=ease_out_cubic, done=None):
        self._tweens[key] = {
            "t0": time.perf_counter(),
            "duration": max(1.0, float(duration_ms)) / 1000.0,
            "step": step,
            "ease": easing,
            "done": done,
        }
        self._ensure_loop()
        return key

    def value(self, key, duration_ms, start, end, setter,
              easing=ease_out_cubic, done=None):
        return self.tween(
            key, duration_ms,
            lambda t: setter(lerp(start, end, t)),
            easing, done,
        )

    def cancel(self, key):
        self._tweens.pop(key, None)

    def cancel_prefix(self, prefix):
        for key in [k for k in self._tweens if k.startswith(prefix)]:
            self._tweens.pop(key, None)

    def is_running(self, key):
        return key in self._tweens

    # ---- 内部驱动
    def _ensure_loop(self):
        if self._after_id is None:
            try:
                self._after_id = self.root.after(self.interval, self._tick)
            except tk.TclError:
                self._after_id = None

    def _tick(self):
        self._after_id = None
        if not self._tweens:
            return
        now = time.perf_counter()
        finished = []
        for key, tween in list(self._tweens.items()):
            progress = (now - tween["t0"]) / tween["duration"]
            try:
                if progress >= 1.0:
                    tween["step"](1.0)
                    finished.append(key)
                else:
                    tween["step"](tween["ease"](progress))
            except tk.TclError:
                finished.append(key)
        for key in finished:
            tween = self._tweens.pop(key, None)
            if tween is None or tween["done"] is None:
                continue
            try:
                tween["done"]()
            except tk.TclError:
                pass
        if self._tweens:
            try:
                self._after_id = self.root.after(self.interval, self._tick)
            except tk.TclError:
                self._after_id = None


# ---------------------------------------------------------------- 转换算法

def digit_value(char, base):
    value = DIGITS.find(char.upper())
    if value < 0 or value >= base:
        raise ValueError(f"数位“{char}”不属于{base}进制")
    return value


def parse_number(text, base):
    """Parse a signed base-N number into an exact rational value."""
    source = text.strip().upper()
    if not source:
        raise ValueError("请输入要转换的数值")

    sign = 1
    if source[0] in "+-":
        if source[0] == "-":
            sign = -1
        source = source[1:]
    if not source or source.count(".") > 1:
        raise ValueError("数值格式不正确")

    if "." in source:
        integer_part, fraction_part = source.split(".", 1)
    else:
        integer_part, fraction_part = source, ""
    if not integer_part and not fraction_part:
        raise ValueError("数值格式不正确")

    for char in integer_part + fraction_part:
        digit_value(char, base)

    integer_value = 0
    for char in integer_part:
        integer_value = integer_value * base + digit_value(char, base)

    fraction_value = Fraction(0)
    for index, char in enumerate(fraction_part, 1):
        fraction_value += Fraction(digit_value(char, base), base ** index)

    return sign * (integer_value + fraction_value), integer_part or "0", fraction_part, sign


def fraction_text(value):
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def decimal_approximation(value, places=14):
    sign = "-" if value < 0 else ""
    value = abs(value)
    integer_part, remainder = divmod(value.numerator, value.denominator)
    if remainder == 0:
        return sign + str(integer_part)

    digits = []
    for _ in range(places):
        remainder *= 10
        digit, remainder = divmod(remainder, value.denominator)
        digits.append(str(digit))
        if remainder == 0:
            break
    suffix = "…" if remainder else ""
    return f"{sign}{integer_part}.{''.join(digits)}{suffix}"


def format_base_integer(value, base):
    if value == 0:
        return "0"
    digits = []
    while value:
        value, remainder = divmod(value, base)
        digits.append(DIGITS[remainder])
    return "".join(reversed(digits))


def round_fraction_digits(digits, base):
    result = list(digits)
    for index in range(len(result) - 1, -1, -1):
        value = DIGITS.index(result[index]) + 1
        if value < base:
            result[index] = DIGITS[value]
            return 0, "".join(result)
        result[index] = "0"
    return 1, "".join(result)


def convert_with_steps(text, from_base, to_base, precision=12, rounding="截断"):
    if from_base not in SUPPORTED_BASES or to_base not in SUPPORTED_BASES:
        raise ValueError("目前支持 2、8、10、16 进制")
    if not 1 <= precision <= MAX_PRECISION:
        raise ValueError(f"小数精度须为 1 到 {MAX_PRECISION} 位")
    if rounding not in ("截断", "四舍五入"):
        raise ValueError("请选择截断或四舍五入")

    value, integer_part, fraction_part, sign = parse_number(text, from_base)
    magnitude = abs(value)
    steps = []
    source = text.strip().upper()
    steps.append(f"转换：({source})₍{from_base}₎ → ({to_base}进制)")
    steps.append("")
    steps.append("一、源数按位权展开")
    terms = []
    for index, char in enumerate(integer_part):
        power = len(integer_part) - index - 1
        digit = digit_value(char, from_base)
        terms.append(f"{digit}×{from_base}^{power}")
    for index, char in enumerate(fraction_part, 1):
        digit = digit_value(char, from_base)
        terms.append(f"{digit}×{from_base}^(-{index})")
    steps.append(f"({source})₍{from_base}₎ = " + " + ".join(terms))
    steps.append(
        f"绝对值 = {fraction_text(magnitude)}₁₀"
        + (f" ≈ {decimal_approximation(magnitude)}₁₀"
           if magnitude.denominator != 1 else "")
    )

    integer_value = magnitude.numerator // magnitude.denominator
    fractional_value = magnitude - integer_value

    steps.extend(["", f"二、十进制整数转{to_base}进制（除基取余）"])
    if integer_value == 0:
        integer_result = "0"
        steps.append("0 ÷ " + str(to_base) + " = 0，整数结果为 0")
    else:
        current = integer_value
        remainders = []
        while current:
            quotient, remainder = divmod(current, to_base)
            remainders.append(DIGITS[remainder])
            steps.append(
                f"{current} ÷ {to_base} = {quotient}，余数 {DIGITS[remainder]}"
            )
            current = quotient
        integer_result = "".join(reversed(remainders))
        steps.append("余数从下往上读取：" + integer_result)

    steps.extend(["", f"三、十进制小数转{to_base}进制（乘基取整）"])
    fraction_digits = []
    remainder = fractional_value
    seen_remainders = {}
    loop_start = None
    rows = []
    for index in range(precision + 1):
        if remainder == 0:
            break
        if remainder in seen_remainders and loop_start is None:
            loop_start = seen_remainders[remainder]
        else:
            seen_remainders[remainder] = index

        product = remainder * to_base
        digit = product.numerator // product.denominator
        next_remainder = product - digit
        fraction_digits.append(DIGITS[digit])
        rows.append(
            f"第 {index + 1} 步：{fraction_text(remainder)} × {to_base}"
            f" = {DIGITS[digit]} + {fraction_text(next_remainder)}"
            f"（取数位 {DIGITS[digit]}，余 {fraction_text(next_remainder)}）"
        )
        remainder = next_remainder

    if fractional_value == 0:
        steps.append("小数部分为 0，无需转换。")
    else:
        steps.extend(rows)

    exact_fraction = remainder == 0
    carry_integer = 0
    if len(fraction_digits) <= precision:
        result_fraction = "".join(fraction_digits)
        if exact_fraction:
            steps.append(f"小数部分在 {len(fraction_digits)} 位后精确终止。")
        else:
            steps.append("小数部分尚未终止，将按所选精度处理。")
    else:
        kept_digits = "".join(fraction_digits[:precision])
        guard_digit = DIGITS.index(fraction_digits[precision])
        steps.append(
            f"保留前 {precision} 位：0.{kept_digits}；"
            f"第 {precision + 1} 位为 {fraction_digits[precision]}。"
        )
        result_fraction = kept_digits
        if rounding == "四舍五入" and guard_digit >= (to_base + 1) // 2:
            carry_integer, result_fraction = round_fraction_digits(kept_digits, to_base)
            steps.append("按四舍五入规则进位。")
        else:
            steps.append(f"按{rounding}规则处理。")

    if loop_start is not None:
        steps.append(f"检测到循环小数，循环从小数位第 {loop_start + 1} 位开始。")
    elif not exact_fraction:
        steps.append("小数部分不能在有限位数内精确表示。")

    integer_value += carry_integer
    integer_result = format_base_integer(integer_value, to_base)
    result_fraction = result_fraction.rstrip("0")
    result = integer_result
    if result_fraction:
        result += "." + result_fraction
    if sign < 0 and magnitude:
        result = "-" + result

    steps.extend(["", "四、转换结果", f"({source})₍{from_base}₎ = ({result})₍{to_base}₎"])
    return result, "\n".join(steps)


# ---------------------------------------------------------------- 圆角按钮

class RoundedButton(tk.Canvas):
    """带颜色过渡与下沉反馈的圆角按钮。"""

    def __init__(self, parent, text, command, ticker=None, accent=False,
                 width=100, height=46, background="#ffffff", radius=18):
        super().__init__(
            parent, width=width, height=height, bg=background,
            highlightthickness=0, bd=0, takefocus=True, cursor="hand2"
        )
        self.command = command
        self.ticker = ticker
        self.accent = accent
        self.text = text
        self.radius = radius
        self._hover = 0.0
        self._press = 0.0
        self._pressed = False
        self._key = f"btn{id(self)}"

        self.shadow = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.shape = self.create_polygon(0, 0, 0, 0, smooth=True)
        self.highlight = self.create_line(0, 0, 0, 0, fill="", smooth=True)
        self.label = self.create_text(
            0, 0, text=text, anchor="center",
            font=(UI_FONT, 10, "bold" if accent else "normal")
        )

        self.bind("<Configure>", self._on_configure)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<KeyPress-space>", self._on_key_press)
        self.bind("<KeyRelease-space>", self._on_key_release)
        self.bind("<KeyPress-Return>", self._on_key_press)
        self.bind("<KeyRelease-Return>", self._on_key_release)
        self._paint()

    @staticmethod
    def _rounded_points(x1, y1, x2, y2, radius):
        return (
            x1 + radius, y1, x2 - radius, y1, x2, y1,
            x2, y1 + radius, x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2, x1, y2,
            x1, y2 - radius, x1, y1 + radius, x1, y1,
        )

    def _on_configure(self, _event):
        self._paint()

    # ---- 补间：hover / press 都从“当前值”继续，中断时也不会跳变
    def _to(self, attr, target, duration, easing=ease_out_cubic):
        current = getattr(self, attr)
        if abs(current - target) < 1e-4:
            setattr(self, attr, target)
            return
        if self.ticker is None:
            setattr(self, attr, target)
            self._paint()
            return

        def step(t):
            setattr(self, attr, lerp(current, target, t))
            self._paint()

        self.ticker.tween(f"{self._key}-{attr}", duration, step, easing)

    def _paint(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 4 or height < 4:
            return

        hover = self._hover
        press = self._press
        sink = press * 2.0  # 按下时整体下沉，阴影被“压”短

        if self.accent:
            base, hover_color, press_color = "#007aff", "#1b8bff", "#005cc4"
            shadow_rest, shadow_down = "#dce5f2", "#c6daf5"
            text_color = "#ffffff"
        else:
            base, hover_color, press_color = "#f2f2f7", "#ececf2", "#dcdce4"
            shadow_rest, shadow_down = "#e7e8ed", "#dedfe7"
            text_color = "#1c1c1e"

        fill = lerp_color(lerp_color(base, hover_color, hover), press_color, press)
        shadow_fill = lerp_color(shadow_rest, shadow_down, max(hover, press))

        self.coords(
            self.shadow,
            *self._rounded_points(3, 4 - sink * 0.4, width - 3, height - 2, self.radius)
        )
        self.itemconfigure(self.shadow, fill=shadow_fill, outline="")

        self.coords(
            self.shape,
            *self._rounded_points(2, 1 + sink, width - 4, height - 5 + sink, self.radius)
        )
        if self.accent:
            self.itemconfigure(self.shape, fill=fill, outline="", width=0)
        else:
            self.itemconfigure(self.shape, fill=fill, outline="#ffffff", width=1)

        self.coords(
            self.highlight, self.radius + 2, 2 + sink, width - self.radius - 2, 2 + sink
        )
        self.itemconfigure(
            self.highlight, fill="#ffffff" if self.accent and press < 0.25 else ""
        )
        self.coords(self.label, width / 2, height / 2 + sink)
        self.itemconfigure(self.label, fill=text_color)

    # ---- 交互
    def _on_enter(self, _event):
        self._to("_hover", 1.0, HOVER_MS, ease_out_cubic)

    def _on_leave(self, _event):
        self._pressed = False
        self._to("_hover", 0.0, HOVER_MS, ease_out_cubic)
        self._to("_press", 0.0, RELEASE_MS, ease_out_back)

    def _on_press(self, _event):
        self.focus_set()
        self._pressed = True
        self._to("_press", 1.0, PRESS_MS, ease_out_cubic)

    def _on_release(self, event):
        activate = (
            self._pressed
            and 0 <= event.x < self.winfo_width()
            and 0 <= event.y < self.winfo_height()
        )
        self._pressed = False
        self._to("_press", 0.0, RELEASE_MS, ease_out_back)
        if activate:
            self.command()

    def _on_key_press(self, _event):
        if not self._pressed:
            self._pressed = True
            self._to("_press", 1.0, PRESS_MS, ease_out_cubic)
        return "break"

    def _on_key_release(self, _event):
        activate = self._pressed
        self._pressed = False
        self._to("_press", 0.0, RELEASE_MS, ease_out_back)
        if activate:
            self.command()
        return "break"


# ---------------------------------------------------------------- 主界面

class BaseConverterApp:
    TIP_COLORS = {
        "normal": ("#eef5ff", "#007aff"),
        "error": ("#fff0f0", "#ff3b30"),
        "success": ("#edf9f0", "#248a3d"),
    }
    BANNER_COLORS = {
        "normal": ("#eef5ff", "#007aff"),
        "error": ("#fff0f0", "#ff3b30"),
        "success": ("#edf9f0", "#248a3d"),
    }

    def __init__(self, root):
        self.root = root
        root.title("进制转换步骤演示器")
        root.geometry("1000x720")
        root.minsize(760, 600)
        root.configure(bg="#f2f2f7")

        self.anim = Ticker(root)

        self._build_styles()

        self.from_var = tk.StringVar(value="10")
        self.to_var = tk.StringVar(value="2")
        self.value_var = tk.StringVar(value="10")
        self.precision_var = tk.StringVar(value="12")
        self.rounding_var = tk.StringVar(value="截断")

        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg="#f2f2f7")
        self.canvas.pack(fill="both", expand=True)

        self._size = (1, 1)
        self._content_size = (0, 0)
        self._bg_size = (0, 0)
        self._intro_offset = 0.0
        self._intro_text = 0.0
        self._intro_played = False
        self._state = None
        self._reveal_token = 0
        self._revealing = False
        self._scroll_key = "scroll"

        # 背景渐变：固定一批横向色带，resize 时只改坐标和颜色。
        # 原来每帧重绘 1536 个格子（或逐格 put 像素）都会让窗口拖动卡顿。
        self._bg_rects = [
            self.canvas.create_rectangle(
                0, 0, 1, 1, fill="#f6f6fb", outline="", tags="background"
            )
            for _ in range(BG_BANDS)
        ]
        self._card_shadow_soft = self.canvas.create_polygon(
            0, 0, 0, 0, smooth=True, splinesteps=16,
            fill="#e8e9ef", outline=""
        )
        self._card_shadow = self.canvas.create_polygon(
            0, 0, 0, 0, smooth=True, splinesteps=12,
            fill="#e1e3e9", outline=""
        )
        self._card = self.canvas.create_polygon(
            0, 0, 0, 0, smooth=True, splinesteps=16,
            fill="#ffffff", outline="#e5e5ea", width=1
        )
        self._header_rule = self.canvas.create_line(
            0, 0, 0, 0, fill="#e5e5ea", width=1
        )
        self._title = self.canvas.create_text(
            0, 0, text="进制转换步骤演示器", anchor="n",
            font=(UI_FONT, 23, "bold"), fill="#1c1c1e"
        )
        self._subtitle = self.canvas.create_text(
            0, 0, text="看得见每一步的数制转换", anchor="n",
            font=(UI_FONT, 10), fill="#8e8e93"
        )
        self._brand_badge = self.canvas.create_polygon(
            0, 0, 0, 0, smooth=True, splinesteps=12,
            fill="#f3f7ff", outline="#dce7f6", width=1
        )
        self._brand_label = self.canvas.create_text(
            0, 0, text="数网知来组", anchor="center",
            font=(UI_FONT, 10, "bold"), fill="#007aff"
        )

        self.content = tk.Frame(self.canvas, bg="#ffffff")
        self.content_window = self.canvas.create_window(
            0, 0, window=self.content, anchor="nw"
        )

        self._build_content()
        self._images = self._load_images()
        self._set_status("normal", "准备就绪", animate=False)
        self._set_banner("等待计算", "normal", animate=False)
        self._set_output("等待输入，点击开始计算查看演算步骤", animate=False)
        self.value_entry.focus_set()

        self.canvas.bind("<Configure>", self._on_configure)

    # ---- ttk 样式
    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f2f7")
        style.configure("TLabel", background="#f2f2f7", foreground="#1c1c1e",
                        font=(UI_FONT, 10))
        style.configure(
            "TButton", font=(UI_FONT, 10), padding=(14, 9),
            background="#f2f2f7", foreground="#1c1c1e", borderwidth=0,
            focusthickness=0
        )
        style.map(
            "TButton",
            background=[("pressed", "#e5e5ea"), ("active", "#eaeaef")],
            foreground=[("disabled", "#aeaeb2")]
        )
        style.configure(
            "Accent.TButton", font=(UI_FONT, 10, "bold"),
            padding=(16, 9), background="#007aff", foreground="#ffffff"
        )
        style.map(
            "Accent.TButton",
            background=[("pressed", "#0063d1"), ("active", "#1684ff"),
                        ("!disabled", "#007aff")],
            foreground=[("!disabled", "#ffffff")]
        )
        style.configure(
            "TCombobox", font=(UI_FONT, 10), padding=(9, 7),
            fieldbackground="#ffffff", background="#f2f2f7",
            foreground="#1c1c1e", arrowcolor="#8e8e93",
            bordercolor="#dcdce4", lightcolor="#dcdce4", darkcolor="#dcdce4",
            insertcolor="#007aff"
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#ffffff")],
            bordercolor=[("focus", "#007aff")],
            selectbackground=[("readonly", "#d9eaff")],
            selectforeground=[("readonly", "#1c1c1e")]
        )
        style.configure(
            "TEntry", font=("Consolas", 11), padding=(10, 8),
            fieldbackground="#ffffff", foreground="#1c1c1e",
            bordercolor="#dcdce4", lightcolor="#dcdce4", darkcolor="#dcdce4",
            insertcolor="#007aff"
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", "#007aff")],
            lightcolor=[("focus", "#007aff")],
            darkcolor=[("focus", "#007aff")],
            fieldbackground=[("disabled", "#f2f2f7")]
        )

    def _build_content(self):
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, minsize=190)
        self.content.grid_rowconfigure(0, weight=1)

        panel = tk.Frame(self.content, bg="#ffffff")
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(5, weight=1)

        tk.Label(panel, text="输入数值", bg="#ffffff", fg="#3a3a3c",
                 font=(UI_FONT, 10)).grid(
                     row=0, column=0, sticky="w", pady=(0, 14)
                 )
        self.value_entry = ttk.Entry(
            panel, textvariable=self.value_var, font=(MONO_FONT, 12)
        )
        self.value_entry.grid(row=0, column=1, sticky="ew", pady=(0, 14))
        self.value_entry.bind("<Return>", lambda _event: self.convert())

        tk.Label(panel, text="转换进制", bg="#ffffff", fg="#3a3a3c",
                 font=(UI_FONT, 10)).grid(
                     row=1, column=0, sticky="w", pady=(0, 12)
                 )
        actions = tk.Frame(panel, bg="#ffffff")
        actions.grid(row=1, column=1, sticky="w", pady=(0, 12))
        self.from_select = ttk.Combobox(
            actions, textvariable=self.from_var, values=("2", "8", "10", "16"),
            state="readonly", width=8
        )
        self.from_select.pack(side="left", padx=(0, 10))
        ttk.Label(actions, text="→", foreground="#8e8e93").pack(
            side="left", padx=(0, 10)
        )
        self.to_select = ttk.Combobox(
            actions, textvariable=self.to_var, values=("2", "8", "10", "16"),
            state="readonly", width=8
        )
        self.to_select.pack(side="left")

        action_buttons = tk.Frame(panel, bg="#ffffff")
        action_buttons.grid(row=2, column=1, sticky="w", pady=(0, 12))
        self.convert_button = RoundedButton(
            action_buttons, text="开始计算", command=self.convert,
            ticker=self.anim, accent=True, width=112
        )
        self.convert_button.pack(side="left", padx=(0, 8))
        RoundedButton(
            action_buttons, text="清空", command=self.clear,
            ticker=self.anim, width=76
        ).pack(side="left", padx=(0, 8))
        RoundedButton(
            action_buttons, text="精度设置", command=self._open_settings,
            ticker=self.anim, width=96
        ).pack(side="left")

        self.hint_label = tk.Label(
            panel, text="支持正负数、小数及 2 / 8 / 10 / 16 进制；十六进制数位使用 A–F",
            bg="#ffffff", fg="#8e8e93", font=(UI_FONT, 9),
            anchor="w", justify="left", wraplength=620
        )
        self.hint_label.grid(row=3, column=0, columnspan=2, sticky="ew",
                             pady=(0, 14))

        self.result_label = tk.Label(
            panel, text="等待计算", bg="#eef5ff", fg="#007aff",
            font=(UI_FONT, 11, "bold"), anchor="w",
            padx=12, pady=9
        )
        self.result_label.grid(row=4, column=0, columnspan=2, sticky="ew",
                               pady=(0, 8))

        output_frame = tk.Frame(
            panel, bg="#ffffff", highlightbackground="#e5e5ea",
            highlightthickness=1, bd=0
        )
        output_frame.grid(row=5, column=0, columnspan=2, sticky="nsew")
        self.output_text = tk.Text(
            output_frame, wrap="word", font=(MONO_FONT, 10),
            bg="#ffffff", fg="#1c1c1e", relief="flat", padx=16, pady=14,
            state="disabled", spacing1=2, spacing3=3
        )
        self.output_text.tag_configure(
            "section", foreground="#007aff",
            font=(UI_FONT, 10, "bold"), spacing1=8, spacing3=4
        )
        self.output_text.tag_configure(
            "error", foreground="#c2414b", font=(UI_FONT, 10, "bold")
        )
        scrollbar = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output_text.yview
        )
        self.output_text.configure(yscrollcommand=scrollbar.set)
        self.output_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.output_text.bind("<MouseWheel>", self._on_wheel)
        output_frame.bind("<MouseWheel>", self._on_wheel)

        side_panel = tk.Frame(
            self.content, bg="#f8f8fa", width=190,
            highlightbackground="#e5e5ea", highlightthickness=1
        )
        side_panel.grid(row=0, column=1, sticky="nsew")
        side_panel.grid_propagate(False)
        side_panel.grid_rowconfigure(0, weight=1)
        self.image_label = tk.Label(side_panel, bg="#f8f8fa")
        self.image_label.grid(row=0, column=0, sticky="s")
        self.tip_label = tk.Label(
            side_panel, text="准备就绪", bg="#eef5ff", fg="#007aff",
            font=(UI_FONT, 10, "bold"), wraplength=160,
            padx=12, pady=10
        )
        self.tip_label.grid(row=1, column=0, sticky="n", padx=12,
                            pady=(12, 18))

    def _load_images(self):
        image_dir = Path(__file__).resolve().parent / "design" / "prototype"
        images = {}
        for state, filename, max_height in (
            ("normal", "nailong_normal_tk.png", 270),
            ("error", "nailong_laugh_tk.png", 210),
            ("success", "nailong_ok_tk.png", 210),
        ):
            path = image_dir / filename
            if not path.exists():
                continue
            image = tk.PhotoImage(file=str(path))
            scale = max(
                1, (image.width() + 179) // 180,
                (image.height() + max_height - 1) // max_height
            )
            images[state] = image.subsample(scale, scale)
        return images

    # ------------------------------------------------------------ 布局

    def _on_configure(self, event):
        if event.width < 2 or event.height < 2:
            return
        self._size = (event.width, event.height)
        self._paint_background(event.width, event.height)
        self._apply_geometry()
        if not self._intro_played:
            self._intro_played = True
            self.root.after(80, self._play_intro)

    def _paint_background(self, width, height):
        """复用固定色带重画渐变，resize 只花零点几毫秒。"""
        if self._bg_size == (width, height):
            return
        self._bg_size = (width, height)
        bands = len(self._bg_rects)
        top = (246, 246, 251)     # #f6f6fb
        bottom = (233, 239, 248)  # #e9eff8
        for index, rect in enumerate(self._bg_rects):
            y0 = int(height * index / bands)
            y1 = int(height * (index + 1) / bands) + 1
            ratio = index / max(1, bands - 1)
            color = "#{:02x}{:02x}{:02x}".format(
                round(lerp(top[0], bottom[0], ratio)),
                round(lerp(top[1], bottom[1], ratio)),
                round(lerp(top[2], bottom[2], ratio)),
            )
            self.canvas.coords(rect, -1, y0, width + 1, y1)
            self.canvas.itemconfigure(rect, fill=color)

    def _apply_geometry(self):
        width, height = self._size
        if width < 2 or height < 2:
            return

        card_width = min(1000, width - 32)
        card_height = max(460, height - 180)
        left = (width - card_width) / 2
        base_top = max(96, (height - card_height) / 2 + 20)
        top = base_top + self._intro_offset

        self.canvas.coords(
            self._card_shadow_soft,
            *self._rounded_points(left, top + 11, left + card_width,
                                  top + card_height + 11, 24)
        )
        self.canvas.coords(
            self._card_shadow,
            *self._rounded_points(left, top + 6, left + card_width,
                                  top + card_height + 6, 24)
        )
        self.canvas.coords(
            self._card,
            *self._rounded_points(left, top, left + card_width,
                                  top + card_height, 24)
        )
        self.canvas.coords(
            self._header_rule, left + 40, top + 1, left + card_width - 40, top + 1
        )

        offset = self._intro_text
        self.canvas.coords(self._title, width / 2, 25 + offset)
        self.canvas.coords(self._subtitle, width / 2, 61 + offset)
        badge_width, badge_height = 142, 34
        badge_right = width - 30
        badge_left = badge_right - badge_width
        badge_top = 30 + offset
        self.canvas.coords(
            self._brand_badge,
            *self._rounded_points(
                badge_left, badge_top, badge_right, badge_top + badge_height, 16
            )
        )
        self.canvas.coords(
            self._brand_label, badge_left + badge_width / 2,
            badge_top + badge_height / 2
        )

        self.canvas.coords(self.content_window, left + 32, top + 32)
        content_size = (card_width - 64, card_height - 64)
        if content_size != self._content_size:
            self._content_size = content_size
            self.canvas.itemconfigure(
                self.content_window, width=content_size[0], height=content_size[1]
            )
            # 提示文字按可用宽度重新折行，窗口变窄也不会溢出
            self.hint_label.configure(wraplength=max(260, content_size[0] - 230))

    @staticmethod
    def _rounded_points(x1, y1, x2, y2, radius):
        return (
            x1 + radius, y1, x2 - radius, y1, x2, y1,
            x2, y1 + radius, x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2, x1, y2,
            x1, y2 - radius, x1, y1 + radius, x1, y1,
        )

    def _play_intro(self):
        """整张卡片与顶部标题自下方缓入。"""
        card_from, text_from = 26.0, 12.0

        def step(t):
            self._intro_offset = card_from * (1.0 - t)
            self._intro_text = text_from * (1.0 - t)
            self._apply_geometry()

        self.anim.tween("intro", INTRO_MS, step, ease_out_cubic)

    # ------------------------------------------------------------ 状态切换

    def _set_status(self, state, tip, animate=True):
        previous = self._state
        self._state = state
        image = self._images.get(state)
        if image is not None:
            self.image_label.configure(image=image)
        self.tip_label.configure(text=tip)

        background, foreground = self.TIP_COLORS[state]
        start_bg = as_rgb(self.tip_label.cget("bg"), background)
        start_fg = as_rgb(self.tip_label.cget("fg"), foreground)
        if animate and (start_bg != background or start_fg != foreground):
            def step(t, bg0=start_bg, fg0=start_fg):
                self.tip_label.configure(
                    bg=lerp_color(bg0, background, t),
                    fg=lerp_color(fg0, foreground, t),
                )
            self.anim.tween("tip-color", STATE_MS, step, ease_out_cubic)
        else:
            self.tip_label.configure(bg=background, fg=foreground)

        if animate and previous is not None and previous != state:
            self._play_image_hop()

    def _play_image_hop(self):
        """插画无法做 alpha 淡入，用一次轻微起落代替，读起来更“活”。"""
        lift = 12

        def step(t):
            offset = lift * math.sin(math.pi * t)
            self.image_label.grid_configure(pady=(0, int(round(offset))))

        def done():
            self.image_label.grid_configure(pady=(0, 0))

        self.anim.tween("image-hop", STATE_MS, step, lambda t: t, done)

    def _set_banner(self, text, state, animate=True):
        self.result_label.configure(text=text)
        background, foreground = self.BANNER_COLORS[state]
        start_bg = as_rgb(self.result_label.cget("bg"), background)
        start_fg = as_rgb(self.result_label.cget("fg"), foreground)
        if not animate:
            self.result_label.configure(bg=background, fg=foreground)
            return
        # 先提亮一档再落回目标色，给结果一条“点亮”的过渡
        flash_bg = lerp_color(background, foreground, 0.12)

        def step(t):
            if t < 0.28:
                ratio = t / 0.28
                self.result_label.configure(
                    bg=lerp_color(start_bg, flash_bg, ratio),
                    fg=lerp_color(start_fg, foreground, ratio),
                )
            else:
                ratio = (t - 0.28) / 0.72
                self.result_label.configure(
                    bg=lerp_color(flash_bg, background, ratio),
                    fg=lerp_color(foreground, foreground, ratio),
                )

        self.anim.tween("banner", BANNER_MS, step, lambda t: t)

    # ------------------------------------------------------------ 输出区

    @staticmethod
    def _line_tag(line):
        if line.startswith(("一、", "二、", "三、", "四、", "转换：")):
            return "section"
        if line.startswith("错误："):
            return "error"
        return None

    def _set_output(self, content, animate=True):
        text = self.output_text
        self._reveal_token += 1
        token = self._reveal_token
        self.anim.cancel("reveal")
        self._revealing = False
        text.configure(state="normal")
        text.delete("1.0", "end")

        lines = content.split("\n")
        tags = [self._line_tag(line) for line in lines]
        inserted = [0]

        def insert_until(target):
            while inserted[0] < target:
                index = inserted[0]
                suffix = "\n" if index < len(lines) - 1 else ""
                text.insert("end", lines[index] + suffix)
                if tags[index]:
                    text.tag_add(tags[index], f"{index + 1}.0", f"{index + 1}.end")
                inserted[0] = index + 1
            text.yview_moveto(0)

        if not animate or len(lines) < 5:
            insert_until(len(lines))
            text.configure(state="disabled")
            return

        duration = min(460, 22 * len(lines))

        def step(t):
            if self._reveal_token != token:
                return
            insert_until(max(1, round(len(lines) * t)))

        def done():
            if self._reveal_token != token:
                return
            insert_until(len(lines))
            text.configure(state="disabled")
            self._revealing = False

        self._revealing = True
        self.anim.tween("reveal", duration, step, ease_out_cubic, done)

    def _on_wheel(self, event):
        if self._revealing:
            return "break"
        direction = -1 if event.delta > 0 else 1
        first, last = self.output_text.yview()
        span = last - first
        if span >= 0.999:
            return "break"
        target = min(1.0 - span, max(0.0, first + direction * span * 0.4))

        def step(t):
            self.output_text.yview_moveto(lerp(first, target, t))

        self.anim.tween(self._scroll_key, SCROLL_MS, step, ease_out_cubic)
        return "break"

    # ------------------------------------------------------------ 交互

    def _open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("小数精度设置")
        dialog.configure(bg="#ffffff")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

        content = tk.Frame(dialog, bg="#ffffff")
        content.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(
            content, text="小数精度（1–64 位）", bg="#ffffff", fg="#1c1c1e",
            font=(UI_FONT, 10)
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 10))
        ttk.Spinbox(content, textvariable=self.precision_var, from_=1,
                    to=MAX_PRECISION, width=7).grid(row=0, column=1, pady=(0, 10))
        tk.Label(
            content, text="精度处理方式", bg="#ffffff", fg="#1c1c1e",
            font=(UI_FONT, 10)
        ).grid(row=1, column=0, sticky="w", padx=(0, 12))
        ttk.Combobox(content, textvariable=self.rounding_var,
                     values=("截断", "四舍五入"), state="readonly",
                     width=12).grid(row=1, column=1)
        RoundedButton(
            content, text="完成", command=dialog.destroy, ticker=self.anim,
            accent=True, width=82, background="#ffffff"
        ).grid(row=2, column=0, columnspan=2, sticky="e", pady=(16, 0))

        dialog.update_idletasks()
        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 3
        dialog.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

        # 顶层窗口才支持 -alpha，这里能做真正的淡入
        try:
            dialog.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

        def fade(alpha):
            try:
                dialog.attributes("-alpha", alpha)
            except tk.TclError:
                self.anim.cancel("dialog-alpha")

        self.anim.value("dialog-alpha", 220, 0.0, 1.0, fade, ease_out_cubic)
        dialog.grab_set()

    def convert(self):
        try:
            precision = int(self.precision_var.get())
            from_base = int(self.from_var.get())
            to_base = int(self.to_var.get())
            result, steps = convert_with_steps(
                self.value_var.get(),
                from_base,
                to_base,
                precision,
                self.rounding_var.get(),
            )
        except (ValueError, ZeroDivisionError) as error:
            self._set_output(f"错误：{error}")
            self._set_banner("输入有误", "error")
            self._set_status("error", "输入不对哦")
            return
        self._set_output(steps)
        self._set_banner(
            f"结果：{result}    ({self.value_var.get().strip()})₍{from_base}₎"
            f" = ({result})₍{to_base}₎",
            "success",
        )
        self._set_status("success", "计算完成！")

    def clear(self):
        self.value_var.set("")
        self._set_output("等待输入，点击开始计算查看演算步骤", animate=False)
        self._set_banner("等待计算", "normal")
        self._set_status("normal", "准备就绪")
        self.value_entry.focus_set()


def main():
    root = tk.Tk()
    BaseConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
