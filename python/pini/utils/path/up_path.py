"""Tools for managing the base Path object."""

import logging
import os
import pathlib
import time

from . import up_utils
from ..u_misc import nice_size, nice_id, strftime
from ..u_six import six_cmp

_LOGGER = logging.getLogger(__name__)


class Path(object):
    """Represents a path on disk."""

    def __init__(self, path):
        """Constructor.

        Args:
            path (str): path on disk
        """
        _path = up_utils.norm_path(path)

        self.path = _path

        self.filename = self.path.split('/')[-1]
        self.dir = up_utils.norm_path(str(self._pathlib.parent))
        self.base = self._pathlib.stem
        self.extn = self._pathlib.suffix[1:]
        if not self.extn:
            self.extn = None

    @property
    def _pathlib(self):
        """Obtain pathlib object for this path.

        Returns:
            (Path): pathlib object
        """
        return pathlib.Path(self.path)

    def age(self):
        """Obtain age of this path, time since modified time.

        Returns:
            (float): age in seconds
        """
        return time.time() - self.mtime()

    def ctime(self):
        """Get last modified time for this path.

        Returns:
            (float): mtime in secs
        """
        up_utils.error_on_file_system_disabled(self.path)
        return os.path.getctime(self.path)

    def exists(self, catch=False, root=None):
        """Test whether this path exists.

        Args:
            catch (bool): no error if permission denied (returns False)
            root (str): override pwd for relative paths

        Returns:
            (bool): whether exists
        """
        up_utils.error_on_file_system_disabled(self.path)
        if root:
            return self.to_abs(root=root).exists()

        try:
            return self._pathlib.exists()
        except OSError as _exc:
            if catch:
                return False
            raise _exc

    def is_abs(self):
        """Test whether this path is absolute.

        Returns:
            (bool): whether absolute
        """
        return up_utils.is_abs(self.path)

    def is_dir(self):
        """Test whether is path is a directory.

        Returns:
            (bool): whether directory
        """
        up_utils.error_on_file_system_disabled(self.path)
        return self._pathlib.is_dir()

    def is_file(self):
        """Test whether is path is a file.

        Returns:
            (bool): whether file
        """
        up_utils.error_on_file_system_disabled(self.path)
        return self._pathlib.is_file()

    def mkdir(self):
        """Create this path as a directory, with all parent dirs."""
        up_utils.error_on_file_system_disabled(self.path)
        if self.exists():
            assert self.is_dir()
            return
        os.makedirs(self.path)

    def mtime(self):
        """Get last modified time for this path.

        Returns:
            (float): mtime in secs
        """
        up_utils.error_on_file_system_disabled(self.path)
        return os.path.getmtime(self.path)

    def nice_age(self):
        """Get nice age for this file (eg. 1w2d).

        Returns:
            (str): nice age
        """
        from pini.utils import nice_age
        return nice_age(self.age())

    def nice_size(self, catch=False):
        """Get size of this file in a readable for (eg. 10GB).

        Args:
            catch (bool): no error on missing file

        Returns:
            (str): readable file size
        """
        try:
            _size = self.size()
        except OSError as _exc:
            if catch:
                return '-'
            raise _exc
        return nice_size(_size)

    def owner(self):
        """Get file owner.

        Returns:
            (str): owner
        """
        up_utils.error_on_file_system_disabled(self.path)
        if os.name == 'nt':
            return _get_owner_nt(self.path)
        from os import stat
        from pwd import getpwuid  # pylint: disable=import-error
        return getpwuid(stat(self.path).st_uid).pw_name

    def replace(self, find, replace):
        """Apply string find/replace to this path object.

        Returns a Path object of matching type.

        Args:
            find (str): find string
            replace (str): replace string

        Returns:
            (Path): updated path
        """
        return type(self)(self.path.replace(find, replace))

    def size(self, catch=False):
        """Obtain size of this path and its contents.

        Args:
            catch (bool): no error if path is missing/unreadable

        Returns:
            (int): size in bytes
        """
        up_utils.error_on_file_system_disabled(self.path)
        try:
            return self._read_size()
        except OSError as _exc:
            if catch:
                return None
            raise _exc

    def _read_size(self):
        """Read size of this path.

        Returns:
            (int): size in bytes
        """
        raise NotImplementedError

    def strftime(self, fmt=None):
        """Get mtime as formatted string.

        Args:
            fmt (str): format to apply

        Returns:
            (str): formatted time string
        """
        return strftime(fmt=fmt, time_=self.mtime())

    def test_dir(self):
        """Test this path's parent directory exists, creating if needed."""
        self.to_dir().mkdir()

    def to_abs(self, root=None):
        """Map this path to an absolute path.

        If the path is already absolute, it is simply returned.

        Args:
            root (str): apply root for relative path (if none provided
                the cwd is used)

        Returns:
            (Path): absolute path
        """
        from pini.utils import path
        if self.is_abs():
            return self
        _root = path.Dir(root or os.getcwd())
        _path = path.abs_path(_root.path+'/'+self.path)
        return type(self)(_path)

    def to_dir(self, levels=1):
        """Get parent directory for this path.

        Args:
            levels (int): how many levels to go up

        Returns:
            (Dir): parent dir
        """
        from . import up_dir
        _LOGGER.debug('TO DIR %s', self.path)
        assert isinstance(levels, int)

        if levels > 1:
            return self.to_dir().to_dir(levels=levels-1)

        _parent = os.path.dirname(self.path)
        _LOGGER.debug(' - PARENT %s', _parent)
        if _parent == self.path:
            return None
        return up_dir.Dir(_parent)

    def __cmp__(self, other):
        _LOGGER.debug('CMP %s %s', self, other)
        if isinstance(other, Path):
            return six_cmp(self.path, other.path)
        return six_cmp(self.path, other)

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if not isinstance(other, Path):
            return False
        return self.path == other.path

    def __lt__(self, other):
        from pini.utils import Seq
        if not isinstance(other, (Path, Seq)):
            return self.path < other
        return self.path < other.path

    def __repr__(self):
        _tag = ''
        if os.environ.get('PINI_REPR_NICE_IDS'):
            _tag = '[{}]'.format(nice_id(self))
        return '<{}{}|{}>'.format(
            type(self).__name__.lstrip('_'), _tag, self.path)


