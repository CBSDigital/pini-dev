"""Tools for checking py file docstrings."""

import logging

from pini.utils import to_nice, copy_text

_LOGGER = logging.getLogger(__name__)


def _copy_suggestion_on_fail(func):
    """Decorator which copies a docs suggestion on fail.

    Args:
        func (fn): docs check function

    Returns:
        (dn): decorated function
    """

    def _copy_suggestion_func(arg):
        from pini.tools import error
        try:
            _result = func(arg)
        except error.FileError as _exc:
            _LOGGER.info('FAILED %s', arg)
            _suggestion = suggest_docs(arg)
            copy_text(_suggestion)
            raise _exc
        return _result

    return _copy_suggestion_func


def check_mod_docs(py_file):
    """Check module docstrings.

    Args:
        py_file (PyFile): file to check
    """
    from pini.tools import error
    _docs = py_file.to_docstring()
    if not _docs:
        raise error.FileError(
            'Missing module docs', file_=py_file, line_n=0)

    # Check title
    if not _docs.split('\n')[0].endswith('.'):
        raise error.FileError(
            'No trailing period in module docs title',
            file_=py_file, line_n=0)
    if not _docs[0].isupper():
        raise error.FileError(
            'Module docs title not capitalized',
            file_=py_file, line_n=0)


@_copy_suggestion_on_fail
def check_def_docs(def_):
    """Check def docstrings.

    Args:
        def_ (PyDef): def to check
    """
    from pini.tools import error

    if def_.clean_name != '__init__' and def_.clean_name.startswith('__'):
        return
    for _callback in ['callback', 'redraw', 'context']:
        if def_.clean_name.startswith(f'_{_callback}__'):
            return

    _docs = def_.to_docs()
    if not _docs.body:
        raise error.FileError(
            'Missing def docs', file_=def_.py_file, line_n=def_.line_n + 1)

    _check_def_title(def_, docs=_docs)
    _check_def_args(def_, docs=_docs)
    _check_def_result(def_, docs=_docs)


def _check_def_title(def_, docs):
    """Check def docstrings title.

    Args:
        def_ (PyDef): def to check
        docs (PyDefDocs): docstrings to check
    """
    from pini.tools import error

    if not docs.title[-1] == '.':
        raise error.FileError(
            'No trailing period in def docs title',
            file_=def_.py_file, line_n=def_.line_n + 1)
    if not docs.title[0].isupper():
        raise error.FileError(
            'Def docs title not capitalized',
            file_=def_.py_file, line_n=def_.line_n + 1)


def _check_def_args(def_, docs):
    """Check def docstrings args.

    Args:
        def_ (PyDef): def to check
        docs (PyDefDocs): docstrings to check
    """
    from pini.tools import error

    # Check for superfluous args
    _has_kwargs = bool(def_.to_ast().args.kwarg)
    if not _has_kwargs:
        for _arg_docs in docs.find_args():
            _arg = def_.find_arg(name=_arg_docs.name, catch=True)
            _LOGGER.debug(' - CHECK ARG DOCS %s %s', _arg_docs, _arg)
            if not _arg:
                raise error.FileError(
                    f'Arg "{_arg_docs.name}" docs are superflouous',
                    file_=def_.py_file, line_n=def_.line_n + 1)

    _args = list(def_.args)
    if _args and _args[0].name == 'self':
        _args.pop(0)

    for _arg in _args:
        _arg_docs = _arg.to_docs()
        _LOGGER.debug(' - CHECKING ARG %s %s', _arg, _arg_docs)
        if not _arg_docs or not _arg_docs.body:
            raise error.FileError(
                f'Arg "{_arg.name}" docs are missing',
                file_=def_.py_file, line_n=def_.line_n + 1)
        if not _arg_docs.type_:
            raise error.FileError(
                f'Arg "{_arg.name}" docs is missing type',
                file_=def_.py_file, line_n=def_.line_n + 1)

    for _arg, _arg_docs in zip(_args, docs.find_args()):
        if _arg.name != _arg_docs.name:
            raise error.FileError(
                f'Arg "{_arg.name}" docs are in the wrong position',
                file_=def_.py_file, line_n=def_.line_n + 1)


