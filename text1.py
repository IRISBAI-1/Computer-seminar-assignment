"""
================================================================
            进制转换器 (2 / 8 / 10 / 16 进制互转)
================================================================

一、核心算法
----------------------------------------------------------------
【算法1】十进制整数 → R 进制：除基取余，逆序排列
    N mod R = 最低位；N // R 继续，直到商为 0。
    余数按产生顺序是低位→高位，所以最后要逆序拼接。

【算法2】十进制小数 → R 进制：乘基取整，顺序排列
    小数 F 连续乘以目标基数 R：
        F × R = 整数部分 a_1 + 剩余小数 F_1
        F_1 × R = 整数部分 a_2 + 剩余小数 F_2
        ...
    每一步乘积的整数部分 a_i 就是新进制小数点后第 i 位；
    继续处理乘积的小数部分，直到：
        (a) 小数部分变为 0        → 可精确表示
        (b) 达到所需精度           → 按截断/舍入处理
    整数位出现的顺序就是高位→低位，所以顺序拼接即可。

【算法3】R 进制 → 十进制：按权展开求和
    N = Σ a_i·R^i，整数部分 i≥0，小数部分 i<0。
    实现用 Horner 法则：value = value·R + a_i，复杂度 O(n)。

【算法4】任意进制 → 任意进制：十进制中转法
    源进制 --按权展开--> 十进制 --除基取余 + 乘基取整--> 目标进制。

二、小数精度说明
----------------------------------------------------------------
  有些小数在目标进制中无法用有限位数精确表示。
  例：十进制 0.1 → 二进制 = 0.0001100110011...（无限循环）
  因此乘基取整需要给定精度 p，并在第 p+1 位上判断：
    - 截断 truncate：保留前 p 位，丢弃第 p+1 位及之后
    - 舍入 round   ：第 p+1 位 ≥ base/2 时向前进位
  舍入可能一路进位到整数部分，由 _round_up_base() 处理。
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
    除基取余法：n // base 得到商，n % base 得到余数；
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
def _round_up_base(digits_str, base):
    """
    在 base 进制下，对小数位串做「末位 +1」并处理进位。
    返回 (carry, result_str)：
      carry = 1 表示所有位都进位（如 0.FF → 整数部分 +1）
    """
    lst = [DIGITS.index(c) for c in digits_str]
    carry = 1
    i = len(lst) - 1
    while i >= 0 and carry:
        lst[i] += 1
        if lst[i] >= base:
            lst[i] = 0
            i -= 1
        else:
            carry = 0
    return carry, ''.join(DIGITS[d] for d in lst)


def _frac_to_digits(frac, base, precision=12, round_mode='truncate'):
    """
    乘基取整核心实现：

        cur = frac
        重复 precision+1 次：
            prod = cur × base
            digit = prod 的整数部分
            小数位追加 digit
            cur = prod 的小数部分
            若 cur == 0 → 精确终止

    返回 (小数位字符串, info)
      info['exact']     : 是否精确终止
      info['loop']      : 是否检测到循环
      info['loop_pos']  : 循环起始位置
      info['truncated'] : 是否因精度被截断/舍入
      info['carry_int'] : 舍入是否向整数部分进位
    """
    if frac <= 1e-15:
        return '', {'exact': True, 'loop': False, 'loop_pos': None,
                    'truncated': False, 'carry_int': 0}

    digits = []
    seen = {}
    loop_pos = None
    exact = False
    cur = frac
    max_steps = precision + 2             # 多算 1~2 位，供舍入判断

    for step in range(max_steps):
        if cur < 1e-15:                   # 小数部分为 0 → 精确终止
            exact = True
            break

        key = round(cur, 14)
        if key in seen and loop_pos is None:
            loop_pos = seen[key]          # 记录循环，但不提前终止
        else:
            seen[key] = len(digits)

        prod = cur * base                 # 乘基
        d = int(prod + 1e-12)             # 取整：乘积的整数部分
        if d >= base:                     # 浮点容错
            d = base - 1
        digits.append(d)
        cur = prod - d                    # 继续处理乘积的小数部分

    info = {
        'exact': exact,
        'loop': loop_pos is not None,
        'loop_pos': loop_pos,
        'truncated': False,
        'carry_int': 0,
    }

    if len(digits) <= precision:
        return ''.join(DIGITS[d] for d in digits), info

    # 超出精度 → 截断或舍入
    info['truncated'] = True
    kept = ''.join(DIGITS[d] for d in digits[:precision])

    if round_mode == 'round' and digits[precision] >= base / 2:
        carry, rounded = _round_up_base(kept, base)
        if carry:
            info['carry_int'] = 1
            return '0' * precision, info
        return rounded, info

    return kept, info


def dec_frac_to_base(frac, base, precision=12, round_mode='truncate'):
    """对外接口：只返回小数位字符串"""
    s, _ = _frac_to_digits(frac, base, precision, round_mode)
    return s


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
def convert(value_str, from_base, to_base, precision=12, round_mode='truncate'):
    """
    通用转换入口。
    value_str : 源数值字符串，可带正负号与小数点，如 "-1011.01"
    from_base : 源进制
    to_base   : 目标进制
    precision : 小数最大位数
    round_mode: 'truncate' 截断 / 'round' 四舍五入
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
    res_frac = ''
    if frac_val:
        res_frac, info = _frac_to_digits(
            frac_val, to_base, precision, round_mode)
        if info.get('carry_int'):
            int_val += 1                   # 舍入向整数部分进位
    res_int = dec_int_to_base(int_val, to_base)

    # 5) 拼装结果
    out = res_int + ('.' + res_frac if res_frac else '')
    if sign == '-' and (int_val or frac_val):
        out = '-' + out
    return out


