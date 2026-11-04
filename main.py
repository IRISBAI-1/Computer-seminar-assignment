import tkinter as tk
from fractions import Fraction
from tkinter import messagebox, ttk


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
        root.minsize(760, 560)
        root.configure(bg="#f4f7fb")

        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TFrame", background="#f4f7fb")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#f4f7fb", foreground="#24364b",
                        font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#24364b",
                        font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Hint.TLabel", background="#f4f7fb", foreground="#718096",
                        font=("Microsoft YaHei UI", 9))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(12, 7))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"))

        container = ttk.Frame(root, padding=24)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="进制转换步骤演示器", style="Title.TLabel").pack(pady=(4, 16))

        controls = ttk.Frame(container, style="Card.TFrame", padding=16)
        controls.pack(fill="x", pady=(0, 10))
        self.value_var = tk.StringVar(value="10")
        self.from_var = tk.StringVar(value="10")
        self.to_var = tk.StringVar(value="2")
        self.precision_var = tk.StringVar(value="12")
        self.rounding_var = tk.StringVar(value="截断")

        ttk.Label(controls, text="输入数值").grid(row=0, column=0, sticky="w", padx=(0, 6))
        value_entry = ttk.Entry(controls, textvariable=self.value_var, font=("Consolas", 12))
        value_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(5, 0))
        ttk.Label(controls, text="源进制").grid(row=0, column=1, sticky="w")
        ttk.Combobox(controls, textvariable=self.from_var, values=("2", "8", "10", "16"),
                     state="readonly", width=7).grid(row=1, column=1, padx=(0, 10), pady=(5, 0))
        ttk.Label(controls, text="→ 目标进制").grid(row=0, column=2, sticky="w")
        ttk.Combobox(controls, textvariable=self.to_var, values=("2", "8", "10", "16"),
                     state="readonly", width=7).grid(row=1, column=2, padx=(0, 10), pady=(5, 0))
        ttk.Label(controls, text="小数精度").grid(row=0, column=3, sticky="w")
        ttk.Spinbox(controls, textvariable=self.precision_var, from_=1, to=MAX_PRECISION,
                    width=5).grid(row=1, column=3, padx=(0, 10), pady=(5, 0))
        ttk.Label(controls, text="舍入方式").grid(row=0, column=4, sticky="w")
        ttk.Combobox(controls, textvariable=self.rounding_var,
                     values=("截断", "四舍五入"), state="readonly",
                     width=9).grid(row=1, column=4, padx=(0, 10), pady=(5, 0))
        ttk.Button(controls, text="转换", style="Accent.TButton",
                   command=self.convert).grid(row=1, column=5, padx=(0, 6), pady=(5, 0))
        ttk.Button(controls, text="清空", command=self.clear).grid(row=1, column=6, pady=(5, 0))
        controls.columnconfigure(0, weight=1)
        value_entry.bind("<Return>", lambda _event: self.convert())

        ttk.Label(container, text="支持正负数、小数及 2 / 8 / 10 / 16 进制；十六进制数位使用 A–F。",
                  style="Hint.TLabel").pack(anchor="w", pady=(0, 12))

        panels = ttk.Frame(container)
        panels.pack(fill="both", expand=True)
        steps_card = ttk.Frame(panels, style="Card.TFrame", padding=14)
        steps_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        result_card = ttk.Frame(panels, style="Card.TFrame", padding=14)
        result_card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Label(steps_card, text="演算步骤", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(result_card, text="转换结果", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))

        self.steps_text = self._text_area(steps_card)
        self.result_text = self._text_area(result_card, height=8)
        self._set_text(self.steps_text, "输入数值并选择进制，点击“转换”查看完整演算过程。")
        self._set_text(self.result_text, "等待计算")
        value_entry.focus_set()

    @staticmethod
    def _text_area(parent, height=None):
        frame = ttk.Frame(parent, style="Card.TFrame")
        text = tk.Text(frame, wrap="word", height=height, font=("Consolas", 10),
                       bg="#ffffff", fg="#263445", relief="flat", padx=4, pady=4,
                       state="disabled", spacing1=2, spacing3=3)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        frame.pack(fill="both", expand=True)
        return text

    @staticmethod
    def _set_text(widget, content):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def convert(self):
        try:
            precision = int(self.precision_var.get())
            result, steps = convert_with_steps(
                self.value_var.get(),
                int(self.from_var.get()),
                int(self.to_var.get()),
                precision,
                self.rounding_var.get(),
            )
        except (ValueError, ZeroDivisionError) as error:
            messagebox.showerror("输入有误", str(error), parent=self.root)
            return
        self._set_text(self.steps_text, steps)
        self._set_text(
            self.result_text,
            f"结果：{result}\n\n({self.value_var.get().strip()})₍{self.from_var.get()}₎"
            f" = ({result})₍{self.to_var.get()}₎",
        )

    def clear(self):
        self.value_var.set("")
        self._set_text(self.steps_text, "输入数值并选择进制，点击“转换”查看完整演算过程。")
        self._set_text(self.result_text, "等待计算")


def main():
    root = tk.Tk()
    BaseConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
