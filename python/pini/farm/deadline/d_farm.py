"""Tools for managing the deadline farm object."""

import getpass
import logging
import time

from pini import pipe, qt
from pini.utils import (
    system, single, to_str, safe_zip, cache_result, find_exe, check_heart,
    to_snake, to_time_f, get_result_cacher, File, abs_path)

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

    def find_job(self, match):
        """Find a job.

        Args:
            match (str): match by name/uid

        Returns:
            (CDFarmJob): farm job
        """
        return single([
            _job for _job in self.find_jobs()
            if match in (_job.uid, _job.name)])

    def find_jobs(
            self, read_metadata=False, user=None, batch_name=None,
            write_file=None, force=False):
        """Find existing deadline jobs for the current user.

        Args:
            read_metadata (bool): read job metadata
            user (str): override user
            batch_name (str): filter by batch name
            write_file (File): write job details to file (for debugging)
            force (bool): force reread jobs

        Returns:
            (CDFarmJob list): farm jobs
        """
        _LOGGER.debug('FIND JOBS %d', read_metadata)
        _all_jobs = self._read_jobs(
            user=user, write_file=write_file, force=force)

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

    @get_result_cacher(use_args=('user',))
    def _read_jobs(
            self, user=None, write_file=False, jobs=None, force=False):
        """Read existing deadline jobs for the current user.

        Args:
            user (str): override user (otherwise current user)
            write_file (File): write job details to file (for debugging)
            jobs (CDFarmJob list): override job list (to update cache)
            force (bool): force reread jobs

        Returns:
            (CDFarmJob list): farm jobs
        """
        from pini import farm

        _jobs = jobs
        if not _jobs:

            # Read results
            _user = user or getpass.getuser()
            _deadline = find_exe('deadlinecommand')
            _cmds = [_deadline, 'GetJobsFilter', f'UserName={_user}']
            _start = time.time()
            _result = system(_cmds, verbose=1)
            farm.JOBS_READ_TIME = time.time()
            farm.JOBS_READ_DUR = farm.JOBS_READ_TIME - _start
            _result = _result.replace('\r', '')
            if write_file:
                write_file.write(_result, force=True)
                _LOGGER.info(
                    ' - WROTE FILE %s %s', write_file.nice_size(), write_file)

            # Process results
            _jobs = []
            for _details_s in qt.progress_bar(_result.split('\n\n\n')):
                _details_s = _details_s.strip()
                if not _details_s:
                    continue
                _job = _details_to_job(_details_s, rtime=farm.JOBS_READ_TIME)
                _jobs.append(_job)

            _LOGGER.info(
                ' - FOUND %d DEADLINE JOBS IN %.01fs', len(_jobs),
                farm.JOBS_READ_DUR)

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


def _details_to_job(details, rtime):
    """Convert job details string to a farm job object.

    Args:
        details (str): job details string (output by deadline command)
        rtime (float): details read time

    Returns:
        (CDFarmJob): farm job
    """
    _details_s = details.strip()
    assert _details_s

    _data = {'rtime': rtime}
    for _line in _details_s.split('\n'):
        if not _line.strip():
            continue
        check_heart()
        _key, _val = _line.strip().split('=', 1)

        if _key not in [
                'BatchName',
                'Comment',
                'ID',
                'JobName',
                'JobOutputDirectories',
                'JobOutputFileNames',
                'PluginInfoDictionary',
                'Status',
                'SubmitDateTimeString',
                'UserName',
        ]:
            continue
        _LOGGER.debug(' - LINE %s', _line)
        _LOGGER.debug('   - KVP %s %s', _key, _val)
        assert _key not in _data

        # Clean data
        if _key == 'SubmitDateTimeString':
            _fmt = '%m/%d/%Y %H:%M:%S'
            # _val = _val.strip()
            _LOGGER.debug('   - CONVERT TIME "%s"', _val)
            _val = to_time_f(time.strptime(_val, _fmt))
        _key = {
            'ID': 'uid',
            'JobName': 'name',
            'JobOutputDirectories': 'out_dirs',
            'JobOutputFileNames': 'out_fname',
            'PluginInfoDictionary': 'info_dict',
            'SubmitDateTimeString': 'ctime',
            'UserName': 'user',
        }.get(_key, to_snake(_key))

        _data[_key] = _val

    # Build output path
    _path = None
    _out_dirs = _data.pop('out_dirs', None)
    _out_fname = _data.pop('out_fname', None)
    _info_dict = _data.pop('info_dict', None)
    if _out_fname and _info_dict:
        _extn = File(_out_fname).extn
        _path = _info_dict_to_path(_info_dict, extn=_extn)
    if not _path and _out_dirs and _out_fname:
        _LOGGER.debug(' - OUT DIRS %s', _out_dirs)
        _LOGGER.debug(' - OUT FNAME %s', _out_fname)
        _path = abs_path(f'{_out_dirs}/{_out_fname}')
        _path = _path.replace('.####.', '.%04d.')
    _data['path'] = _path
    _LOGGER.debug('   - PATH %s', _path)

    _LOGGER.debug('   - ADD JOB %s', _data)
    return d_farm_job.CDFarmJob(**_data)


def _info_dict_to_path(dict_s, extn, log=10):
    """Read output path from info dict.

    Args:
        dict_s (str): plugin info dict string
        extn (str): output extension
        log (int): log level

    Returns:
        (str): output path
    """
    _LOGGER.log(log, ' - INFO DICT %s', dict_s)
    if not dict_s:
        return None

    # Process string into dict
    _data = {}
    for _kvp_s in dict_s.split(','):
        _LOGGER.debug('   - KVP %s', _kvp_s)
        _key, _val = _kvp_s.split('=', 1)
        _LOGGER.debug('     - KEY / VAL %s %s', _key, _val)
        _data[_key] = _val

    for _key in [
            'SceneFile', 'RenderLayer', 'OutputFilePrefix', 'OutputFilePath']:
        if _key not in _data:
            return None

    # Determine prefix
    _scn = _data['SceneFile']
    _lyr = _data['RenderLayer']
    if _lyr.startswith('rs_'):
        _lyr = _lyr[3:]
    _prefix = _data['OutputFilePrefix']
    for _tokens, _val in [
            (['<layer>', '<Layer>'], _lyr),
            (['<Scene>'], File(_scn).base),
    ]:
        for _token in _tokens:
            _prefix = _prefix.replace(_token, _val)
    _LOGGER.log(log, ' - PREFIX %s', _prefix)

    # Build path
    _path = f'{_data["OutputFilePath"]}/{_prefix}.%04d.{extn}'
    _LOGGER.log(log, ' - PATH %s', _path)

    return _path
