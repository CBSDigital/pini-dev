"""Tools for managing the deadline farm object."""

import getpass
import logging
import time

from pini import pipe, qt
from pini.utils import system, single, to_str, safe_zip, cache_result, find_exe

from .. import base
from . import submit, d_farm_job

_LOGGER = logging.getLogger(__name__)


class CDFarm(base.CFarm):
    """Represents the deadline farm."""

    NAME = 'Deadline'
    ICON = submit.ICON

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

    def find_jobs(
            self, read_metadata=False, user=None, batch_name=None, force=False):
        """Find existing deadline jobs for the current user.

        Args:
            read_metadata (bool): read job metadata
            user (str): override user
            batch_name (str): filter by batch name
            force (bool): force reread jobs

        Returns:
            (CDFarmJob list): farm jobs
        """
        _LOGGER.debug('FIND JOBS %d', read_metadata)
        _all_jobs = self._read_jobs(user=user, force=force)

        # Read metadata
        if read_metadata:
            _LOGGER.debug(' - READ METADATA')
            for _job in qt.progress_bar(
                    _all_jobs, 'Reading {:d} job{}', show_delay=2,
                    stack_key='ReadDeadlineJobs'):
                _job.to_details()

        # Apply filters
        _LOGGER.debug(' - APPLY FILTERS')
        _jobs = []
        for _job in _all_jobs:

            if batch_name and _job.batch_name != batch_name:
                continue
            _jobs.append(_job)

        return _jobs

    @cache_result
    def _read_jobs(self, user=None, force=False):
        """Read existing deadline jobs for the current user.

        Args:
            user (str): override user
            force (bool): force reread jobs

        Returns:
            (CDFarmJob list): farm jobs
        """
        _user = user or getpass.getuser()
        _cmds = [
            find_exe('deadlinecommand'),
            '-GetJobIdsFilter', f'UserName={_user}']
        _start = time.time()
        _results = system(_cmds, verbose=1).split()
        _jobs = [d_farm_job.CDFarmJob(_result) for _result in _results]
        _LOGGER.info(
            ' - FOUND %d DEADLINE JOBS IN %.01fs', len(_jobs),
            time.time() - _start)

        return _jobs

    def submit_job(self, job):
        """Submit a job to the farm.

        Args:
            job (CJob): job to submit
        """
        return single(self.submit_jobs([job]))

    def submit_jobs(self, jobs, name='jobs', submit_=True):
        """Submit jobs to the farm.

        Args:
            jobs (CJob list): jobs to submit
            name (str): override submission name (for .sub file)
            submit_ (bool): execute submission

        Returns:
            (str list): job ids
        """
        assert single({_job.stime for _job in jobs})

        # Write job files
        for _job in jobs:
            _job.write_submission_files()

        # Write submit file
        _sub_file = jobs[0].job_file.to_dir().to_file(name + '.sub')
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
        if submit_:
            _out, _err = system(_cmds, result='out/err')
            _LOGGER.debug(' - OUT %s', _out)
            _LOGGER.debug(' - ERR %s', _err)
            _job_ids = submit.read_job_ids(_out)
            if not _job_ids:
                _LOGGER.error(' - OUT %s', _out)
                _LOGGER.error(' - ERR %s', _err)
                raise RuntimeError('Deadline submission failed')
        else:
            _job_ids = [None] * len(jobs)
        _LOGGER.info(' - JOB IDS %s', _job_ids)

        # Apply job ids to jobs
        for _job, _id in safe_zip(jobs, _job_ids):
            _job.jid = _id

        submit.flush_old_submissions(job=pipe.cur_job(), force=True)

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
                f'_cbl = m_pipe.find_cacheable("{_cbl.node}")',
                f'_checks_data = {_checks_data}',
                f'_flags = {flags or {}}',
                f'_extn = "{extn}"',
                'm_pipe.cache(',
                '    [_cbl], checks_data=_checks_data, extn=_extn, force=True,',
                '    snapshot=False, **_flags)',
            ]
            _py = '\n'.join(_lines)
            _name = f'{_batch} - {_cbl.output_name} [cache]'
            _job = submit.CDMayaPyJob(
                py=_py, comment=comment, priority=priority, work=_work,
                machine_limit=machine_limit, stime=_stime, error_limit=1,
                name=_name, batch_name=_work.base)
            _cache_jobs.append(_job)
        self.submit_jobs(_cache_jobs, name='cache')
        _progress.set_pc(50)

        # Submit update cache job
        _outs = [_cbl.output for _cbl in _cbls]
        _update_job = self.submit_update_job(
            work=_work, dependencies=_cache_jobs, comment=comment,
            batch_name=_batch, stime=_stime, outputs=_outs)
        _progress.set_pc(100)
        _progress.close()

        return _cache_jobs + [_update_job]

    def submit_maya_py(
            self, name, py, comment='', priority=50, machine_limit=0,
            error_limit=0, edit_py=False, tmp_py=None, submit_=True):
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
            submit_ (bool): execute submission

        Returns:
            (str list): job ids
        """
        _sub = submit.CDMayaPyJob(
            name=name, py=py, priority=priority, machine_limit=machine_limit,
            error_limit=error_limit, comment=comment, tmp_py=tmp_py,
            edit_py=edit_py)
        return _sub.submit(submit_=submit_)

    def submit_py(
            self, name, py, comment='', priority=50, machine_limit=0,
            error_limit=0, edit_py=False, tmp_py=None, submit_=True,
            batch_name=None, **kwargs):
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
            submit_ (bool): execute submission
            batch_name (str): job batch name
            dependencies (CDJob list): jobs to wait for before updating

        Returns:
            (str list): job ids
        """
        _sub = submit.CDPyJob(
            name=name, py=py, priority=priority, machine_limit=machine_limit,
            error_limit=error_limit, comment=comment, tmp_py=tmp_py,
            edit_py=edit_py, batch_name=batch_name, **kwargs)
        return _sub.submit(submit_=submit_)

    def submit_update_job(
            self, work, dependencies, comment, batch_name, stime,
            priority=50, metadata=None, outputs=None, submit_=True):
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
            submit_ (bool): execute submission

        Returns:
            (CDPyJob): update job
        """

        # Submit job
        _py = _build_update_job_py(
            outputs=outputs, metadata=metadata, work=work)
        _update_job = submit.CDPyJob(
            name=f'{work.base} [update cache]', comment=comment,
            py=_py, batch_name=batch_name, dependencies=dependencies,
            stime=stime, priority=priority)
        assert not _update_job.jid
        if submit_:
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
        'from pini import farm',
        '',
        f'_work = "{work.path}"',
        '_outs = [']
    for _out in outputs:
        _lines += [f'    "{_out.path}",']
    _lines += [
        ']',
        f'_metadata = {metadata}',
        'farm.update_cache(work=_work, outputs=_outs, metadata=_metadata)']
    return '\n'.join(_lines)
