"""Tools for managing the base File object."""

import filecmp
import logging
import json
import os
import pickle
import shutil
import time

import yaml

from . import up_path, up_utils
from ..u_misc import single
from ..u_system import system

_LOGGER = logging.getLogger(__name__)
_DIFF_TOOL = None
_BKP_FMT = '.bkp/{base}_{tstr}_{user}'


class ReadDataError(RuntimeError):
    """Raised when a data archive (eg. pkl/yml) errors on read."""


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
        _path = f'{self.dir}/{self.base}.{extn}'
        return File(_path)

    def bkp(self, force=True, verbose=1):
        """Backup this file.

        Args:
            force (bool): overwrite existing without confirmation
            verbose (int): print process data

        Returns:
            (File): bkp file
        """
        _start = time.time()
        if not self.exists():
            _LOGGER.warning('UNABLE TO BACKUP MISSING FILE %s', self.path)
            return None

        # Check for unchanged
        _bkps = self.find_bkps()
        _LOGGER.debug(' - FOUND %d BKPS', len(_bkps))
        if _bkps:
            _latest = _bkps[-1]
            _LOGGER.debug(' - LATEST BKP %s', _latest)
            if self.matches(_latest):
                _LOGGER.warning('NO CHANGES SINCE LAST BKP %s', self.path)
                return _latest

        _bkp = self.to_bkp()
        self.copy_to(_bkp, force=force)
        if verbose:
            _LOGGER.info(
                'SAVED BKP %s (%.01fs)', _bkp.path, time.time() - _start)

        return _bkp

    def browser(self):
        """Open a browser in this file's parent directory."""
        self.to_dir().browser()

    def copy_to(self, trg, force=False, diff=False, verbose=1):
        """Copy this file.

        Args:
            trg (str): target location
            force (bool): overwrite existing without warning dialog
            diff (bool): show diffs
            verbose (int): print process data (required)
        """
        up_utils.error_on_file_system_disabled()
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
                    f'Replace existing file:\n\n{_trg.path}\n\nwith this '
                    f'one?\n\n{self.path}',
                    icon=icons.find('Spider'))
                if not _result:
                    return

        _trg.test_dir()
        shutil.copyfile(self.path, _trg.path)

    def delete(
            self, wording='delete', execute=True, icon=None, force=False,
            verbose=True):
        """Delete this file.

        Args:
            wording (str): override wording of warning dialog
            execute (bool): execute the deletion (this can be disabled
                if deletion will occur later but the warning is useful)
            icon (str): path to icon for confirmation dialog
            force (bool): delete without warning dialog
            verbose (int): print out contents of confirmation dialog
        """
        up_utils.error_on_file_system_disabled()
        if not self.exists():
            return
        if not force:
            from pini import qt, icons
            _icon = icon or icons.find('Sponge')
            qt.ok_cancel(
                title=f'Confirm {wording}',
                icon=_icon,
                msg=f'{wording.capitalize()} existing file?\n\n{self.path}',
                verbose=verbose)
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
        if not _other.exists():
            raise OSError('Missing file ' + _other.path)
        if self.matches(_other):
            raise RuntimeError("Files are identical")
        if check_extn and self.extn not in [
                'py', 'txt', None, 'yml', 'gizmo', 'mel', 'cs', 'env',
                'xml', 'bat', 'vbs', 'ma', 'md', 'ui', 'rc']:
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
            _arg += f':{line_n:d}'
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
        _tail = _tail.format(user=get_user())
        _LOGGER.debug(' - HEAD/TAIL %s %s', _head, _tail)
        _dir, _head = _head.rsplit('/', 1)
        _LOGGER.debug(' - DIR/BASE %s %s', _dir, _head)
        _dir = self.to_dir().to_subdir(_dir)
        _LOGGER.debug(' - DIR %s', _dir)

        _bkps = _dir.find(
            head=_head, tail=_tail, class_=True, type_='f', extn=self.extn,
            hidden=True, catch_missing=True, depth=1)
        _LOGGER.debug(' - FOUND %d BKPS', len(_bkps))
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

    def is_editable(self):
        """Test whether this file can be opened in a text editor.

        Returns:
            (bool): editable
        """
        return self.extn in ['py', 'ma', 'nk', 'txt', 'atom']

    def matches(self, other):
        """Test if this file matches another one.

        Args:
            other (str): path to other file

        Returns:
            (bool): whether files match
        """
        up_utils.error_on_file_system_disabled()
        _other = File(other)
        return filecmp.cmp(self.path, _other.path)

    def move_to(self, target, force=False):
        """Move this file to another location.

        Args:
            target (str): target location
            force (bool): overwrite existing target without confirmation
        """
        up_utils.error_on_file_system_disabled()
        _trg = File(target)
        _trg.delete(force=force, wording='replace')
        _trg.test_dir()
        shutil.move(self.path, _trg.path)

    def read(self, encoding='utf-8', catch=False):
        """Read contents of this file as text.

        Args:
            encoding (str): override default encoding (utf-8)
            catch (bool): no error if file missing

        Returns:
            (str): file contents
        """
        up_utils.error_on_file_system_disabled()

        if not self.exists():
            if catch:
                return None
            raise OSError('File does not exist ' + self.path)

        with open(self.path, 'r', encoding=encoding) as _hook:
            _body = _hook.read()

        return _body

    def read_json(self):
        """Read this file as json.

        Returns:
            (dict): json data
        """
        _body = self.read()
        return json.loads(_body)

    def read_lines(self, encoding='utf-8'):
        """Read lines of this file.

        Args:
            encoding (str): override default encoding (utf-8)

        Returns:
            (str list): text lines
        """
        return self.read(encoding=encoding).split('\n')

    def read_pkl(self, catch=False):
        """Read pickle file.

        Args:
            catch (bool): no error if fail to read (return empty dict)

        Returns:
            (any): pickled data
        """
        if not self.exists():
            if catch:
                return {}
            raise OSError('Missing file ' + self.path)

        try:
            with open(self.path, "rb") as _handle:
                _obj = pickle.load(_handle)
        except Exception as _exc:
            if catch:
                return {}
            _handle.close()
            raise ReadDataError(f'{_exc} {self.path}') from _exc
        _handle.close()
        return _obj

    def _read_size(self, catch=True):
        """Read size of this file.

        Args:
            catch (bool): no error on permissions fail

        Returns:
            (int): size in bytes
        """
        try:
            return os.path.getsize(self.path)
        except OSError as _exc:
            if catch:
                return 0
            raise _exc

    def read_yml(self, encoding=None, catch=False):
        """Read this file as yaml.

        Args:
            encoding (str): force encoding (eg. utf-8)
            catch (bool): no error on file missing or yaml parse fail

        Returns:
            (any): file contents
        """
        _LOGGER.debug('READ YAML: %s', yaml)

        # Read contents
        if not self.exists(catch=catch):
            if catch:
                return {}
            raise OSError('Missing file ' + self.path)
        try:
            _body = self.read(encoding=encoding)
        except IOError as _exc:
            if catch:
                return {}
            raise _exc
        assert isinstance(_body, str)

        # Parse contents
        try:
            return yaml.unsafe_load(_body)
        except Exception as _exc:
            _LOGGER.info('SCANNER ERROR: %s', _exc)
            _LOGGER.info(' - FILE: %s', self.path)
            _LOGGER.info(' - MESSAGE %s', str(_exc))
            if catch:
                return {}
            raise RuntimeError('Yaml scanner error ' + self.path) from _exc

    def to_bkp(self):
        """Obtain backup file for this file.

        Backups are stored in a hidden folder with a date and user
        stamp appended to the filename.

        Returns:
            (File): backup file
        """
        from pini.utils import get_user
        _base = _BKP_FMT.format(
            base=self.base,
            tstr=time.strftime('%y%m%d_%H%M%S'),
            user=get_user())
        return self.to_file(base=_base, extn=self.extn)

    def to_file(
            self, filename=None, dir_=None, base=None, extn=None,
            hidden=False, class_=None):
        """Build a file object with matching attributes to this one.

        Args:
            filename (str): update filename
            dir_ (str): update directory
            base (str): update filename base
            extn (str): update extension
            hidden (bool): make file hidden (add . prefix to filename)
            class_ (class): override file class

        Returns:
            (File): updated file object
        """
        _LOGGER.debug('TO FILE')
        from pini.utils import Dir
        _class = class_ or File
        if filename:
            assert not base and not extn
            _filename = filename
        else:
            assert not filename
            _extn = extn or self.extn
            _LOGGER.debug(' - EXTN %s %s', extn, _extn)
            _base = base or self.base
            if not _extn:
                _filename = _base
            else:
                _filename = f'{_base}.{_extn}'
        if hidden:
            _filename = '.' + _filename
        _LOGGER.debug(' - FILENAME %s', _filename)
        _path = f'{Dir(dir_ or self.dir).path}/{_filename}'
        _LOGGER.debug(' - PATH %s', _path)
        return _class(_path)

    def touch(self):
        """Touch this file.

        Create an empty file if it doesn't exist, otherwise just update
        the mtime.
        """
        up_utils.error_on_file_system_disabled()
        self.test_dir()
        self._pathlib.touch()

    def write(
            self, text, force=False, wording='Overwrite', encoding='utf-8',
            diff=False):
        """Write text to this file.

        Args:
            text (str): text to write
            force (bool): replace existing contents without warning
            wording (str): override warning dialog wording
            encoding (str): apply encoding (eg. utf-8)
            diff (bool): offer to show diffs before overwrite
        """
        up_utils.error_on_file_system_disabled()

        # Handle replace
        if self.exists():
            if force:
                pass
            elif diff:
                self._write_apply_diff(text, wording)
                return
            else:
                from pini import qt
                qt.ok_cancel(f'{wording} existing file?\n\n{self.path}')
            os.remove(self.path)

        # Write file
        self.test_dir()
        with open(self.path, 'w', encoding=encoding) as _file:
            _file.write(text)

    def _write_apply_diff(self, text, wording=None):
        """Apply write with diff option.

        Args:
            text (str): text to write
            wording (str): wording for diffs dialog
        """
        from pini import qt
        from pini.utils import TMP

        # Apply show diffs
        _force = False
        _prompt = wording or 'Update file'
        _result = qt.raise_dialog(
            f'{_prompt}?\n\n{self.path}', title='Confirm',
            buttons=('Yes', 'Show diffs', 'No'))
        if _result == 'Yes':
            _force = True
        elif _result == 'No':
            return
        elif _result == 'Show diffs':
            _tmp = TMP.to_file(f'.pini/{self.filename}')
            _tmp.write(text, force=True)
            _tmp.diff(self)

        # Apply updates
        if self.read() == text:
            _LOGGER.info('UPDATES APPLIED IN DIFF TOOL')
            return
        if not _force:
            _result = qt.yes_no_cancel(
                f'Update file?\n\n{self.path}', title='Confirm')
        self.write(text, force=True)

    def write_json(self, data):
        """Write the given data as json.

        Args:
            data (dict): data to write
        """
        assert self.extn == 'json'
        self.write(json.dumps(data))

    def write_pkl(self, data, catch=False, force=False):
        """Write data to pickle file.

        Args:
            data (any): data to pickle
            catch (bool): no error if fail to write
            force (bool): replace existing file without confirmation
        """
        up_utils.error_on_file_system_disabled()
        self.test_dir()
        assert self.extn == 'pkl'

        try:
            self.delete(force=force, wording='replace')
            with open(self.path, "wb") as _handle:
                pickle.dump(data, _handle, protocol=0)
        except OSError as _exc:
            if catch:
                return
            raise _exc

    def write_yml(
            self, data, force=False, mode='w', fix_unicode=False,
            wording='replace'):
        """Write yaml data to this file.

        Args:
            data (any): data to write
            force (bool): replace existing contents without warning
            mode (str): write mode (default is w)
            fix_unicode (bool): save unicode as str - need to execute in
                safe mode which prevents arbitrary objects from being saved
            wording (str): override warning dialog wording
        """
        up_utils.error_on_file_system_disabled()
        assert self.extn == 'yml'
        if mode != 'a':
            self.delete(force=force, wording=wording)
        self.to_dir().mkdir()
        with open(self.path, mode=mode, encoding='utf-8') as _hook:
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

    cache_file_extn = 'yml'
    cache_loc = 'adjacent'
    cache_namespace = None

    def __init__(self, file_, cache_loc=None):
        """Constructor.

        Args:
            file_ (str): path to file
            cache_loc (str): apply cache location (eg. home/tmp)
        """
        super().__init__(file_)
        if cache_loc:
            self.cache_loc = cache_loc

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
        assert isinstance(_val, (str, float, int, dict))
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
