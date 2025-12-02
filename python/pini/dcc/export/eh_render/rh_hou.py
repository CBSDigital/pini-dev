"""Tools for managing houdini deadline submission."""

# pylint: disable=unused-argument

import logging

import hou

from pini import qt, pipe, farm
from pini.farm import deadline
from pini.utils import File, find_exe, system, single

from . import rh_base, rh_pass

_LOGGER = logging.getLogger(__name__)


class CHouDeadlineRender(rh_base .CRenderHandler):
    """Render handler for managing deadline submission in houdini."""

    NAME = 'Hou Deadline Render'
    ICON = deadline.ICON
    LABEL = '\n'.join([
        'Renders the current scene to deadline.',
        '',
        'Renderable passes are identifed as Mantra/Redshift ROPs '
        'with a single deadline node attached.'])

    add_cameras = False
    add_range = False

    def set_settings(self, *args, **kwargs):
        """Setup settings dict."""
        super().set_settings(
            *args, update_metadata=False, update_cache=False,
            bkp=True, **kwargs)

    def find_passes(self):
        """Find renderable passes in the scene.

        Returns:
            (CHouDeadlinePass list): pass list
        """
        _type = hou.nodeTypeCategories()['Driver'].nodeTypes()['deadline']
        _passes = []
        for _dl in _type.instances():
            _LOGGER.debug(' - CHECKING %s', _dl)
            _rop = single(_dl.inputs(), catch=True)
            _LOGGER.debug('   - ROP %s', _rop)
            if not _rop:
                continue
            try:
                _pass = _CHouDeadlinePass(render=_rop, deadline_=_dl)
            except ValueError as _exc:
                _LOGGER.info('   - REJECTED %s', _exc)
                continue
            _passes.append(_pass)
        return _passes

    def export(
            self, passes, version_up=True, notes=None, submit=True,
            priority=50, progress=True):
        """Execute this render export.

        Args:
            passes (CHouDeadlinePass list): passes to render
            version_up (bool): version up after export
            notes (str): export notes
            submit (bool): execute submission (disable for debugging)
            priority (int): apply render priority
            progress (bool): show submit progress

        Returns:
            (CPOutputSeq list): renders
        """
        _LOGGER.info('EXPORT %s', self)
        _LOGGER.info(' - PASSES %s', passes)

        # Prepare submission
        _outs = []
        for _pass in passes:
            _outs += _setup_deadline_rop(
                _pass.deadline, comment=notes, priority=priority)
        self.progress.set_pc(20)

        if submit:

            # Save scene to avoid deadline unsaved changes dialog
            hou.hipFile.save()
            assert not hou.hipFile.hasUnsavedChanges()
            self.progress.set_pc(40)

            # Execute submission
            _submit = _find_new_jobs(_submit_deadline_rops)
            _deadlines = [_pass.deadline for _pass in passes]
            _LOGGER.info(' - DEADLINES %s', _deadlines)
            _jobs = _submit(_deadlines)
            if len(_jobs) == 1:
                _check_job_batch_name(single(_jobs), batch_name=self.work.base)
            _LOGGER.info(' - JOBS %s', _jobs)
            self.progress.set_pc(60)

            # Add update job
            farm.submit_update_job(
                work=self.work, batch_name=self.work.base, comment=notes,
                dependencies=_jobs, outputs=_outs, stime=_jobs[0].ctime,
                metadata=self.metadata, priority=priority)
            self.progress.set_pc(70)

        return _outs


class _CHouDeadlinePass(rh_pass.CRenderPass):
    """Represents a render pass in houdini.

    This is defined as a mantra/redshift ROP with a single deadline node
    attached.
    """

    def __init__(self, render, deadline_):
        """Constructor.

        Args:
            render (RopNode): mantra/redshift node
            deadline_ (RopNode): deadline node
        """
        self.render = render
        self.deadline = deadline_
        _rop_t = render.type().name()
        if _rop_t == 'ifd':
            _parm = 'vm_picture'
        elif _rop_t == 'Redshift_ROP':
            _parm = 'RS_outputFileNamePrefix'
        else:
            raise ValueError(_rop_t)
        _path = render.parm(_parm).eval()
        _extn = File(_path).extn or 'exr'
        super().__init__(node=render, name=render.name(), extn=_extn)

    @property
    def renderable(self):
        """Check renderable state of this ROP.

        Returns:
            (bool): renderable
        """
        return not self.deadline.isBypassed()

    def set_renderable(self, renderable):
        """Set renderable state of this ROP.

        Args:
            renderable (bool): state to apply
        """
        self.deadline.bypass(not renderable)


def _find_new_jobs(func):
    """Decorater that finds new farm jobs that were created on execute.

    Args:
        func (fn): function to decorate

    Returns:
        (fn): decorated function
    """

    def _find_new_jobs_func(*args, **kwargs):

        _pre_jobs = farm.find_jobs(force=True)
        func(*args, **kwargs)
        # time.sleep(5)
        _post_jobs = farm.find_jobs(force=True)
        return sorted(set(_post_jobs) - set(_pre_jobs))

    return _find_new_jobs_func


