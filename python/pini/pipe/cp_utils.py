"""General utilities for the pipe module."""

import logging
import os
import re

import lucidity
import six

from pini.utils import (
    passes_filter, abs_path, single, safe_zip, norm_path, get_user)

_LOGGER = logging.getLogger(__name__)

EXTN_TO_DCC = {
    'blend': 'blender',
    'c4d': 'c4d',
    'hip': 'hou',
    'hiplc': 'hou',
    'nk': 'nuke',
    'nknc': 'nuke',
    'ma': 'maya',
    'mb': 'maya',
}


def admin_mode():
    """Test whether we are in admin mode.

    Returns:
        (bool): whether admin mode
    """
    if 'PINI_ADMIN_MODE' in os.environ:
        return os.environ['PINI_ADMIN_MODE'] == '1'
    return True


def are_valid_tokens(data, job):
    """Check whether the given token are valid based on given job config.

    Args:
        data (dict): token/value data
        job (CPJob): job to use config from

    Returns:
        (bool): whether tokens are valid
    """
    try:
        validate_tokens(data=data, job=job)
    except ValueError:
        return False
    return True


def cur_user():
    """Obtain current pipeline user.

    In shotgrid this is the current user's login field with non-path
    friendly characters replaced with hyphens. Otherwise this is simply
    the current username.

    Returns:
        (str): current pipeline user
    """
    from pini import pipe
    if pipe.MASTER == 'shotgrid':
        from . import shotgrid
        _login = shotgrid.SGC.find_user(get_user()).login
        _user = '-'.join(re.split('[@.]', _login))
        return _user
    return get_user()


def extract_template_dir_data(path, template, job=None, safe=True):
    """Extract directory information from the given template.

    This assumes that the path points to somewhere within the given
    template. The path is cropped to the template depth and then
    the template data is extracted from the cropped path.

    Args:
        path (str): path to read
        template (Template): template to apply
        job (CPJob): job to read path from
        safe (bool): error if job object not passed (to avoid unnecessary
            building of job objects)

    Returns:
        (str, dict): cropped path, extracted data

    Raises:
        (ValueError): if template did not match path
    """
    from pini import pipe
    _LOGGER.debug('EXTRACT TEMPLATE DIR DATA')
    _LOGGER.debug(' - PATH (A) %s', path)
    _LOGGER.debug(' - TMPL %s', template)

    _job = job
    if not _job:
        if safe:
            raise RuntimeError("Failed to pass job object")
        _job = pipe.CPJob(path)

    # Get template path
    _tmpl_path = template.pattern.replace('{job_path}', _job.path)

    # Crop path to template depth
    _path = abs_path(path)
    _path = '/'.join(_path.split('/')[:_tmpl_path.count('/')+1])

    _tmpl = pipe.CPTemplate('tmp', _tmpl_path)
    _LOGGER.debug(' - PATH (B) %s', _path)
    _LOGGER.debug(' - TMP TMPL %s', _tmpl)
    try:
        _data = _tmpl.parse(_path)
    except lucidity.ParseError:
        raise ValueError(path)

    validate_tokens(_data, job=_job)

    return _path, _data


def expand_pattern_variations(fmt):
    """Expand optional tokens in a template.

    eg. {AAA}/{BBB}[_{CCC}].{extn}

    -> {AAA}/{BBB}_{CCC}.{extn}
       {AAA}/{BBB}.{extn}

    The more complex patterns are returned first so these are matched in
    preference to less complex ones.

    Args:
        fmt (str): format str to expand

    Returns:
        (str list): list of patterns to parse
    """
    _LOGGER.debug('EXPAND PATTERN VARIATIONS %s', fmt)
    assert fmt.count('[') == fmt.count(']')
    if '[' not in fmt:
        return [fmt]

    _opts = {_token.split(']')[0] for _token in fmt.split('[')[1:]}

    # Handle single opt (could be removed but remains for clarity)
    if len(_opts) == 1:
        _opt = single(_opts)
        _token = '[{}]'.format(_opt)
        return fmt.replace(_token, ''), fmt.replace(_token, _opt)

    # Expand all possible combinations of option toggles
    _n_opts = len(_opts)
    _toggle_combis = []
    for _idx in range(2**_n_opts):
        _toggle_combi = [bool(int(_idx/(2**_jdx)) % 2)
                         for _jdx in range(_n_opts-1, -1, -1)]
        _toggle_combis.append(_toggle_combi)
        _LOGGER.debug(' - ADD COMBINATION %s', _toggle_combi)

    # Expand to formats
    _fmts = []
    for _toggle_combi in _toggle_combis:
        _fmt = fmt
        for _enabled, _opt in safe_zip(_toggle_combi, _opts):
            if not _enabled:
                _replace = ''
            else:
                _replace = _opt
            _token = '[{}]'.format(_opt)
            _fmt = _fmt.replace(_token, _replace)
        _fmts.append(norm_path(_fmt))

    return _fmts


def is_valid_token(value, token, job):
    """Test whether the given token is valid.

    Args:
        value (str): token value (eg. shot010/anim)
        token (str): token name (eg. entity/task)
        job (CPJob): job (for config)

    Returns:
        (bool): whether token valid
    """
    try:
        validate_token(value=value, token=token, job=job)
    except ValueError:
        return False
    return True


