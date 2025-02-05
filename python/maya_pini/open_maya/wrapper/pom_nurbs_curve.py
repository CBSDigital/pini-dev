"""Tools for adding functionilty to OpenMaya.MFnMesh object."""

import logging

from maya import cmds
from maya.api import OpenMaya as om

from pini.utils import cache_result
from maya_pini.utils import to_shp

from .. import base
from ..pom_utils import to_mobject

_LOGGER = logging.getLogger(__name__)


class CNurbsCurve(base.CBaseTransform, om.MFnNurbsCurve):
    """Wrapper for OpenMaya.MFnNurbsCurve object."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): curve transform node
        """
        _tfm = node
        if not cmds.objectType(_tfm) == 'transform':
            raise ValueError(node)
        _shp = to_shp(str(_tfm), catch=True)
        if not _shp:
            raise ValueError(f'Missing shape {_tfm}')
        super().__init__(_tfm)
        _mobj = to_mobject(_shp)
        om.MFnNurbsCurve.__init__(self, _mobj)

    def length(self):
        """Obtain length of this curve.

        Returns:
            (float): length
        """
        return cmds.arclen(self.shp)

    def l_to_m(self, length):
        """Obtain matrix at a given postion on this curve.

        Args:
            length (float): distance along curve

        Returns:
            (MMatrix): transformation matrix
        """
        _param = self.findParamFromLength(length)
        _mtx = self.param_to_m(_param)
        return _mtx

    def param_to_m(self, param, up_=None):
        """Obtain matrix at the given parametric length on this curve.

        Args:
            param (float): parametric distance along curve
            up_ (MVector): up vector (default is y-axis)

        Returns:
            (MMatrix): transformation matrix
        """
        from maya_pini import open_maya as pom
        _pos = self.param_to_p(param)
        _lz = self.param_to_t(param)
        _up = up_ or pom.Y_AXIS
        _ly = _up.normalized()
        _lx = (-_lz ^ _ly).normalized()  # pylint: disable=invalid-unary-operand-type
        _mtx = pom.to_m(pos=_pos, lx=_lx, ly=_ly, lz=_lz)
        return _mtx

    def param_to_p(self, param):
        """Obtain position at the given parametric length on this curve.

        Args:
            param (float): parametric distance along curve

        Returns:
            (MPoint): position
        """
        from maya_pini import open_maya as pom
        _pt = self.getPointAtParam(param)
        return pom.CPoint(_pt)

    def param_to_t(self, param):
        """Obtain curve tangent at the given parametric length.

        Args:
            param (float): parametric distance along curve

        Returns:
            (CVector): tangent
        """
        from maya_pini import open_maya as pom
        _tan = pom.CVector(self.tangent(param))
        return _tan.normalized()

    def path_animation(
            self, target, use_u_length=False, follow_axis='z',
            up_axis='y', loop=None):
        """Create motion path attached to this curve.

        The position on the path is driven by a u attribute
        (uValue or uLength) on the target object.

        Args:
            target (str): object to attach to this curve
            use_u_length (bool): convert motion path uValue
                to curve length (uLength) representing the real
                curve length rather than fractional length
            follow_axis (str): motion path follow axis
            up_axis (str): motion path up axis
            loop (bool): apply looping (default is off for open
                curves, or for closed ones)

        Returns:
            (CPlug): motion path driver attribute on target
        """
        from maya_pini import open_maya as pom
        _LOGGER.info('PATH ANIMATION')

        _trg = pom.CTransform(target)
        _m_path = pom.CMDS.pathAnimation(
            _trg, self, follow=True, fractionMode=True, followAxis=follow_axis,
            upAxis=up_axis)
        _m_path_u = _m_path.plug['uValue']
        _m_path_u.break_conns()

        # Add u attr
        if use_u_length:
            _info = self.to_curve_info()
            _length = _info.plug['arcLength']
            _u_len = _trg.add_attr('uLength', 0.0)
            _tail = _u_len.divide(_length)
            _result = _u_len
        else:
            _u_val = _trg.add_attr('uValue', 0.0)
            _tail = _u_val
            _result = _u_val
        _LOGGER.info(' - RESULT %s (tail=%s)', _result, _tail)

        # Apply looping
        _form = self.shp.plug['form'].get_enum()
        _loop = loop if loop is not None else _form in ('Closed', 'Periodic')
        if _loop:
            _LOGGER.info(' - LOOPING %s %% 1', _tail)
            _tail = _tail.modulo(1)
            _LOGGER.info(' - LOOPED %s', _tail)

        _tail.connect(_m_path_u)
        _LOGGER.info(' - CONNECT TAIL %s -> %s', _tail, _m_path_u)

        return _result

    def fr_to_m(self, fraction):
        """Obtain matrix at the given fractional distance on this curve.

        Args:
            fraction (float): fractional distance

        Returns:
            (MMatrix): transformation matrix
        """
        _len = self.length()
        return self.l_to_m(fraction*_len)

    def fr_to_p(self, fraction):
        """Obtain position at the given fractional distance on this curve.

        Args:
            fraction (float): fractional distance

        Returns:
            (CPoint): position
        """
        return self.fr_to_m(fraction).to_p()

    @cache_result
    def to_curve_info(self):
        """Build a curve info node attached to this curve.

        Returns:
            (CNode): curve info node
        """
        from maya_pini import open_maya as pom
        _info = pom.CMDS.createNode('curveInfo')
        self.shp.plug['worldSpace[0]'].connect(_info.plug['inputCurve'])
        return _info

    def to_cv(self, idx, mode='attr'):
        """Obtain the given cv attribute.

        Args:
            idx (int): cv index
            mode (str): what data to return (attr/pos)

        Returns:
            (str): cv attribute (eg. nurbCurve1Shape.cv[10])
        """
        from maya_pini import open_maya as pom
        _attr = self.shp.attr[f'cv[{idx:d}]']
        if mode == 'attr':
            return _attr
        if mode == 'pos':
            return pom.to_p(_attr)
        raise ValueError(mode)

    def to_ps(self):
        """Obtain cv point positions.

        Returns:
            (CPoint list): points
        """
        from maya_pini import open_maya as pom
        _pts = []
        for _idx in range(self.numCVs):
            _cv = self.to_cv(_idx)
            _pt = pom.CPoint(cmds.xform(_cv, query=True, translation=True))
            _pts.append(_pt)
        return _pts
