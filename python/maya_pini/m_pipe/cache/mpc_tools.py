"""Tools for managing caching out abcs."""

import logging

from maya import cmds

from pini import pipe, icons, qt, dcc, farm
from pini.tools import sanity_check
from pini.utils import single, plural, safe_zip, passes_filter

from maya_pini import ref
from maya_pini.utils import hide_img_planes, restore_frame, blast_frame

from . import mpc_ref, mpc_cam, mpc_cset

_LOGGER = logging.getLogger(__name__)


def _check_for_abc_clash(cacheables):
    """Check for multiple abcs writing to the same path.

    Args:
        cacheables (CPCacheable list): items being cached
    """
    _LOGGER.debug('CHECK FOR ABC CLASH')
    _abcs = []
    for _cbl in cacheables:
        _LOGGER.debug(' - TESTING %s', _cbl)
        _abc = _cbl.to_output()
        _LOGGER.debug('   - ABC %s', _abc.path)
        if _abc in _abcs:
            raise RuntimeError(
                'Multiple {} cacheables writing to same path: {}'.format(
                    _cbl.output_name, _abc.path))
        _abcs.append(_abc)


def _check_for_overwrite(cacheables, force):
    """Check for overwrite existing abcs.

    Args:
        cacheables (CPCacheable list): items being cached
        force (bool): replace existing without confirmation
    """

    _to_replace = []
    for _cbl in cacheables:
        _abc = _cbl.to_output()
        if _abc.exists():
            _to_replace.append(_abc)

    # Warn on overwrite
    if _to_replace:
        if not force:
            _msg = 'Replace {:d} existing abc{}?\n\n{}'.format(
                len(_to_replace), plural(_to_replace),
                '\n\n'.join([_abc.path for _abc in _to_replace[:10]]))
            if len(_to_replace) > 10:
                _msg += '\n\n(and {:d} other abc{})'.format(
                    len(_to_replace)-10, plural(_to_replace[10:]))
            _icon = icons.find('Bear')
            qt.ok_cancel(
                _msg, title='Replace Existing', icon=_icon, verbose=0)
    for _abc in _to_replace:
        _abc.delete(force=True)


def _setup_cache(
        cacheables, uv_write, world_space, step, renderable_only,
        format_, range_, force):
    """Prepare for cache + setup job args and abc objects.

    Args:
        cacheables (CPCacheable list): items being cached
        uv_write (bool): write uvs
        world_space (bool): write in world space
        step (float): step size in frames
        renderable_only (bool): export only renderable (visible) geometry
        format_ (str): cache format
        range_ (tuple): start/end frames
        force (bool): replace existing without confirmation

    Returns:
        (tuple): job args, abcs
    """

    _check_for_abc_clash(cacheables)
    _check_for_overwrite(cacheables, force=force)

    _job_args = []
    _abcs = []
    for _cbl in cacheables:

        _LOGGER.debug('CACHEABLE %s', _cbl)

        # Check dir exists
        _abc = _cbl.to_output()
        _abc.test_dir()
        _abcs.append(_abc)

        # Get job arg
        _job_arg = _cbl.to_job_arg(
            uv_write=uv_write, world_space=world_space, step=step,
            renderable_only=renderable_only, format_=format_, range_=range_)
        _job_args.append(_job_arg)

    return _job_args, _abcs


def _write_metadata(abcs, cacheables, range_, step, checks_data):
    """Write metadata to abcs on disk.

    Args:
        abcs (CPOutput list): cache abcs
        cacheables (CPCacheable list): items that were cached
        range_ (tuple): start/end frames
        step (float): step size in frames
        checks_data (dict): sanity checks data to apply
    """
    for _abc, _cbl in safe_zip(abcs, cacheables):
        assert _abc.exists()
        _data = _cbl.obtain_metadata()
        _data['range'] = range_
        _data['step'] = step
        _data['checks'] = checks_data
        _abc.set_metadata(_data)


