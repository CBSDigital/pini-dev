# pylint: disable=import-error,abstract-method

import inspect
import unittest

from maya import cmds

from pini.tools import sanity_check
from pini.tools.sanity_check import utils
from pini.utils import single, PyFile, abs_path

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
        utils.fix_uvs(_cube.node)
        assert single(_cube.cmds.polyUVSet(query=True, currentUVSet=True)) == 'map1'
        assert len(_cube.cmds.polyUVSet(query=True, allUVSets=True)) == 1

    def test_basic_checks_import(self):

        from pini.tools.sanity_check.core import sc_check, sc_maya_check
        from pini.tools.sanity_check import core
        from pini.tools.sanity_check.checks import (
            scc_maya, scc_maya_asset, scc_maya_render)
        from pini.tools.sanity_check.core import sc_checks

        assert scc_maya.CheckCacheables
        assert sanity_check.SCCheck is core.SCCheck
        assert sanity_check.SCCheck is sc_check.SCCheck
        assert sanity_check.SCMayaCheck is core.SCMayaCheck
        assert sanity_check.SCMayaCheck is sc_maya_check.SCMayaCheck

        class _Check(sanity_check.SCCheck):
            pass

        assert issubclass(_Check, sanity_check.SCCheck)
        assert issubclass(_Check, sc_check.SCCheck)
        assert issubclass(_Check, core.SCCheck)

        class _MayaCheck(sanity_check.SCMayaCheck):
            pass

        assert issubclass(_MayaCheck, sanity_check.SCCheck)
        assert issubclass(_MayaCheck, sc_check.SCCheck)
        assert issubclass(_MayaCheck, core.SCCheck)

        _mro = inspect.getmro(scc_maya.CheckCacheables)
        assert object in _mro
        assert _mro[0] is scc_maya.CheckCacheables
        assert _mro[1] is sanity_check.SCMayaCheck
        assert _mro[-1] is object

        assert issubclass(scc_maya.CheckCacheables, sanity_check.SCCheck)
        assert issubclass(scc_maya.CheckCacheables, sc_check.SCCheck)
        assert issubclass(scc_maya.CheckCacheables, core.SCCheck)

        for _mod in [scc_maya, scc_maya_asset, scc_maya_render]:
            _py = PyFile(abs_path(_mod.__file__))
            assert sc_checks._checks_from_py(_py)
