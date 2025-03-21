"""Tools for managing writing out caches."""

import logging

from maya import cmds

from pini import pipe, icons, qt, dcc, farm
from pini.tools import sanity_check, error
from pini.utils import single, plural, safe_zip, passes_filter, last

from maya_pini import ref, open_maya as pom
from maya_pini.utils import (
    hide_img_planes, restore_frame, blast_frame, save_fbx, restore_sel)

from . import mpc_ref, mpc_cam, mpc_cset

_LOGGER = logging.getLogger(__name__)


def _check_for_output_clash(cacheables, extn):
    """Check for multiple outputs writing to the same path.

    Args:
        cacheables (CPCacheable list): items being cached
        extn (str): cache output format (abc/fbx)
    """
    _LOGGER.debug('CHECK FOR OUTPUT CLASH')
    _outs = []
    for _cbl in cacheables:
        _LOGGER.debug(' - TESTING %s', _cbl)
        _out = _cbl.to_output(extn=extn)
        _LOGGER.debug('   - OUTPUT %s', _out.path)
        if _out in _outs:
            raise RuntimeError(
                f'Multiple {_cbl.output_name} cacheables writing to same '
                f'path: {_out.path}')
        _outs.append(_out)


def _check_for_overwrite(cacheables, extn, force):
    """Check for overwrite existing outputs.

    Args:
        cacheables (CPCacheable list): items being cached
        extn (str): cache output format (abc/fbx)
        force (bool): replace existing without confirmation
    """

    _to_replace = []
    for _cbl in cacheables:
        _out = _cbl.to_output(extn=extn)
        if _out.exists():
            _to_replace.append(_out)

    # Warn on overwrite
    if _to_replace:
        if not force:
            _msg = 'Replace {:d} existing {}{}?\n\n{}'.format(
                len(_to_replace), extn, plural(_to_replace),
                '\n\n'.join([_out.path for _out in _to_replace[:10]]))
            if len(_to_replace) > 10:
                _n_over = len(_to_replace) - 10
                _msg += f'\n\n(and {_n_over:d} other abc{plural(_n_over)})'
            _icon = icons.find('Bear')
            qt.ok_cancel(
                _msg, title='Replace existing', icon=_icon, verbose=0)
    for _out in _to_replace:
        _out.delete(force=True)


def _setup_cache(cacheables, extn='abc', force=False):
    """Prepare for cache + setup job args and abc objects.

    Args:
        cacheables (CPCacheable list): items being cached
        extn (str): cache output format (abc/fbx)
        force (bool): replace existing without confirmation

    Returns:
        (tuple): job args, outputs
    """

    _check_for_output_clash(cacheables, extn=extn)
    _check_for_overwrite(cacheables, extn=extn, force=force)

    _outs = []
    for _cbl in cacheables:

        _LOGGER.debug('CACHEABLE %s', _cbl)

        # Check dir exists
        _out = _cbl.to_output(extn=extn)
        _out.test_dir()
        _outs.append(_out)

    return _outs


def _write_metadata(outputs, cacheables, range_, step, checks_data):
    """Write metadata to outputs on disk.

    Args:
        outputs (CPOutput list): cache outputs
        cacheables (CPCacheable list): items that were cached
        range_ (tuple): start/end frames
        step (float): step size in frames
        checks_data (dict): sanity checks data to apply
    """
    for _out, _cbl in safe_zip(outputs, cacheables):
        assert _out.exists()
        _data = _cbl.build_metadata()
        _data['range'] = range_
        _data['step'] = step
        _data['sanity_check'] = checks_data
        _out.set_metadata(_data)


