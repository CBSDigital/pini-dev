"""Tools for managing PublishedFile entries in shotgrid."""

import logging
import operator
import platform

from pini import pipe
from pini.utils import Seq, Video, TMP, Image, single, File, get_result_cacher

from . import sg_handler

_LOGGER = logging.getLogger(__name__)
_PUB_FILE_FIELDS = [
    'path', 'published_file_type', 'name', 'path_cache', 'id']
_TMP_THUMB = TMP.to_file('PiniTmp/thumb_tmp.jpg')


def create_pub_file(
        output, thumb=None, status='cmpt', update_cache=True, force=False):
    """Create PublishedFile entry in shotgrid.

    Args:
        output (CPOutput): output to register
        thumb (File): apply thumbnail image
        status (str): status for entry (default is complete)
        update_cache (bool): update cache on create
            (disable for multiple creates)
        force (bool): if an entry exists, update data

    Returns:
        (dict): registered data
    """
    from pini.pipe import shotgrid
    _LOGGER.info('CREATE PUB FILE %s', output)

    _sg_proj = shotgrid.SGC.find_proj(output.job)
    _sg_ety = _sg_proj.find_entity(output.entity)

    # Catch already exists
    _sg_pub = _find_sg_pub(output, sg_ety=_sg_ety)
    _LOGGER.info(' - SG PUB %s', _sg_pub)
    if _sg_pub:
        _LOGGER.info(
            ' - ALREADY REGISTERED IN SHOTGRID %d %s',
            _sg_pub.id_, output.path)

    _LOGGER.debug(
        ' - CREATE PUBLISHED FILE %s update_cache=%d', output.path,
        update_cache)
    _notes = output.metadata.get('notes')

    _sg_type = shotgrid.SGC.find_pub_type(
        output.extn, type_='Sequence' if isinstance(output, Seq) else 'File')
    _sg_user = shotgrid.SGC.find_user()
    _sg_task = _sg_ety.find_task(step=output.step, task=output.task, catch=True)

    # Build data
    _data = _build_pub_data(
        output, ver_n=output.ver_n, job=output.job, entity=output.entity,
        task=_sg_task, user=_sg_user, type_=_sg_type, status=status,
        notes=_notes)
    _data['sg_slotname'] = output.output_name
    _scene_entry = _obt_scene_entry(
        output, user=_sg_user, task=_sg_task, notes=_notes)
    if _scene_entry:
        _data['sg_scene_file'] = _scene_entry

    # Apply to shotgrid
    if not _sg_pub:
        _result = shotgrid.create('PublishedFile', _data)
        _LOGGER.debug(' - RESULT %s', _result)
        _id = _result['id']
    else:
        for _field in ['created_by', 'updated_by']:
            _data.pop(_field)
        sg_handler.update('PublishedFile', _sg_pub.id_, _data)
        _id = _sg_pub.id_

    # Update cache
    if update_cache:
        _LOGGER.info(' - UPDATING CACHE')
        _ety_c = pipe.CACHE.obt(output.entity)
        _ety_c.find_outputs(force=True)
        _out_c = pipe.CACHE.obt(output)
        assert _out_c
        _LOGGER.info(' - UPDATED CACHE')
        _sg_pub = shotgrid.SGC.find_pub_file(output)
        assert _sg_pub

    # Apply thumb
    _thumb = thumb
    if not _thumb:
        if isinstance(output, Seq):
            _thumb = Image(output.to_frame_file())
            if _thumb.extn not in ('png', 'jpg'):
                _thumb.convert(_TMP_THUMB, force=True)
                _thumb = _TMP_THUMB
        elif isinstance(output, Video):
            output.build_thumbnail(_TMP_THUMB, width=None, force=True)
            _thumb = _TMP_THUMB
    if _thumb:
        _LOGGER.debug(' - APPLY THUMB %s', _thumb)
        assert _thumb.exists()
        shotgrid.upload_thumbnail(
            'PublishedFile', _id, _thumb.path)

    return _sg_pub


def _build_path_data(file_, name=None):
    """Build the given path into shotgrid path data.

    Args:
        file_ (File): file to convert
        name (str): override name token

    Returns:
        (dict): path data
    """
    if platform.system() == 'Windows':
        _local_path_key = 'local_path_windows'
    else:
        raise NotImplementedError(platform.system())

    return {
        'link_type': 'local',
        'local_path': file_.path,
        _local_path_key: file_.path,
        'name': name or file_.filename,
    }


