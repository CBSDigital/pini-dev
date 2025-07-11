"""General utilities for the pipe module."""

import logging
import os
import re

import lucidity

from pini.utils import (
    passes_filter, abs_path, single, safe_zip, norm_path, get_user, EMPTY)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TAG = os.environ.get('PINI_PIPE_DEFAULT_TAG', 'main')
ASSET_PROFILE = 'asset'
SHOT_PROFILE = 'shot'

EXTN_TO_DCC = {
    'blend': 'blender',
    'c4d': 'c4d',
    'hip': 'hou',
    'hiplc': 'hou',
    'nk': 'nuke',
    'nknc': 'nuke',
    'ma': 'maya',
    'mb': 'maya',
    'spp': 'substance',
    'tgd': 'terragen',
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
    _path = '/'.join(_path.split('/')[:_tmpl_path.count('/') + 1])

    _tmpl = pipe.CPTemplate('tmp', _tmpl_path)
    _LOGGER.debug(' - PATH (B) %s', _path)
    _LOGGER.debug(' - TMP TMPL %s', _tmpl)
    try:
        _data = _tmpl.parse(_path)
    except lucidity.ParseError as _exc:
        raise ValueError(path) from _exc

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
        _token = f'[{_opt}]'
        return fmt.replace(_token, ''), fmt.replace(_token, _opt)

    # Expand all possible combinations of option toggles
    _n_opts = len(_opts)
    _toggle_combis = []
    for _idx in range(2**_n_opts):
        _toggle_combi = [
            bool(int(_idx / (2 ** _jdx)) % 2)
            for _jdx in range(_n_opts - 1, -1, -1)]
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
            _token = f'[{_opt}]'
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
                return _dest + _path[len(_src):]
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


def passes_filters(  # pylint: disable=too-many-return-statements,too-many-branches
        obj, type_=None, path=None, status=None, dcc_=EMPTY, user=None,
        entity=None, entity_type=None, asset=None, asset_type=None,
        profile=None, output_name=None, output_type=EMPTY, content_type=None,
        id_=None, step=None, task=None, tag=EMPTY, ver_n=EMPTY,
        versionless=None, extn=EMPTY, extns=None, filter_=None,
        filter_attr='path', latest=False, filename=None, base=None):
    """Check whether the given object passes pipeline filters.

    Args:
        obj (CPOutput|any): pipeline object being tested
        type_ (str): match type (eg. cache, shot, render)
        path (str): apply path filter
        status (str): apply status filter
        dcc_ (str): apply dcc filter
        user (str): apply user filter
        entity (CPEntity): match entity
        entity_type (str): match entity type (ie. asset_type/sequence)
        asset (str): match asset name
        asset_type (str): match asset type
        profile (str): apply profile filter (ie. asset/shot)
        output_name (str): match output name
        output_type (str): match output type
        content_type (str): filter by content type
        id_ (int): match by id (for shotgrid elements)
        step (str): apply step filter
        task (str): match task (or pini task)
        tag (str): match tag
        ver_n (int|str): match version number
            (use "latest" to match latest version)
        versionless (bool): match by versionless status
        extn (str): match by extension
        extns (str list): match by extension list
        filter_ (str): apply filter to filter attribute
        filter_attr (str): filter attribute (default is path)
        latest (bool): filter out non-latest items
        filename (str): match by filename
        base (str): match by filename base

    Returns:
        (bool): whether object passed filters
    """
    from pini import pipe

    # Basic path filters
    if path and obj.path != path:
        return False
    if filter_:
        _filter_val = getattr(obj, filter_attr)
        if not passes_filter(_filter_val, filter_):
            return False
    if base:
        if obj.base != base:
            return False
    if filename:
        if obj.filename != filename:
            return False
    if extn is not EMPTY and obj.extn != extn:
        return False
    if extns and obj.extn not in extns:
        return False

    # Apply entity level filters
    assert profile in (None, 'asset', 'shot')
    if profile and obj.profile != profile:
        return False
    assert asset is None or isinstance(asset, str)
    if asset and obj.asset != asset:
        return False
    if asset_type and obj.asset_type != asset_type:
        return False
    assert entity is None or isinstance(entity, pipe.CPEntity)
    if entity and obj.entity != entity:
        return False
    if entity_type and obj.entity_type != entity_type:
        return False

    if type_ and obj.type_ != type_:
        return False

    # Apply token filters
    if task:
        _task_matches = {obj.task, obj.pini_task}
        if obj.step:
            _task_matches.add(f'{obj.step}/{obj.task}')
        if task not in _task_matches:
            return False
    if step and step != obj.step:
        return False
    if tag is not EMPTY and obj.tag != tag:
        return False
    if output_type is not EMPTY and obj.output_type != output_type:
        return False
    if output_name and obj.output_name != output_name:
        return False
    if content_type and obj.content_type != content_type:
        return False
    if dcc_ is not EMPTY and obj.dcc_ != dcc_:
        return False
    if user and obj.user != user:
        return False
    if status and obj.status != status:
        return False
    if versionless is not None and bool(obj.ver_n) == versionless:
        return False
    if id_ is not None and id_ != obj.id_:
        return False

    # Could be expensive so run last
    if latest and obj.latest:
        return obj.latest
    if ver_n is not EMPTY:
        if ver_n == 'latest':
            return obj.latest
        if obj.ver_n != ver_n:
            return False

    return True


def tag_sort(tag):
    """Sort tags with None as first to avoid py3 sorting error.

    Args:
        tag (str): tag to sort

    Returns:
        (str): tag sort key
    """
    _default_tags = {
        DEFAULT_TAG, 'default', 'main', None}
    return tag not in _default_tags, (tag or '').lower()


def task_sort(task):
    """Sort function for tasks.

    Args:
        task (str): task to sort

    Returns:
        (tuple): sort token
    """

    _task = task or ''

    if not isinstance(_task, str):
        raise ValueError(_task)

    # Test for step (if task has embedded step eg. surf/dev)
    _step = None
    if _task and '/' in _task:
        _step, _task = _task.split('/')

    _step_idx = _to_task_sort_idx(_step)
    _task_idx = _to_task_sort_idx(_task)
    _LOGGER.debug(
        ' - TASK SORT %d (%s), %d (%s), %s', _step_idx, _step,
        _task_idx, _task, _task)
    return _step_idx, _task_idx, _task


def _to_task_sort_idx(task):
    """Obtain task sort key for the given task name.

    Args:
        task (str): task name to sort

    Returns:
        (int): task sort index
    """
    from pini import pipe

    _tasks = [
        'none',

        'default',
        'cam',

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
    _task_s = str(_task).lower()
    if _task_s in _tasks:
        _idx = _tasks.index(_task_s)
    else:
        _idx = len(_tasks)
    _LOGGER.debug(' - TASK SORT KEY %s mapped=%s idx=%d', task, _task, _idx)

    return _idx


def to_basic_type(type_):
    """Obtain basic type name for a template type.

    This is the template type in a simple, readable form.

    eg. render -> render
        cache_seq -> cache
        blast_mov -> blast
        mov -> render

    Args:
        type_ (str): template type

    Returns:
        (str): nice type
    """
    _type = type_
    if _type.endswith('_mov'):
        _type = _type[:-4]
    if _type.endswith('_seq'):
        _type = _type[:-4]
    if _type == 'mov':
        _type = 'render'
    return _type


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
            f'Token "{token}" as "{value}" not in allowed values')

    # Apply length filter
    _len = _cfg.get('len')
    _strict_len = _cfg.get('strict_len')
    _LOGGER.debug(' - LEN %s', _len)
    if _strict_len and _len:
        _lens = _len if isinstance(_len, list) else [_len]
        if len(value) not in _lens:
            raise ValueError(
                f'Token "{token}" as "{value}" fails len')

    # Apply isdigit filter
    _is_digit = _cfg.get('isdigit')
    _LOGGER.debug(' - IS DIGIT %s', _is_digit)
    if _is_digit and value.isdigit() != _is_digit:
        raise ValueError(
            f'Token "{token}" as "{value}" fails as it is non-numeric')

    # Apply nospace filter
    _no_space = _cfg.get('nospace')
    _LOGGER.debug(' - NO SPACE %s', _no_space)
    if _no_space and ' ' in value:
        raise ValueError(
            f'Token "{token}" as "{value}" fails as it contains spaces')

    # Apply nounderscore filter
    _no_underscore = _cfg.get('nounderscore')
    _LOGGER.debug(' - NO UNDERSCORE %s', _no_underscore)
    if _no_underscore and '_' in value:
        raise ValueError(
            f'Token "{token}" as "{value}" fails as it contains underscores')

    # Apply text filter
    _filter = _cfg.get('filter')
    _LOGGER.debug(' - FILTER %s', _filter)
    if _filter and not passes_filter(value, _filter):
        raise ValueError(
            f'Token "{token}" as "{value}" fails filter')


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