def _setup_rs_rop(rop):
    """Setup redshift ROP.

    Args:
        rop (RopNode): node to update

    Returns:
        (CPOutput list): ROP outputs
    """
    _LOGGER.info('   - SETUP REDSHIFT ROP %s', rop)

    _outs = []
    _work = pipe.cur_work()

    # Set up redshift archive export
    _rs_seq = _work.to_output(
        'cache_seq', extn='rs', output_name=rop.name())
    _LOGGER.info('     - RS SEQ %s', _rs_seq)
    for _parm_s in [
            'rspath',
            'RS_archive_file',
    ]:
        _parm = rop.parm(_parm_s)
        _parm.deleteAllKeyframes()
        _parm.set(_rs_seq.path.replace('.%04d.', '.$F4.'))
    _outs.append(_rs_seq)

    # Set up render
    _exr = _work.to_output('render', extn='exr', output_name=rop.name())
    _LOGGER.info('     - EXR %s', _exr)
    for _parm_s in [
            'RS_outputFileNamePrefix',
    ]:
        _parm = rop.parm(_parm_s)
        _parm.deleteAllKeyframes()
        _parm.set(_exr.path.replace('.%04d.', '.$F4.'))
    _outs.append(_exr)

    # Disable/mark unused parms
    for _parm in [
            'imgpath',
            'scene',
    ]:
        _parm = rop.parm(_parm)
        _parm.set('N/A')
        _parm.deleteAllKeyframes()
    rop.parm('ver').set(-1)
    rop.parm('ver').deleteAllKeyframes()

    return _outs


def _setup_mantra_rop(rop):
    """Setup mantra ROP.

    Args:
        rop (RopNode): node to update

    Returns:
        (CPOutput list): ROP outputs
    """
    _LOGGER.info('   - SETUP MANTRA ROP %s', rop)

    _outs = []
    _work = pipe.cur_work()

    # Set up redshift archive export
    _ifd_seq = _work.to_output(
        'cache_seq', extn='ifd', output_name=rop.name())
    _LOGGER.info('     - IFD SEQ %s', _ifd_seq)
    for _parm_s in [
            'soho_diskfile',
            'ifdpath',
    ]:
        _parm = rop.parm(_parm_s)
        _parm.deleteAllKeyframes()
        _parm.set(_ifd_seq.path.replace('.%04d.', '.$F4.'))
    _outs.append(_ifd_seq)

    # Set up render
    _exr = _work.to_output('render', extn='exr', output_name=rop.name())
    if len(_exr.path) > 260:
        raise RuntimeError(
            f'Image path too long ({len(_exr.path)}): {_exr.path}')
    _LOGGER.info('     - EXR %s', _exr)
    for _parm_s in [
            'vm_picture',
    ]:
        _parm = rop.parm(_parm_s)
        _parm.deleteAllKeyframes()
        _parm.set(_exr.path.replace('.%04d.', '.$F4.'))
    _outs.append(_exr)

    # Disable/mark unused parms
    for _parm in [
            'imgpath',
            'scene',
    ]:
        _parm = rop.parm(_parm)
        _parm.set('N/A')
        _parm.deleteAllKeyframes()

    rop.parm('ver').set(-1)
    rop.parm('ver').deleteAllKeyframes()

    return _outs


def _setup_deadline_rop(rop, comment, priority=50):
    """Setup deadline ROP.

    Args:
        rop (RopNode): deadline node to update
        comment (str): comment to apply
        priority (int): priority to apply

    Returns:
        (CPOutput list): ROP outputs
    """
    _LOGGER.info(' - SETUP DEADLINE ROP %s', rop)
    _work = pipe.cur_work()
    _priority = rop.parm('dl_priority').eval()

    _outs = []
    for _input in rop.inputs():
        _type = _input.type().name()
        if _type == 'Redshift_ROP':
            _outs += _setup_rs_rop(_input)
        elif _type == 'ifd':
            _outs += _setup_mantra_rop(_input)
        else:
            raise NotImplementedError(
                f'Unhandled type {_type}: {_input.path()}')

    rop.parm('dl_comment').set(comment)
    for _parm_s in ['dl_priority', 'dl_redshift_priority']:
        _parm = rop.parm(_parm_s)
        if _parm:
            _parm.set(priority)
        else:
            _LOGGER.warning('   - MISSING PARM %s', _parm_s)

    return _outs


def _submit_deadline_rops(rops):
    """Submit deadline ROPs.

    Args:
        rops (RopNode list): ROPs to submit
    """
    for _node in qt.progress_bar(
            rops, 'Submitting {:d} rop{}'):
        _node.parm('dl_Submit').pressButton()


def _check_job_batch_name(job, batch_name, force=False):
    """Check the given job has correct batch name, applying if needed.

    Args:
        job (CDFarmJob): job to check
        batch_name (str): batch name to apply
        force (bool): force reread details
    """
    _LOGGER.info(' - CHECK JOB BATCH NAME %s', job)
    job.to_details(force=force)

    _batch_name = job.to_details()['Batch Name']
    _LOGGER.info('   - CUR BATCH NAME %s (req %s)', _batch_name, batch_name)
    if _batch_name == batch_name:
        return

    _LOGGER.info('   - UPDATING BATCH NAME')
    _deadline = find_exe('deadlinecommand')
    _cmds = [_deadline, '-SetJobSetting ', job.uid, 'BatchName', batch_name]
    _result = system(_cmds, verbose=2, result='out/err')
    assert job.to_details(force=True)['Batch Name'] == batch_name