def cache(
        cacheables, uv_write=True, world_space=True, format_='Ogawa',
        range_=None, step=1.0, save=True, clean_up=True, renderable_only=True,
        checks_data=None, use_farm=False, snapshot=False, version_up=False,
        force=False):
    """Cache the current scene.

    Args:
        cacheables (CPCacheable list): items to cache
        uv_write (bool): write uvs
        world_space (bool): write in world space
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
        force (bool): overwrite existing without confirmation

    Returns:
        (COutputFile list): caches generated
    """
    _LOGGER.info('CACHE SCENE %d %s', len(cacheables), cacheables)

    _work = pipe.CACHE.cur_work
    _range = range_ or dcc.t_range(int, expand=1)
    _checks_data = checks_data or sanity_check.launch_export_ui(
        'cache', force=force)
    _updated = False
    assert _work

    # Warn on no cache template set up
    if not _work.job.find_templates('cache'):
        qt.notify(
            'No cache template found in this job:\n\n{}\n\n'
            'Unable to cache.'.format(_work.job.path),
            title='Warning')
        return None

    # Setup cache
    _job_args, _abcs = _setup_cache(
        cacheables=cacheables, uv_write=uv_write, world_space=world_space,
        step=step, renderable_only=renderable_only, format_=format_,
        range_=_range, force=force)
    if save and not dcc.batch_mode():
        _work.save(reason='cache', force=True)
    if snapshot:
        _take_snapshot(image=_work.image, frame=int(sum(_range)/2))
        _updated = True

    # Execute cache
    if use_farm:
        _flags = {
            'uv_write': uv_write,
            'world_space': world_space,
            'format_': format_,
            'range_': _range,
            'renderable_only': renderable_only,
            'step': step}
        farm.submit_maya_cache(
            cacheables=cacheables, save=False, checks_data=_checks_data,
            flags=_flags)
    else:
        _exec_local_cache(
            cacheables=cacheables, abcs=_abcs, job_args=_job_args, work=_work,
            checks_data=_checks_data, range_=_range, step=step,
            clean_up=clean_up)
        _updated = True

    # Post cache
    if _updated:
        _work.update_outputs()
    if version_up:
        pipe.version_up()
    elif save and not dcc.batch_mode():
        cmds.file(modified=False)  # Ignore cleanup changes

    if use_farm:
        qt.notify(
            'Submitted {:d} caches to {}.\n\nBatch name:\n{}'.format(
                len(cacheables), farm.NAME, _work.base),
            title='Cache Submitted', icon=farm.ICON)

    return _abcs


def _exec_local_cache(
        cacheables, abcs, work, checks_data, range_, step, job_args, clean_up):
    """Exec cache locally.

    Args:
        cacheables (Cacheable list): items to cache
        abcs (CPOutput list): output paths
        work (CPWork): work file
        checks_data (dict): sanity checks data
        range_ (tuple): start/end frame
        step (float): step size in frames
        job_args (str): abc export args
        clean_up (bool): clean up tmp nodes after cache (on by default)
    """

    # Pre cache
    for _cbl in cacheables:
        _cbl.pre_cache()

    # Execute cache
    cmds.loadPlugin('AbcExport', quiet=True)
    _LOGGER.info(' - cmds.AbcExport(jobArg=%s)', job_args)
    hide_img_planes(cmds.AbcExport)(jobArg=job_args)
    _write_metadata(
        abcs=abcs, cacheables=cacheables, range_=range_,
        checks_data=checks_data, step=step)

    # Post cache
    if clean_up:
        for _cbl in cacheables:
            _cbl.post_cache()

    # Register in shotgrid
    if pipe.SHOTGRID_AVAILABLE:
        from pini.pipe import shotgrid
        _thumb = work.image if work.image.exists() else None
        for _abc in qt.progress_bar(
                abcs, 'Registering {:d} abc{} in shotgrid'):
            shotgrid.create_pub_file(_abc, thumb=_thumb)


@restore_frame
def _take_snapshot(frame, image):
    """Take snapshot of the current scene.

    Args:
        frame (int): frame to take snapshot of
        image (File): path to save snapshot to
    """
    cmds.currentTime(frame)
    blast_frame(file_=image, force=True)


def find_cacheable(filter_=None, type_=None, output_name=None, catch=False):
    """Find a cacheable in the current scene.

    Args:
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

    _name_match = single(
        [_cbl for _cbl in _cbls if _cbl.output_name == filter_], catch=True)
    if _name_match:
        return _name_match

    if catch:
        return None
    raise ValueError(filter_)


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
        _cbls.append(_cbl)

    return _cbls
