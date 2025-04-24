"""Tools for managing the base container class for the shotgrid cache.

This manages global shotgrid requests, eg. jobs, steps, users.
"""

# pylint: disable=too-many-public-methods

import logging
import operator

from pini import pipe
from pini.utils import (
    single, basic_repr, apply_filter, get_user, passes_filter)

from ...cache import pipe_cache_on_obj
from . import sgc_proj, sgc_elems, sgc_elem_reader

_LOGGER = logging.getLogger(__name__)
_GLOBAL_CACHE_DIR = pipe.GLOBAL_CACHE_ROOT.to_subdir('sgc')


class SGCRoot(sgc_elem_reader.SGCElemReader):
    """Base container class for the shotgrid data cache."""

    @property
    def projs(self):
        """Obtain list of valid projs.

        Returns:
            (SGCProj list): projs
        """
        return self._read_projs()

    @property
    def steps(self):
        """Obtain list of steps.

        Returns:
            (SGCStep list): steps
        """
        return self._read_steps()

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
        _LOGGER.debug('FIND ASSET %s', match)
        _job = pipe.to_job(match)
        _proj_s = self.find_proj(_job)
        _LOGGER.debug(' - JOB %s %s', _job, _proj_s)
        return _proj_s.find_asset(match)

    def find_assets(self, job):
        """Search assets in the cache.

        Args:
            job (CPJob): job to search

        Returns:
            (SGCAsset list): assets
        """
        return self.find_proj(job).find_assets()

    def find_entity(self, match=None):
        """Find an entity within the cache.

        Args:
            match (str|CPEntity): entity or path to match

        Returns:
            (SGCAsset|SGCShot): matching entity
        """
        _ety = pipe.to_entity(match) if match else pipe.cur_entity()
        _sg_proj = self.find_proj(_ety.job)
        return _sg_proj.find_entity(_ety)

    def find_proj(self, match=None, catch=False, force=False):
        """Find a job.

        Args:
            match (str|int): job name/prefix/id
            catch (bool): no error if fail to match project
            force (bool): force rebuild cache

        Returns:
            (SGCProj): matching job
        """
        _match = match or pipe.cur_job()

        _match_projs = [
            _job for _job in self.find_projs(force=force)
            if _match in (_job.name, _job.id_, _job.prefix, _job.job)]
        if len(_match_projs) == 1:
            return single(_match_projs)

        _filter_projs = apply_filter(
            self.projs, str(_match), key=operator.attrgetter('name'))
        if len(_filter_projs) == 1:
            return single(_filter_projs)

        if catch:
            return None
        raise ValueError(match)

    def find_projs(self, filter_=None, force=False):
        """Search for valid projs.

        Args:
            filter_ (str): apply proj name filter
            force (bool): force rebuild cache

        Returns:
            (SGCProj list): projs
        """
        _projs = []
        for _proj in self._read_projs(force=force):
            if filter_ and not passes_filter(_proj.name, filter_):
                continue
            _projs.append(_proj)
        return _projs

    def find_pub_file(self, match, job=None, catch=False):
        """Find a pub file in the cache.

        Args:
            match (str|File): match by path/file
            job (CPJob): job to search
            catch (bool): no error if fail to find matching pub file

        Returns:
            (SGCPubFile): matching pub file
        """
        assert not job
        _ety = pipe.to_entity(match)
        _sg_ety = self.find_entity(_ety)
        return _sg_ety.find_pub_file(match, catch=catch)

    def find_pub_files(
            self, entity=None, work_dir=None, force=False, **kwargs):
        """Search pub files in the cache.

        Args:
            entity (CPEntity): filter by entity
            work_dir (CPWorkDir): filter by work dir
            force (bool): force rebuild cache

        Returns:
            (SGCPubFile list): pub files
        """
        _entity = None
        if entity:
            _entity = entity
        if _entity and work_dir:
            _entity = work_dir.entity
        assert _entity
        _sgc_ety = self.find_entity(_entity)
        return _sgc_ety.find_pub_files(
            work_dir=work_dir, force=force, **kwargs)

    def find_pub_type(self, match, type_='File', force=False):
        """Find published file type.

        Args:
            match (str): token to match
            type_ (str): path type (File/Sequence)
            force (bool): force rebuild cache

        Returns:
            (SGCPubType): published file type
        """
        _types = self.find_pub_types(force=force)
        _match_s = str(match)

        # Try simple field match
        _matches = [
            _type for _type in _types
            if match in (_type.code, _type.id_)]
        if len(_matches) == 1:
            return single(_matches)

        # Try using type suffix
        _file_matches = [
            _type for _type in _types
            if _type.code == f'{_match_s.capitalize()} {type_}']
        if len(_file_matches) == 1:
            return single(_file_matches)

        # Try using mapping
        _map = {
            'hip': 'Houdini Scene',
            'mp4': 'Movie',
            'mov': 'Movie',
            'rs': 'Redshift Proxy',
            'exr': 'Exr File',
            'gz': 'Ass Proxy',
            'vdb': 'VDB File',
        }
        _map_matches = [
            _type for _type in _types
            if _type.code == _map.get(match)]
        if len(_map_matches) == 1:
            return single(_map_matches)

        if type_ == 'Sequence':
            return self.find_pub_type('Image Sequence')

        raise ValueError(match)

    def find_pub_types(self, force=False):
        """Find published file types.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCPubType list): published file types
        """
        return self._read_pub_types(force=force)

    def find_shot(self, match, job=None):
        """Find a shot in the cache.

        Args:
            match (str): shot name/path
            job (CPJob): job to search

        Returns:
            (SGCShot): matching shot
        """
        _LOGGER.debug('FIND SHOT %s', match)
        _job = job or pipe.to_job(match)
        _sgc_proj = self.find_proj(_job)
        _LOGGER.debug(' - JOB %s %s', _job, _sgc_proj)
        return _sgc_proj.find_shot(match)

    def find_shots(self, job):
        """Search the cache for shots.

        Args:
            job (CPJob): job to search

        Returns:
            (SGCShot list): matching shots
        """
        return self.find_proj(job).find_shots()

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

    def find_user(self, match=None, catch=True, force=False):
        """Find a user entry.

        Args:
            match (str): username/login/email
            catch (bool): no error if no entry found
            force (bool): force reread from shotgrid

        Returns:
            (SGCUser): user entry
        """
        _match = match or get_user()
        _LOGGER.debug('FIND USER %s', _match)

        _users = self.find_users(force=force)
        _users = [_user for _user in _users if _user.status != 'dis']

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

    def find_users(self, force=False):
        """Find users.

        Args:
            force (bool): force reread from shotgrid

        Returns:
            (SGCUser list): user entries
        """
        return self._read_users(force=force)

    def find_ver(self, match):
        """Find a version.

        Args:
            match (str): match by name/path
        """
        if isinstance(match, pipe.CPOutputBase):
            _ety_s = match.entity.sg_entity
        elif isinstance(match, str):
            _out = pipe.CACHE.obt_output(match)
            _ety_s = _out.entity.sg_entity
        else:
            raise NotImplementedError(match)
        return _ety_s.find_ver(match)

    @pipe_cache_on_obj
    def _read_projs(self, force=False):
        """Build list of valid projs on shotgrid.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCProj list): projs
        """
        _LOGGER.debug(' - READING PROJECTS')
        _projs = self._read_elems(sgc_proj.SGCProj, force=force)
        _LOGGER.debug('   - FOUND %d PROJS', len(_projs))
        assert _projs

        # Filter dup projects + embed job object
        _projs_map = {}
        for _proj in sorted(_projs, key=operator.attrgetter('id_')):
            _LOGGER.debug('PROJECT %d %s', _proj.id_, _proj)
            _job_path = pipe.ROOT.to_subdir(_proj.name)
            _cfg = _job_path.to_file('.pini/config.yml')
            if not _cfg.exists():
                _LOGGER.debug(' - REJECT NO CFG %s', _proj)
                continue
            _proj.job = pipe.CPJob(_job_path)
            _projs_map[_proj.name] = _proj

        return sorted(_projs_map.values())

    @pipe_cache_on_obj
    def _read_pub_types(self, force=False):
        """Build list of publish types.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCPubType list): steps
        """
        return self._read_elems(sgc_elems.SGCPubType)

    @pipe_cache_on_obj
    def _read_steps(self, force=False):
        """Build list of pipeline steps.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCStep list): steps
        """
        return self._read_elems(sgc_elems.SGCStep, force=force)

    @pipe_cache_on_obj
    def _read_users(self, force=False):
        """Build list of users.

        Args:
            force (bool): force rebuild cache

        Returns:
            (SGCUser list): users
        """
        return self._read_elems(sgc_elems.SGCUser)

    def to_filter(self):
        """Build shotgrid search filter from this entry.

        Returns:
            (None): not applicable
        """
        return None

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


SGC = SGCRoot()
