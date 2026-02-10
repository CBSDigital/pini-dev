"""Tools for managing the maya sanity check object."""

import copy
import logging

from maya import cmds

from pini.utils import wrap_fn

from maya_pini import open_maya as pom
from maya_pini.utils import to_shps

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

    def check_attr(self, attr, val, fail=None, catch=False):
        """Check a attribute has the given value.

        Args:
            attr (str): attribute to check
            val (any): expected value
            fail (str): override fail message
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
        _msg = fail or f'Attribute "{_plug}" is not set to "{val}"'
        _fix = wrap_fn(_plug.set_val, val)
        self.add_fail(_msg, fix=_fix, node=_plug.node)

    def check_pref(self, func, flag, val, fail=None, elem=None, **kwargs):
        """Check a preference is set to the given value.

        Args:
            func (fn): maya.cmds function to query/edit
            flag (str): name of flag to read
            val (any): required value for preference
            fail (str): override fail message
            elem (str): element arg (if required)
        """
        _LOGGER.debug('CHECK PREF %s', func)
        _args = []
        if elem:
            _args = [elem]

        _kwargs = copy.copy(kwargs)
        _kwargs[flag] = True

        _cur_val = func(*_args, query=True, **_kwargs)

        self.write_log(
            f'check "{func.__name__}|{flag}" set to "{val}" '
            f'(current val "{_cur_val}"')
        _LOGGER.debug(' - CUR VAL "%s" (%s)', _cur_val, type(_cur_val).__name__)
        _LOGGER.debug(' - REQ VAL "%s" (%s)', val, type(val).__name__)
        _LOGGER.debug(' - MISMATCH %d', _cur_val != val)
        assert type(_cur_val) is type(val)

        if _cur_val != val:
            _fail = fail or (
                f'Setting "{func.__name__}|{flag}" is set to "{_cur_val}" '
                f'(should be "{val}")')
            _kwargs[flag] = val
            _fix = wrap_fn(func, *_args, edit=True, **_kwargs)
            self.add_fail(_fail, fix=_fix)
            _LOGGER.debug(' - ADDED FAIL %s', _fail)

    def check_shp(self, node):
        """Check node shapes.

        Checks for multiple shape nodes and shape nodes not matching
        transform.

        Args:
            node (CTransform): node to check
        """
        _LOGGER.debug('CHECK SHP %s', node)
        _node = node
        if isinstance(_node, str):
            _node = pom.cast_node(_node)
        if not isinstance(_node, (
                pom.CTransform, pom.CMesh, pom.CCamera)):
            raise TypeError(_node)

        # Apply multiple shape checks - NOT: this is on CMesh init so check
        # is not required for mesh nodes
        if not isinstance(_node, (pom.CMesh, pom.CCamera)):

            # Ignore group nodes
            _shps = to_shps(str(_node))
            if not _shps:
                return

            # Handle multiple shapes
            if len(_shps) > 1:
                _shps_s = '/'.join(_shps)
                _msg = f'Node "{_node}" has multiple shapes ({_shps_s})'
                self.add_fail(_msg, node=_node)
                return

            raise NotImplementedError

        # Avoid checking shapes multiple times
        assert _node.shp
        if _node.shp in self._checked_shps:
            return
        self._checked_shps.add(_node.shp)

        # Check shape name
        _cur_shp = _node.shp.to_clean()
        _correct_shp = f'{_node.to_clean()}Shape'
        if _cur_shp != _correct_shp:

            _LOGGER.debug(' - SHP NODE %s', _node.shp)

            # Ignore instanced shapes
            if _node.shp.is_instanced():
                self.write_log(' - ignoring instanced shape %s', _cur_shp)
                return

            # Add fail
            if _node.shp.is_referenced():
                _fix = None
            else:
                _fix = wrap_fn(_fix_bad_shape, _node.shp, _correct_shp)
            _msg = (
                f'Node "{_node}" has badly named shape node "{_node.shp}" '
                f'(should be "{_correct_shp}")')
            _LOGGER.debug(' - ADDING FAIL %s', _msg)
            self.add_fail(_msg, fix=_fix, node=_node)

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        return f'<SCMayaCheck:{_type}>'


def _fix_bad_shape(cur_shp, new_shp):
    """Fix a badly named shape.

    Args:
        cur_shp (str): current shape
        new_shp (str): correctly named shape
    """
    if cmds.objExists(new_shp):
        cmds.rename(new_shp, f'{new_shp}1')
    cmds.rename(cur_shp, new_shp)
