import logging

from pini.utils import (
    basic_repr, strftime, cache_method_to_file, Dir)

from . import sgc_container

_LOGGER = logging.getLogger(__name__)


class _SGCEntity(sgc_container.SGCContainer):

    PROFILE = None

    _cache_fmt = None

    def __init__(self, data, proj, name, entity_type):
        assert self.PROFILE
        self.name = name
        self.entity_type = entity_type
        self.uid = f'{entity_type}.{name}'
        super().__init__(data=data, proj=proj)

    @property
    def cache_fmt(self):
        if not self._cache_fmt:
            from pini import pipe
            # _job = pipe.find_job(self.job.name)
            _job = self.proj.job
            _LOGGER.debug(' - JOB %s', _job)
            _tmpl = _job.find_template('entity_path', profile=self.PROFILE)
            _LOGGER.debug(' - TMPL %s', _tmpl)
            _root = Dir(_tmpl.format(
                job_path=_job.path, asset_type=self.entity_type,
                asset=self.name))
            _LOGGER.debug(' - ROOT %s', _root.path)
            _cfg_name = _job.cfg['name']
            _cache_dir = _root.to_subdir(
                f'.pini/SGC/P{pipe.VERSION}_{_cfg_name}')
            self._cache_fmt = _cache_dir.to_file('{func}.pkl').path
            _LOGGER.debug(' - CACHE FMT %s', self._cache_fmt)
        return self._cache_fmt

    @property
    def pub_files(self):
        return self.find_pub_files()

    @property
    def tasks(self):
        return self.find_tasks()

    def find_pub_files(self):
        return self._read_pub_files()

    def find_tasks(self):
        return self._read_tasks()

    def _read_pub_files(self):
        _LOGGER.info('READ PUB FILES %s', self)
        _last_t = self._read_data_last_t(sgc_container.SGCPubFile)

        if not _last_t:
            return []
        _LOGGER.info(' - LAST T %s', strftime('nice', _last_t))

        _last_t_c, _pub_files_c = self._obt_last_t_pub_files_cache()
        if _last_t_c != _last_t:
            _last_t_c, _pub_files_c = self._obt_last_t_pub_files_cache(
                force=True)
            assert _last_t_c == _last_t
        return _pub_files_c

    @cache_method_to_file
    def _obt_last_t_pub_files_cache(self, force=False):
        _LOGGER.info(' - BUILD PUB FILES DATA %s', self)
        _LOGGER.info(' - CACHE FMT %s', self.cache_fmt)
        _pub_files = self._read_data(sgc_container.SGCPubFile)
        import pprint
        pprint.pprint(_pub_files)
        asdasd
        assert _pub_files
        for _pub_file in _pub_files:
            _out = pipe.to_output(_pub_file.path, catch=True)
            _validated = bool(_out)
            _pub_file.validated = _validated
            # asdasd
            # return None, []
        _last_t = max(_pub_file.mtime for _pub_file in _pub_files)
        return _last_t, _pub_files

    def _read_tasks(self):
        _tasks = []
        for _item in self._read_data(sgc_container.SGCTask):
            _task = sgc_container.SGCTask(_item, entity=self)
            _tasks.append(_task)
        return _tasks

    def to_filter(self):
        return 'entity', 'is', self.to_entry()


class SGCAsset(_SGCEntity):
    """Represents an asset."""
    
    PROFILE = 'asset'
    ENTITY_TYPE = 'Asset'
    FIELDS = ('sg_asset_type', 'code', 'sg_status_list', 'updated_at')

    def __init__(self, data, proj):
        """Constructor.

        Args:
            data (dict): shotgrid data
            proj (SGCProj): parent proj
        """
        self.asset_type = data['sg_asset_type']
        # self.name = 
        # _path = f'{job.path}/assets/{self.asset_type}/{self.name}'
        # _LOGGER.info(' - PATH %s', _path)
        super().__init__(
            data, proj=proj, name=data['code'], entity_type=self.asset_type)

    

    def __repr__(self):
        return basic_repr(
            self, f'{self.proj.name}:{self.asset_type}.{self.name}')



class SGCShot(_SGCEntity):
    """Represents a shot."""

    PROFILE = 'shot'
    ENTITY_TYPE = 'Shot'
    FIELDS = (
        'sg_head_in', 'code', 'sg_sequence', 'sg_status_list',
        'updated_at', 'sg_has_3d')

    def __init__(self, data, proj):
        """Constructor.

        Args:
            data (dict): shotgrid data
            proj (SGCProj): parent proj
        """
        # _path = f'{proj.path}/episodes/        
        # self.name = 
        self.sg_sequence = data['sg_sequence']['name']
        super().__init__(
            data, proj=proj, name=data['code'], entity_type=self.sg_sequence)
        # self.has_3d = data['sg_has_3d']

    def __repr__(self):
        return basic_repr(
            self, f'{self.proj.name}:{self.name}')
