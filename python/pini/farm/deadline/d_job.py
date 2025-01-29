"""Tools for managing deadline jobs."""

# pylint: disable=too-many-instance-attributes

import logging
import os
import sys
import time

from pini import pipe, dcc
from pini.utils import strftime, get_user, to_pascal, File, ints_to_str

from . import d_utils

_LOGGER = logging.getLogger(__name__)


class CDJob:
    """Represents a deadline job submission."""

    stype = None
    plugin = None

    machine_limit = 0
    priority = 50
    camera = ''
    frames = (1, )
    error_limit = None
    draft = False

    jid = None
    batch_name = None

    def __init__(
            self, name, work=None, stime=None, priority=50, machine_limit=0,
            comment=None, error_limit=0, frames=None, batch_name=None,
            dependencies=(), group=None, chunk_size=1, limit_groups=None,
            scene=None, output=None):
        """Constructor.

        Args:
            name (str): job name
            work (File): job work file
            stime (float): job submission time
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            comment (str): job comment
            error_limit (int): job error limit
            frames (int list): job frame list
            batch_name (str): job batch/group name
            dependencies (CDJob list): jobs to depend on
            group (str): submission group
            chunk_size (int): apply chunk size
            limit_groups (str): comma separated limit groups
                (eg. maya-2023,vray)
            scene (File): render scene (if not work file)
            output (CPOutput): output for this job
        """
        from pini import farm

        self.stime = stime or time.time()
        self.comment = comment
        self.priority = priority
        self.machine_limit = machine_limit
        self.name = name
        self.work = work
        self.error_limit = error_limit
        self.batch_name = batch_name
        if not self.batch_name and work:
            self.batch_name = work.base
        self.scene = scene or self.work
        self.output = output

        self.chunk_size = chunk_size

        if frames:
            self.frames = frames
        self.dependencies = dependencies
        assert isinstance(self.dependencies, (list, tuple))

        _group = group or os.environ.get('PINI_DEADLINE_GROUP')
        if _group not in farm.find_groups():
            raise RuntimeError(f'Bad group {_group}')
        self.group = _group
        if limit_groups:
            _LOGGER.debug(' - LIMIT GROUPS %s', limit_groups)
            if not isinstance(limit_groups, (list, tuple)):
                raise RuntimeError(limit_groups)
            for _group in limit_groups:
                if _group not in farm.find_limit_groups():
                    raise RuntimeError('Bad limit group '+_group)
        self.limit_groups = limit_groups or ()

        assert self.stype
        assert self.name

        self.info_file = self._to_submission_file(extn='info')
        self.job_file = self._to_submission_file(extn='job')

    @property
    def tag(self):
        """Obtain tag for this job.

        This is the name in a form which can be saved in a file path.

        Returns:
            (str): tag
        """
        return to_pascal(self.name)

    @property
    def uid(self):
        """Obtain job uid.

        The defines the tmp directory where job files are written.

        Returns:
            (str): uid (timestamp)
        """
        return strftime('%y%m%d_%H%M%S', self.stime)

    @property
    def job(self):
        """Obtain pipeline job which is generating this farm submission.

        Returns:
            (CPJob): pipeline job
        """
        return pipe.CACHE.cur_job

    def _to_submission_file(self, extn):
        """Build a submission file for this job.

        Args:
            extn (str): file extension

        Returns:
            (File): submission file
        """
        _fmt = '.pini/Deadline/{user}/{uid}/{stype}_{name}.{extn}'
        _kwargs = dict(  # pylint: disable=use-dict-literal
            user=get_user(), day=strftime('%y%m%d', self.stime),
            uid=self.uid, name=self.tag, stype=self.stype)
        return self.job.to_file(_fmt.format(extn=extn, **_kwargs))

    def _build_info_data(self):
        """Build info data for this job.

        Returns:
            (dict): submission info data
        """
        assert self.plugin
        assert self.group
        assert 0 < self.priority < 100

        # Add dependencies
        for _job in self.dependencies:
            assert _job.jid
            assert isinstance(_job, CDJob)
        _dep_str = ','.join(_job.jid for _job in self.dependencies)
        assert 'None' not in _dep_str

        _frames_s = ints_to_str(self.frames)
        _data = {
            'Plugin': self.plugin,
            'Name': self.name,
            'Comment': self.comment,
            'Department': '',
            'Pool': 'none',
            'SecondaryPool': '',
            'Group': self.group,
            'Priority': str(self.priority),
            'TaskTimeoutMinutes': '0',
            'EnableAutoTimeout': 'False',
            'ConcurrentTasks': '1',
            'LimitConcurrentTasksToNumberOfCpus': 'True',
            'MachineLimit': str(self.machine_limit),
            'Whitelist': '',
            'LimitGroups': ','.join(self.limit_groups),
            'JobDependencies': _dep_str,
            'OnJobComplete': 'Nothing',
            'InitialStatus': 'Active',
            'Frames': _frames_s,
            'ChunkSize': str(self.chunk_size),
            'ExtraInfo0': self.job.name,
        }
        _LOGGER.debug(
            ' - LIMIT GROUPS %s %s', self.limit_groups, _data['LimitGroups'])

        if self.batch_name:
            _data['BatchName'] = self.batch_name
        if self.output:
            _data['OutputDirectory0'] = self.output.to_dir().path

        if self.error_limit:
            _data['OverrideJobFailureDetection'] = 'True'
            _data['FailureDetectionJobErrors'] = str(self.error_limit)

        return _data

    def _build_job_data(self):
        """Build job data for this submission.

        Returns:
            (dict): submission job data
        """
        # _ver, _ = dcc.to_version(str)
        _data = {}
        if dcc.NAME:
            _data['Version'] = dcc.to_version(str)
        if self.scene:
            _data['SceneFile'] = self.scene
        return _data

    def write_submission_files(self):
        """Write job submission files to disk."""

        # Write info file
        _LOGGER.debug(' - INFO FILE %s', self.info_file.path)
        assert not self.info_file.exists()
        _info_data = self._build_info_data()
        d_utils.write_deadline_data(
            data=_info_data, file_=self.info_file,
            sort=d_utils.info_key_sort)
        _LOGGER.debug(' - INFO DATA %s', _info_data)

        # Write job file
        assert not self.job_file.exists()
        _job_data = self._build_job_data()
        d_utils.write_deadline_data(
            data=_job_data, file_=self.job_file,
            sort=d_utils.job_key_sort)
        _LOGGER.debug(' - JOB DATA %s', _job_data)
        _LOGGER.debug(' - JOB %s', self.job_file.path)

    def submit(self, submit=True, name=None):
        """Submit this job to deadline.

        Args:
            submit (bool): execute submission
            name (str): override submission name (for .sub file)

        Returns:
            (str): job id
        """
        from .. import deadline
        return deadline.FARM.submit_jobs(
            [self], submit=submit, name=name or self.tag)


