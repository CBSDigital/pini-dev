"""Tools for wrapping maya.cmds calls to pom objects.

This aims to wrap all maya.cmds and map the results into appropriate
pom objects.

It will also make sure that functions always return lists, rather
than returning None if there are no results.
"""

import functools
import logging

from maya import cmds

from pini.utils import basic_repr, single
from maya_pini.utils import to_parent

from .pom_utils import cast_node

_LOGGER = logging.getLogger(__name__)


class CmdsMapper:
    """Maps commands to wrapped maya.cmds functions.

    eg. CmdsMapper().camera maps to a function which returns a
        single pom.CCamera node.
    """

    def __init__(self, node=None):
        """Constructor.

        Args:
            node (str): prepend node to args
        """
        self.node = node

    def __getattr__(self, attr):
        _func = getattr(cmds, attr)
        return _results_wrapper(
            _func, node=self.node)

    def __repr__(self):
        return basic_repr(self, label=None)


def _results_wrapper(func, node=None):  # pylint: disable=too-many-statements
    """Map results to pom objects.

    Args:
        func (fn): maya.cmds function to wrap
        node (str): node to preprend to args list

    Returns:
        (fn): wrapped function
    """

    @functools.wraps(func)
    def _map_results_func(*args, **kwargs):  # pylint: disable=too-many-branches,too-many-statements

        from maya_pini import open_maya as pom

        _name = func.__name__
        _LOGGER.debug('EXECUTING %s', _name)

        # Process args
        _kwargs = kwargs
        if (
                _name == 'curve' and
                'point' in _kwargs and
                isinstance(_kwargs['point'][0], pom.CPoint)):
            _kwargs['point'] = [_pt.to_tuple() for _pt in _kwargs['point']]

        # Read result
        _args = list(args)
        if node:
            _args.insert(0, node)
        _LOGGER.debug(' - ARGS/KWARGS %s %s', _args, _kwargs)
        _result = func(*_args, **_kwargs)
        _LOGGER.debug(' - RESULT "%s"', _result)

        # Process results
        if _name == 'annotate':
            _shp = _result.strip()
            _tfm = to_parent(_shp)
            _result = pom.CTransform(_tfm)
        elif _name == 'camera':
            _tfm, _ = _result
            _result = pom.CCamera(_tfm)
        elif _name in ['circle']:
            _tfm, _ = _result
            _result = pom.CNurbsCurve(_tfm)
        elif _name in ['curve']:
            _result = pom.CNurbsCurve(_result)
        elif _name == 'imagePlane':
            _tfm, _ = _result
            _result = pom.CTransform(_tfm)
        elif _name in ['createNode', 'pathAnimation', 'shadingNode']:
            _result = pom.CNode(_result)
        elif _name in [
                'parentConstraint',
                'pointConstraint',
                'orientConstraint',
                'scaleConstraint',
                'spaceLocator',
        ]:
            _tfm = single(_result)
            _result = pom.CTransform(_tfm)
        elif _name in ['group']:
            _result = pom.CTransform(_result)

        # Special handlers
        elif _name == 'listConnections':
            _result = _clean_list_connections(_result, **_kwargs)
        elif _name == 'listRelatives':
            _result = _clean_list_relatives(_result, **_kwargs)
        elif _name in ('listSets', 'sets'):
            _result = _clean_list(_result)
        elif _name == 'ls':
            _result = _clean_ls(_result, **_kwargs)

        elif _name == 'polyUVSet':
            _result = _result or []
        elif _name in [
                'polySphere', 'polyCube', 'polyCylinder', 'polyPyramid',
                'polyPlane',
        ]:
            _tfm, _ = _result
            _result = pom.CMesh(_tfm)
        elif _name in ['parent', 'delete']:
            _result = None
        elif _name == 'ikHandle':
            _ik, _ee = _result
            _result = pom.CTransform(_ik), pom.CNode(_ee)

        else:
            raise NotImplementedError(_name, _result)

        return _result

    return _map_results_func


def _clean_list(results, class_=None):
    """Generic clean function for list results.

    Replaces None result for empty list and casts each item to the
    given type.

    Args:
        results (list|None): cmds result
        class_ (class): type to cast to

    Returns:
        (CNode list): cast results
    """
    _results = []
    for _result in results or []:
        if class_:
            _result = class_(_result)
        else:
            _result = cast_node(_result)
        _results.append(_result)
    return _results


def _clean_list_connections(results, plugs=False, type=None, **kwargs):  # pylint: disable=redefined-builtin,unused-argument
    """Clean listConnections results.

    Args:
        results (str list|None): results to clean
        plugs (bool): return plugs
        type (str): type filter

    Returns:
        (CNode|CTransform|CPlug list): cleaned results
    """
    _LOGGER.debug('CLEAN listConnections %s', results)
    from maya_pini import open_maya as pom

    _results = results or []

    # Remove weird image plane arrow
    _results = [_result.split('->')[-1] for _result in _results]

    # Cast to class
    if plugs:
        _class = pom.CPlug
    elif type == 'animCurve':
        _class = pom.CAnimCurve
    elif type == 'imagePlane':
        _class = pom.CTransform
    else:
        _class = pom.CNode
    _results = [_class(_result) for _result in _results]

    return _results


def _clean_list_relatives(results, type=None, parent=False, **kwargs):  # pylint: disable=redefined-builtin,unused-argument
    """Clean listRelatives results.

    Args:
        results (str list|None): results to clean
        type (str): type filter
        parent (bool): parent flag

    Returns:
        (CNode|CTransform list): cleaned results
    """
    from maya_pini import open_maya as pom
    _results = results or []
    return [pom.cast_node(_result, maintain_shapes=True)
            for _result in _results]


def _clean_ls(results, type=None, **kwargs):   # pylint: disable=redefined-builtin,unused-argument
    """Clean ls results.

    Args:
        results (str list|None): results to clean
        type (str): type filter

    Returns:
        (CNode|CCamera list): cleaned results
    """
    from maya_pini import open_maya as pom

    _LOGGER.debug('CLEAN ls %s', results)
    _results = results or []
    if type == 'camera':
        return [cast_node(_node, type_='camera') for _node in _results]

    if type == 'imagePlane':
        _results = [_result.split('->')[-1] for _result in _results]

    if type == 'animCurve':
        _class = pom.CAnimCurve
    elif type in ('joint', 'transform'):
        _class = pom.CTransform
    else:
        _class = pom.CNode

    return [_class(_node) for _node in _results]


CMDS = CmdsMapper()
