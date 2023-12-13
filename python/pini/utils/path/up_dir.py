"""Tools for managing the base directory object."""

import logging
import os
import platform
import shutil

from . import up_path, up_utils

_LOGGER = logging.getLogger(__name__)


class Dir(up_path.Path):
    """Represents a directory on disk."""

    def browser(self):
        """Open this dir in a file browser."""
        _LOGGER.debug('BROWSER %s', self.path)
        if platform.system() == 'Windows':
            self._browser_win()
        elif platform.system() == "Linux":
            self._browser_linux()
        else:
            raise ValueError(platform.system())

    @up_utils.restore_cwd
    def _browser_win(self):
        """Open windows explorer in this directory."""
        from pini.utils import system

        # Apply path mapping
        _path = self.path
        _env = os.environ.get('PINI_PATH_WIN_BROWSER_MAP')
        if _env:
            _LOGGER.debug('ENV %s', _env)
            _maps = [_item.split('>>>') for _item in _env.split(';')]
            _LOGGER.debug('MAPS %s', _maps)
            for _find, _replace in _maps:
                _LOGGER.debug('MAP %s -> %s', _find, _replace)
                _path = _path.replace(_find, _replace)

        # Launch explorer
        os.chdir(_path)
        system('explorer .')

    def _browser_linux(self):
        """Open linux file browser in this directory."""
        from pini.utils import find_exe
        if find_exe('dolphin'):
            _exe = 'dolphin'
        elif find_exe('caja'):
            _exe = 'caja'
        else:
            raise RuntimeError('No file browser app found')
        os.system('{} "{}" &'.format(_exe, self.path))

    def contains(self, path):
        """Test whether this dir contains the given path.

        Args:
            path (str): path to test

        Returns:
            (bool): whether this dir is a parent of the given path
        """
        _path = up_utils.abs_path(path)
        return _path.startswith(self.path)

    def copy_to(self, trg, force=False):
        """Copy this dir and its contents to another location.

        Args:
            trg (str): path to new location
            force (bool): replace existing without confirmation
        """
        assert self.exists()
        assert self.is_dir()
        _target = Dir(trg)
        _target.delete(force=force)
        shutil.copytree(self.path, _target.path)

    def delete(self, wording='Delete', force=False):
        """Delete this directory and its contents.

        Args:
            wording (str): override wording of warning dialog
            force (bool): delete contents without warning dialog
        """
        if not self.exists():
            return
        if not force:
            from pini import qt, icons
            _icon = icons.find('Sponge')
            qt.ok_cancel(
                msg='{} directory and contents?\n\n{}'.format(
                    wording, self.path),
                icon=_icon)
        shutil.rmtree(self.path)

    def find(self, class_=False, **kwargs):
        """Search for files in this directory.

        Args:
            class_ (class|bool): apply class to results

        Returns:
            (str list): list of children
        """
        return up_utils.find(self.path, class_=class_, **kwargs)

    def find_seqs(self, depth=1, include_files=False):
        """Find file sequences within this dir.

        Args:
            depth (int): search depth
            include_files (bool): include files which are not
                part of any sequence

        Returns:
            (Seq list): file sequences
        """
        from pini.utils import find_seqs
        return find_seqs(self, depth=depth, include_files=include_files)

    def flush(self, force=False):
        """Flush the contents of this dir.

        Should leave an empty dir which exists.

        Args:
            force (bool): remove contents without confirmation
        """
        self.delete(force=force)
        if not self.exists():
            self.mkdir()

    @up_utils.block_on_file_system_disabled
    def move_to(self, target, force=False):
        """Move this dir to a different location.

        Args:
            target (str): target location
            force (bool): move without confirmation
        """
        if not force:
            raise NotImplementedError
        _trg = Dir(target)
        _trg.delete(force=force, wording='Replace')
        _trg.test_dir()
        shutil.move(self.path, _trg.path)

    def rel_path(self, path, allow_outside=False):
        """Get relative path of the given path from this dir.

        Args:
            path (str): path to read
            allow_outside (bool): allow for paths outside this
                dir (eg. "../../blah.txt")

        Returns:
            (str): relative path

        Raises:
            (ValueError): if path provide is not inside this dir
        """
        _LOGGER.debug('REL PATH %s', path)
        _LOGGER.debug(' - ROOT %s', self.path)
        _path = up_utils.norm_path(path)

        _outside = not _path.startswith(self.path)
        if _outside and not allow_outside:
            raise ValueError('Not in {} dir - {}'.format(
                self.path, _path))

        # Calculate relative path within this dir
        if not _outside:
            if self.path.endswith('/'):  # eg. C:/
                _depth = len(self.path)
            else:
                _depth = len(self.path)+1
            return _path[_depth:]

        # Calculate relative path outside this dir
        _t_tokens = self.path.split('/')
        _LOGGER.debug(' - T TOKENS %s', _t_tokens)
        _o_tokens = _path.split('/')
        _LOGGER.debug(' - O TOKENS %s', _o_tokens)
        _s_tokens = []
        for _t_folder, _o_folder in zip(_t_tokens, _o_tokens):
            if _t_folder != _o_folder:
                break
            _s_tokens.append(_t_folder)
        _LOGGER.debug(' - S TOKENS %s', _s_tokens)
        _shared = Dir('/'.join(_s_tokens))
        _LOGGER.debug(' - SHARED %s', _shared)
        _to_this = _shared.rel_path(self)
        _LOGGER.debug(' - TO THIS %s', _to_this)
        _to_other = _shared.rel_path(_path)
        _LOGGER.debug(' - TO OTHER %s', _to_other)
        return '{}{}'.format('../' * (_to_this.count('/')+1), _to_other)

    def _read_size(self):
        """Read size of this directory.

        This seems to require each file size to be read individually - the
        os.path.getsize funtion doesn't seem to work for dirs.

        Returns:
            (int): size in bytes
        """
        from pini.utils import check_heart
        _size = 0
        for _file in self.find(type_='f', hidden=True, class_=True):
            check_heart()
            _size += _file.size()
        return _size

    def rename(self, name):
        """Rename this directory (keeping it in the same parent directory).

        Args:
            name (str): new name
        """
        _new_path = self.to_dir().to_subdir(name)
        shutil.move(self.path, _new_path.path)

    def sync_to(self, target, filter_=None, force=False):
        """Sync this directory to a different location.

        This will check for files which need to be added, removed or
        overwritten, and then show a summary in a confirmation dialog.

        Args:
            target (Dir): where to sync to
            filter_ (str): apply path filter
            force (bool): force sync without confirmation
        """
        from pini import qt

        _trg_dir = Dir(target)
        if not _trg_dir.exists():
            self.copy_to(_trg_dir)
            return

        _src_paths = self.find(
            full_path=False, type_='f', class_=True, filter_=filter_)
        _trg_paths = _trg_dir.find(
            full_path=False, type_='f', class_=True, filter_=filter_)
        _rel_paths = sorted(set(_src_paths+_trg_paths))

        _to_remove = []
        _to_sync = []

        for _file in _rel_paths:
            _LOGGER.debug('FILE %s', _file)
            _src = self.to_file(_file.path)
            _trg = _trg_dir.to_file(_file.path)
            _LOGGER.debug(' - SRC %s', _src)
            _LOGGER.debug(' - TRG %s', _trg)

            if _file not in _src_paths:
                _LOGGER.info(' - TO REMOVE %s', _trg.path)
                _to_remove.append(_file)
                continue
            if _file not in _trg_paths:
                _LOGGER.debug(' - TO ADD')
                _to_sync.append((_src, _trg))
                continue

            assert _file in _src_paths and _file in _trg_paths

            if _src.matches(_trg):
                _LOGGER.debug(' - IGNORE MATCHING FILE')
                continue

            _LOGGER.info(' - TO SYNC %s', _trg.path)
            _to_sync.append((_src, _trg))

        if not (_to_remove or _to_sync):
            _LOGGER.debug('NOTHING TO SYNC')
            return

        # Confirm
        if not force:
            _msg = 'Confirm execute sync?\n\n'
            if _to_sync:
                _msg += ' - {:d} files to sync'.format(len(_to_sync))
            if _to_remove:
                _msg += ' - {:d} files to remove'.format(len(_to_remove))
            qt.ok_cancel(_msg, title='Execute Sync')

        # Execute sync
        for _src, _trg in qt.progress_bar(_to_sync, 'Syncing {:d} file{}'):
            _src.copy_to(_trg, force=True)
        for _file in qt.progress_bar(_to_remove, 'Removing {:d} file'):
            assert _trg_dir.contains(_file)
            assert not self.contains(_file)
            _file.remove(force=True)

    def to_file(self, rel_path, class_=None):
        """Build a child of this directory as a file object.

        Args:
            rel_path (str): relative path to file from this dir
            class_ (class): override file class

        Returns:
            (File): child file
        """
        from pini.utils import File
        _class = class_ or File
        _rel_path = up_path.Path(rel_path)
        return _class(self.path+'/'+_rel_path.path)

    def to_seq(self, rel_path):
        """Build a child sequence object for this directory.

        Args:
            rel_path (str): relative path to sequence from this dir

        Returns:
            (Seq): child sequence
        """
        from pini.utils import Seq
        return self.to_file(rel_path, class_=Seq)

    def to_subdir(self, rel_path):
        """Get subdirectory of this dir.

        Args:
            rel_path (str): relative path to subdir from this dir

        Returns:
            (Dir): child subdir
        """
        _rel_path = up_path.Path(rel_path)
        return Dir(self.path+'/'+_rel_path.path)


HOME = Dir(up_utils.HOME_PATH)
TMP = Dir(up_utils.TMP_PATH)
