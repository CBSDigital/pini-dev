"""Tools for managing the base File object."""

import codecs
import filecmp
import logging
import json
import os
import pickle
import shutil
import time

import six
import yaml

from . import up_path, up_utils
from ..u_misc import system, single

_LOGGER = logging.getLogger(__name__)
_DIFF_TOOL = None
_BKP_FMT = '.bkp/{base}_{tstr}_{user}.{extn}'


def _find_diff_exe():
    """Find diff tool executable.

    Returns:
        (str): path to diff tool
    """
    global _DIFF_TOOL
    if _DIFF_TOOL:
        return _DIFF_TOOL
    from pini.utils import find_exe
    for _name in ['Diffinity', 'meld']:
        _exe = find_exe(_name)
        if _exe:
            _DIFF_TOOL = _exe
            return _exe
    raise RuntimeError('No diff tool found')


class File(up_path.Path):  # pylint: disable=too-many-public-methods
    """Represents a file on disk."""

    def apply_extn(self, extn):
        """Swap out the extension of this file.

        Args:
            extn (str): extension to apply

        Returns:
            (File): updated file
        """
        _path = '{}/{}.{}'.format(self.dir, self.base, extn)
        return File(_path)

    def bkp(self):
        """Backup this file.

        Returns:
            (File): bkp file
        """
        if not self.exists():
            _LOGGER.warning('UNABLE TO BACKUP MISSING FILE %s', self.path)
            return None
        return self.copy_to(self.to_bkp())

    def browser(self):
        """Open a browser in this file's parent directory."""
        self.to_dir().browser()

    @up_utils.block_on_file_system_disabled
    def copy_to(self, trg, force=False, diff=False, verbose=1):
        """Copy this file.

        Args:
            trg (str): target location
            force (bool): overwrite existing without warning dialog
            diff (bool): show diffs
            verbose (int): print process data (required)
        """
        _LOGGER.debug('COPY TO %s', self)
        _LOGGER.debug(' - TARGET %s', trg)
        _trg = File(trg)
        if _trg.exists():
            _LOGGER.debug(' - TARGET EXISTS')
            if self.matches(_trg):
                if verbose:
                    _LOGGER.info('FILES MATCH')
                return
            if diff:
                self.diff(_trg)
                if self.matches(_trg):
                    _LOGGER.info('FILES MATCH')
                    return
            if not force:
                from pini import qt, icons
                _result = qt.yes_no_cancel(
                    'Replace existing file:\n\n{}\n\nwith this '
                    'one?\n\n{}'.format(_trg.path, self.path),
                    icon=icons.find('Spider'))
                if not _result:
                    return

        _trg.test_dir()
        shutil.copyfile(self.path, _trg.path)

    @up_utils.block_on_file_system_disabled
    def delete(self, wording='Delete', execute=True, icon=None, force=False):
        """Delete this file.

        Args:
            wording (str): override wording of warning dialog
            execute (bool): execute the deletion (this can be disabled
                if deletion will occur later but the warning is useful)
            icon (str): path to icon for confirmation dialog
            force (bool): delete without warning dialog
        """
        if not self.exists():
            return
        if not force:
            from pini import qt, icons
            _icon = icon or icons.find('Sponge')
            qt.ok_cancel(
                title='Confirm {}'.format(wording.capitalize()),
                icon=_icon, msg='{} existing file?\n\n{}'.format(
                    wording, self.path))
        if execute:
            os.remove(self.path)

    def diff(self, other, check_extn=True):
        """Show diffs between this and another file.

        Args:
            other (str): file to compare with
            check_extn (bool): check file extension is approved
        """
        _other = File(other)

        # Safety checks (avoid comparing binary)
        assert self.exists()
        assert _other.exists()
        if self.matches(_other):
            raise RuntimeError("Files are identical")
        if check_extn and self.extn not in [
                'py', 'txt', None, 'yml', 'gizmo', 'mel', 'cs', 'env',
                'xml', 'bat', 'vbs', 'ma', 'md']:
            raise ValueError(self.extn)

        # Execute diff
        _cmds = [_find_diff_exe(), self.path, _other.path]
        system(_cmds)

    def edit(self, line_n=None, verbose=0):
        """Edit this file in text editor.

        Args:
            line_n (int): line number to open file at
            verbose (int): print process data
        """

        _subl = os.environ.get('SUBL_EXE')
        if _subl:
            assert File(_subl).exists()
        _subl = _subl or 'subl'
        _arg = self.path
        if line_n is not None:
            _arg += ':{:d}'.format(line_n)
        _LOGGER.debug('EXE %s', _subl)
        _cmds = [_subl, _arg]
        system(_cmds, verbose=verbose, result=False)

    def find_bkps(self):
        """Find backups of this file.

        Returns:
            (File list): backup files
        """
        from pini.utils import get_user
        _LOGGER.debug('FIND BKPS %s', self.path)

        # Read bkp format
        _head, _tail = _BKP_FMT.split('{tstr}')
        _head = _head.format(base=self.base)
        _tail = _tail.format(extn=self.extn, user=get_user())
        _LOGGER.debug(' - HEAD/TAIL %s %s', _head, _tail)
        _dir, _head = _head.rsplit('/', 1)
        _LOGGER.debug(' - DIR/BASE %s %s', _dir, _head)
        _dir = self.to_dir().to_subdir(_dir)
        _LOGGER.debug(' - DIR %s', _dir)

        _bkps = _dir.find(head=_head, tail=_tail, class_=True, type_='f')
        return _bkps

    def find_and_replace_text(self, find, replace, force=False, diff=False):
        """Find and replace the body of this file.

        Args:
            find (str): string to find
            replace (str): string to replace
            force (bool): overwrite without confirmation
            diff (bool): show diffs
        """
        _body = self.read().replace(find, replace)
        if diff:
            _tmp = self.to_file(dir_=up_utils.TMP_PATH)
            _tmp.write(_body, force=True)
            _tmp.diff(self)
            if self.read() == _body:
                return
        self.write(_body, force=force, wording='Update')

    def flush_bkps(self, count=10, force=False):
        """Flush old backup files.

        Args:
            count (int): how many backups to leave.
            force (bool): remove old backups without confirmation
        """
        from pini import qt
        _bkps = self.find_bkps()
        _to_flush = _bkps[:-count]
        if not _to_flush:
            _LOGGER.info('NO BKPS TO FLUSH')
            return
        if not force:
            qt.ok_cancel(
                'Remove {:d} old backup files?\n\n{}'.format(
                    len(_to_flush), '\n'.join(_bkp.path for _bkp in _to_flush)))
        for _bkp in _to_flush:
            _bkp.delete(force=True)

    @up_utils.block_on_file_system_disabled
    def matches(self, other):
        """Test if this file matches another one.

        Args:
            other (str): path to other file

        Returns:
            (bool): whether files match
        """
        _other = File(other)
        return filecmp.cmp(self.path, _other.path)

    @up_utils.block_on_file_system_disabled
    def move_to(self, target, force=False):
        """Move this file to another location.

        Args:
            target (str): target location
            force (bool): overwrite existing target without confirmation
        """
        _trg = File(target)
        _trg.delete(force=force, wording='Replace')
        _trg.test_dir()
        shutil.move(self.path, _trg.path)

    @up_utils.block_on_file_system_disabled
    def read(self, encoding=None, catch=False):
        """Read contents of this file as text.

        Args:
            encoding (str): force encoding (eg. utf8)
            catch (bool): no error if file missing

        Returns:
            (str): file contents
        """

        if not self.exists():
            if catch:
                return None
            raise OSError('File does not exist '+self.path)

        if not encoding:
            with open(self.path, 'r') as _hook:
                _body = _hook.read()
        else:
            with codecs.open(self.path, encoding=encoding) as _hook:
                _body = _hook.read()

        return _body

    def read_json(self):
        """Read this file as json.

        Returns:
            (dict): json data
        """
        _body = self.read()
        return json.loads(_body)

    def read_lines(self):
        """Read lines of this file.

        Returns:
            (str list): text lines
        """
        return self.read().split('\n')

    def read_pkl(self):
        """Read pickle file.

        Returns:
            (any): pickled data
        """
        _handle = open(self.path, "rb")
        _obj = pickle.load(_handle)
        _handle.close()
        return _obj

    def _read_size(self):
        """Read size of this file.

        Returns:
            (int): size in bytes
        """
        return os.path.getsize(self.path)

    def read_yml(self, encoding=None, catch=False):
        """Read this file as yaml.

        Args:
            encoding (str): force encoding (eg. utf8)
            catch (bool): no error on file missing or yaml parse fail

        Returns:
            (any): file contents
        """
        _LOGGER.debug('READ YAML: %s', yaml)

        # Read contents
        if not self.exists(catch=catch):
            if catch:
                return {}
            raise OSError('Missing file '+self.path)
        try:
            _body = self.read(encoding=encoding)
        except IOError as _exc:
            if catch:
                return {}
            raise _exc
        assert isinstance(_body, six.string_types)

        # Parse contents
        try:
            return yaml.unsafe_load(_body)
        except Exception as _exc:
            _LOGGER.info('SCANNER ERROR: %s', _exc)
            _LOGGER.info(' - FILE: %s', self.path)
            _LOGGER.info(' - MESSAGE %s', str(_exc))
            raise RuntimeError('Yaml scanner error '+self.path)

    def to_bkp(self):
        """Obtain backup file for this file.

        Backups are stored in a hidden folder with a date and user
        stamp appended to the filename.

        Returns:
            (File): backup file
        """
        from pini.utils import get_user
        return self.to_file(_BKP_FMT.format(
            base=self.base,
            tstr=time.strftime('%y%m%d_%H%M%S'),
            user=get_user(),
            extn=self.extn))

    def to_file(self, filename=None, dir_=None, base=None, extn=None,
                hidden=False):
        """Build a file object with matching attributes to this one.

        Args:
            filename (str): update filename
            dir_ (str): update directory
            base (str): update filename base
            extn (str): update extension
            hidden (bool): make file hidden (add . prefix to filename)

        Returns:
            (File): updated file object
        """
        _LOGGER.debug('TO FILE')
        from pini.utils import Dir
        if filename:
            assert not base and not extn
            _filename = filename
        else:
            assert not filename
            _filename = '{}.{}'.format(
                base or self.base,
                extn or self.extn)
        if hidden:
            _filename = '.'+_filename
        _LOGGER.debug(' - FILENAME %s', _filename)
        _path = '{}/{}'.format(Dir(dir_ or self.dir).path, _filename)
        _LOGGER.debug(' - PATH %s', _path)
        return File(_path)

    @up_utils.block_on_file_system_disabled
    def touch(self):
        """Touch this file.

        Create an empty file if it doesn't exist, otherwise just update
        the mtime.
        """
        self.test_dir()
        self._pathlib.touch()

    @up_utils.block_on_file_system_disabled
    def write(self, text, force=False, wording='Overwrite', encoding=None):
        """Write text to this file.

        Args:
            text (str): text to write
            force (bool): replace existing contents without warning
            wording (str): override warning dialog wording
            encoding (str): apply encoding (eg. utf-8)
        """

        # Handle replace
        if self.exists():
            if not force:
                from pini import qt
                qt.ok_cancel('{} existing file?\n\n{}'.format(
                    wording, self.path))
            os.remove(self.path)

        # Write file
        _kwargs = {}
        if encoding:
            _kwargs['encoding'] = encoding
        self.test_dir()
        with open(self.path, 'w', **_kwargs) as _file:
            _file.write(text)

    def write_json(self, data):
        """Write the given data as json.

        Args:
            data (dict): data to write
        """
        assert self.extn == 'json'
        self.write(json.dumps(data))

    @up_utils.block_on_file_system_disabled
    def write_pkl(self, data, force=False):
        """Write data to pickle file.

        Args:
            data (any): data to pickle
            force (bool): replace existing file without confirmation
        """
        self.test_dir()
        assert self.extn == 'pkl'
        self.delete(force=force)
        _handle = open(self.path, "wb")
        pickle.dump(data, _handle, protocol=0)
        _handle.close()

    @up_utils.block_on_file_system_disabled
    def write_yml(
            self, data, force=False, mode='w', fix_unicode=False,
            wording='Replace'):
        """Write yaml data to this file.

        Args:
            data (any): data to write
            force (bool): replace existing contents without warning
            mode (str): write mode (default is w)
            fix_unicode (bool): save unicode as str - need to execute in
                safe mode which prevents arbitrary objects from being saved
            wording (str): override warning dialog wording
        """
        assert self.extn == 'yml'
        if mode != 'a':
            self.delete(force=force, wording=wording)
        self.to_dir().mkdir()
        with open(self.path, mode=mode) as _hook:
            if not fix_unicode:
                yaml.dump(data, _hook, default_flow_style=False)
            else:
                yaml.safe_dump(data, _hook, encoding='utf-8',
                               allow_unicode=True)
        _LOGGER.debug("WROTE YAML %s %s", self.nice_size(), self.path)