def _build_pub_data(
        path, user, task, job, entity, notes, ver_n=None, type_=None,
        status='cmpt', name=None):
    """Build pub data dict.

    Args:
        path (Path): object being published
        user (SGCUser): publishing user
        task (SGCTask): parent task
        job (CPJob): parent job
        entity (CPEntity): parent entity
        notes (str): publish notes
        ver_n (int): publish version number
        type_ (SGCPubType): override publish type
        status (str): override status
        name (str): override path name

    Returns:
        (dict): publish data
    """
    from pini.pipe import shotgrid

    _type = type_ or shotgrid.SGC.find_pub_type(path.extn)
    _path_cache = pipe.ROOT.rel_path(path)
    _name = name or path.filename
    _data = {
        'code': _name,
        'created_by': user.to_entry(),
        'description': notes,
        'entity': entity.sg_entity.to_entry(),
        'name': _name,
        'path': _build_path_data(path, name=_name),
        'path_cache': _path_cache,
        'project': job.sg_proj.to_entry(),
        'published_file_type': _type.to_entry(),
        'sg_status_list': status,
        'updated_by': user.to_entry(),
    }
    if ver_n is not None:
        _data['version_number'] = ver_n
    if task:
        _data['task'] = task.to_entry()
    return _data


def _find_sg_pub(output, sg_ety):
    """Find any existing shotgrid published file for the given output.

    If there more than one file matches then all but the latest one are
    omitted.

    Args:
        output (CPOutput): output to search for
        sg_ety (SGCEntity): parent entity

    Returns:
        (SGCPubFile|None): pub file entry (if any)
    """
    from pini import qt
    _LOGGER.info(' - FIND SG PUB %s', output)

    _sg_pubs = sg_ety.find_pub_files(path=output.path)
    _sg_pubs.sort(key=operator.attrgetter('updated_at'))
    if len(_sg_pubs) == 1:
        _sg_pub = single(_sg_pubs)
        _LOGGER.info(' - MATCHED SINGLE PUB %d %s', _sg_pub.id_, _sg_pub)
        return _sg_pub
    if not _sg_pubs:
        _LOGGER.info(' - NO MATCHING PUBS FOUND %s', output.path)
        return None

    # Test for a single or no entry that is not omitted
    _unomitted = sg_ety.find_pub_files(path=output.path, omitted=False)
    if len(_unomitted) == 1:
        _sg_pub = single(_unomitted)
        _LOGGER.info(' - MATCHED SINGLE UNOMITTED %d %s', _sg_pub.id_, _sg_pub)
        return _sg_pub
    if not _unomitted:
        _sg_pub = _sg_pubs[-1]
        _LOGGER.info(' - uSE RECENT OMITTED %d %s', _sg_pub.id_, _sg_pub)
        return _sg_pub

    qt.ok_cancel(
        f'Found {len(_sg_pubs)} published files in shotgrid for this output:'
        f'\n\n{output.path}\n\nUpdate the latest entry and omit others?',
        title='Multiple entries')

    _sg_pub = _sg_pubs.pop(-1)
    _LOGGER.info(' - uSE LATEST OMITTED %d %s', _sg_pub.id_, _sg_pub)
    for _pub in _sg_pubs[:-1]:
        _LOGGER.info(' - OMITTING %d %s', _pub.id_, _pub)
        _pub.omit()
    _sg_pub.set_status('wtg')
    return _sg_pub


def _obt_scene_entry(output, user, task, notes):
    """Obtain PublishedFile data for the given output.

    Args:
        output (CCPOutput): output file
        user (SGCUser): output user
        task (SGCTask): output task
        notes (str): publish notes

    Returns:
        (dict): scene file data
    """

    # Obtain scene path + name
    _scene = _name = None
    _bkp = output.metadata.get('bkp')
    if _bkp:
        _scene = _bkp
        _file = File(_scene)
        _name = f'{_file.to_dir().filename}/{_file.filename}'
    _scene = _scene or output.metadata.get('src')
    if not _scene and output.entity == pipe.cur_entity():
        _scene = pipe.cur_work()
    _LOGGER.info(' - SCENE %s', _scene)
    if not _scene:
        return None

    return _scene_to_entry(
        scene=_scene, output=output, user=user, task=task, notes=notes,
        name=_name)


@get_result_cacher(use_args=['scene'])
def _scene_to_entry(scene, output, user, task, notes, name):
    """Obtain scene file entry for given scene path.

    Args:
        scene (str): path to scene file
        output (CCPOutput): output file
        user (SGCUser): output user
        task (SGCTask): output task
        notes (str): publish notes
        name (str): pub file name overide

    Returns:
        (dict): scene file data
    """
    from pini.pipe import shotgrid
    assert isinstance(scene, str)

    # Try to find existing
    _path_cache = pipe.ROOT.rel_path(scene)
    _scene_entry = shotgrid.find_one(
        'PublishedFile', entity=output.entity,
        filters=[('path_cache', 'is', _path_cache)])

    # Create entry if required
    if not _scene_entry:
        _LOGGER.info(' - CREATE PublishedFile %s', scene)
        _file = File(scene)
        _data = _build_pub_data(
            _file, name=name, job=output.job, entity=output.entity,
            user=user, task=task, ver_n=output.ver_n, notes=notes)
        _LOGGER.info(' - SCENE DATA %s', _data)
        _scene_entry = shotgrid.create('PublishedFile', _data)
        _LOGGER.info(' - SCENE ENTRY %s', _scene_entry)

    return _scene_entry
