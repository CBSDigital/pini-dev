"""Tools for managing traceback lines."""

from pini.utils import abs_path, File


class PETraceLine(object):
    """Represents a line of a traceback."""

    def __init__(self, file_, line_n, func, code):
        """Constructor.

        Args:
            file_ (str): path to code file
            line_n (int): error line number
            func (str): error function name
            code (str): code which errored
        """
        _file = file_
        if _file not in ['<string>']:
            _file = abs_path(_file)
        self.file_ = _file
        self.line_n = line_n
        self.func = func
        self.code = code

    def view_code(self):
        """Edit this line's code in a text editor."""
        File(self.file_).edit(line_n=self.line_n)

    def to_text(self, prefix=''):
        """Get this traceback line as text.

        Args:
            prefix (str): add line prefix

        Returns:
            (str): traceback text
        """
        return (
            '{prefix}File "{file}", line {line:d}, in {func}\n'
            '{prefix}  {code}').format(
                prefix=prefix, file=self.file_, line=self.line_n,
                func=self.func, code=self.code)


def line_from_str(line):
    """Convert string to tracback line object.

    Args:
        line (str): traceback line

    Returns:
        (PETraceLine): traceback line object
    """
    _top, _bot = line.split('\n')

    _file = _top.split('"')[1]
    _line_n = int(_top.split(',')[1].replace('line', '').strip())
    _func = _top.split()[-1]

    _code = _bot

    return PETraceLine(file_=_file, line_n=_line_n, func=_func, code=_code)
