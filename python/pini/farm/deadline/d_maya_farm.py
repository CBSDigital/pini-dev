"""Deadline tools to be run inside maya."""

import logging
import time

from maya.app.renderSetup.model import renderSetup

from pini import pipe, qt, dcc
from pini.dcc import export
from pini.utils import single, plural

from maya_pini import open_maya as pom
from maya_pini.utils import cur_renderer

from . import d_farm, submit

_LOGGER = logging.getLogger(__name__)


class CDMayaFarm(d_farm.CDFarm):
    """Represents the deadline farm inside maya."""

    def submit_maya_render(  # pylint: disable=too-many-branches,too-many-statements
            self, camera=None, comment='', priority=50, machine_limit=0,
            frames=None, chunk_size=1, version_up=False, checks_data=None,
            submit_=True, metadata=None, layers=None,
            result='jobs', force=False, **kwargs):
        """Submit maya render job to the farm.

        Args:
            camera (CCamera): render cam
            comment (str): job comment
            priority (int): job priority (0 [low] - 100 [high])
            machine_limit (int): job machine limit
            frames (int list): frames to render
            chunk_size (int): apply job chunk size
            version_up (bool): version up on render
            checks_data (dict): override sanity checks data
            submit_ (bool): submit render to deadline (disable for debugging)
            metadata (dict): override render metadata
            layers (CRenderLayer list): override list of layers to render
            result (str): what to return
                jobs - list of submitted jobs
                msg - submit message
            force (bool): submit without confirmation dialogs

        Returns:
            (CDJob list): jobs
        """
        _cam = camera or pom.find_render_cam()
        _stime = time.time()
        _work = pipe.CACHE.obt_cur_work()
        _batch = _work.base
        _lyrs = layers or pom.find_render_layers(renderable=True)
        if not _lyrs:
            raise RuntimeError('No renderable layers')

        _render_scene = _work.save(
            force=True, reason='deadline render', result='bkp')
        _metadata = metadata or export.build_metadata(
            'render', sanity_check_=True, checks_data=checks_data,
            task=_work.task, force=force, require_notes=True)
        _metadata['bkp'] = _render_scene.path
        _progress = qt.progress_dialog(
            title='Submitting Render', stack_key='SubmitRender',
            col='OrangeRed')

        # Submit render jobs
        _render_jobs = []
        _outs = []
        for _lyr in _lyrs:

            _LOGGER.debug(' - SUBMIT LYR %s', _lyr)

            # Determine range for this layer
            _frames = frames
            _LOGGER.debug('   - FRAMES (A) %s', _frames)
            if isinstance(_frames, list):
                pass
            elif _frames == 'From render globals':
                _frames = _to_layer_frames(_lyr)
            else:
                raise NotImplementedError(_frames)
            _LOGGER.debug('   - FRAMES (B) %s', _frames)
            assert _frames
            assert isinstance(_frames, list)
            assert isinstance(_frames[0], int)

            # Build output job
            _job = submit.CDMayaRenderJob(
                stime=_stime, layer=_lyr.pass_name, priority=priority,
                work=_work, frames=_frames, camera=_cam, comment=comment,
                machine_limit=machine_limit, chunk_size=chunk_size,
                scene=_render_scene, **kwargs)
            _render_jobs.append(_job)
            _LOGGER.debug('   - SCENE %s', _job.scene)
            assert _job.scene == _render_scene
            _outs.append(_job.output)

            # Add redshift cryptomatte output
            if cur_renderer() == 'redshift' and pom.find_aov('Cryptomatte'):
                _crypto_path = _job.output.path.replace(
                    '.%04d.', '.Cryptomatte.%04d.')
                _crypto_out = pipe.to_output(_crypto_path, catch=True)
                if _crypto_out:
                    _outs.append(_crypto_out)

        assert not _render_jobs[0].jid
        if submit_:
            self.submit_jobs(_render_jobs, name='render')
            assert _render_jobs[0].jid
        _progress.set_pc(50)

        # Submit update cache job
        _update_job = self.submit_update_job(
            work=_work, dependencies=_render_jobs, comment=comment,
            batch_name=_batch, stime=_stime, metadata=_metadata,
            priority=priority, submit_=submit_, outputs=_outs)
        _progress.set_pc(100)
        _progress.close()

        if version_up:
            pipe.version_up()

        # Notify on submission
        _submit_msg = (
            f'Submitted {len(_lyrs):d} layer{plural(_lyrs)} to deadline.'
            f'\n\nBatch name:\n{_batch}')
        if not force:
            qt.notify(_submit_msg, title='Render submitted', icon=submit.ICON)

        if result == 'jobs':
            _result = _render_jobs + [_update_job]
        elif result == 'msg':
            _result = _submit_msg
        elif result == 'msg/outs':
            _result = _submit_msg, _outs
        else:
            raise ValueError(result)
        return _result


def _to_default_val(plug):
    """To default value for the given plug.

    ie. to value ignoring any render layer overrides.

    Args:
        plug (CPlug): plug to read

    Returns:
        (float): value
    """
    _LOGGER.debug('TO DEFAULT VAL %s', plug)
    _input = plug.find_incoming().node
    _input_t = _input.object_type()
    _LOGGER.debug(' - INPUT %s %s', _input, _input_t)
    if _input_t == 'unitToTimeConversion':
        _input = _input.plug['input'].find_incoming().node
    elif _input_t in ('applyAbsFloatOverride', ):
        pass
    else:
        raise NotImplementedError(_input.object_type())
    return _input.plug['original'].get_val()


def _to_layer_val(attr, layer):
    """Obtain the value of the given attribute in the given layer.

    This takes account of any layer overrides which may have been applied.

    Args:
        attr (str): attribute name
        layer (CRenderLayer): render layer to read

    Returns:
        (float): attribute value
    """
    _LOGGER.debug(' - TO LYR VAL %s %s', attr, layer)
    _plug = pom.CPlug(attr)
    _val = _to_default_val(_plug)
    if layer.pass_name == 'masterLayer':
        return _val

    _rs = renderSetup.instance()
    _layer = _rs.getRenderLayer(layer.pass_name)
    _col = _layer.renderSettingsCollectionInstance()
    _overs = [
        _over for _over in _col.getOverrides()
        if _over.getRenderLayer() == _layer and
        hasattr(_over, 'attributeName') and
        f'{_over.targetNodeName()}.{_over.attributeName()}' == attr]
    _LOGGER.debug('   - OVERS %d %s', len(_overs), _overs)

    if _overs:
        assert len(_overs) == 1
        _over = single(_overs)
        _LOGGER.debug('   - OVER %s', _over)
        _type = _plug.get_type()
        _LOGGER.debug('   - TYPE %s', _type)

        _val = _over.getAttrValue()
        _LOGGER.debug('   - VAL %s', _val)
        if _type == 'time':
            _val /= 6000 / dcc.get_fps()
            _LOGGER.debug('   - VAL (B) %s', _val)

    return _val


def _to_layer_frames(layer):
    """Read layer render frames from render globals.

    This takes account of any layer overrides which may have been applied.

    Args:
        layer (CRenderLayer): layer

    Returns:
        (int list): frames
    """
    _LOGGER.debug('TO LYR FRAMES %s', layer)
    _start = int(_to_layer_val(
        "defaultRenderGlobals.startFrame", layer=layer))
    _end = int(_to_layer_val(
        "defaultRenderGlobals.endFrame", layer=layer))
    _step = int(_to_layer_val(
        "defaultRenderGlobals.byFrameStep", layer=layer))
    return list(range(_start, _end, _step))