def _get_owner_nt(path):
    """Get windows path owner.

    Args:
        path (str): path to read

    Returns:
        (str): file owner
    """

    import ctypes
    from ctypes import wintypes

    def _get_file_security(filename, request):
        length = wintypes.DWORD()
        _get_file_security_w(filename, request, None, 0, ctypes.byref(length))
        if length.value:
            _sd = (wintypes.BYTE * length.value)()
            if _get_file_security_w(
                    filename, request, _sd, length, ctypes.byref(length)):
                return _sd
        return None

    def _get_security_descriptor_owner(sd_):
        if sd_ is not None:
            sid = _psid()
            sid_defaulted = wintypes.BOOL()
            if _get_security_desc_owner(
                    sd_, ctypes.byref(sid), ctypes.byref(sid_defaulted)):
                return sid
        return None

    def _look_up_account_sid(sid):
        if sid is not None:
            size = 256
            name = ctypes.create_unicode_buffer(size)
            domain = ctypes.create_unicode_buffer(size)
            cch_name = wintypes.DWORD(size)
            cch_domain = wintypes.DWORD(size)
            sid_type = wintypes.DWORD()
            if _lookup_accounts_sid(
                    None, sid, name, ctypes.byref(cch_name), domain,
                    ctypes.byref(cch_domain), ctypes.byref(sid_type)):
                return name.value, domain.value, sid_type.value
        return None, None, None

    _descriptor = ctypes.POINTER(wintypes.BYTE)
    _psid = ctypes.POINTER(wintypes.BYTE)
    _lpd_word = ctypes.POINTER(wintypes.DWORD)
    _lpd_bool = ctypes.POINTER(wintypes.BOOL)

    _owner_security_info = 0X00000001
    _sid_types = dict(enumerate(
        "User Group Domain Alias WellKnownGroup DeletedAccount "
        "Invalid Unknown Computer Label".split(), 1))

    _advapi32 = ctypes.windll.advapi32

    # MSDN windows/desktop/aa446639
    _get_file_security_w = _advapi32.GetFileSecurityW
    _get_file_security_w.restype = wintypes.BOOL
    _get_file_security_w.argtypes = [
        wintypes.LPCWSTR,  # File Name (in)
        wintypes.DWORD,  # Requested Information (in)
        _descriptor,  # Security Descriptor (out_opt)
        wintypes.DWORD,  # Length (in)
        _lpd_word, ]  # Length Needed (out)

    # MSDN windows/desktop/aa446651
    _get_security_desc_owner = _advapi32.GetSecurityDescriptorOwner
    _get_security_desc_owner.restype = wintypes.BOOL
    _get_security_desc_owner.argtypes = [
        _descriptor,  # Security Descriptor (in)
        ctypes.POINTER(_psid),  # Owner (out)
        _lpd_bool, ]  # Owner Exists (out)

    # MSDN windows/desktop/aa379166
    _lookup_accounts_sid = _advapi32.LookupAccountSidW
    _lookup_accounts_sid.restype = wintypes.BOOL
    _lookup_accounts_sid.argtypes = [
        wintypes.LPCWSTR,  # System Name (in)
        _psid,  # SID (in)
        wintypes.LPCWSTR,  # Name (out)
        _lpd_word,  # Name Size (inout)
        wintypes.LPCWSTR,  # Domain(out_opt)
        _lpd_word,  # Domain Size (inout)
        _lpd_word]  # SID Type (out)

    _request = _owner_security_info

    _path = os.path.abspath(path)
    _sd = _get_file_security(_path, _request)
    _sid = _get_security_descriptor_owner(_sd)
    _name, _, _ = _look_up_account_sid(_sid)

    return _name


def _get_data_dir():
    """Get pini data directory.

    Returns:
        (str): path to data dir
    """
    _dir = None
    for _ in range(5):
        _dir = os.path.dirname(_dir or __file__)
    return up_utils.abs_path(_dir+'/data')


DATA_PATH = _get_data_dir()
