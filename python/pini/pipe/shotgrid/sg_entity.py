"""Tools for managing shotgrid shots."""

import logging
import os

from pini import qt, pipe
from pini.utils import single

from . import sg_handler, sg_utils, sg_sequence, sg_job

_LOGGER = logging.getLogger(__name__)

ASSET_TEMPLATE = os.environ.get(
    'PINI_SG_ASSET_TEMPLATE', 'Film VFX - Character Asset')
SHOT_TEMPLATE = os.environ.get(
    'PINI_SG_SHOT_TEMPLATE', 'Film VFX - Full CG Shot w/o Character')

_ASSET_TYPE_TO_SG = {
    'char': 'Character',
    'env': 'Environment',
    'prop': 'Prop',
    'fx': 'FX',
    'veh': 'Vehicle',
    'utl': 'Utility',
}

_SHOT_FIELDS = ['sg_head_in', 'id', 'code', 'sg_sequence']


def create_entity(entity, force=False):
    """Register the given entity on shotgrid.

    Args:
        entity (CPEntity): entity to register
        force (bool): register without confirmation
    """
    to_entity_data(entity, force=force)


def find_assets(job=None):
    """Find assets in the given job.

    Args:
        job (CPJob): job to read

    Returns:
        (CPAsset list): assets
    """

    _job = job or pipe.cur_job()
    _tmpl = _job.find_template('entity_path', profile='asset')
    _LOGGER.debug(' - TMPL %s', _tmpl)

    # Read results
    _results = sg_handler.find(
        'Asset', filters=[
            sg_job.to_job_filter(_job),
            ('sg_asset_type', 'is_not', None),
        ],
        fields=['sg_asset_type', 'code'])

    # Build assets
    _assets = []
    for _data in _results:
        _LOGGER.debug(' - DATA %s', _data)
        _path = _tmpl.format(
            job_path=_job.path, asset=_data['code'],
            asset_type=_data['sg_asset_type'])
        _LOGGER.debug('   - PATH %s', _path)
        _asset = pipe.CPAsset(_path, job=_job)
        _ety_to_data(_asset, force=True, data=[_data])  # Update cache
        _assets.append(_asset)

    return sorted(_assets)


def find_shots(job=None, only_3d=False):
    """Find shots in the given job.

    Args:
        job (CPJob): job to read
        only_3d (bool): filter out non-3d shots

    Returns:
        (CPShot list): shots
    """
    _LOGGER.debug('FIND SHOTS %s', job)

    _job = job or pipe.cur_job()
    _tmpl = _job.find_template('entity_path', profile='shot')
    _LOGGER.debug(' - TMPL %s', _tmpl)

    # Read results
    _filters = [
        sg_job.to_job_filter(_job),
        ('sg_sequence', 'is_not', None),
        ('sg_status_list', 'not_in', ('omt', )),
    ]
    if only_3d:
        _filters += [('sg_has_3d', 'is', True)]
    _results = sg_handler.find('Shot', filters=_filters, fields=_SHOT_FIELDS)

    # Build assets
    _shots = []
    for _data in _results:

        _LOGGER.debug(' - DATA %s', _data)
        _path = _tmpl.format(
            job_path=_job.path, shot=_data['code'],
            sequence=_data['sg_sequence']['name'])
        _LOGGER.debug('   - PATH %s', _path)

        # Build sequence (to allow data to be cached)
        try:
            _seq = pipe.CPSequence(_path, job=_job)
        except ValueError:
            continue
        sg_sequence.to_sequence_data(
            _seq, force=True, data=[_data['sg_sequence']])

        # Build shot
        try:
            _shot = pipe.CPShot(_path, job=_job)
        except ValueError:
            continue
        _ety_to_data(_shot, force=True, data=[_data])  # Update caches
        _shots.append(_shot)

    return sorted(_shots)


def set_entity_range(entity, range_, force=False):
    """Set shotgrid entity range.

    Args:
        entity (CPEntity): entity to update
        range_ (tuple): work in/out
        force (bool): apply update without confirmation
    """
    if not force:
        qt.ok_cancel(
            'Are you sure you want to update the shotgrid range this {} '
            'to {}-{}?\n\n{}'.format(
                entity.profile, range_[0], range_[1], entity.path),
            icon=sg_utils.ICON, title='Update Range')
    _id = to_entity_id(entity)
    sg_handler.update(
        entity_type=entity.profile.capitalize(),
        entity_id=_id,
        data={'sg_work_in': range_[0], 'sg_work_out': range_[1]})


@sg_utils.get_sg_result_cacher(use_args=['entity'])
def _ety_to_data(entity, data=None, force=False):
    """Obtain shotgrid data for the given entity.

    Args:
        entity (CPEntity): entity to read
        data (dict): force shotgrid data into cache
        force (bool): rewrite cache

    Returns:
        (dict): shotgrid data
    """
    if isinstance(entity, pipe.CPShot):
        return _to_shot_data(entity, data=data, force=force)
    if isinstance(entity, pipe.CPAsset):
        return _to_asset_data(entity, data=data, force=force)
    raise ValueError(entity)


def to_entity_data(entity=None, force=False):
    """Obtain shotgrid data for the given entity.

    Args:
        entity (str): path to entity
        force (bool): create entity (if necessary) without confirmation

    Returns:
        (dict): entity data
    """
    _ety = entity or pipe.cur_entity()
    _ety = pipe.to_entity(_ety)
    return _ety_to_data(_ety)


