"""General tools for managing outputs."""

import logging

from pini import dcc
from pini.utils import File, abs_path, to_str

_LOGGER = logging.getLogger(__name__)


def cur_output():
    """Get output currently loaded in dcc (if any).

    Returns:
        (CPOutput): matching output
    """
    _file = dcc.cur_file()
    if not _file:
        return None
    try:
        return to_output(_file)
    except ValueError:
        return None


def to_output(
        path, job=None, entity=None, work_dir=None, template=None,
        latest=None, catch=False):
    """Get an output object based on the given path.

    Args:
        path (str): path to convert
        job (CPJob): parent job
        entity (CPEntity): parent entity
        work_dir (CPWorkDir): parent work dir
        template (CPTemplate): template to use
        latest (bool): apply latest status to output
        catch (bool): no error if no output created

    Returns:
        (CPOutput|CPOutputSeq): output or output seq
    """
    _LOGGER.log(9, 'TO OUTPUT %s', path)
    _kwargs = locals()
    from pini import pipe

    # Handle catch
    if catch:
        _kwargs.pop('catch')
        try:
            return to_output(**_kwargs)
        except ValueError as _exc:
            return None

    if not path:
        raise ValueError('Empty path')

    _path = abs_path(to_str(path))
    _file = File(_path)
    _LOGGER.log(9, ' - PATH %s', _file.path)
    if '%' in _file.path:
        _class = pipe.CPOutputSeq
    elif _file.extn and _file.extn.lower() in ('mp4', 'mov'):
        _class = pipe.CPOutputVideo
    else:
        _class = pipe.CPOutputFile
    return _class(
        _path, job=job, entity=entity, template=template, work_dir=work_dir,
        latest=latest)
