"""General utilities for managing deadline."""

import ast
import logging
import os
import time

from pini import icons, qt
from pini.utils import single, to_str, get_user, to_time_f, plural

_LOGGER = logging.getLogger(__name__)

ICON = icons.find('Balloon')
_USE_DEADLINE_SORTING = bool(os.environ.get('PINI_DEADLINE_USE_SORTING', False))


def _age_from_nice(nice):
    """Obtain age from readable age.

    Args:
        nice (str): readable age (eg. 6w)

    Returns:
        (int): age in seconds
    """
    if nice.endswith('w') and nice[:-1].isdigit():
        return int(nice[:-1]) * 60 * 60 * 24 * 7
    raise NotImplementedError(nice)


def flush_old_submissions(job, max_age='2w', count=20, force=False):
    """Flush old submission file from job tmp dir.

    Args:
        job (CPJob): job to flush
        max_age (str): remove submissions old than this
        count (int): leave a maximum of this many submissions
        force (bool): remove submissions without confirmation
    """
    _LOGGER.debug("FLUSH OLD SUBMISSIONS")

    _max_age = _age_from_nice(max_age)
    _root = job.to_subdir('.pini/Deadline/' + get_user())

    # Find submissions
    _subs = _root.find(type_='d', class_=True, catch_missing=True, depth=1)
    _subs.reverse()
    _LOGGER.debug(' - OUND %d SUBS', len(_subs))
    _subs = _subs[count:]
    _LOGGER.debug(' - CHECKING %d OLD SUBS', len(_subs))

    # Check remaining for older that max age
    _to_delete = []
    for _sub in _subs:
        _LOGGER.debug(' - SUB %s', _sub.filename)
        _time_f = to_time_f(time.strptime(_sub.filename, '%y%m%d_%H%M%S'))
        _age = time.time() - _time_f
        if _age > _max_age:
            _LOGGER.debug('   - OLD')
            _to_delete.append(_sub)

    if not _to_delete:
        _LOGGER.debug(' - NOTHING TO FLUSH')
    else:
        if not force:
            qt.ok_cancel(
                f'Flush {len(_to_delete):d} old '
                f'submission{plural(_to_delete)}?',
                title="Clean submissions", icon=icons.CLEAN)
        for _sub in qt.progress_bar(_to_delete):
            _sub.delete(force=True)


def info_key_sort(key):
    """Sort key for info data.

    Attempts to sort info data in the same order as deadline.

    Args:
        key (str): data key to sort

    Returns:
        (tuple): sort key
    """
    if not _USE_DEADLINE_SORTING:
        return key
    _list = [
        'Plugin', '\ufeffPlugin', 'Name', 'BatchName', 'Comment', 'Pool',
        'SecondaryPool', 'MachineLimit', 'Priority', 'OnJobComplete',
        'TaskTimeoutMinutes', 'MinRenderTimeMinutes', 'EnableAutoTimeout',
        'ConcurrentTasks', 'Department', 'Group', 'LimitGroups',
        'JobDependencies', 'Whitelist', 'OutputFilename0', 'Frames',
        'ChunkSize', 'AWSAssetFile', 'ExtraInfoKeyValue']
    _idx = len(_list)
    for _prefix in ['AWSAssetFile', 'ExtraInfoKeyValue']:
        if not key.startswith(_prefix):
            continue
        _suffix = key[len(_prefix):]
        if not _suffix.isdigit():
            continue
        _idx = _list.index('AWSAssetFile') + 0.001 * int(_suffix)
        break
    else:
        if key in _list:
            _idx = _list.index(key)
    return _idx, key


def job_key_sort(key):
    """Sort key for job data.

    Attempts to sort job data in the same order as deadline.

    Args:
        key (str): data key to sort

    Returns:
        (tuple): sort key
    """
    if not _USE_DEADLINE_SORTING:
        return key
    _list = [
        'Animation', 'RenderSetupIncludeLights', 'Renderer',
        'UsingRenderLayers', 'RenderLayer', 'RenderHalfFrames',
        'FrameNumberOffset', 'LocalRendering', 'StrictErrorChecking',
        'MaxProcessors', 'ArnoldVerbose', 'MayaToArnoldVersion', 'Version',
        'UseLegacyRenderLayers', 'Build', 'ProjectPath', 'StartupScript',
        'ImageWidth', 'ImageHeight', 'OutputFilePath', 'OutputFilePrefix',
        'Camera', 'Camera0', 'Camera1', 'Camera2', 'Camera3', 'Camera4',
        'Camera5', 'Camera6', 'Camera7', 'CountRenderableCameras',
        'IgnoreError211', 'UseLocalAssetCaching', 'EnableOpenColorIO',
        'OCIOConfigFile', 'OCIOPolicyFile']
    _idx = len(_list)
    if key in _list:
        _idx = _list.index(key)
    return _idx, key


def read_job_id(result):
    """Read deadline job id from submission output.

    Args:
        result (str): output to parse

    Returns:
        (str): job id
    """
    return single(read_job_ids(result))