class CDCmdlineJob(CDJob):
    """Represents a command line job."""

    stype = 'Cmdline'
    plugin = 'CommandLine'

    def __init__(self, cmds: list, name, stime=None, **kwargs):
        """Constructor.

        Args:
            cmds (str list): list of commands
            name (str): job name
            stime (float): override job submission time
        """
        self.name = name
        self.stime = stime or time.time()

        self.cmds = cmds
        self.exe = cmds[0]
        self.args = cmds[1:]
        self.sh_file = self._to_submission_file(extn='sh')

        super().__init__(
            work=self.sh_file, name=name, stime=stime, **kwargs)

    def _build_job_data(self):
        """Build job data for this submission.

        Returns:
            (dict): submission job data
        """
        _data = {
            'Executable': self.exe,
            'Arguments': ' '.join(self.args),
        }
        return _data

    def write_submission_files(self):
        """Write job submission files to disk."""

        # Write tmp py file
        self.sh_file.write(' '.join(self.cmds), force=True)
        _LOGGER.debug(' - SH FILE %s', self.sh_file.path)

        super().write_submission_files()


class CDPyJob(CDJob):
    """Represents a python job to be executed on deadline."""

    stype = 'Py'
    plugin = 'Python'

    def __init__(
            self, name, py, stime=None, priority=50, machine_limit=0,
            comment=None, error_limit=1, batch_name=None, dependencies=(),
            tmp_py=None, edit_py=False, wrap_py=True):
        """Constructor.

        Args:
            name (str): job name
            py (str): python code to execute
            stime (float): job submission time
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            comment (str): job comment
            error_limit (int): job error limit
            batch_name (str): job batch/group name
            dependencies (CDJob list): jobs to depend on
            tmp_py (File): override tmp py file
            edit_py (bool): edit py file on save to disk
            wrap_py (bool): wrap py with pipeline init
        """
        self.name = name
        self.stime = stime

        # Setup python
        if not self.job:
            raise RuntimeError('No current job found')
        self.py_file = File(tmp_py or self._to_submission_file(extn='py'))
        self.py = py
        if wrap_py:
            self.py = d_utils.wrap_py(py, py_file=self.py_file, name=self.name)
        if edit_py:
            self.py_file.edit()

        super().__init__(
            name=name, stime=stime, comment=comment, priority=priority,
            machine_limit=machine_limit, work=self.py_file,
            error_limit=error_limit, batch_name=batch_name,
            dependencies=dependencies)

    def _build_job_data(self):
        """Build job data for this submission.

        Returns:
            (dict): submission job data
        """
        _py_ver = os.environ.get(
            'PINI_DEADLINE_PYVER',
            f'{sys.version_info.major:d}.{sys.version_info.minor:d}')
        _data = {
            'Arguments': '',
            'Version': str(_py_ver),
            'SingleFramesOnly': 'False',
        }
        return _data

    def write_submission_files(self):
        """Write job submission files to disk."""

        # Write tmp py file
        self.py_file.write(self.py, force=True)
        _LOGGER.debug(' - PY FILE %s', self.py_file.path)

        super().write_submission_files()
