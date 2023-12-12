"""Tools for managing the deadline farm object."""

import logging
import time

from pini import pipe, qt
from pini.utils import system, single, to_str, safe_zip

from .. import base
from . import d_job, d_utils

_LOGGER = logging.getLogger(__name__)


class CDFarm(base.CFarm):
    """Represents the deadline farm."""

    NAME = 'Deadline'
    ICON = d_utils.ICON

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
                _job.work.path]
        _sub_text = '\n'.join(_sub_lines)
        assert not _sub_file.exists()
        _sub_file.write(_sub_text)
        _LOGGER.info(' - SUB FILE %s', _sub_file.path)

        # Execute submission
        assert d_utils.DEADLINE_CMD and d_utils.DEADLINE_CMD.exists()
        _cmds = [d_utils.DEADLINE_CMD, _sub_file]
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

        return _job_ids

    def submit_maya_cache(
            self, cacheables, comment='', priority=50, machine_limit=0,
            save=True, checks_data=None, flags=None):
        """Submit maya cache job to the farm.

        Args:
            cacheables (CPCacheable list): cacheables to submit
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            save (bool): save scene on submit
            checks_data (dict): sanity check data
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
        _checks_data = checks_data or sanity_check.launch_export_ui('Cache')
        if save:
            _work.save(reason='deadline cache')
        _progress = qt.progress_dialog(
            title='Submitting Cache', stack_key='SubmitCache', col='OrangeRed')

        # Build cache jobs
        _cache_jobs = []
        for _cbl in _cbls:
            _lines = [
                'from maya_pini import m_pipe',
                '_cbl = m_pipe.{}("{}")'.format(type(_cbl).__name__, _cbl.node),
                '_checks_data = {}'.format(_checks_data),
                '_flags = {}'.format(flags or {}),
                'm_pipe.cache('
                '    [_cbl], checks_data=_checks_data, force=True, **_flags)',
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

        qt.notify(
            'Submitted {:d} caches to deadline.\n\nBatch name:\n{}'.format(
                len(_cbls), _batch),
            title='Cache Submitted', icon=d_utils.ICON)

        return _cache_jobs + [_update_job]

    def submit_maya_render(
            self, camera=None, comment='', priority=50, machine_limit=0,
            frames=None):
        """Submit maya render job to the farm.

        Args:
            camera (CCamera): render cam
            comment (str): job comment
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            frames (int list): frames to render

        Returns:
            (CDJob list): jobs
        """
        from maya_pini import open_maya as pom
        from pini.dcc import export_handler
        from . import d_maya_job

        _stime = time.time()
        _work = pipe.CACHE.cur_work
        _batch = _work.base
        _lyrs = pom.find_render_layers(renderable=True)

        _work.save(reason='deadline render')
        _progress = qt.progress_dialog(
            title='Submitting Render', stack_key='SubmitRender',
            col='OrangeRed')
        _metadata = export_handler.obtain_metadata('render', sanity_check_=True)

        # Submit render jobs
        _render_jobs = []
        for _lyr in _lyrs:
            _job = d_maya_job.CDMayaRenderJob(
                stime=_stime, layer=_lyr.pass_name, priority=priority,
                work=_work, frames=frames, camera=camera, comment=comment,
                machine_limit=machine_limit)
            _render_jobs.append(_job)
        assert not _render_jobs[0].jid
        self.submit_jobs(_render_jobs, name='render')
        assert _render_jobs[0].jid
        _progress.set_pc(50)

        # Submit update cache job
        _update_job = self._submit_update_job(
            work=_work, dependencies=_render_jobs, comment=comment,
            batch_name=_batch, stime=_stime, metadata=_metadata,
            outputs=[_job.output for _job in _render_jobs])
        _progress.set_pc(100)
        _progress.close()

        qt.notify(
            'Submitted {:d} layers to deadline.\n\nBatch name:\n{}'.format(
                len(_lyrs), _batch),
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
            priority (int): job priority (0-100)
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
            priority (int): job priority (0-100)
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
            metadata=None, outputs=None):
        """Submit job which updates work file output cache.

        Args:
            work (CCPWork): work file to update output cache for
            dependencies (CDJob list): jobs to wait for before updating
            comment (str): job comment
            batch_name (str): job batch name
            stime (float): submission time
            metadata (dict): metadata to apply to outputs
            outputs (CPOutput list): outputs to apply metadata to

        Returns:
            (CDPyJob): update job
        """

        # Build update py
        _lines = [
            'from pini import pipe',
            '',
            '# Update work outputs cache',
            '_work = pipe.CACHE.obt_work("{}")'.format(work.path),
            '_work.find_outputs(force=2)']
        if outputs and metadata:
            _lines += [
                '',
                '# Update metadata',
                '_metadata = {}'.format(metadata)]
            for _out in outputs:
                _lines.append(
                    'pipe.to_output("{}").set_metadata(_metadata)'.format(
                        _out.path))
        _py = '\n'.join(_lines)

        # Submit job
        _update_job = d_job.CDPyJob(
            name='{} [update cache]'.format(work.base), comment=comment,
            py=_py, batch_name=batch_name, dependencies=dependencies,
            stime=stime)
        assert not _update_job.jid
        _update_job.submit(name='update')
        assert _update_job.jid

        return _update_job
