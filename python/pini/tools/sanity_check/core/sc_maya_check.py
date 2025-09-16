"""Tools for managing the maya sanity check object."""

import logging

from maya import cmds

from pini.utils import single, wrap_fn

from maya_pini import open_maya as pom
from maya_pini.utils import to_shps, to_clean

from . import sc_check

_LOGGER = logging.getLogger(__name__)


class SCMayaCheck(sc_check.SCCheck):
    """Base class for any maya check.

    This adds a check shape method, so allow shape naming fails to be shared
    across muliple checks.
    """

    _checked_shps = None

    def run(self):
        """Execute this check."""
        self._checked_shps = set()

    def check_attr(self, attr, val, catch=False):
        """Check a attribute has the given value.

        Args:
            attr (str): attribute to check
            val (any): expected value
            catch (bool): no error if attr missing
        """
        try:
            _plug = pom.CPlug(attr)
        except RuntimeError as _exc:
            if catch:
                self.write_log('Missing attr %s', attr)
                return
            raise _exc
        _cur_val = _plug.get_val()
        _passed = _cur_val == val
        self.write_log(
            ' - check setting %s == %s passed=%d', attr, val, _passed)
        if _passed:
            return
        _msg = f'Attribute "{_plug}" is not set to "{val}"'
        _fix = wrap_fn(_plug.set_val, val)
        self.add_fail(_msg, fix=_fix, node=_plug.node)

    def check_pref(self, func, flag, val, fail=None):
        """Check a preference is set to the given value.

        Args:
            func (fn): maya.cmds function to query/edit
            flag (str): name of flag to read
            val (any): required value for preference
            fail (str): override fail message
        """
        _cur_val = func(query=True, **{flag: True})
        self.write_log(
            f'check "{func.__name__}|{flag}" set to "{val}" '
            f'(current val "{_cur_val}"')
        if _cur_val != val:
            _fail = fail or (
                f'Setting "{func.__name__}|{flag}" is set to "{_cur_val}" '
                f'(should be "{val}")')
            self.add_fail(_fail, fix=wrap_fn(func, edit=True, **{flag: val}))

    def check_shp(self, node):
        """Check node shapes.

        Checks for multiple shape nodes and shape nodes not matching
        transform.

        Args:
            node (str): node to check
        """
        _shps = to_shps(str(node))
        if not _shps:
            return

        # Handle multiple shapes
        if len(_shps) > 1:
            _shps_s = '/'.join(_shps)
            _msg = f'Node "{node}" has multiple shapes ({_shps_s})'
            self.add_fail(_msg, node=node)
            return

        _shp = single(_shps)
        if _shp in self._checked_shps:
            return
        self._checked_shps.add(_shp)

        # Check shape name
        _cur_shp = to_clean(_shp)
        _correct_shp = to_clean(node) + 'Shape'
        if _cur_shp != _correct_shp:
            if pom.CNode(_shp).is_referenced():
                _fix = None
            else:
                _fix = wrap_fn(_fix_bad_shape, _shp, _correct_shp)
            _msg = (
                f'Node "{node}" has badly named shape node "{_shp}" (should '
                f'be "{_correct_shp}")')
            self.add_fail(_msg, fix=_fix, node=node)


def _fix_bad_shape(cur_shp, new_shp):
    """Fix a badly named shape.

    Args:
        cur_shp (str): current shape
        new_shp (str): correctly named shape
    """
    if cmds.objExists(new_shp):
        cmds.rename(new_shp, f'{new_shp}1')
    cmds.rename(cur_shp, new_shp)
