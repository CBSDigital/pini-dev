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

    def _check_attr(self, attr, val):
        """Check a attribute has the given value.

        Args:
            attr (str): attribute to check
            val (any): expected value
        """
        _plug = pom.CPlug(attr)
        _cur_val = _plug.get_val()
        _passed = _cur_val == val
        self.write_log(
            ' - check setting %s == %s passed=%d', attr, val, _passed)
        if _passed:
            return
        _msg = f'Attribute "{_plug}" is not set to "{val}"'
        _fix = wrap_fn(_plug.set_val, val)
        self.add_fail(_msg, fix=_fix, node=_plug.node)

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
            _msg = 'Node "{}" has multiple shapes ({})'.format(
                node, '/'.join(_shps))
            self.add_fail(_msg, node=node)
            return

        _shp = single(_shps)
        if _shp in self._checked_shps:
            return
        self._checked_shps.add(_shp)

        # Check shape name
        _cur_shp = to_clean(_shp)
        _correct_shp = to_clean(node)+'Shape'
        if _cur_shp != _correct_shp:
            if pom.CNode(_cur_shp).is_referenced():
                _fix = None
            else:
                _fix = wrap_fn(cmds.rename, _shp, _correct_shp)
            _msg = (
                f'Node "{node}" has badly named shape node "{_shp}" (should '
                f'be "{_correct_shp}")')
            self.add_fail(_msg, fix=_fix, node=node)