class MetadataFile(File):
    """File object with build in caching functionality.

    Data is cached to .pini subdirectory in the same directory as
    the file itself.
    """

    @property
    def cache_fmt(self):
        """Obtain cache format path.

        Returns:
            (str): cache format
        """
        return '{}/.pini/{}_{{func}}.yml'.format(self.dir, self.base)

    @property
    def metadata(self):
        """Obtain metadata for this file.

        Returns:
            (dict): metadata
        """
        return self._read_metadata()

    @property
    def metadata_yml(self):
        """Obtain path to metadata yml file.

        Returns:
            (File): metadata yml
        """
        return File(self.cache_fmt.format(func='metadata'))

    def add_metadata(self, **kwargs):
        """Add to this file's metadata.

        Args:
            <key> (any): <value> - metadata key/value to apply
            force (bool): overwrite existing metadata without confirmation
        """
        _LOGGER.debug("ADD METADATA %s", kwargs)
        _force = kwargs.pop('force', False)
        _kwarg = single(list(kwargs.items()))
        _key, _val = _kwarg
        _LOGGER.debug(' - KEY/VAL %s %s', _key, _val)
        assert isinstance(_val, (six.string_types, float, int, dict))
        _data = self._read_metadata()
        if _data.get(_key) == _val:
            _LOGGER.debug(' - VAL ALREADY SET')
            return
        _data[_key] = _val
        self.set_metadata(_data, force=_force)

    def _read_metadata(self):
        """Read this file's metadata from disk.

        Returns:
            (dict): metadata
        """
        return self.metadata_yml.read_yml(catch=True)

    def set_metadata(self, data, force=False):
        """Set this file's metadata, replacing any existing metadata.

        Args:
            data (dict): metadata to apply
            force (bool): overwrite existing metadata without confirmation
        """
        self.metadata_yml.write_yml(data, force=force)
