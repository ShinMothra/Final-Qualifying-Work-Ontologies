# modules/formula_module/formula_core.py

import re
from sympy import sympify, latex, Symbol, SympifyError, Eq, symbols as sympy_symbols
from sympy import __version__ as sympy_version
from typing import Dict, Any, Optional, List


# Символы зарезервированные в SymPy — их нужно создавать явно через Symbol(...)
_SYMPY_RESERVED = {
    'E', 'I', 'S', 'N', 'C', 'O',
    'pi', 'oo', 'zoo', 'nan',
    'exp', 'log', 'sin', 'cos', 'tan',
}

# Паттерн: строка содержит LaTeX-команды (\sum, \frac, \alpha и т.д.)
_LATEX_PATTERN = re.compile(r'\\[a-zA-Z]+[_^{]?')


def _is_latex(expr_str: str) -> bool:
    """Возвращает True если строка похожа на LaTeX-выражение."""
    return bool(_LATEX_PATTERN.search(expr_str))


def _try_parse_latex(expr_str: str):
    """
    Пробует разобрать строку через sympy.parsing.latex.
    Возвращает SymPy-выражение или None при ошибке.
    """
    try:
        from sympy.parsing.latex import parse_latex
        return parse_latex(expr_str.strip())
    except Exception:
        return None


def _safe_sympify(expr_str: str, local_syms: dict = None):
    """
    Безопасный sympify с явным созданием символов для зарезервированных имён.
    """
    identifiers = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', expr_str))

    local_dict = {}
    if local_syms:
        local_dict.update(local_syms)

    for ident in identifiers:
        if ident not in local_dict:
            local_dict[ident] = Symbol(ident)

    return sympify(expr_str, locals=local_dict, evaluate=False)


def _parse_expr(expr_str: str):
    """
    Универсальный парсер: сначала пробует LaTeX, затем SymPy-синтаксис.
    Возвращает SymPy-выражение.
    Бросает исключение если оба способа не сработали.
    """
    expr_str = expr_str.strip()

    if _is_latex(expr_str):
        result = _try_parse_latex(expr_str)
        if result is not None:
            return result
        # parse_latex недоступен (нет antlr4) — пробуем sympify как фоллбэк.
        # Для большинства простых LaTeX-выражений sympify тоже справится.
        try:
            return _safe_sympify(expr_str)
        except Exception:
            raise ValueError(
                f"Не удалось разобрать LaTeX-выражение: '{expr_str}'.\n"
                f"Для полной поддержки LaTeX установите: pip install antlr4-python3-runtime==4.11\n"
                f"Или используйте SymPy-нотацию: Sum(p_i, (i, 1, m))."
            )

    return _safe_sympify(expr_str)


class FormulaEvaluator:
    def __init__(self):
        self.expr = None
        self.lhs = None
        self.rhs = None
        self.symbols: Dict[str, Symbol] = {}
        self.original_string = ""
        self.is_latex_input = False   # флаг: формула введена в LaTeX-синтаксисе

    def parse(self, formula_str: str) -> tuple[bool, str]:
        """
        Парсит формулу. Поддерживает:
          - SymPy-синтаксис:  x**2 + y**2,  a = b*c + d
          - LaTeX-синтаксис:  \\sum_{i=1}^m p_i = 1,  \\frac{a}{b}
        """
        try:
            self.original_string = formula_str.strip()
            self.is_latex_input = _is_latex(self.original_string)

            if '=' in formula_str and not self.is_latex_input:
                # Для SymPy-синтаксиса делим по '=' вручную
                lhs_str, rhs_str = [p.strip() for p in formula_str.split('=', 1)]
                self.lhs = _parse_expr(lhs_str)
                self.rhs = _parse_expr(rhs_str)
                self.expr = Eq(self.lhs, self.rhs)
            else:
                # Для LaTeX — parse_latex сам разбирает уравнения
                parsed = _parse_expr(formula_str)
                # parse_latex может вернуть Eq напрямую
                if hasattr(parsed, 'lhs') and hasattr(parsed, 'rhs'):
                    self.lhs = parsed.lhs
                    self.rhs = parsed.rhs
                    self.expr = parsed
                else:
                    self.rhs = parsed
                    self.expr = parsed
                    self.lhs = None

            # Собираем символы из обеих частей
            all_free = set(self.rhs.free_symbols) if self.rhs is not None else set()
            if self.lhs is not None:
                all_free |= set(self.lhs.free_symbols)

            self.symbols = {str(s): s for s in all_free if s.is_Symbol}

            return True, "Формула успешно разобрана"

        except SympifyError as e:
            return False, f"Ошибка парсинга SymPy: {str(e)}"
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Неизвестная ошибка: {str(e)}"

    def get_latex(self) -> str:
        """
        Возвращает LaTeX-представление формулы.
        Если формула уже была введена в LaTeX — возвращаем оригинальную строку,
        так как SymPy может упростить/изменить вид при обратном переводе.
        """
        if self.expr is None:
            return ""
        # Если введено как LaTeX — рендерим оригинал, не конвертируя обратно
        if self.is_latex_input:
            return self.original_string
        try:
            return latex(self.expr, mode='plain')
        except Exception:
            return str(self.expr)

    def get_symbols(self) -> List[str]:
        return sorted(self.symbols.keys())

    def get_rhs_symbols(self) -> List[str]:
        if self.rhs is None:
            return []
        return sorted(str(s) for s in self.rhs.free_symbols if s.is_Symbol)

    def substitute(self, values: Dict[str, Any], constants: Dict[str, Any] = None) -> tuple[Optional[Any], str]:
        if self.rhs is None:
            return None, "Формула ещё не разобрана"

        try:
            subs_dict = {}

            if constants:
                for k, v in constants.items():
                    if k in self.symbols:
                        try:
                            subs_dict[self.symbols[k]] = float(str(v).replace(' ', ''))
                        except (ValueError, TypeError):
                            pass

            for k, v in values.items():
                if k in self.symbols:
                    try:
                        subs_dict[self.symbols[k]] = float(v)
                    except (ValueError, TypeError):
                        subs_dict[self.symbols[k]] = v

            result = self.rhs.subs(subs_dict)

            if hasattr(result, 'evalf'):
                result = result.evalf()

            return result, ""

        except Exception as e:
            return None, f"Ошибка вычисления: {str(e)}"

    def to_dict(self) -> dict:
        return {
            "string": self.original_string,
            "latex":  self.get_latex(),
            "lhs":    str(self.lhs) if self.lhs is not None else None,
            "rhs":    str(self.rhs) if self.rhs is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict):
        instance = cls()
        try:
            instance.original_string = data.get("string", "")
            if instance.original_string:
                instance.parse(instance.original_string)
        except Exception:
            pass
        return instance
