"""General utilities for managing deadline."""

import ast
import logging
import os

from pini import icons
from pini.utils import File, single, to_str

_LOGGER = logging.getLogger(__name__)

ICON = icons.find('Balloon')
DEADLINE_CMD = os.environ.get('PINI_DEADLINE_CMD')
if DEADLINE_CMD:
    DEADLINE_CMD = File(DEADLINE_CMD)
_INIT_PY = os.environ.get('PINI_DEADLINE_INIT_PY', 'pass')


def info_key_sort(key):
    """Sort key for info data.

    Attempts to sort info data in the same order as deadline.

    Args:
        key (str): data key to sort

    Returns:
        (tuple): sort key
    """
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
        _line[len('JobID='):]
        for _line in result.split('\n')
        if _line.startswith('JobID=')]


def wrap_py(py, name, work=None, maya=False):
    """Wrap mayapy code to be executed on deadline.

    Args:
        py (str): python code to execute
        name (str): task name
        work (File): work file
        maya (bool): apply maya init to wrapper

    Returns:
        (str): wrapped python
    """
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
    _lines += [
        '    # Run $PINI_DEADLINE_INIT_PY code',
        '    {}'.format('\n    '.join(_INIT_PY.split('\n'))),
        '    from pini import testing, dcc',
        '    testing.setup_logging()',
        '    _LOGGER.info("RUNNING {} %s", _FILE)'.format(name),
        '']
    if maya and work:
        _lines += [
            '    # Load scene (deadline manages this but need for standalone)',
            '    dcc.load("{}", lazy=True, force=True)'.format(to_str(work)),
            '']
    _lines += ['']

    # Add task py
    _lines += [
        'def _exec_task():',
        '    """Execute this task."""',
        '',
        '    {}'.format('\n    '.join(py.split('\n'))),
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
        '        _LOGGER.info(" - ERRORED %s", _exc)',
        '        _err = error.CEError()',
        '        _LOGGER.info("TRACEBACK:\\n%s", _err.to_text())']
    if maya:
        _lines += ['        cmds.quit(exitCode=1, force=True)']
    else:
        _lines += ['        sys.exit()']
    _lines += [
        '',
        '    _LOGGER.info("COMPLETE")',
        '']

    _py = '\n'.join(_line for _line in _lines if _line is not None)
    ast.parse(_py)

    return _py


def write_deadline_data(file_, data, sort=None):
    """Write data in deadline format to the given file.

    Args:
        file_ (File): file to write data to
        data (dict): data to write
        sort (fn): sort key for data
    """
    _text = ''
    for _key in sorted(data.keys(), key=sort):
        _val = data[_key]
        _text += '{}={}\n'.format(_key, _val)
    file_.write(_text)