def to_entity_filter(entity=None):
    """Obtain entity filter for the given entity.

    Args:
        entity (CPEntity): entity

    Returns:
        (tuple): entity filter
    """
    _data = to_entity_data(entity)
    _key = {'id': _data['id'], 'type': _data['type']}
    return 'entity', 'is', _key


def to_entity_id(entity):
    """Obtain shotgrid id for the given entity.

    Args:
        entity (str|CPEntity): entity to test

    Returns:
        (int): entity id
    """
    return to_entity_data(entity)['id']


def to_entity_range(entity=None):
    """Obtain frame range for the given entity.

    Args:
        entity (CPEntity): entity to read

    Returns:
        (tuple|None): start/end
    """
    from pini.pipe import shotgrid

    _ety = entity or pipe.cur_entity()
    _id = to_entity_id(_ety)
    _data = shotgrid.find_one(
        'Shot', id_=_id, fields=['sg_head_in', 'sg_tail_out'])
    _start = _data['sg_head_in']
    _end = _data['sg_tail_out']
    if _start is None or _end is None:
        return None
    return _start, _end


def to_entities_filter(entities):
    """Build a filter to match the given entities.

    Args:
        entities (CPEntity list): entities to match

    Returns:
        (tuple): entities filter
    """
    _ety_datas = []
    for _ety in entities:
        _, _, _ety_data = to_entity_filter(_ety)
        _ety_datas.append(_ety_data)
    return 'entity', 'in', _ety_datas


def _create_asset(asset, force=False):
    """Register the given asset on shotgrid.

    Args:
        asset (CPAsset): asset to register
        force (bool): register without confirmation

    Returns:
        (list): new entry
    """
    from pini.pipe import shotgrid

    _sg = shotgrid.to_handler()
    _type = _ASSET_TYPE_TO_SG[asset.asset_type]

    _LOGGER.debug(' - ASSET TEMPLATE %s', ASSET_TEMPLATE)
    _tmpl = single(_sg.find(
        'TaskTemplate',
        [('code', 'is', ASSET_TEMPLATE)]))
    _data = {
        "project": shotgrid.to_job_data(asset.job),
        "sg_asset_type": _type,
        "code": asset.name,
        "task_template": _tmpl,
    }

    if not force:
        qt.ok_cancel(
            'Register asset {}/{}/{} in shotgrid?\n\n{}'.format(
                asset.job.name, asset.asset_type, asset.name, asset.path),
            icon=shotgrid.ICON, title='Shotgrid')

    return [_sg.create("Asset", _data)]


def _create_shot(shot, force=False):
    """Register the given shot on shotgrid.

    Args:
        shot (CPShot): shot to register
        force (bool): register without confirmation

    Returns:
        (list): new entry
    """
    from pini.pipe import shotgrid

    _sg = shotgrid.to_handler()
    _task_tmpl = single(_sg.find(
        'TaskTemplate',
        [('code', 'is', SHOT_TEMPLATE)]))
    _data = {
        "project": shotgrid.to_job_data(shot.job),
        "sg_sequence": shotgrid.to_sequence_data(shot.to_sequence()),
        "code": shot.name,
        "task_template": _task_tmpl,
    }

    if not force:
        qt.ok_cancel(
            'Register shot {}/{}/{} in shotgrid?\n\n{}'.format(
                shot.job.name, shot.sequence, shot.name, shot.path),
            icon=shotgrid.ICON, title='Shotgrid')

    return [_sg.create("Shot", _data)]


def _to_asset_data(asset, data=None, force=False):
    """Obtain shotgrid data for the given asset.

    Args:
        asset (CPAsset): asset to read data from
        data (dict): force shotgrid data into cache
        force (bool): create entity (if necessary) without confirmation

    Returns:
        (dict): asset data
    """
    from pini.pipe import shotgrid

    _LOGGER.debug('TO ASSET DATA %s', asset)
    assert isinstance(asset, pipe.CPAsset)
    _sg = shotgrid.to_handler()
    _job = asset.job

    if pipe.MASTER == 'shotgrid':
        _type = asset.asset_type
    elif asset.asset_type in _ASSET_TYPE_TO_SG:
        _type = _ASSET_TYPE_TO_SG[asset.asset_type]
    else:
        raise RuntimeError('Unhandled asset type '+asset.asset_type)
    _filters = [
        shotgrid.to_job_filter(asset.job),
        ('sg_asset_type', 'is', _type),
        ('code', 'is', asset.name),
    ]
    _fields = ['sg_asset_type', 'code']
    _results = data or _sg.find('Asset', _filters, _fields)
    assert len(_results) in (0, 1)

    if not _results:
        _results = _create_asset(asset, force=force)

    assert len(_results) == 1

    return single(_results, catch=True)


def _to_shot_data(shot, data=None, force=False):
    """Obtain shotgrid data for the given shot.

    Args:
        shot (CPShot): shot to obtain data for
        data (dict): force shotgrid data into cache
        force (bool): create entity (if necessary) without confirmation

    Returns:
        (dict): shot data
    """
    from pini.pipe import shotgrid

    assert isinstance(shot, pipe.CPShot)
    _job = shot.job

    _filters = [
        shotgrid.to_job_filter(_job),
        shotgrid.to_sequence_filter(shot.to_sequence()),
        ('code', 'is', shot.name),
    ]
    _results = data or sg_handler.find(
        'Shot', filters=_filters, fields=_SHOT_FIELDS)
    assert len(_results) in (0, 1)

    # Create shot
    if not _results:
        _results = _create_shot(shot, force=force)

    assert len(_results) == 1

    return single(_results)