def cache(
        cacheables, uv_write=True, world_space=True, extn='abc',
        format_='Ogawa', range_=None, step=1.0, save=True, clean_up=True,
        renderable_only=True, checks_data=None, use_farm=False, snapshot=True,
        version_up=False, update_cache=True, force=False):
    """Cache the current scene.

    Args:
        cacheables (CPCacheable list): items to cache
        uv_write (bool): write uvs
        world_space (bool): write in world space
        extn (str): cache output format (abc/fbx)
        format_ (str): cache format (Ogawa/HDF)
        range_ (tuple): override start/end frames
        step (float): step size in frames
        save (bool): save on cache
        clean_up (bool): clean up tmp nodes after cache (on by default)
        renderable_only (bool): export only renderable (visible) geometry
        checks_data (dict): sanity checks data to apply
        use_farm (bool): cache using farm
        snapshot (bool): take thumbnail snapshot on cache
        version_up (bool): version up on cache
        update_cache (bool): update cache with new outputs
        force (bool): overwrite existing without confirmation

    Returns:
        (COutputFile list): caches generated
    """
    _LOGGER.info('CACHE SCENE %d %s', len(cacheables), cacheables)

    _work = pipe.CACHE.obt_cur_work()
    _range = range_ or dcc.t_range(int, expand=1)
    _checks_data = checks_data or sanity_check.launch_export_ui(
        action='Cache', force=force)
    _updated = False
    if not _work:
        raise error.HandledError(
            'No current work file.\n\nPlease save your scene using pini '
            'before caching.')

    # Warn on no cache template set up
    if not _work.job.find_templates('cache'):
        qt.notify(
            f'No cache template found in this job:\n\n{_work.job.path}\n\n'
            f'Unable to cache.',
            title='Warning')
        return None

    # Setup cache
    _outs = _setup_cache(cacheables=cacheables, force=force, extn=extn)
    if save and not dcc.batch_mode():
        _work.save(reason='cache', force=True, update_outputs=False)
    if snapshot:
        _take_snapshot(image=_work.image, frame=int(sum(_range) / 2))
        _updated = True

    # Execute cache
    _flags = {
        'uv_write': uv_write,
        'world_space': world_space,
        'format_': format_,
        'range_': _range,
        'renderable_only': renderable_only,
        'step': step}
    if use_farm:
        farm.submit_maya_cache(
            cacheables=cacheables, save=False, checks_data=_checks_data,
            flags=_flags, extn=extn)
    else:
        _exec_local_cache(
            cacheables=cacheables, outputs=_outs, work=_work, flags=_flags,
            checks_data=_checks_data, clean_up=clean_up, extn=extn)
        _updated = True

    # Post cache
    if update_cache and _updated:
        _work.update_outputs()
    if version_up:
        pipe.version_up()
    elif save and not dcc.batch_mode():
        cmds.file(modified=False)  # Ignore cleanup changes

    if use_farm and not force:
        qt.notify(
            f'Submitted {len(cacheables):d} caches to {farm.NAME}.\n\n'
            f'Batch name:\n{_work.base}',
            title='Cache Submitted', icon=farm.ICON)

    return _outs


def _exec_local_cache(
        cacheables, outputs, work, checks_data, extn, flags, clean_up):
    """Exec cache locally.

    Args:
        cacheables (Cacheable list): items to cache
        outputs (CPOutput list): output paths
        work (CPWork): work file
        checks_data (dict): sanity checks data
        extn (str): cache output format (abc/fbx)
        flags (dict): cache flags
        clean_up (bool): clean up tmp nodes after cache (on by default)
    """

    # Pre cache
    for _cbl in cacheables:
        _cbl.pre_cache(extn=extn)

    # Execute cache
    if extn == 'abc':
        _exec_local_abc_cache(cacheables=cacheables, flags=flags)
    elif extn == 'fbx':
        _exec_local_fbx_cache(cacheables=cacheables, flags=flags)
    _write_metadata(
        outputs=outputs, cacheables=cacheables, range_=flags['range_'],
        checks_data=checks_data, step=flags['step'])

    # Post cache
    if clean_up:
        for _cbl in cacheables:
            _cbl.post_cache()

    # Register in shotgrid
    if pipe.SHOTGRID_AVAILABLE:
        from pini.pipe import shotgrid
        _thumb = work.image if work.image.exists() else None
        for _last, _out in qt.progress_bar(
                last(outputs), 'Registering {:d} output{} in shotgrid'):
            shotgrid.create_pub_file_from_output(
                _out, thumb=_thumb, update_cache=_last, force=True)


