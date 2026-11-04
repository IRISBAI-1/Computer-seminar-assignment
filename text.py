"""
================================================================
            进制转换器 (2 / 8 / 10 / 16 进制互转)
================================================================

一、核心算法与推导
----------------------------------------------------------------
【算法1】十进制整数 → R 进制：除基取余，逆序排列

  推导：设 N 用 R 进制表示为
        N = a_k·R^k + ... + a_2·R^2 + a_1·R + a_0     (0 ≤ a_i < R)

  (1) 两边同时对 R 取余：
        N mod R = a_0                         → 得到最低位 a_0
  (2) 两边同时整除 R：
        N // R = a_k·R^(k-1) + ... + a_1      → 商中已消去 a_0
  (3) 对商重复 (1)(2)，依次得到 a_1, a_2, ...
  (4) 余数出现的顺序是 低位 → 高位，因此需要【逆序】拼接。

【算法2】十进制小数 → R 进制：乘基取整，顺序排列

  推导：设小数 F = a_1·R^-1 + a_2·R^-2 + a_3·R^-3 + ...   (0 ≤ F < 1)
  (1) 两边乘 R：F·R = a_1 + (a_2·R^-1 + a_3·R^-2 + ...)
  (2) 其整数部分恰为 a_1                     → 小数点后第 1 位
  (3) 取走整数部分，余下的小数继续乘 R，依次得到 a_2, a_3, ...
  (4) 整数出现的顺序就是 高位 → 低位，因此【顺序】拼接。
  注：可能无限循环，故需给定精度上限。

【算法3】R 进制 → 十进制：按权展开求和

  N = Σ a_i · R^i  (整数部分 i ≥ 0，小数部分 i < 0)

  实现上用 Horner 法则：value = value·R + a_i
  它等价于按权展开，但避免了重复计算幂，复杂度 O(n)。

【算法4】任意进制 → 任意进制：十进制中转法

  规则：源进制  --按权展开-->  十进制  --除基取余-->  目标进制
  以十进制作为"中转站"，避免为 4×3=12 种组合各写一套算法。

  特例优化（二进制 ↔ 八/十六进制）：
    八进制每位 = 3 个二进制位，十六进制每位 = 4 个二进制位，
    可以直接"位组映射"，无需经过十进制。
================================================================
"""

DIGITS = "0123456789ABCDEF"          # 数码表，支持到 16 进制


# ==============================================================
#  基础工具
# ==============================================================
def char_to_val(ch, base):
    """单个字符 → 数值，并校验是否属于该进制"""
    ch = ch.upper()
    if ch not in DIGITS:
        raise ValueError(f"非法字符: {ch}")
    v = DIGITS.index(ch)
    if v >= base:
        raise ValueError(f"字符 '{ch}' 不属于 {base} 进制")
    return v


# ==============================================================
#  算法1：除基取余  （十进制整数 → R 进制）
# ==============================================================
def dec_int_to_base(n, base):
    """
    除基取余法：n // base 得到商，n % base 得到余数，
    余数从低位到高位依次产生，最后逆序拼接。
    """
    if n == 0:
        return "0"
    stack = []
    while n > 0:
        stack.append(DIGITS[n % base])     # 取余 —— 当前最低位
        n //= base                         # 取商 —— 下次的被除数
    return ''.join(reversed(stack))        # 逆序排列


# ==============================================================
#  算法2：乘基取整  （十进制小数 → R 进制）
# ==============================================================
def dec_frac_to_base(frac, base, precision=12):
    """
    乘基取整法：小数反复乘 base，整数部分依次取出，
    整数从高位到低位依次产生，顺序拼接即可。
    """
    out = []
    while frac > 1e-15 and len(out) < precision:
        frac *= base
        d = int(frac + 1e-12)              # 取整（加微小量消除浮点误差）
        if d >= base:                      # 容错保护
            d = base - 1
        out.append(DIGITS[d])
        frac -= d                          # 去掉已取走的整数部分
    return ''.join(out)


# ==============================================================
#  算法3：按权展开  （R 进制 → 十进制）
# ==============================================================
def base_to_dec_int(s, base):
    """整数部分按权展开，用 Horner 法则实现"""
    value = 0
    for ch in s:
        value = value * base + char_to_val(ch, base)
    return value