def map_path(path, mode='start'):
    """Map a path to a local standard if $PINI_PATH_MAP is set.

    For example: to map 'V:/Jobs/blah' -> '/mnt/jobs/blah'
                 $PINI_PATH_MAP should be set to 'V:/Jobs>>>/mnt/jobs'

    If $PINI_PATH_MAP is not set, the path is just returned.

    Args:
        path (str): path to map
        mode (str): how to map path
            start - assume the whole input path is a path (default)
            any - assume any part of the input can contain a path

    Returns:
        (str): mapped path
    """
    if not path:
        return None
    _map = os.environ.get('PINI_PATH_MAP')
    if not _map:
        return path

    _path = norm_path(path)
    for _entry in _map.split(';'):
        _src, _dest = _entry.split('>>>')
        if mode == 'start':
            if _path.lower().startswith(_src.lower()):
                return _dest+_path[len(_src):]
        elif mode == 'any':
            _path = _path.replace(_src, _dest)
        else:
            raise ValueError(mode)

    return _path


def output_clip_sort(output):
    """Sort for output sequences to priorities certain layers.

    Args:
        output (CPOutput): output to sort

    Returns:
        (tuple): sort key
    """
    _priority_lyrs = ['masterLayer', 'defaultRenderLayer']
    return output.output_name not in _priority_lyrs, output.path


def tag_sort(tag):
    """Sort tags with None as first to avoid py3 sorting error.

    Args:
        tag (str): tag to sort

    Returns:
        (str): tag sort key
    """
    _default_tags = {
        os.environ.get('PINI_PIPE_DEFAULT_TAG'), 'default', 'main', None}
    return tag not in _default_tags, (tag or '').lower()


def task_sort(task):
    """Sort function for tasks.

    Args:
        task (str): task to sort

    Returns:
        (tuple): sort token
    """

    _task = task or ''

    if not isinstance(_task, six.string_types):
        raise ValueError(_task)

    # Test for step (if task has embedded step eg. surf/dev)
    _step = None
    if _task and '/' in _task:
        _step, _task = _task.split('/')

    return _to_task_sort_idx(_step), _to_task_sort_idx(_task), _task


def _to_task_sort_idx(task):
    """Obtain task sort key for the given task name.

    Args:
        task (str): task name to sort

    Returns:
        (int): task sort index
    """
    from pini import pipe

    _tasks = [
        None,

        'default',

        'mod',
        'model',
        'modelling',
        'scan',
        'photo',

        'rig',
        'rigging',

        'texture',
        'texturing',
        'lookdev',
        'shade',
        'mat',
        'surf',

        'previz',
        'layout',
        'trk',
        'track',
        'tracking',
        'anm',
        'anim',
        'animation',

        'cfx',
        'techanim',
        'crowd',

        'fx',

        'light',
        'lighting',

        'mattepainting',
        'paint',
        'roto',
        'comp',
        'nuke',
        'gfx',

        'test',
        'dev',
    ]
    _task = pipe.map_task(task)
    if str(_task).lower() in _tasks:
        _idx = _tasks.index(_task.lower())
    else:
        _idx = len(_tasks)
    _LOGGER.debug(' - TASK SORT KEY %s mapped=%s idx=%d', task, _task, _idx)

    return _idx


def validate_token(value, token, job):
    """Validate the given token.

    This reads config validation from job config and checks whether the
    given token passes.

    Args:
        value (str): token value
        token (str): token name (eg. task)
        job (CPJob): job to read config from

    Raises:
        (ValueError): if validation fails
    """
    _LOGGER.debug('VALIDATE TOKEN value=%s token=%s', value, token)

    _tokens_cfg = job.cfg['tokens']
    if token not in _tokens_cfg:
        _LOGGER.debug(' - MISSING FROM CFG')
        return
    _cfg = _tokens_cfg[token]

    # Apply whitelist
    _whitelist = _cfg.get('whitelist', [])
    _LOGGER.debug(' - WHITELIST %s', _whitelist)
    if value in _whitelist:
        _LOGGER.debug(' - IN WHITELIST')
        return

    # Apply allowed values
    _allowed = _cfg.get('allowed')
    if _allowed and value not in _allowed:
        raise ValueError(
            'Token "{}" as "{}" not in allowed values'.format(
                token, value))

    # Apply length filter
    _len = _cfg.get('len')
    _LOGGER.debug(' - LEN %s', _len)
    if _len:
        _lens = _len if isinstance(_len, list) else [_len]
        if len(value) not in _lens:
            raise ValueError('Token "{}" as "{}" fails len'.format(
                token, value))

    # Apply isdigit filter
    _is_digit = _cfg.get('isdigit')
    _LOGGER.debug(' - IS DIGIT %s', _is_digit)
    if _is_digit and value.isdigit() != _is_digit:
        raise ValueError(
            'Token "{}" as "{}" fails as it is non-numeric'.format(
                token, value))

    # Apply nospace filter
    _no_space = _cfg.get('nospace')
    _LOGGER.debug(' - NO SPACE %s', _no_space)
    if _no_space and ' ' in value:
        raise ValueError(
            'Token "{}" as "{}" fails as it contains spaces'.format(
                token, value))

    # Apply nounderscore filter
    _no_underscore = _cfg.get('nounderscore')
    _LOGGER.debug(' - NO UNDERSCORE %s', _no_underscore)
    if _no_underscore and '_' in value:
        raise ValueError(
            'Token "{}" as "{}" fails as it contains underscores'.format(
                token, value))

    # Apply text filter
    _filter = _cfg.get('filter')
    _LOGGER.debug(' - FILTER %s', _filter)
    if _filter and not passes_filter(value, _filter):
        raise ValueError('Token "{}" as "{}" fails filter'.format(
            token, value))


def validate_tokens(data, job):
    """Validate token data using job config.

    This reads the filter for the given token from job config (if there
    is one) and raises an error if the token value does not pass the
    filter.

    Args:
        data (dict): token name/value data
        job (CPJob): job to read config from

    Raises:
        (ValueError): if validation fails
    """
    _tokens_cfg = job.cfg['tokens']
    for _token, _val in data.items():
        validate_token(job=job, token=_token, value=_val)