@hide_img_planes
def _exec_local_abc_cache(cacheables, flags):
    """Execute local abc cache.

    Args:
        cacheables (Cacheable list): items to cache
        flags (dict): cache flags
    """
    cmds.loadPlugin('AbcExport', quiet=True)

    # Build job args
    _job_args = []
    for _cbl in cacheables:
        _job_arg = _cbl.to_job_arg(**flags)
        _job_args.append(_job_arg)

    _LOGGER.info(' - cmds.AbcExport(jobArg=%s)', _job_args)
    cmds.AbcExport(jobArg=_job_args)


@restore_sel
def _exec_local_fbx_cache(cacheables, flags):  # pylint: disable=unused-argument
    """Exec local fbx cache.

    Args:
        cacheables (Cacheable list): items to cache
        flags (dict): cache flags
    """
    for _cbl in qt.progress_bar(cacheables, 'Exporting {:d} fbx{}'):
        _LOGGER.info(' - FBX CACHE %s', _cbl)
        cmds.select(_cbl.to_geo(extn='fbx'), hierarchy=True)
        _out = _cbl.to_output(extn='fbx')
        save_fbx(
            _out, animation=True, constraints=True, step=flags['step'],
            range_=flags['range_'])


@restore_frame
def _take_snapshot(frame, image):
    """Take snapshot of the current scene.

    Args:
        frame (int): frame to take snapshot of
        image (File): path to save snapshot to
    """
    cmds.currentTime(frame)
    blast_frame(file_=image, force=True)


def find_cacheable(
        match, filter_=None, type_=None, output_name=None, catch=False):
    """Find a cacheable in the current scene.

    Args:
        match (str): match by name
        filter_ (str): label filter
        type_ (str): filter by cacheable type (ref/cam/cset)
        output_name (str): match by output name
        catch (bool): no error if no single cacheable matched

    Returns:
        (CPCacheable): matching cacheable
    """
    _cbls = find_cacheables(
        filter_=filter_, output_name=output_name, type_=type_)
    _cbl = single(_cbls, catch=True)
    if _cbl:
        return _cbl

    if isinstance(match, str):
        _match_s = str
    elif isinstance(match, pom.CReference):
        _match_s = match.namespace
    else:
        raise NotImplementedError(match)

    _name_match = single(
        [_cbl for _cbl in _cbls if _cbl.output_name == _match_s], catch=True)
    if _name_match:
        return _name_match

    if catch:
        return None
    raise ValueError(_match_s)


def find_cacheables(filter_=None, task=None, type_=None, output_name=None):
    """Find cacheables in the current scene.

    Args:
        filter_ (str): filter cacheables by label
        task (str): return only cacheables from the given task
        type_ (str): filter by cacheable type (ref/cam/cset)
        output_name (str): match by output name

    Returns:
        (CPCacheable list): cacheables
    """

    # Find all cacheables in scene
    _all = []
    if type_ in ('ref', None):
        _all += ref.find_refs(class_=mpc_ref.CPCacheableRef)
    if type_ in ('cam', None):
        _all += mpc_cam.find_cams()
    if type_ in ('cset', None):
        _all += mpc_cset.find_csets()
    if type_ not in (None, 'cset', 'cam', 'ref'):
        raise ValueError(type_)
    _all.sort()

    # Apply filters
    _cbls = []
    for _cbl in _all:

        if not passes_filter(_cbl.label, filter_):
            continue
        if task and _cbl.task != task:
            continue
        if output_name and _cbl.output_name != output_name:
            continue

        # Check maps to asset correctly
        if pipe.cur_work():
            try:
                assert _cbl.to_output()
            except ValueError:
                continue

        _cbls.append(_cbl)

    return _cbls
