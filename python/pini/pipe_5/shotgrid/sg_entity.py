"""Tools for managing shotgrid shots."""

import logging
import os

from pini import qt, pipe
from pini.utils import single

from . import sg_handler, sg_utils

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


def create_entity(entity, force=False):
    """Register the given entity on shotgrid.

    Args:
        entity (CPEntity): entity to register
        force (bool): register without confirmation
    """
    raise NotImplementedError


def set_entity_range(entity, range_, force=False):
    """Set shotgrid entity range.

    Args:
        entity (CPEntity): entity to update
        range_ (tuple): work in/out
        force (bool): apply update without confirmation
    """
    from .. import shotgrid
    if not force:
        qt.ok_cancel(
            f'Are you sure you want to update the shotgrid range this '
            f'{entity.profile} to {range_[0]}-{range_[1]}?\n\n'
            f'{entity.path}',
            icon=sg_utils.ICON, title='Update Range')
    _ety_s = shotgrid.SGC.find_entity(entity)
    sg_handler.update(
        entity_type=_ety_s.ENTITY_TYPE,
        entity_id=_ety_s.id_,
        data={'sg_work_in': range_[0], 'sg_work_out': range_[1]})


def to_entity_range(entity=None):
    """Obtain frame range for the given entity.

    Args:
        entity (CPEntity): entity to read

    Returns:
        (tuple|None): start/end
    """
    from pini.pipe import shotgrid

    _ety = entity or pipe.cur_entity()
    _ety_s = shotgrid.SGC.find_entity(_ety)
    _data = shotgrid.find_one(
        'Shot', id_=_ety.id_, fields=['sg_head_in', 'sg_tail_out'])
    _start = _data['sg_head_in']
    _end = _data['sg_tail_out']
    if _start is None or _end is None:
        return None
    return _start, _end


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
        "project": shotgrid.SGC.find_proj(asset.job).to_entry(),
        "sg_asset_type": _type,
        "code": asset.name,
        "task_template": _tmpl,
    }

    if not force:
        qt.ok_cancel(
            f'Register asset {asset.job.name}/{asset.asset_type}/{asset.name} '
            f'in shotgrid?\n\n{asset.path}',
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

    _proj = shotgrid.SGC.find_proj(shot.job)
    _seq = shotgrid.find_one(
        'Sequence', job=shot.job,
        filters=[('code', 'is', shot.sequence)])
    _task_tmpl = shotgrid.find_one(
        'TaskTemplate', [('code', 'is', SHOT_TEMPLATE)])

    _data = {
        "project": _proj.to_entry(),
        "sg_sequence": _seq,
        "code": shot.name,
        "task_template": _task_tmpl,
    }

    if not force:
        qt.ok_cancel(
            f'Register shot {shot.job.name}/{shot.sequence}/{shot.name} '
            f'in shotgrid?\n\n{shot.path}',
            icon=shotgrid.ICON, title='Shotgrid')

    return [shotgrid.create("Shot", _data)]