# ==============================================================
#  演示函数
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


def demo_frac_conversion(value_str, from_base, to_base,
                         precision=12, round_mode='truncate'):
    """
    演示小数转换全过程：
      步骤1：源小数按负权展开 → 十进制小数
      步骤2：乘基取整 → 目标进制小数
      步骤3：判定终止 / 循环，按精度截断或舍入
    """
    s = value_str.strip().replace(' ', '').upper()
    if not s:
        print("× 输入为空")
        return

    sign = ''
    if s[0] in '+-':
        sign = '-' if s[0] == '-' else ''
        s = s[1:]
    int_part, _, frac_part = s.partition('.')
    if not frac_part:
        print("× 该数值不含小数部分，请输入带小数的数（如 0.1 / 101.01）")
        return
    if not int_part:
        int_part = '0'

    print("\n" + "=" * 70)
    print(f"  小数转换演示：({from_base}) {sign}{s} → ({to_base})")
    print(f"  精度 = {precision} 位    舍入模式 = "
          f"{'四舍五入' if round_mode == 'round' else '截断'}")
    print("=" * 70)
    print(f"\n  说明：整数部分 {sign}{int_part} 用【除基取余】处理（略）")
    print(f"        下面只演示小数部分 {frac_part} 的转换")

    # ---------- 步骤 1：按负权展开 ----------
    print(f"\n【步骤1】{from_base} 进制小数 → 十进制小数（按负权展开）")
    terms, value, weight = [], 0.0, 1.0
    for i, ch in enumerate(frac_part, 1):
        weight /= from_base
        d = char_to_val(ch, from_base)
        terms.append(f"{d}×{from_base}^(-{i})")
        value += d * weight
    print("  0." + frac_part + " = " + " + ".join(terms))
    print(f"           ≈ {value:.17g}")

    if value < 1e-15:
        print("\n  ✓ 小数部分数值为 0，结果就是 0")
        return

    # ---------- 步骤 2：乘基取整 ----------
    print(f"\n【步骤2】乘基取整：小数部分连续乘以目标基数 {to_base}")
    print(f"  每一步：当前小数 × {to_base} = 乘积")
    print(f"          乘积的整数部分 → 新进制的一位")
    print(f"          乘积的小数部分 → 继续下一步")
    print()
    print(f"  {'步':<3}{'当前小数':<20}{'× ' + str(to_base):<6}"
          f"{'乘积':<20}{'整数位':<8}{'剩余小数':<20}")
    print("  " + "-" * 78)

    cur = value
    digits = []
    seen = {}
    loop_pos = None
    exact = False
    max_steps = precision + 1          # 多算 1 位，用于舍入判断

    for step in range(max_steps):
        if cur < 1e-15:
            exact = True
            break

        key = round(cur, 14)
        if key in seen and loop_pos is None:
            loop_pos = seen[key]
        else:
            seen[key] = len(digits)

        prod = cur * to_base
        d = int(prod + 1e-12)
        if d >= to_base:
            d = to_base - 1
        rest = prod - d
        digits.append(d)

        print(f"  {step + 1:<3}{cur:<20.15f}{'':<6}"
              f"{prod:<20.10f}{DIGITS[d]:<8}{rest:<20.15f}")
        cur = rest

    # ---------- 步骤 3：判定与精度处理 ----------
    print(f"\n【步骤3】终止判定 & 按精度 {precision} 位处理")

    if exact:
        print(f"  ✓ 某一步乘积的小数部分为 0 → 可精确表示，共 {len(digits)} 位")
    elif loop_pos is not None:
        print(f"  ⚠ 剩余小数在第 {loop_pos + 1} 步已出现过 → 检测到循环")
        print(f"    该小数在 {to_base} 进制中【无法用有限位数精确表示】")
    else:
        print(f"  ⚠ 在 {max_steps} 步内小数部分仍未变为 0 → 无法精确表示")

    if len(digits) > precision:
        kept = ''.join(DIGITS[d] for d in digits[:precision])
        next_d = digits[precision]
        print(f"  保留前 {precision} 位：0.{kept}")
        print(f"  第 {precision + 1} 位：'{DIGITS[next_d]}'（数值 {next_d}）")
        if round_mode == 'round':
            half = to_base / 2
            if next_d >= half:
                print(f"  {next_d} ≥ {to_base}/2 = {half:g} → 进位")
                carry, rounded = _round_up_base(kept, to_base)
                if carry:
                    print("  ⚠ 所有位均进位 → 需向整数部分 +1")
                    print(f"  小数部分结果：0.{'0' * precision}")
                else:
                    print(f"  ✓ 四舍五入结果：0.{rounded}_{to_base}")
            else:
                print(f"  {next_d} < {to_base}/2 = {half:g} → 舍去")
                print(f"  ✓ 四舍五入结果：0.{kept}_{to_base}")
        else:
            print(f"  [截断模式] 舍去第 {precision + 1} 位及之后")
            print(f"  ✓ 截断结果：0.{kept}_{to_base}")
    else:
        result = ''.join(DIGITS[d] for d in digits)
        print(f"  位数 {len(digits)} ≤ 精度 {precision}，完整保留")
        print(f"  ✓ 结果：0.{result}_{to_base}")


