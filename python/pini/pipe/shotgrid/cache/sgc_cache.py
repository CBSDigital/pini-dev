"""Tools for managing the base container class for the shotgrid cache.

This manages global shotgrid requests, eg. jobs, steps, users.
"""

import logging
import operator

from pini import pipe
from pini.pipe.cache import pipe_cache_on_obj
from pini.utils import (
    single, strftime, basic_repr, apply_filter, get_user)

from . import sgc_job, sgc_utils, sgc_container

_LOGGER = logging.getLogger(__name__)
_GLOBAL_CACHE_DIR = pipe.GLOBAL_CACHE_ROOT.to_subdir('sgc')


class SGDataCache(object):
    """Base container class for the shotgrid data cache."""

    _sg = None

    @property
    def jobs(self):
        """Obtain list of valid jobs.

        Returns:
            (SGCJob list): jobs
        """
        return self._read_jobs()

    @property
    def steps(self):
        """Obtain list of steps.

        Returns:
            (SGCStep list): steps
        """
        return self._read_steps()

    @property
    def sg(self):
        """Obtain shotgrid handler.

        Returns:
            (CSGHandler): shotgrid request handler
        """
        if not self._sg:
            from pini.pipe import shotgrid
            self._sg = shotgrid.to_handler()
        return self._sg

    @property
    def users(self):
        """Obtain list of users.

        Returns:
            (SGCUser list): users
        """
        return self._read_users()

    def find_asset(self, match):
        """Find an asset.

        Args:
            match (str): path/name to match

        Returns:
            (SGCAsset): matching asset
        """
        _job = pipe.to_job(match)
        return self.find_job(_job).find_asset(match)

    def find_assets(self, job):
        """Search assets in the cache.

        Args:
            job (CPJob): job to search

        Returns:
            (SGCAsset list): assets
        """
        return self.find_job(job).find_assets()

    def find_entity(self, match):
        """Find an entity within the cache.

        Args:
            match (str|CPEntity): entity or path to match

        Returns:
            (SGCAsset|SGCShot): matching entity
        """
        _job = pipe.to_job(match)
        return self.find_job(_job).find_entity(match)

    def find_job(self, match=None):
        """Find a job.

        Args:
            match (str|int): job name/prefix/id

        Returns:
            (SGCJob): matching job
        """
        _match = match or pipe.cur_job()

        _match_jobs = [
            _job for _job in self.jobs
            if _match in (_job.name, _job.id_, _job.prefix, _job.job)]
        if len(_match_jobs) == 1:
            return single(_match_jobs)

        _filter_jobs = apply_filter(
            self.jobs, _match, key=operator.attrgetter('name'))
        if len(_filter_jobs) == 1:
            return single(_filter_jobs)

        raise ValueError(match)

    def find_jobs(self, force=False):
        """Search for valid jobs.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCJob list): jobs
        """
        return self._read_jobs(force=force)

    def find_pub_file(self, path=None, job=None):
        """Find a pub file in the cache.

        Args:
            path (str): match by path
            job (CPJob): job to search

        Returns:
            (SGCPubFile): matching pub file
        """
        _job = job or pipe.CPJob(path)
        return self.find_job(_job).find_pub_file(path=path)

    def find_pub_files(
            self, job=None, entity=None, work_dir=None, force=False):
        """Search pub files in the cache.

        Args:
            job (CPJob): job to search
            entity (CPEntity): filter by entity
            work_dir (CPWorkDir): filter by work dir
            force (bool): force rebuild cache

        Returns:
            (SGCPubFile list): pub files
        """
        _job = None
        if job:
            _job = job
        if not _job and entity:
            _job = entity.job
        if not _job and work_dir:
            _job = work_dir.job
        assert _job
        return self.find_job(_job).find_pub_files(
            entity=entity, work_dir=work_dir, force=force)

    def find_pub_type(self, match, type_='File'):
        """Find published file type.

        Args:
            match (str): token to match
            type_ (str): path type (File/Sequence)

        Returns:
            (SGCPubType): published file type
        """

        # Try matching code
        _code_matches = [
            _type for _type in self.find_pub_types() if _type.code == match]
        if len(_code_matches) == 1:
            return single(_code_matches)

        # Try using type suffix
        _file_matches = [
            _type for _type in self.find_pub_types()
            if _type.code == '{} {}'.format(match.capitalize(), type_)]
        if len(_file_matches) == 1:
            return single(_file_matches)

        # Try using mapping
        _map = {
            'mp4': 'Movie',
            'mov': 'Movie',
        }
        _map_matches = [
            _type for _type in self.find_pub_types()
            if _type.code == _map.get(match)]
        if len(_map_matches) == 1:
            return single(_map_matches)

        if type_ == 'Sequence':
            return self.find_pub_type('Image Sequence')

        raise ValueError(match)

    def find_pub_types(self):
        """Find published file types.

        Returns:
            (SGCPubType list): published file types
        """
        return self._read_pub_types()

    def find_shot(self, match):
        """Find a shot in the cache.

        Args:
            match (str): shot name/path

        Returns:
            (SGCShot): matching shot
        """
        _job = pipe.to_job(match)
        return self.find_job(_job).find_shot(match)

    def find_shots(self, job, has_3d=None):
        """Search the cache for shots.

        Args:
            job (CPJob): job to search
            has_3d (bool): filter by shot has 3D status

        Returns:
            (SGCShot list): matching shots
        """
        return self.find_job(job).find_shots(has_3d=has_3d)

    def find_step(self, match):
        """Find a pipeline step.

        Args:
            match (str|int): step id/name

        Returns:
            (SGCStep): matching step
        """
        _matches = [
            _step for _step in self.steps
            if match in (_step.id_, _step.short_name)]
        if len(_matches) == 1:
            return single(_matches)

        if _matches:
            _matches.sort(key=operator.attrgetter('list_order'))
            return _matches[0]

        raise ValueError(match)

    def find_steps(self, short_name=None, department=None, force=False):
        """Search pipeline steps.

        Args:
            short_name (str): filter by short name (NOTE: short
                names are not unique - eg. multiple fx steps)
            department (str): filter by department (eg. 3D/2D)
            force (bool): force rebuild cache

        Returns:
            (SGCStep list): matching steps
        """
        _steps = []
        for _step in self._read_steps(force=force):
            if department and _step.department != department:
                continue
            if short_name and _step.short_name != short_name:
                continue
            _steps.append(_step)
        return _steps

    def find_task(self, path=None, entity=None, step=None, task=None):
        """Find a task in the cache.

        Args:
            path (str): path to match
            entity (str): filter by entity
            step (str): filter by step
            task (str): filter by task

        Returns:
            (SGCTask): matching task
        """
        _job = None
        if entity:
            _job = entity.job
        if not _job and path:
            _job = pipe.CPJob(path)
        assert _job

        return self.find_job(_job).find_task(
            path=path, entity=entity, step=step, task=task)

    def find_tasks(
            self, job=None, entity=None, step=None, task=None, department=None,
            filter_=None):
        """Search tasks in the cache.

        Args:
            job (CPJob): job to search
            entity (str): filter by entity
            step (str): filter by step
            task (str): filter by task
            department (str): filter by department (eg. 3D/2D)
            filter_ (str): apply step/task name filter

        Returns:
            (SGCTask list): matching tasks
        """
        _job = job
        if not _job and entity:
            _job = entity.job
        assert _job
        return self.find_job(_job).find_tasks(
            department=department, entity=entity, filter_=filter_, task=task,
            step=step)

    def find_user(self, match=None, catch=True):
        """Find a user entry.

        Args:
            match (str): username/login/email
            catch (bool): no error if no entry found

        Returns:
            (SGCUser): user entry
        """
        _match = match or get_user()
        _LOGGER.debug('FIND USER %s', _match)

        _users = [_user for _user in self.users if _user.status != 'dis']

        _login_matches = [
            _user for _user in _users
            if _name_to_login(_user.name) == _match]
        if len(_login_matches) == 1:
            return single(_login_matches)
        _LOGGER.debug(' - FOUND %d LOGIN MATCHES', len(_login_matches))

        _email_matches = [
            _user for _user in _users
            if _email_to_login(_user.email) == _match]
        if len(_email_matches) == 1:
            return single(_email_matches)
        _LOGGER.debug(' - FOUND %d EMAIL MATCHES', len(_email_matches))

        if catch:
            return None
        raise ValueError(match)

    def _read_data(self, entity_type, fields, force=False):
        """Read data from shotgrid.

        Data is written to a day so if it's already been read today
        then that read is reused. Otherwise the cache is rebuilt.

        Args:
            entity_type (str): entity type to read
            fields (str list): fields to read
            force (bool): force rebuild cache
                1 - rebuild day cache
                2 - rebuild all caches from shotgrid

        Returns:
            (dict list): shotgrid results
        """
        _fields = tuple(sorted(set(fields) | {'updated_at'}))
        _day_cache = _GLOBAL_CACHE_DIR.to_file(
            '{}_D{}_{}.pkl'.format(
                entity_type, strftime('%y%m%d'),
                sgc_utils.to_fields_key(_fields)))
        if not force and _day_cache.exists():
            _data = _day_cache.read_pkl()
        else:
            _data = self._read_data_last_update(
                entity_type=entity_type, fields=_fields, force=force > 1)
            _day_cache.write_pkl(_data, force=True)

        return _data

    def _read_data_last_update(self, entity_type, fields, force=False):
        """Find last time the given field was updated.

        Args:
            entity_type (str): entity type to read
            fields (str list): fields to be requested
            force (bool): force rebuild cache

        Returns:
            ():
        """

        # Find most recent update
        _recent = single(self.sg.find(
            entity_type=entity_type,
            fields=['updated_at'],
            limit=1,
            order=[{'field_name': 'updated_at', 'direction': 'desc'}]))
        _update_t = _recent['updated_at']
        _update_s = strftime('%y%m%d_%H%M')
        _LOGGER.info(
            ' - LAST STEPS UPDATE %s', strftime('%d/%m/%y %H:%M', _update_t))

        # Obtain jobs data
        _cache_file = _GLOBAL_CACHE_DIR.to_file(
            '{}_T{}_{}.pkl'.format(
                entity_type, _update_s,
                sgc_utils.to_fields_key(fields)))
        if not force and _cache_file.exists():
            _data = _cache_file.read_pkl()
        else:
            _LOGGER.info(' - READING STEPS')
            _data = self.sg.find(entity_type, fields=fields)
            _cache_file.write_pkl(_data, force=True)

        return _data

    @pipe_cache_on_obj
    def _read_jobs(self, force=False):
        """Build list of valid jobs on shotgrid.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCJob list): jobs
        """
        _LOGGER.debug(' - READING JOBS')
        _fields = (
            'updated_at', 'tank_name', 'sg_short_name', 'sg_frame_rate',
            'sg_status', 'created_at')
        _jobs_data = self._read_data('Project', force=force, fields=_fields)
        assert _jobs_data

        _jobs = []
        for _result in _jobs_data:
            if not _result['tank_name']:
                continue
            _job_root = pipe.JOBS_ROOT.to_subdir(_result['tank_name'])
            _cfg = _job_root.to_file('.pini/config.yml')
            if not _cfg.exists():
                continue
            _result['path'] = _job_root.path
            _job = pipe.CPJob(_job_root)
            _job = sgc_job.SGCJob(_result, cache=self, job=_job)
            _jobs.append(_job)

        return sorted(_jobs)

    @pipe_cache_on_obj
    def _read_pub_types(self, force=False):
        """Build list of publish types.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCPubType list): steps
        """
        _fields = ('code', )
        _steps_data = self._read_data('PublishedFileType', fields=_fields)
        _steps = [sgc_container.SGCPubType(_data) for _data in _steps_data]
        return _steps

    @pipe_cache_on_obj
    def _read_steps(self, force=False):
        """Build list of pipeline steps.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCStep list): steps
        """
        _fields = (
            'entity_type', 'code', 'short_name', 'department', 'updated_at',
            'list_order')
        _steps_data = self._read_data('Step', fields=_fields)
        _steps = [sgc_container.SGCStep(_data) for _data in _steps_data]
        return _steps

    @pipe_cache_on_obj
    def _read_users(self, force=False):
        """Build list of users.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCUser list): users
        """
        _fields = ('name', 'email', 'login', 'sg_status_list', 'updated_at')
        _users_data = self._read_data('HumanUser', fields=_fields)
        _users = [sgc_container.SGCUser(_data) for _data in _users_data]
        return _users

    def __repr__(self):
        return basic_repr(self, None)


def _email_to_login(email):
    """Try to convert an email to a login.

    eg. billy.thekid@wildwest.com -> bthekid

    Args:
        email (str): email to convert

    Returns:
        (str): login
    """
    if '@' not in email:
        return None
    _name, _ = email.split('@', 1)
    return _name_to_login(_name.replace('.', ' '))


def _name_to_login(name):
    """Try to convert a name to a login.

    eg. "Billy the Kid" -> bthekid

    Args:
        name (str): name to convert

    Returns:
        (str): login
    """
    if ' ' not in name:
        return None
    _first, _last = name.split(' ', 1)
    return _first[0].lower() + _last.lower().replace(' ', '')
