"""Tools for managing sequence tools."""

import logging
import os
import re

from ..u_error import DebuggingError
from ..u_misc import EMPTY
from ..path import Path, norm_path, Dir, File

from . import uc_seq

_LOGGER = logging.getLogger(__name__)


def find_seqs(
        dir_=None, files=None, depth=1, include_files=False, split_chrs='.',
        filter_=None, extn=EMPTY):
    """Find sequences in the given directory.

    Args:
        dir_ (str): path to search
        files (File list): override files to check (to avoid disk read)
        depth (int): search depth
        include_files (bool): include files which are not
            part of any sequence
        split_chrs (str): override frame split character
            eg. use "._" to match "blah_%04d.jpg" seqs
        filter_ (str): apply filename filter
        extn (str): filter by extension

    Returns:
        (Seq list): sequences found
    """
    if os.environ.get('PINI_DISABLE_FIND_SEQS'):
        raise DebuggingError(
            "Find sequences disabled using PINI_DISABLE_FIND_SEQS")

    # Obtain list of files
    _LOGGER.debug('FIND SEQS')
    if files is not None:
        _files = files
    else:
        assert dir_
        _dir = Dir(dir_)
        _LOGGER.debug(' - DIR %s', _dir.path)
        _files = _dir.find(
            type_='f', class_=True, depth=depth, filter_=filter_, extn=extn)
        _LOGGER.debug(' - FOUND %d FILES', len(_files))

    # Check which files fall into sequences
    _seqs = {}
    _non_seqs = []
    for _file in _files:

        _LOGGER.debug(' - TESTING FILE %s', _file)
        if not _count_split_chrs(_file.base, split_chrs=split_chrs):
            _non_seqs.append(_file)
            continue

        # Extract frame str
        _LOGGER.debug('   - BASE %s', _file.base)
        _tokens = _tokenise_base(_file.base, split_chrs=split_chrs)
        _frame_str = _tokens[-1]
        if not _frame_str.isdigit():
            _non_seqs.append(_file)
            continue
        _LOGGER.debug('   - FRAME STR %s', _frame_str)

        # Convert to frame expression + seq
        _frame = int(_frame_str)
        _frame_expr = f'%0{len(_frame_str):d}d'
        _LOGGER.debug('   - FRAME EXPR %s', _frame_expr)
        _seq_base = _file.base[:-len(_frame_str)] + _frame_expr
        _seq_path = _file.to_file(base=_seq_base).path

        # Ignore
        if _seq_path not in _seqs:
            _LOGGER.debug('   - CREATING SEQ %s', _seq_path)
            _LOGGER.debug('   - FILE frame_str=%s %s', _frame_str, _file.path)
            _safe = split_chrs == '.'
            try:
                _seq = uc_seq.Seq(_seq_path, safe=_safe)
            except ValueError:
                continue
            else:
                _seqs[_seq_path] = _seq

        _seqs[_seq_path].add_frame(_frame)

    _result = list(_seqs.values())
    if include_files:
        _result += _non_seqs

    return sorted(_result)


def _count_split_chrs(base, split_chrs):
    """Count split characters in the given base.

    Args:
        base (str): sequence base (eg. "blah.0001")
        split_chrs (str): character to split by (eg. ".")

    Returns:
        (int): number of instances of split characters
    """
    if len(split_chrs) == 1:
        return base.count('.')

    return sum(base.count(_chr) for _chr in split_chrs)


def _tokenise_base(base, split_chrs):
    """Tokenise the given base by split characters.

    Args:
        base (str): sequence base (eg. "blah.0001")
        split_chrs (str): character to split by (eg. ".")

    Returns:
        (str list): tokenised base (eg. ["blah", "0001"]
    """
    if len(split_chrs) == 1:
        return base.split(split_chrs)
    return re.split('[' + split_chrs + ']', base)