def _check_def_result(def_, docs):
    """Check def docstrings return statement.

    Args:
        def_ (PyDef): def to check
        docs (PyDefDocs): docstrings to check
    """
    from pini.tools import error
    if not docs.returns:
        return
    _LOGGER.debug(' - RETURNS %s', docs.returns)
    _r_type = docs.returns.split('):', 1)[0].strip('(')
    if not _r_type:
        raise error.FileError(
            'Missing returns type',
            file_=def_.py_file, line_n=def_.line_n)
    _r_body = docs.returns.split('):', 1)[1].strip()
    if not _r_body:
        raise error.FileError(
            'Missing returns body',
            file_=def_.py_file, line_n=def_.line_n)


def check_class_docs(class_):
    """Check class docstrings.

    Args:
        class_ (PyClass): class to check
    """
    from pini.tools import error
    _docs = class_.to_docstring()
    if not _docs:
        raise error.FileError(
            'Missing class docs',
            file_=class_.py_file, line_n=class_.line_n)


def suggest_docs(def_):
    """Suggest docstrings for the given def.

    Args:
        def_ (PyDef): def to suggest docstrings for

    Returns:
        (str): docstrings suggestion
    """
    _LOGGER.info('SUGGEST DOCS %s', def_)
    _LOGGER.info(' - NAME %s', def_.name)

    _ast = def_.to_ast()
    _indent = ' ' * (_ast.col_offset + 4)
    _LOGGER.info(' - INDENT %d "%s"', len(_indent), _indent)
    _code = def_.to_code()
    _cur_docs = def_.to_docs()
    _return = 'return ' in _code
    _LOGGER.info(' - CUR DOCS %s', _cur_docs)

    # Build header
    if _cur_docs:
        _header = _cur_docs.to_str('Header')
        _header = '\n'.join(
            _line for _line in _header.split('\n'))
        # _header = '\n'.join([_line.rstrip() for _line in _header.split('\n')])
    if not _header:
        _header = to_nice(def_.clean_name).capitalize()
    # _LOGGER.info(' - HEADER %s', _header)
    _header_lines = _header.split('\n')

    _lines = [f'"""{_header_lines[0]}']
    _lines += _header_lines[1:]

    # Add args
    _args = [  # Ignore method self args
        _arg for _idx, _arg in enumerate(def_.args)
        if _idx or _arg.name != 'self']
    if _args:
        _lines += [
            '',
            'Args:']
        for _idx, _arg in enumerate(_args):

            _cur_docs = _arg.to_docs()
            _LOGGER.info(' - ADDING ARG %s %s %s', _arg, _arg.type_, _cur_docs)

            # Get arg type
            _type = ''
            if _cur_docs and _cur_docs.type_:
                _type = _cur_docs.type_
            if not _type and _arg.has_default and _arg.default is not None:
                _LOGGER.info(
                    '   - APPLY TYPE FROM DEFAULT %s %s', _arg.type_,
                    _arg.type_.__name__)
                _type = _arg.type_.__name__

            _docs = ''
            if _cur_docs and _cur_docs.body:
                _docs = '\n        '.join(_cur_docs.body.split('\n'))

            _lines += [f'    {_arg.name} ({_type}): {_docs}']

    # Add returns
    if _return:
        _lines += [
            '',
            'Returns:',
            '    (): ']

    # Add tail
    if len(_lines) == 1:
        _lines[0] += '"""'
    else:
        _lines += ['"""']

    _docs = _indent + f'\n{_indent}'.join(_lines) + '\n'
    _docs = '\n'.join([
        _line if _line.strip() else ''
        for _line in _docs.split('\n')])
    return _docs
