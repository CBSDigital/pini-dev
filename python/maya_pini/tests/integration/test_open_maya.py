import logging
import unittest

from maya import cmds

from pini.utils import single
from maya_pini import open_maya as pom
from maya_pini.utils import use_tmp_ns

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
