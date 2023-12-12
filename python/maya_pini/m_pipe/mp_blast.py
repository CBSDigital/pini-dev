"""Tools for blasting to pipeline."""

import logging

from pini import dcc, qt
from pini import pipe

from maya_pini import open_maya as pom, ui
from maya_pini.utils import blast as u_blast

_LOGGER = logging.getLogger(__name__)


def blast(
        settings='Nice', camera='<cur>', format_='mp4', output_name='blast',
        range_=None, res='Full', use_scene_audio=True, burnins=False, view=True,
        cleanup=True, save=True, force=False):
    """Blast current scene to pipeline.

    Args:
        settings (str): blast settings mode
        camera (str): blast camera
        format_ (str): blast format/extn
        output_name (str): override blast output name
        range_ (tuple): override blast range
        res (str|tuple): overide blast res - eg. Full, Half, (1024, 768)
        use_scene_audio (bool): apply scene audio to blast videos
        burnins (bool): write burnins (on video compile only)
        view (bool): view blast on completion
        cleanup (bool): clean up tmp nodes/files
        save (bool): save scene on cache (default is true)
        force (bool): overwrite existing without confirmation
    """
    _work = pipe.CACHE.cur_work
    _LOGGER.info(' - WORK %s', _work)

    # Determine cam
    if camera in [None, '<cur>']:
        _cam = ui.get_active_cam()
    else:
        _cam = camera

    # Determine output path
    _output_name = output_name
    if output_name == '<camera>':
        _output_name = str(pom.CCamera(_cam))
    if format_ in ['mp4']:
        _tmpl = 'blast_mov'
        _tmp_seq = _work.to_output('blast', output_name='BlastTmp', extn='jpg')
        _tmp_seq.delete(force=True)
    else:
        _tmpl = 'blast'
        _tmp_seq = None
    _out = _work.to_output(_tmpl, output_name=_output_name, extn=format_)
    _LOGGER.info(' - OUT %s', _out)

    if save:
        _work.save(reason='blast', force=True)
    u_blast(
        clip=_out, settings=settings, camera=_cam,  range_=range_, res=res,
        force=force, use_scene_audio=use_scene_audio, burnins=burnins,
        view=view, cleanup=cleanup, tmp_seq=_tmp_seq)
    _work.update_outputs()

    if pipe.SHOTGRID_AVAILABLE:
        _rng = range_ or dcc.t_range(int)
        _update_shotgrid_range(entity=_work.entity, range_=_rng)

    return _out


def _update_shotgrid_range(entity=None, range_=None, force=False):
    """Check shotgrid range matches blast range.

    Args:
        entity (CPEntity): override entity
        range_ (tuple): override start/end
        force (bool): update shotgrid without confirmation
    """
    from pini.pipe import shotgrid

    _ety = entity or pipe.cur_entity()
    _LOGGER.debug('UPDATE SHOTGRID RANGE %s', _ety)

    _cur_rng = range_ or dcc.t_range(int)
    _LOGGER.debug(' - CUR RANGE %s', _cur_rng)
    # print shotgrid.to_entity_filter(_ety)

    # Read range from shotgrid
    _job_filter = shotgrid.to_job_filter(_ety)
    _data = shotgrid.find_one(
        _ety.profile.capitalize(),
        filters=[_job_filter, ('code', 'is', _ety.name)],
        fields=['sg_work_in', 'sg_work_out'])
    _sg_rng = _data.get('sg_work_in'), _data.get('sg_work_out')
    _LOGGER.debug(' - SHOTGRID RANGE %s', _sg_rng)

    if _sg_rng == _cur_rng:
        _LOGGER.debug(' - SHOTGRID RANGE IS UP TO DATE')
        return
    _LOGGER.debug(' - SHOTGRID RANGE NEEDS UPDATE')

    # Confirm
    if not force:
        if _sg_rng[0] is None or _sg_rng[1] is None:
            _fmt = ('Shotgrid range for {ety.name} is not set.\n\n'
                    'Would you like to set it to the blast range '
                    '{cur_rng[0]:d}-{cur_rng[1]:d}?')
        else:
            _fmt = ('Blast range {cur_rng[0]:d}-{cur_rng[1]:d} does not match '
                    'shotgrid range {sg_rng[0]:d}-{sg_rng[1]:d}.\n\n'
                    'Would you like to update the shotgrid range?')
        _LOGGER.debug(' - FMT %s', _fmt)
        _msg = _fmt.format(sg_rng=_sg_rng, cur_rng=_cur_rng, ety=_ety)
        _result = qt.yes_no_cancel(
            _msg, title='Update Shotgrid', icon=shotgrid.ICON)
        _LOGGER.debug(' - RESULT %s', _result)
        if _result is False:
            return
        if _result is not True:
            raise ValueError(_result)

    # Update shotgrid
    shotgrid.set_entity_range(entity=_ety, range_=_cur_rng, force=True)
