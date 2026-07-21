import logging
import unittest

from maya import cmds

from pini import dcc
from pini.utils import single, TMP, assert_eq

from maya_pini import open_maya as pom
from maya_pini.utils import use_tmp_ns, to_clean

from maya_pini.open_maya.wrapper import pom_plug

_LOGGER = logging.getLogger(__name__)


class TestOpenMaya(unittest.TestCase):

    def test_basic_node_relationships(self):

        _persp_s = pom.CNode('perspShape')
        _persp = pom.CTransform('persp')
        _cam = pom.CCamera('persp')

        assert pom.CTransform('persp') == pom.CTransform('persp')
        assert str(_persp) == 'persp'
        assert isinstance(str(_persp), str)

        # Test get selected
        cmds.select('persp')
        assert _persp == pom.get_selected()

        # Test to parent
        assert _persp_s.to_parent()
        assert _persp_s.to_parent() == _persp
        _LOGGER.info(' - PERSP S %s %s %s', _persp_s, _persp_s.to_parent(),
                     type(_persp_s.to_parent()))
        assert isinstance(_persp_s.to_parent(), pom.CCamera)
        assert not _persp.to_parent()

        # Test to shape
        assert isinstance(_persp_s, pom.CBaseNode)
        assert isinstance(_persp_s, pom.CNode)
        assert _persp.to_shp()
        assert _persp.to_shp() == _persp_s
        assert isinstance(_persp.to_shp(), pom.CBaseNode)
        assert isinstance(_persp.to_shp(), pom.CNode)

        # Check cam
        assert _cam.shp == _persp_s
        assert _cam == _persp

        # Test eq/ne
        assert pom.CNode('persp') == "persp"
        assert not pom.CNode('persp') != "persp"  # pylint: disable=unneeded-not

    @use_tmp_ns
    def test_camera(self):

        # Test weird tmp cam hidden in transform (ie. like one created
        # if you look through a light)
        _sphere = pom.CMDS.polySphere()
        _tmp_cam = pom.CMDS.camera()
        _tmp_cam.shp.cmds.parent(_sphere.node, shape=True, add=True)
        _tmp_cam.delete()
        assert len(_sphere.to_shps()) == 2
        _cam = pom.CCamera(_sphere.node)
        assert _cam
        assert _cam.renderable

    @use_tmp_ns
    def test_cmds_wrapper(self):

        _persp_s = pom.CNode('perspShape')
        _persp = pom.CTransform('persp')
        _cam = pom.CCamera('persp')
        _sphere = pom.CMDS.polySphere()

        # Check list relatives
        _children = _cam.cmds.listRelatives(children=True)
        assert _children
        _child = single(_children)
        assert _child
        _LOGGER.info(' - CHILD %s %s', _child, type(_child))
        assert isinstance(_child, pom.CNode)
        _children = _persp_s.cmds.listRelatives(children=True)
        assert not _children
        assert isinstance(_children, list)
        _parent = _persp_s.cmds.listRelatives(parent=True)
        assert isinstance(_parent, list)
        assert isinstance(single(_parent), pom.CCamera)

        # Check list connections
        assert _sphere.namespace == 'tmp'
        assert isinstance(_sphere, pom.CMesh)
        _conns = _sphere.cmds.listConnections()
        assert not _conns
        assert isinstance(_conns, list)
        _conns = _sphere.shp.cmds.listConnections()
        assert isinstance(_conns[0], pom.CNode)
        assert _sphere.shp.cmds.listConnections(plugs=True)

    @use_tmp_ns
    def test_find_connections(self):

        _LOGGER.info('TEST FIND CONNECTIONS')

        _grp1 = pom.CTransform(pom.CMDS.createNode('transform', name='grp1'))
        _grp2 = pom.CTransform(pom.CMDS.createNode('transform', name='grp2'))
        _grp3 = pom.CTransform(pom.CMDS.createNode('transform', name='grp3'))

        _grp1.tx.connect(_grp2.tx)
        _grp2.ty.connect(_grp3.ty)

        assert _grp1.tx == _grp1.plug['tx']
        assert _grp1.tx == _grp1.plug['translateX']

        # Test connnections
        _conns = _grp1.tx.find_connections()
        _LOGGER.info(' - grp1.tx CONNS %s', _conns)
        assert len(_conns) == 1
        assert _conns[0] == _grp2.tx
        _conns = _grp1.tx.find_connections(connections=True)
        _LOGGER.info(' - grp1.tx CONNS (conns) %s', _conns)
        assert len(_conns) == 1
        assert _grp1.tx == _grp1.plug['tx']
        assert isinstance(_conns[0][0], pom.CPlug)
        assert _conns[0][0] == _grp1.tx
        assert _conns[0][1] == _grp2.tx
        assert _conns == [(_grp1.tx, _grp2.tx)]

        # Test outgoing
        _out = _grp1.tx.find_outgoing()
        _LOGGER.info(' - grp1.tx OUTGOING %s', _out)
        assert isinstance(_out, list)
        assert len(_out) == 1
        assert isinstance(_out[0], pom.CPlug)
        _out = _grp1.tx.find_outgoing(connections=True)
        assert isinstance(_out, list)
        assert len(_out) == 1
        assert isinstance(_out[0], tuple)
        assert isinstance(_out[0][0], pom.CPlug)

        # Test incoming
        assert not _grp1.tx.find_incoming()
        _in = _grp2.tx.find_incoming()
        assert isinstance(_in, pom.CPlug)
        assert _in == _grp1.tx

        assert _grp1.find_connections() == _conns

        # Test flags
        _conns = _grp2.find_connections()
        _LOGGER.info(' - grp2.tx CONNS %s', _conns)
        assert len(_conns) == 2
        assert len(_conns[0]) == 2
        _conns = _grp2.find_connections(connections=False)
        _LOGGER.info(' - grp2.tx CONNS (no conns) %s', _conns)
        assert len(_conns) == 2
        assert isinstance(_conns[0], pom.CPlug)
        assert _conns[0] == _grp1.tx
        _conns = _grp2.find_connections(connections=False, plugs=False)
        _LOGGER.info(' - grp2.tx CONNS (no plugs) %s', _conns)
        assert len(_conns) == 2
        assert isinstance(_conns[0], pom.CNode)
        assert _conns[0] == _grp1

    @use_tmp_ns
    def test_save_preset(self):

        _sphere_a = pom.CMDS.polySphere(name='SphereA')
        _sphere_b = pom.CMDS.polySphere(name='SphereB')
        assert not round((_sphere_a.to_p() - _sphere_b.to_p()).length(), 4)

        # Test preset fmt a
        _mtx_1 = pom.CMatrix([
            0.9019, -0.2978, -0.3129, 0.0000, 0.2347, 0.9459, -0.2240, 0.0000,
            0.3626, 0.1286, 0.9230, 0.0000, 1.4026, 4.0941, -4.4732, 1.0000])
        _mtx_1.apply_to(_sphere_a)
        assert round((_sphere_a.to_p() - _sphere_b.to_p()).length(), 4)
        _mpa = TMP.to_file('.pini/test.mpa')
        _sphere_a.save_preset(_mpa, force=True)
        assert _mpa.exists()
        _sphere_b.load_preset(_mpa)
        assert not round((_sphere_a.to_p() - _sphere_b.to_p()).length(), 4)

        # Test preset fmt b
        _mtx_2 = pom.CMatrix([
            3.1062, -0.2362, 0.0059, 0.0000, 0.2356, 3.0913, -0.3042, 0.0000,
            0.0172, 0.3038, 3.1003, 0.0000, -4.9101, 4.2355, 1.7335, 1.0000])
        _mtx_2.apply_to(_sphere_a)
        assert round((_sphere_a.to_p() - _sphere_b.to_p()).length(), 4)
        _mpb = TMP.to_file('.pini/test.mpb')
        _sphere_a.save_preset(_mpb, force=True)
        _sphere_b.load_preset(_mpb)
        assert not round((_sphere_a.to_p() - _sphere_b.to_p()).length(), 4)

    @use_tmp_ns
    def test_plug(self):

        # Test CPlug.plus
        _node = pom.CMDS.createNode('unknown')
        _a = _node.add_attr('A', 7)
        _b = _node.add_attr('B', 6)
        _c = _node.add_attr('C', 0)
        _a.plus(_b, output=_c)
        assert _c.get_val() == 13

        # Test plus_plug
        _node = pom.CMDS.createNode('unknown')
        _a = _node.add_attr('A', 7)
        _b = _node.add_attr('B', 6)
        _c = _node.add_attr('C', 0)
        pom.plus_plug(_a, _b, output=_c)
        assert _c.get_val() == 13
        pom.plus_plug(10, _b, output=_c, force=True)
        assert _c.get_val() == 16

        # Test minus_plug
        _node = pom.CMDS.createNode('unknown')
        _a = _node.add_attr('A', 7)
        _b = _node.add_attr('B', 6)
        _c = _node.add_attr('C', 0)
        pom.minus_plug(_a, _b, output=_c)
        assert _c.get_val() == 1

        # Test complex attrs
        _cube = pom.CMDS.polyCube()
        _ramp = pom.CMDS.shadingNode('ramp', asShader=True)
        _LOGGER.info(' - NODES %s %s', _cube, _ramp)
        for _attr in [
                _cube.shp.to_attr('uvSize'),
                _cube.shp.to_attr('vertexNormal'),
                _ramp.to_attr('colorEntryList'),
                _ramp.to_attr('colorEntryList[0].color'),
                _cube.to_attr('tx'),
        ]:
            _LOGGER.info('ATTR %s', _attr)
            _node, _plug = _attr.split('.', 1)
            _node = pom.CNode(_node)
            pom_plug._to_mplug(node=_node, attr=_plug)
            pom.CPlug(_attr)

    @use_tmp_ns
    def test_plug_maths(self):

        _node = pom.CMDS.createNode('unknown')
        for _val in range(10):
            _attr = f'V{_val}'
            _plug = _node.add_attr(_attr, float(_val), force=True)
            setattr(_node, _attr, _plug)
            _LOGGER.info(' - ADDED PLUG %s %d', _plug, _val)
        _node.out = _node.add_attr('output', 0.0, force=True)

        # Test plus
        _node.V0.plus(_node.V1, output=_node.out)
        assert _node.out.get_val() == 1
        _out = pom.plus_plug(
            _node.V0, _node.V1, _node.V2, output=_node.out, force=True)
        assert _node.out.get_val() == 3
        assert to_clean(_out).startswith('plus')

        # Test minus
        _node.V0.minus(_node.V1, output=_node.out, force=True)
        assert _node.out.get_val() == -1
        _out = pom.minus_plug(1, _node.V0, output=_node.out, force=True)
        assert _node.out.get_val() == 1
        assert to_clean(_out).startswith('minus')

        # Test multiply
        _node.V0.multiply(_node.V1, output=_node.out, force=True)
        assert _node.out.get_val() == 0
        _node.V2.multiply(_node.V3, output=_node.out, force=True)
        assert _node.out.get_val() == 6
        _out = pom.multiply_plug(_node.V3, _node.V2, output=_node.out, force=True)
        assert_eq(_node.out.get_val(), 6)
        assert to_clean(_out).startswith('multiply')

        # Test divide
        _node.V6.divide(_node.V2, output=_node.out, force=True)
        assert _node.out.get_val() == 3
        _out = pom.divide_plug(12, _node.V4, output=_node.out, force=True)
        assert_eq(_node.out.get_val(), 3)
        assert to_clean(_out).startswith('divide')

        # Test reverse
        _out = _node.V6.reverse(output=_node.out, force=True)
        assert _node.out.get_val() == -5
        assert to_clean(_out).startswith('reverse')

        # Test negate
        _out = _node.V6.negate(output=_node.out, force=True)
        assert _node.out.get_val() == -6
        assert to_clean(_out).startswith('negate')

        # Test invert
        _out = _node.V5.invert(output=_node.out, force=True)
        assert_eq(_node.out.get_val(), 0.2, dp=4)
        assert to_clean(_out).startswith('invert')

        # Test modulo
        _out = _node.V5.modulo(_node.V3, output=_node.out, force=True)
        assert _node.out.get_val() == 2
        assert to_clean(_out).startswith('modulo')

    @use_tmp_ns
    def test_read_cache_set_test(self):

        _sphere = pom.CMDS.polySphere()
        _shp = pom.cast_node(str(_sphere.shp), maintain_shapes=True)
        _LOGGER.info('SHP %s', _shp)
        assert not isinstance(_shp, pom.CMesh)

        _grp = _sphere.add_to_grp('GEO')
        _grp.add_to_set('cache_SET')
        pom.set_to_tfms('cache_SET')

    @use_tmp_ns
    def test_transform(self):

        dcc.new_scene(force=True)

        # Test solidify
        if cmds.objExists('BLAH'):
            cmds.delete('BLAH')
        _sphere = pom.CMDS.polySphere()
        _grp = _sphere.add_to_grp('BLAH')
        _LOGGER.info('GRP %s %s %d', _grp, _grp.tx, _grp.tx.is_locked())
        assert not _grp.tx.is_locked()
        _grp.solidify()
        assert _grp.tx.is_locked()
        _sphere = pom.CMDS.polySphere()
        _grp = _sphere.add_to_grp('BLEE')
        _grp.tx.set_val(1)
        try:
            _grp.solidify()
        except RuntimeError:
            pass
        else:
            raise RuntimeError