# ==============================================================
#  交互主程序
# ==============================================================
def main():
    menu = """
--------------------------------------------------
  1. 进制转换（2 / 8 / 10 / 16 任意互转）
  2. 演示：除基取余（十进制整数 → R 进制）
  3. 演示：按权展开（R 进制 → 十进制）
  4. 演示：乘基取整（小数转换 + 精度处理）
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
                ps = input("小数精度（默认 12 位）: ").strip()
                prec = int(ps) if ps else 12
                if prec < 1:
                    print("× 精度必须 ≥ 1")
                    continue
                m = input("舍入方式（t=截断 / r=四舍五入，默认 t）: ").strip().lower()
                mode = 'round' if m == 'r' else 'truncate'
                result = convert(v, fb, tb, prec, mode)
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

        elif choice == '4':
            try:
                v = input("请输入带小数的数值（如 0.1 / 101.01 / -FF.A）: ").strip()
                fb = int(input("源进制 (2/8/10/16): ").strip())
                tb = int(input("目标进制 (2/8/10/16): ").strip())
                if fb not in (2, 8, 10, 16) or tb not in (2, 8, 10, 16):
                    print("× 仅支持 2 / 8 / 10 / 16 进制")
                    continue
                ps = input("精度（默认 12 位）: ").strip()
                prec = int(ps) if ps else 12
                if prec < 1:
                    print("× 精度必须 ≥ 1")
                    continue
                m = input("舍入方式（t=截断 / r=四舍五入，默认 t）: ").strip().lower()
                mode = 'round' if m == 'r' else 'truncate'
                demo_frac_conversion(v, fb, tb, prec, mode)
            except ValueError as e:
                print(f"× 输入错误: {e}")

        else:
            print("× 无效选项")


if __name__ == "__main__":
    main()