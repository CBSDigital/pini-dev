"""Tools for managing the deadline farm object."""

import logging
import time

from pini import pipe, qt
from pini.utils import (
    system, single, to_str, safe_zip, cache_result, find_exe, plural)

from .. import base
from . import d_job, d_utils

_LOGGER = logging.getLogger(__name__)


class CDFarm(base.CFarm):
    """Represents the deadline farm."""

    NAME = 'Deadline'
    ICON = d_utils.ICON

    @cache_result
    def find_groups(self):
        """Find avaliable submission groups.

        Returns:
            (str list): groups
        """
        return system([find_exe('deadlinecommand'), '-Groups']).split()

    @cache_result
    def find_limit_groups(self):
        """Find avaliable submission groups.

        Returns:
            (str list): groups
        """
        _cmds = [find_exe('deadlinecommand'), '-GetLimitGroupNames']
        return system(_cmds).split()

    def submit_job(self, job):
        """Submit a job to the farm.

        Args:
            job (CJob): job to submit
        """
        return single(self.submit_jobs([job]))

    def submit_jobs(self, jobs, name='jobs', submit=True):
        """Submit jobs to the farm.

        Args:
            jobs (CJob list): jobs to submit
            name (str): override submission name (for .sub file)
            submit (bool): execute submission

        Returns:
            (str list): job ids
        """
        assert single({_job.stime for _job in jobs})

        # Write job files
        for _job in jobs:
            _job.write_submission_files()

        # Write submit file
        _sub_file = jobs[0].job_file.to_dir().to_file(name+'.sub')
        _sub_lines = ['-SubmitMultipleJobs']
        for _job in jobs:
            _sub_lines += [
                '', '-Job',
                _job.info_file.path,
                _job.job_file.path,
                _job.scene.path]
        _sub_text = '\n'.join(_sub_lines)
        assert not _sub_file.exists()
        _sub_file.write(_sub_text)
        _LOGGER.info(' - SUB FILE %s', _sub_file.path)

        # Execute submission
        _deadline_cmd = find_exe('deadlinecommand')
        assert _deadline_cmd
        _cmds = [_deadline_cmd, _sub_file]
        _cmds = [to_str(_cmd) for _cmd in _cmds]
        _LOGGER.debug(' - CMDS %s', ' '.join(_cmds))
        if submit:
            _result = system(_cmds)
            _LOGGER.debug(' - RESULT %s', _result)
            _job_ids = d_utils.read_job_ids(_result)
        else:
            _job_ids = [None]*len(jobs)
        _LOGGER.info(' - JOB IDS %s', _job_ids)

        # Apply job ids to jobs
        for _job, _id in safe_zip(jobs, _job_ids):
            _job.jid = _id

        d_utils.flush_old_submissions(job=pipe.cur_job(), force=True)

        return _job_ids

    def submit_maya_cache(
            self, cacheables, comment='', priority=50, machine_limit=0,
            save=True, checks_data=None, extn='abc', flags=None):
        """Submit maya cache job to the farm.

        Args:
            cacheables (CPCacheable list): cacheables to submit
            comment (str): job comment
            priority (int): job priority (0 [low] - 100 [high])
            machine_limit (int): job machine limit
            save (bool): save scene on submit
            checks_data (dict): sanity check data
            extn (str): cache output format (abc/fbx)
            flags (dict): cache flags

        Returns:
            (str list): job ids
        """
        from pini.tools import sanity_check
        from . import d_maya_job

        _stime = time.time()
        _work = pipe.CACHE.cur_work
        _batch = _work.base

        # Reverse list so they appear in order on deadline
        _cbls = sorted(cacheables, reverse=True)
        _checks_data = checks_data or sanity_check.launch_export_ui(
            action='cache')
        if save:
            _work.save(reason='deadline cache')
        _progress = qt.progress_dialog(
            title='Submitting Cache', stack_key='SubmitCache', col='OrangeRed')

        # Build cache jobs
        _cache_jobs = []
        for _cbl in _cbls:
            _lines = [
                'from maya_pini import m_pipe',
                '_cbl = m_pipe.{}("{}")'.format(
                    type(_cbl).__name__, str(_cbl.node)),
                '_checks_data = {}'.format(_checks_data),
                '_flags = {}'.format(flags or {}),
                '_extn = "{}"'.format(extn),
                'm_pipe.cache('
                '    [_cbl], checks_data=_checks_data, extn=_extn, force=True,'
                '    **_flags)',
            ]
            _py = '\n'.join(_lines)
            _name = '{} - {} [cache]'.format(_batch, _cbl.output_name)
            _job = d_maya_job.CDMayaPyJob(
                py=_py, comment=comment, priority=priority, work=_work,
                machine_limit=machine_limit, stime=_stime, error_limit=1,
                name=_name, batch_name=_work.base)
            _cache_jobs.append(_job)
        self.submit_jobs(_cache_jobs, name='cache')
        _progress.set_pc(50)

        # Submit update cache job
        _update_job = self._submit_update_job(
            work=_work, dependencies=_cache_jobs, comment=comment,
            batch_name=_batch, stime=_stime)
        _progress.set_pc(100)
        _progress.close()

        return _cache_jobs + [_update_job]

    def submit_maya_render(
            self, camera=None, comment='', priority=50, machine_limit=0,
            frames=None, group=None, chunk_size=1, version_up=False,
            limit_groups=None, checks_data=None, submit=True, force=False):
        """Submit maya render job to the farm.

        Args:
            camera (CCamera): render cam
            comment (str): job comment
            priority (int): job priority (0 [low] - 100 [high])
            machine_limit (int): job machine limit
            frames (int list): frames to render
            group (str): submission group
            chunk_size (int): apply job chunk size
            version_up (bool): version up on render
            limit_groups (str): comma separated limit groups
                (eg. maya-2023,vray)
            checks_data (dict): override sanity checks data
            submit (bool): submit render to deadline (disable for debugging)
            force (bool): submit without confirmation dialogs

        Returns:
            (CDJob list): jobs
        """
        from maya_pini import open_maya as pom
        from pini.dcc import export
        from . import d_maya_job

        _cam = camera or pom.find_render_cam()
        _stime = time.time()
        _work = pipe.CACHE.obt_cur_work()
        _batch = _work.base
        _lyrs = pom.find_render_layers(renderable=True)

        _render_scene = _work.save(
            force=True, reason='deadline render', result='bkp')
        _metadata = export.build_metadata(
            'render', sanity_check_=True, checks_data=checks_data,
            task=_work.task, force=force)
        _progress = qt.progress_dialog(
            title='Submitting Render', stack_key='SubmitRender',
            col='OrangeRed')

        # Submit render jobs
        _render_jobs = []
        for _lyr in _lyrs:
            _job = d_maya_job.CDMayaRenderJob(
                stime=_stime, layer=_lyr.pass_name, priority=priority,
                work=_work, frames=frames, camera=_cam, comment=comment,
                machine_limit=machine_limit, group=group, chunk_size=chunk_size,
                limit_groups=limit_groups, scene=_render_scene)
            _render_jobs.append(_job)
            _LOGGER.info(' - SCENE %s', _job.scene)
            assert _job.scene == _render_scene
        assert not _render_jobs[0].jid
        if submit:
            self.submit_jobs(_render_jobs, name='render')
            assert _render_jobs[0].jid
        _progress.set_pc(50)

        # Submit update cache job
        _update_job = self._submit_update_job(
            work=_work, dependencies=_render_jobs, comment=comment,
            batch_name=_batch, stime=_stime, metadata=_metadata,
            priority=priority, submit=submit,
            outputs=[_job.output for _job in _render_jobs])
        _progress.set_pc(100)
        _progress.close()

        if version_up:
            pipe.version_up()

        if not force:
            qt.notify(
                'Submitted {:d} layer{} to deadline.\n\nBatch name:\n{}'.format(
                    len(_lyrs), plural(_lyrs), _batch),
                title='Render Submitted', icon=d_utils.ICON)

        return _render_jobs + [_update_job]

    def submit_maya_py(
            self, name, py, comment='', priority=50, machine_limit=0,
            error_limit=0, edit_py=False, tmp_py=None, submit=True):
        """Submit mayapy job to farm.

        Args:
            name (str): job name
            py (str): python to execute
            comment (str): job comment
            priority (int): job priority (0 [low] - 100 [high])
            machine_limit (int): job machine limit
            error_limit (int): job error limit
            edit_py (bool): edit tmp python file on submit
            tmp_py (File): override tmp py file path
            submit (bool): execute submission

        Returns:
            (str list): job ids
        """
        from . import d_maya_job
        _sub = d_maya_job.CDMayaPyJob(
            name=name, py=py, priority=priority, machine_limit=machine_limit,
            error_limit=error_limit, comment=comment, tmp_py=tmp_py,
            edit_py=edit_py)
        return _sub.submit(submit=submit)

    def submit_py(
            self, name, py, comment='', priority=50, machine_limit=0,
            error_limit=0, edit_py=False, tmp_py=None, submit=True):
        """Submit python job to farm.

        Args:
            name (str): job name
            py (str): python to execute
            comment (str): job comment
            priority (int): job priority (0 [low] - 100 [high])
            machine_limit (int): job machine limit
            error_limit (int): job error limit
            edit_py (bool): edit py file on save to disk
            tmp_py (File): override path to tmp py file
            submit (bool): execute submission

        Returns:
            (str list): job ids
        """
        _sub = d_job.CDPyJob(
            name=name, py=py, priority=priority, machine_limit=machine_limit,
            error_limit=error_limit, comment=comment, tmp_py=tmp_py,
            edit_py=edit_py)
        return _sub.submit(submit=submit)

    def _submit_update_job(
            self, work, dependencies, comment, batch_name, stime,
            priority=50, metadata=None, outputs=None, submit=True):
        """Submit job which updates work file output cache.

        Args:
            work (CCPWork): work file to update output cache for
            dependencies (CDJob list): jobs to wait for before updating
            comment (str): job comment
            batch_name (str): job batch name
            stime (float): submission time
            priority (int): job priority (0 [low] - 100 [high])
            metadata (dict): metadata to apply to outputs
            outputs (CPOutput list): outputs to apply metadata to
            submit (bool): execute submission

        Returns:
            (CDPyJob): update job
        """

        # Submit job
        _py = _build_update_job_py(
            outputs=outputs, metadata=metadata, work=work)
        _update_job = d_job.CDPyJob(
            name='{} [update cache]'.format(work.base), comment=comment,
            py=_py, batch_name=batch_name, dependencies=dependencies,
            stime=stime, priority=priority)
        assert not _update_job.jid
        if submit:
            _update_job.submit(name='update')
            assert _update_job.jid

        return _update_job


