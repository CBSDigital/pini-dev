"""Tools for managing terragen interaction via the pini.dcc module."""

import logging

import json
import SyPy3 as SyPy  # pylint: disable=import-error

from pini.utils import abs_path, File, single

from .d_base import BaseDCC

_LOGGER = logging.getLogger(__name__)
_PINI_REFS_NAME = "<PiniPrefs>"


class SyntheyesDCC(BaseDCC):
    """Manages interactions with syntheyes."""

    NAME = 'syntheyes'
    DEFAULT_EXTN = 'sni'
    VALID_EXTNS = ('sni', )

    _lev = None

    @property
    def lev(self):
        """Obtain syntheyes level.

        Returns:
            (SyLevel): level
        """
        return self.to_level()

    def cur_file(self):
        """Get path to current file.

        Returns:
            (str|None): current file (if any)
        """
        _file = self.lev.SNIFileName()
        if not _file:
            return None
        return abs_path(_file)

    def _force_load(self, file_):
        """Force load the given scene.

        Args:
            file_ (str): scene to load
        """
        _file = File(file_)
        _LOGGER.debug('FORCE LOAD %s', _file)
        self.lev.ClearChanged()
        self.lev.OpenSNI(_file.path)

    def _force_new_scene(self):
        """Force new scene."""
        self.lev.ClearChanged()
        self.lev.PerformActionByNameAndWait('Close')

    def _force_save(self, file_=None):
        """Force save the current scene without overwrite confirmation.

        Args:
            file_ (str): path to save scene to
        """
        _LOGGER.debug('FORCE SAVE %s', file_)
        if file_:
            _file = File(file_)
            _LOGGER.debug(' - CLEAR CHANGED')
            self.lev.ClearChanged()
            _LOGGER.debug(' - SET SNI %s', _file)
            self.lev.SetSNIFileName(_file.path)
        elif not self.cur_file():
            raise RuntimeError('No current scene')
        _LOGGER.debug(' - APPLY SAVE')
        self.lev.PerformActionByNameAndWait('Save')
        _LOGGER.debug(' - DONE')

    def get_scene_data(self, key):
        """Retrieve data stored with this scene.

        Args:
            key (str): data to obtain
        """
        return _read_scn_data().get(key)

    def set_range(self, start, end):
        """Set current frame range.

        Args:
            start (float): start frame
            end (float): end frame
        """
        self.lev.SetAnimStart(start)
        self.lev.SetAnimEnd(end)

    def set_scene_data(self, key, val):
        """Store data within this scene.

        Args:
            key (str): name of data to store
            val (any): value of data to store
        """
        _data = _read_scn_data()
        _data[key] = val
        _data_s = json.dumps(_data)

        _LOGGER.info(' - APPLY DATA %s', _data_s)

        _lev = SyPy.SyLevel()
        _lev.OpenExisting()
        _prefs_mesh = _obt_prefs_mesh(level=_lev)
        _LOGGER.info(' - PREFS MESH %s', _prefs_mesh)
        _lev.Begin()
        _prefs_mesh.kind = _data_s
        _lev.Accept("Update prefs mesh")

    def t_end(self, class_=float):
        """Get end frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): end time
        """
        return class_(self.lev.AnimEnd())

    def t_start(self, class_=float):
        """Get start frame.

        Args:
            class_ (class): override result type

        Returns:
            (float): start time
        """
        return class_(self.lev.AnimStart())

    def to_level(self, force=False):
        """Obtain level object.

        Args:
            force (bool): force rebuild existing

        Returns:
            (SyLevel): level
        """
        if force or not self._lev:
            self._lev = _to_level()
        return self._lev

    def unsaved_changes(self):
        """Test whether the current scene has unsaved changes.

        Returns:
            (bool): unsaved changes
        """
        return self.to_level().HasChanged()


def _obt_prefs_mesh(level=None):
    """Find pini preferences mesh, creating if needed.

    Args:
        level (SyLevel): level

    Returns:
        (SyObj): pini prefs
    """
    _lev = level or _to_level()
    _prefs_mesh = single(
        [_mesh for _mesh in _lev.Meshes() if _mesh.Name() == _PINI_REFS_NAME],
        catch=True)
    if not _prefs_mesh:

        _lev.Begin()
        _prefs_mesh = _lev.CreateNew("MESH")
        _prefs_mesh.nm = _PINI_REFS_NAME
        _prefs_mesh.kind = ""
        _lev.Accept("Create test mesh")

    return _prefs_mesh


def _read_scn_data():
    """Read data embedded in this scene.

    Returns:
        (dict): scene data
    """
    _prefs_mesh = _obt_prefs_mesh()

    _data_s = _prefs_mesh.kind
    _LOGGER.debug(' - DATA S %s', _data_s)
    if not _data_s or _data_s in ('Custom', ):
        return {}

    try:
        _data = json.loads(_data_s)
    except json.JSONDecodeError:
        return {}

    return _data


def _to_level():
    """Obtain a syntheye level connection.

    Returns:
        (SyLevel): level
    """
    _lev = SyPy.SyLevel()
    _lev.OpenExisting()
    return _lev
