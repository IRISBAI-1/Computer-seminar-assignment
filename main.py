import tkinter as tk
from fractions import Fraction
from pathlib import Path
from tkinter import ttk


DIGITS = "0123456789ABCDEF"
SUPPORTED_BASES = (2, 8, 10, 16)
MAX_PRECISION = 64


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


class BaseConverterApp:
    def __init__(self, root):
        self.root = root
        root.title("进制转换步骤演示器")
        root.geometry("1000x720")
        root.minsize(760, 600)

        style = ttk.Style()
        style.configure("TFrame", background="#ffffff")
        style.configure("TLabel", background="#ffffff", foreground="#333333",
                        font=("Microsoft YaHei UI", 10))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 7))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"),
                        padding=(12, 8))
        style.map("Accent.TButton",
                  background=[("!disabled", "#73a9ff"), ("active", "#5893ee")],
                  foreground=[("!disabled", "#ffffff")])
        style.configure("TCombobox", font=("Microsoft YaHei UI", 10), padding=5)

        self.from_var = tk.StringVar(value="10")
        self.to_var = tk.StringVar(value="2")
        self.value_var = tk.StringVar(value="10")
        self.precision_var = tk.StringVar(value="12")
        self.rounding_var = tk.StringVar(value="截断")

        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._layout)
        self._background_ids = []
        self._card_shadow = self.canvas.create_polygon(0, 0, 0, 0, smooth=True)
        self._card = self.canvas.create_polygon(0, 0, 0, 0, smooth=True)
        self._title = self.canvas.create_text(
            0, 0, text="进制转换步骤演示器", anchor="n",
            font=("Microsoft YaHei UI", 23, "bold"), fill="#444444"
        )

        self.content = tk.Frame(self.canvas, bg="#ffffff")
        self.content_window = self.canvas.create_window(
            0, 0, window=self.content, anchor="nw"
        )
        self._build_content()
        self._images = self._load_images()
        self._set_status("normal", "准备就绪")
        self.value_entry.focus_set()

    def _build_content(self):
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, minsize=190)
        self.content.grid_rowconfigure(0, weight=1)

        panel = tk.Frame(self.content, bg="#ffffff")
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(4, weight=1)

        tk.Label(panel, text="输入数值：", bg="#ffffff", fg="#333333",
                 font=("Microsoft YaHei UI", 10)).grid(
                     row=0, column=0, sticky="w", pady=(0, 12)
                 )
        self.value_entry = ttk.Entry(
            panel, textvariable=self.value_var, font=("Consolas", 12)
        )
        self.value_entry.grid(row=0, column=1, sticky="ew", pady=(0, 12))
        self.value_entry.bind("<Return>", lambda _event: self.convert())

        tk.Label(panel, text="转换进制：", bg="#ffffff", fg="#333333",
            font=("Microsoft YaHei UI", 10)
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))
        actions = tk.Frame(panel, bg="#ffffff")
        actions.grid(row=1, column=1, sticky="w", pady=(0, 12))
        self.from_select = ttk.Combobox(
            actions, textvariable=self.from_var, values=("2", "8", "10", "16"),
            state="readonly", width=10
        )
        self.from_select.pack(side="left", padx=(0, 8))
        ttk.Label(actions, text="→").pack(side="left", padx=(0, 8))
        self.to_select = ttk.Combobox(
            actions, textvariable=self.to_var, values=("2", "8", "10", "16"),
            state="readonly", width=10
        )
        self.to_select.pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="开始计算", style="Accent.TButton",
                   command=self.convert).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="清空", command=self.clear).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="精度", command=self._open_settings).pack(side="left")

        self.hint_label = tk.Label(
            panel, text="支持正负数、小数及 2 / 8 / 10 / 16 进制，十六进制数位使用 A–F",
            bg="#ffffff", fg="#888888", font=("Microsoft YaHei UI", 9),
            anchor="w", justify="left", wraplength=620
        )
        self.hint_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        output_frame = tk.Frame(
            panel, bg="#ffffff", highlightbackground="#e6e6e6",
            highlightthickness=1
        )
        output_frame.grid(row=4, column=0, columnspan=2, sticky="nsew")
        self.result_label = tk.Label(
            panel, text="等待计算", bg="#ffffff", fg="#333333",
            font=("Microsoft YaHei UI", 12, "bold"), anchor="w"
        )
        self.result_label.grid(row=3, column=0, columnspan=2, sticky="ew",
                               pady=(0, 8))
        self.output_text = tk.Text(
            output_frame, wrap="word", font=("Consolas", 10),
            bg="#ffffff", fg="#222222", relief="flat", padx=14, pady=12,
            state="disabled", spacing1=2, spacing3=3
        )
        scrollbar = ttk.Scrollbar(
            output_frame, orient="vertical", command=self.output_text.yview
        )
        self.output_text.configure(yscrollcommand=scrollbar.set)
        self.output_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        side_panel = tk.Frame(self.content, bg="#ffffff", width=190)
        side_panel.grid(row=0, column=1, sticky="nsew")
        side_panel.grid_propagate(False)
        side_panel.grid_rowconfigure(0, weight=1)
        self.image_label = tk.Label(side_panel, bg="#ffffff")
        self.image_label.grid(row=0, column=0, sticky="s")
        self.tip_label = tk.Label(
            side_panel, text="准备就绪", bg="#ffffff", fg="#666666",
            font=("Microsoft YaHei UI", 10), wraplength=180
        )
        self.tip_label.grid(row=1, column=0, sticky="n", pady=(10, 0))
        self._set_output("等待输入，点击开始计算查看演算步骤")

    def _load_images(self):
        image_dir = Path(__file__).resolve().parent / "design" / "prototype"
        images = {}
        for state, filename, max_height in (
            ("normal", "nailong_normal_tk.png", 270),
            ("error", "nailong_laugh_tk.png", 210),
            ("success", "nailong_ok_tk.png", 210),
        ):
            image = tk.PhotoImage(file=str(image_dir / filename))
            scale = max(
                1, (image.width() + 179) // 180,
                (image.height() + max_height - 1) // max_height
            )
            images[state] = image.subsample(scale, scale)
        return images

    @staticmethod
    def _rounded_points(x1, y1, x2, y2, radius):
        return (
            x1 + radius, y1, x2 - radius, y1, x2, y1,
            x2, y1 + radius, x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2, x1, y2,
            x1, y2 - radius, x1, y1 + radius, x1, y1,
        )

    def _layout(self, event):
        if event.width < 2 or event.height < 2:
            return
        for item in self._background_ids:
            self.canvas.delete(item)
        self._background_ids.clear()

        columns, rows = 24, 18
        start, end = (255, 247, 240), (240, 248, 255)
        for row in range(rows):
            for column in range(columns):
                ratio = (
                    column / max(1, columns - 1)
                    + row / max(1, rows - 1)
                ) / 2
                color = "#" + "".join(
                    f"{round(a + (b - a) * ratio):02x}"
                    for a, b in zip(start, end)
                )
                self._background_ids.append(self.canvas.create_rectangle(
                    event.width * column / columns,
                    event.height * row / rows,
                    event.width * (column + 1) / columns + 1,
                    event.height * (row + 1) / rows + 1,
                    fill=color, outline="", tags="background"
                ))

        card_width = min(1000, event.width - 32)
        card_height = max(460, event.height - 180)
        left = (event.width - card_width) / 2
        top = max(96, (event.height - card_height) / 2 + 20)
        self.canvas.coords(
            self._card_shadow,
            *self._rounded_points(left, top + 6, left + card_width,
                                  top + card_height + 6, 22)
        )
        self.canvas.itemconfigure(
            self._card_shadow, fill="#e7e7e8", outline="", smooth=True,
            splinesteps=12
        )
        self.canvas.coords(
            self._card,
            *self._rounded_points(left, top, left + card_width,
                                  top + card_height, 22)
        )
        self.canvas.itemconfigure(
            self._card, fill="#ffffff", outline="", smooth=True, splinesteps=12
        )
        self.canvas.coords(self._title, event.width / 2, 36)
        self.canvas.coords(self.content_window, left + 32, top + 32)
        self.canvas.itemconfigure(
            self.content_window, width=card_width - 64, height=card_height - 64
        )
        self.canvas.tag_lower("background")

    def _open_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("小数精度设置")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        content = ttk.Frame(dialog, padding=18)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="小数精度（1–64 位）").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 10)
        )
        ttk.Spinbox(content, textvariable=self.precision_var, from_=1,
                    to=MAX_PRECISION, width=7).grid(row=0, column=1, pady=(0, 10))
        ttk.Label(content, text="精度处理方式").grid(
            row=1, column=0, sticky="w", padx=(0, 12)
        )
        ttk.Combobox(content, textvariable=self.rounding_var,
                     values=("截断", "四舍五入"), state="readonly",
                     width=12).grid(row=1, column=1)
        ttk.Button(content, text="完成", command=dialog.destroy).grid(
            row=2, column=0, columnspan=2, sticky="e", pady=(16, 0)
        )

    def _set_output(self, content):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", content)
        self.output_text.configure(state="disabled")

    def _set_status(self, state, tip):
        self.image_label.configure(image=self._images[state])
        self.tip_label.configure(text=tip)

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
            self.result_label.configure(text="输入有误")
            self._set_status("error", "输入不对哦")
            return
        self._set_output(steps)
        self.result_label.configure(
            text=f"结果：{result}    ({self.value_var.get().strip()})₍{from_base}₎"
                 f" = ({result})₍{to_base}₎"
        )
        self._set_status("success", "计算完成！")

    def clear(self):
        self.value_var.set("")
        self._set_output("等待输入，点击开始计算查看演算步骤")
        self.result_label.configure(text="等待计算")
        self._set_status("normal", "准备就绪")


def main():
    root = tk.Tk()
    BaseConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