def _build_update_job_py(outputs, metadata, work):
    """Build update for update job.

    Args:
        outputs (CPOutput list): new outputs
        metadata (dict): output metadata
        work (CPWork): parent work file

    Returns:
        (str): python to update outputs
    """
    _lines = [
        'from pini import pipe',
        'from pini.utils import last',
        '']

    if outputs:

        # Build output objects
        _lines += [
            '# Build output objects',
            '_outs = [']
        for _out in outputs:
            _lines += ['    pipe.to_output("{}"),'.format(_out.path)]
        _lines += [']', '']

        # Register shotgrid
        if pipe.MASTER == 'shotgrid':
            _lines += [
                '# Register outputs in shotgrid',
                '_LOGGER.info("REGISTER OUTPUTS")',
                'from pini.pipe import shotgrid',
                'for _last, _out in last(_outs):',
                '    assert _out.exists()',
                '    shotgrid.create_pub_file(',
                '        _out, force=True, update_cache=_last)',
                '']

        # Apply metadata
        if metadata:
            _lines += [
                '# Update metadata',
                '_LOGGER.info("UPDATE METADATA")',
                '_metadata = {}'.format(metadata),
                'for _out in _outs:',
                '    if not _out.exists():',
                '        raise RuntimeError(_out.path)',
                '    _out.set_metadata(_metadata)',
                '']

    # Update workfile output cache
    _lines += [
        '# Update work outputs cache',
        '_LOGGER.info("UPDATE CACHE")',
        '_work_c = pipe.CACHE.obt_work("{}")'.format(work.path),
        '_work_c.find_outputs(force=True)',
        '',
        '_LOGGER.info("UPDATE CACHE COMPLETE")',
        '']

    return '\n'.join(_lines)