def base_to_dec_frac(s, base):
    """小数部分按负权展开：a_1·R^-1 + a_2·R^-2 + ..."""
    value = 0.0
    weight = 1.0
    for ch in s:
        weight /= base                     # 1/R, 1/R², ...
        value += char_to_val(ch, base) * weight
    return value


# ==============================================================
#  算法4：任意进制 → 任意进制（十进制中转）
# ==============================================================
def convert(value_str, from_base, to_base, precision=12):
    """
    通用转换入口。
    value_str : 源数值字符串，可带正负号与小数点，如 "-1011.01"
    from_base : 源进制
    to_base   : 目标进制
    """
    s = value_str.strip().replace(' ', '').upper()
    if not s:
        raise ValueError("输入为空")

    # 1) 处理符号
    sign = ''
    if s[0] in '+-':
        sign = '-' if s[0] == '-' else ''
        s = s[1:]

    # 2) 拆分整数/小数部分
    int_part, _, frac_part = s.partition('.')
    if not int_part and not frac_part:
        raise ValueError("输入非法")

    # 3) 源进制 → 十进制（按权展开）
    int_val = base_to_dec_int(int_part or '0', from_base)
    frac_val = base_to_dec_frac(frac_part, from_base) if frac_part else 0.0

    # 4) 十进制 → 目标进制（除基取余 + 乘基取整）
    res_int = dec_int_to_base(int_val, to_base)
    res_frac = dec_frac_to_base(frac_val, to_base, precision) if frac_val else ''

    # 5) 拼装结果
    out = res_int + ('.' + res_frac if res_frac else '')
    if sign == '-' and (int_val or frac_val):
        out = '-' + out
    return out


# ==============================================================
#  演示函数：把推导过程可视化
# ==============================================================
def demo_division(n, base):
    """演示 除基取余 的完整过程"""
    print(f"\n[除基取余] 十进制 {n} → {base} 进制")
    if n == 0:
        print("  结果为 0")
        return
    remainders = []
    while n > 0:
        q, r = divmod(n, base)
        print(f"  {n:>4} ÷ {base} = {q:>4}  …… 余 {DIGITS[r]}")
        remainders.append(DIGITS[r])
        n = q
    print("  余数从下往上读: " + ''.join(reversed(remainders)))


def demo_weight(s, base):
    """演示 按权展开 的完整过程"""
    s = s.strip().upper()
    print(f"\n[按权展开] {base} 进制 {s} → 十进制")
    terms, value = [], 0
    for i, ch in enumerate(s):
        power = len(s) - 1 - i
        d = char_to_val(ch, base)
        terms.append(f"{d}×{base}^{power}")
        value = value * base + d
    print("  " + " + ".join(terms))
    print(f"  = {value}")


# ==============================================================
#  交互主程序
# ==============================================================
def main():
    menu = """
--------------------------------------------------
  1. 进制转换（2 / 8 / 10 / 16 任意互转）
  2. 演示：除基取余（十进制整数 → R 进制）
  3. 演示：按权展开（R 进制 → 十进制）
  0. 退出
--------------------------------------------------"""
    while True:
        print(menu)
        choice = input("请选择: ").strip()

        if choice == '0':
            print("再见！")
            break

        elif choice == '1':
            try:
                v = input("请输入数值（如 1011.01 / -FF / 255）: ").strip()
                fb = int(input("源进制 (2/8/10/16): ").strip())
                tb = int(input("目标进制 (2/8/10/16): ").strip())
                if fb not in (2, 8, 10, 16) or tb not in (2, 8, 10, 16):
                    print("× 仅支持 2 / 8 / 10 / 16 进制")
                    continue
                result = convert(v, fb, tb)
                print(f"\n√  ({v})_{fb}  =  ({result})_{tb}\n")
            except ValueError as e:
                print(f"× 输入错误: {e}")

        elif choice == '2':
            try:
                n = int(input("十进制整数: ").strip())
                b = int(input("目标进制 (2/8/16): ").strip())
                if b not in (2, 8, 16):
                    print("× 请选择 2 / 8 / 16")
                    continue
                demo_division(n, b)
            except ValueError:
                print("× 请输入合法整数")

        elif choice == '3':
            try:
                s = input("源数值: ").strip()
                b = int(input("源进制 (2/8/16): ").strip())
                if b not in (2, 8, 16):
                    print("× 请选择 2 / 8 / 16")
                    continue
                demo_weight(s, b)
            except ValueError as e:
                print(f"× 输入错误: {e}")

        else:
            print("× 无效选项")


if __name__ == "__main__":
    main()