import unittest

from maya import cmds

from pini.tools import sanity_check
from pini.tools.sanity_check.checks import scc_maya_asset
from pini.utils import single

from maya_pini import open_maya as pom
from maya_pini.utils import use_tmp_ns


class TestSanityCheck(unittest.TestCase):

    @use_tmp_ns
    def test_check_uvs(self):

        _check = sanity_check.find_check('CheckUVs', task='model')

        # Setup node with uvs in wrong map
        _cube = pom.CMDS.polyCube()
        assert single(_cube.cmds.polyUVSet(query=True, currentUVSet=True)) == 'map1'
        _cube.cmds.polyUVSet(newUVSet='blah', uvSet='map1', copy=True)
        cmds.polyMapDel(_cube.to_attr('map[:]'))
        _cube.cmds.polyUVSet(currentUVSet=True, uvSet='blah')
        assert single(_cube.cmds.polyUVSet(query=True, currentUVSet=True)) == 'blah'

        # Apply check
        assert single(_cube.cmds.polyUVSet(query=True, currentUVSet=True)) != 'map1'
        assert len(_cube.cmds.polyUVSet(query=True, allUVSets=True)) != 1
        scc_maya_asset._fix_uvs(_cube.node)
        assert single(_cube.cmds.polyUVSet(query=True, currentUVSet=True)) == 'map1'
        assert len(_cube.cmds.polyUVSet(query=True, allUVSets=True)) == 1