def file_to_seq(file_, safe=True, frame_expr=None, catch=False):
    """Build a sequence object from the given file path.

    eg. /blah/test.0123.jpg -> Seq("/blah/test.%04d.jpg")

    Args:
        file_ (str): file to convert
        safe (bool): only allow 4-zero frame padding (ie. %04d)
        frame_expr (str): override frame expression (eg. "<UDIM>")
        catch (bool): no error if file fails to map to sequence

    Returns:
        (Seq): sequence (if any)

    Raises:
        (ValueError): if the file is not a valid frame
    """
    _LOGGER.debug('FILE TO SEQ %s', file_)
    _file = File(file_)
    if safe and _file.filename.count('.') < 2:
        if catch:
            return None
        raise ValueError(_file.path)

    # Break out tokens
    if safe >= 2:
        _base, _f_str, _extn = _file.filename.rsplit('.', 2)
        _head, _tail = f'{_base}.', f'.{_extn}'
    else:
        try:
            _head, _f_str, _tail = _file_to_seq_unsafe(_file)
        except ValueError as _exc:
            if catch:
                return None
            raise ValueError(
                f'Failed to convert to path seq {file_}') from _exc
    _LOGGER.debug(' - TOKENS %s // %s // %s', _head, _f_str, _tail)

    # Check tokens
    if not (_f_str.isdigit() or _f_str in ['<UDIM>', '<U>_<V>']):
        if catch:
            return None
        raise ValueError(_f_str)
    if safe and len(_f_str) != 4:
        if catch:
            return None
        raise ValueError(_f_str)
    _f_expr = frame_expr or f'%0{len(_f_str):d}d'

    # Build into seq object
    _path = f'{_file.dir}/{_head}{_f_expr}{_tail}'
    _seq = uc_seq.Seq(_path, safe=safe)

    return _seq


def _file_to_seq_unsafe(file_):
    """Attempt to build an unsafe sequence object from a file.

    Args:
        file_ (File): file to convert

    Returns:
        (tuple): head / frame string / tail
    """
    _LOGGER.debug(' - FILE TO SEQ UNSAFE')

    # Try using standard splitters
    _tokens = re.split('[._]', file_.filename)
    if len(_tokens) >= 2 and (
            _tokens[-2].isdigit() or _is_fr_expr(_tokens[-2])):
        _LOGGER.debug('   - USING TOKENS %s', _tokens)
        _f_str, _extn = _tokens[-2], _tokens[-1]
        _head_len = len(file_.filename) - len(_f_str) - len(_extn) - 1
        _head = file_.filename[:_head_len]
        _tail = file_.filename[-len(_extn) - 1:]
        return _head, _f_str, _tail

    # Try 4-padded base suffix
    _LOGGER.debug('   - CHECKING BASE %s', file_.base)
    if len(file_.base) >= 4 and file_.base[-4:].isdigit():
        _LOGGER.debug('   - USING BASE SUFFIX %s', file_.base[-4:])
        _head = file_.base[:-4]
        _f_str = file_.base[-4:]
        _tail = f'.{file_.extn}'

        return _head, _f_str, _tail

    raise ValueError(file_)


def _is_fr_expr(text):
    """Test whether the given string is a valid frame expression.

    eg. "%04d", "<UDIM>"

    Args:
        text (str): string to check

    Returns:
        (bool): whether frame expression
    """
    if text in ['%04d', '<UDIM>', '<U>_<V>']:
        return True
    if (
            text.startswith('%0') and
            text.endswith('d') and
            text[3:-1].isdigit()):
        return True
    return False


def to_seq(obj, catch=True, safe=False):
    """Obtain a sequence from the given object.

    eg. "/tmp/blah.0001.jpg" -> Seq("/tmp/blah.%04d.jpg")
        "/tmp/blah.%04d.jpg" -> Seq("/tmp/blah.%04d.jpg")
        Seq("/tmp/blah.%04d.jpg") -> Seq("/tmp/blah.%04d.jpg")

    Args:
        obj (any): object to read sequence from
        catch (bool): no error if no seq found
        safe (bool): only allow sequences in blah.%04d.jpg format

    Returns:
        (Seq): sequence
    """
    _obj = obj
    _LOGGER.debug('TO SEQ %s', _obj)
    if isinstance(_obj, uc_seq.Seq):
        return _obj
    if isinstance(_obj, Path):
        _obj = _obj.path
    if isinstance(_obj, str):
        _seq = norm_path(_obj)
        for _token in ('.####.', '.$F4.'):
            _seq = _seq.replace(_token, '.%04d.')
        _LOGGER.debug(' - STR %s', _seq)
        if '%04d' in _seq:
            return uc_seq.Seq(_seq, safe=safe)
        _seq = file_to_seq(_obj, catch=True)
        if _seq:
            return _seq
    if catch:
        return None
    raise ValueError(obj)
