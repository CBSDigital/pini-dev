"""Tools for managing the metadata file object."""

import logging

from . import up_file
from .. import u_misc

_LOGGER = logging.getLogger(__name__)


class MetadataFile(up_file.File):
    """File object with build in caching functionality.

    Data is cached to .pini subdirectory in the same directory as
    the file itself.
    """

    cache_file_extn = 'yml'
    cache_loc = 'adjacent'
    cache_namespace = None

    def __init__(self, file_, cache_loc=None, cache_file_extn=None):
        """Constructor.

        Args:
            file_ (str): path to file
            cache_loc (str): apply cache location (eg. home/tmp)
            cache_file_extn (str): apply cache file extn (eg. yml/pkl)
        """
        super().__init__(file_)
        if cache_loc:
            self.cache_loc = cache_loc
        if cache_file_extn:
            self.cache_file_extn = cache_file_extn

    @property
    def cache_fmt(self):
        """Obtain cache format path.

        Returns:
            (str): cache format
        """
        _filename = f'{self.base}_{{func}}.{self.cache_file_extn}'

        if self.cache_loc == 'adjacent':
            _ns_dir = f'{self.cache_namespace}/' if self.cache_namespace else ''
            return f'{self.dir}/.pini/{_ns_dir}{_filename}'

        if self.cache_loc == 'home':
            from pini.utils import HOME
            _root = HOME
        elif self.cache_loc == 'tmp':
            from pini.utils import TMP
            _root = TMP
        else:
            raise NotImplementedError(self.cache_loc)

        assert self.path[1] == ':'
        assert self.path[2] == '/'
        _drive = self.path[0]
        _dir = _root.to_subdir('.pini/cache')
        if self.cache_namespace:
            _dir = _dir.to_subdir(self.cache_namespace)
        return _dir.to_file(
            f'{_drive}/{self.dir[3:]}/{_filename}').path

    @property
    def metadata(self):
        """Obtain metadata for this file.

        Returns:
            (dict): metadata
        """
        return self._read_metadata()

    @property
    def metadata_file(self):
        """Obtain path to metadata yml file.

        Returns:
            (File): metadata yml
        """
        return up_file.File(self.cache_fmt.format(func='metadata'))

    @property
    def metadata_yml(self):
        """Obtain path to metadata yml file.

        Returns:
            (File): metadata yml
        """
        from pini.tools import release
        release.apply_deprecation('25/04/25', 'Use MetadataFile.metadata_file')
        assert self.cache_file_extn == 'yml'
        return up_file.File(self.cache_fmt.format(func='metadata'))

    def add_metadata(self, parent=None, bkp=False, force=False, **kwargs):
        """Add to this file's metadata.

        USAGE: file.add_metadata(key=value)
            use a single kwarg to apply the given metadata value

        Args:
            parent (QDialog): parent dialog for prompt
            bkp (bool): backup metadata file on update
            force (bool): overwrite existing metadata without confirmation
        """
        _LOGGER.debug("ADD METADATA %s", kwargs)
        _kwarg = u_misc.single(list(kwargs.items()))
        _key, _val = _kwarg
        _LOGGER.debug(' - KEY/VAL %s %s', _key, _val)
        if not isinstance(_val, (str, float, int, dict, list, tuple)):
            raise TypeError(_val, type(_val))
        _data = self._read_metadata()

        _cur_val = _data.get(_key)
        if _cur_val == _val:
            _LOGGER.debug(' - VAL ALREADY SET')
            return
        if not force and _key in _data:
            from pini import qt
            qt.ok_cancel(
                f'Update "{_key}" metadata value from '
                f'"{_cur_val}" to  "{_val}"?\n\n'
                f'{self.path}', parent=parent)
        _data[_key] = _val
        self.set_metadata(_data, bkp=bkp, force=True)

    def get_metadata(self, key):
        """Obtain item from metadata.

        Args:
            key (str): metadata dict key

        Returns:
            (any): stored metadata
        """
        return self.metadata.get(key)

    def _read_metadata(self):
        """Read this file's metadata from disk.

        Returns:
            (dict): metadata
        """
        if self.cache_file_extn == 'yml':
            _data = self.metadata_file.read_yml(catch=True)
        elif self.cache_file_extn == 'pkl':
            _data = self.metadata_file.read_pkl(catch=True)
        else:
            raise NotImplementedError(self.cache_file_extn)
        if not isinstance(_data, dict):
            from pini import qt, icons
            qt.ok_cancel(
                f'Remove bad metadata file?\n\n{self.metadata_file}',
                icon=icons.CLEAN)
            self.metadata_file.delete(force=True)
            _data = {}
        return _data

    def set_metadata(self, data, bkp=False, force=False):
        """Set this file's metadata, replacing any existing metadata.

        Args:
            data (dict): metadata to apply
            bkp (bool): backup metadata file on update
            force (bool): overwrite existing metadata without confirmation
        """
        assert isinstance(data, dict)
        if bkp:
            self.metadata_file.bkp()
        if self.cache_file_extn == 'yml':
            self.metadata_file.write_yml(data, force=force)
        elif self.cache_file_extn == 'pkl':
            self.metadata_file.write_pkl(data, force=force)
        else:
            raise NotImplementedError(self.cache_file_extn)
