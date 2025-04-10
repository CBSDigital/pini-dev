"""Tools for managing the system command."""

import logging
import platform
import subprocess

from . import u_text

_LOGGER = logging.getLogger(__name__)


def _build_cmds(cmd, verbose):
    """Build cmds list.

    Args:
        cmd (str|str_list): command(s) to execute
        verbose (int): print process data

    Returns:
        (str list): commands list
    """
    from pini.utils import Path, Seq, clip

    if isinstance(cmd, (list, tuple)):
        _cmds = cmd
    else:
        _cmds = []
        if platform.system() == 'Windows':
            _cmds += ["cmd", "/C"]
        _cmds += cmd.split()
    _cmds = [
        _item.path if isinstance(_item, (Path, Seq, clip.Seq))
        else str(_item)
        for _item in _cmds]
    if verbose:
        _LOGGER.info(' - SYSTEM %s', u_text.nice_cmds(_cmds))

    return _cmds


def system(
        cmd, result=True, decode='utf-8', block_shell_window=True, env=None,
        timeout=None, verbose=0):
    """Execute a system command.

    Args:
        cmd (str): command to execute
        result (bool): whether to wait + return result
            True|out - return stdout
            out/err - return stout/stderr as tuple
        decode (str): encoding to decode bytes result with
            (default is utf-8)
        block_shell_window (bool): prevent shell window from appearing
            (windows only)
        env (dict): override environment
        timeout (float): apply timeout in seconds
        verbose (int): print process data

    Returns:
        (str|tuple|None): result (if requested)
    """

    _cmds = _build_cmds(cmd, verbose=verbose)

    # Submit command
    _si = None
    if block_shell_window and platform.system() == 'Windows':
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _kwargs = {}
    if env is not None:
        _kwargs['shell'] = True
        _kwargs['env'] = env
    _pipe = subprocess.Popen(
        _cmds,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=_si,
        **_kwargs)
    if not result:
        return None

    # Process results
    _kwargs = {}
    if timeout:
        _kwargs['timeout'] = timeout
    _out, _err = _pipe.communicate(**_kwargs)
    if decode and isinstance(_out, bytes):
        _out = _out.decode(decode)
    if decode and isinstance(_err, bytes):
        _err = _err.decode(decode)

    # Handle result
    if result in [True, 'out']:
        return _out
    if result == 'out/err':
        return _out, _err
    if result == 'err':
        return _err
    raise ValueError(result)