def read_job_ids(result):
    """Read deadline job ids from submission output.

    Args:
        result (str): output to parse

    Returns:
        (str list): job ids
    """
    return [
        _line[len('JobID='):].strip()
        for _line in result.split('\n')
        if _line.startswith('JobID=')]


def setup_deadline_submit(group=None, paths=None, update_root=None, verbose=0):
    """Setup deadline ready for submission.

    Args:
        group (str): apply default group
        paths (str): paths to append to sys.path
        update_root (str): apply update libs check root
        verbose (int): print process data
    """

    # Apply group
    if group:
        os.environ['PINI_DEADLINE_GROUP'] = group

    # Set startup code
    if paths:

        # Gather path update py lines
        _lines = []
        _lines += [
            'import sys',
            'for _idx, _path in enumerate([']
        for _path in paths:
            _lines += [f'        "{_path}",']
        _lines += [
            ']):',
            '    sys.path.insert(_idx, _path)']
        _lines += [
            'import pini_startup',
            f'pini_startup.init(user="{get_user()}")']
        if update_root:
            _lines += [
                'from pini import refresh',
                f'refresh.update_libs(check_root="{update_root}")']

        # Build py + apply to env
        _py = '\n'.join(_lines)
        os.environ['PINI_DEADLINE_INIT_PY'] = _py
        if verbose:
            print('DEADLINE INIT PY:\n' + _py)


def wrap_py(py, name, py_file, work=None, maya=False, print_traceback=False):
    """Wrap mayapy code to be executed on deadline.

    Args:
        py (str): python code to execute
        name (str): task name
        py_file (PyFile): py file being written to
        work (File): work file
        maya (bool): apply maya init to wrapper
        print_traceback (bool): print formatted traceback (not needed
            generally - deadline/shell already prints traceback)

    Returns:
        (str): wrapped python
    """
    _init_py = os.environ.get('PINI_DEADLINE_INIT_PY')

    # Check init py is valid
    ast.parse(py)

    # Add header
    _lines = [
        'import logging',
        'import inspect',
        'import sys',
        'import traceback',
        '',
        'from maya import cmds' if maya else None,
        '',
        '_LOGGER = logging.getLogger("task")',
        '_FILE = inspect.getfile(lambda: None)',
        '', '']

    # Add init pipeline
    _lines += [
        'def _init_pipeline():',
        '    """Set up the pipeline."""',
        '']
    if maya:
        _lines += [
            '    # Initialize maya standalone',
            '    try:',
            '        from maya import standalone',
            '        standalone.initialize()',
            '    except RuntimeError:',
            '        pass',
            '']

    if _init_py:
        _code = '\n    '.join(_init_py.split('\n'))
        _lines += [
            '    # Run $PINI_DEADLINE_INIT_PY code',
            f'    {_code}',
            '']
    _lines += [
        '    # Setup loggging',
        '    from pini import testing',
        '    testing.setup_logging()',
        f'    _LOGGER.info("RUNNING {name} {py_file.path}")',
        '    _LOGGER.info(" - FILE %s", _FILE)',
        '',
        '    # Create QApplication to allow qt operations',
        '    from pini import qt',
        '    qt.get_application()',
        '']
    if maya and work:
        _lines += [
            '    # Load scene (deadline manages this but need for standalone)',
            '    from pini import dcc',
            f'    dcc.load("{to_str(work)}", lazy=True, force=True)',
            '']
    _lines += ['']

    # Add task py
    _task_py = '\n    '.join(py.split('\n'))
    _lines += [
        'def _exec_task():',
        '    """Execute this task."""',
        '',
        f'    {_task_py}',
        '', '']

    # Add main
    _lines += [
        'if __name__ == "__main__":',
        '',
        '    _init_pipeline()',
        '',
        '    # Execute task',
        '    from pini.tools import error',
        '    try:',
        '        _exec_task()',
        '    except Exception as _exc:',
        '        _LOGGER.info(" - ERRORED %s", _exc)']
    if print_traceback:
        _lines += [
            '        _err = error.PEError()',
            '        _LOGGER.info("TRACEBACK:\\n%s", _err.to_text())']
    if maya:
        _lines += ['        cmds.quit(exitCode=1, force=True)']
    else:
        _lines += ['        raise _exc']
    _lines += [
        '',
        '    _LOGGER.info("COMPLETE")',
        '']

    _py = '\n'.join(_line for _line in _lines if _line is not None)
    ast.parse(_py)

    return _py


def write_deadline_data(file_, data, sort=None, force=False):
    """Write data in deadline format to the given file.

    Args:
        file_ (File): file to write data to
        data (dict): data to write
        sort (fn): sort key for data
        force (bool): replace existing without confirmation
    """
    _text = ''
    for _key in sorted(data.keys(), key=sort):
        _val = data[_key]
        _text += f'{_key}={_val}\n'
        _LOGGER.debug(' - WRITE TEXT %s', _text)
    file_.write(_text, encoding='utf8', force=force)
