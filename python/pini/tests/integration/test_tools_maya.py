# pylint: disable=import-error,abstract-method,redundant-keyword-arg

import inspect
import logging
import pprint
import unittest

from maya import cmds

from pini import dcc, pipe, testing
from pini.dcc import export
from pini.tools import sanity_check
from pini.utils import single, PyFile, abs_path, assert_eq

from pini.tools.sanity_check import utils
from pini.tools.sanity_check.core import sc_check, sc_maya_check
from pini.tools.sanity_check import core
from pini.tools.sanity_check.checks import (
    scc_maya, scc_maya_asset, scc_maya_render)
from pini.tools.sanity_check.core import sc_checks

from maya_pini import open_maya as pom
from maya_pini.utils import use_tmp_ns

_LOGGER = logging.getLogger(__name__)


class TestSanityCheck(unittest.TestCase):

    def test_task_and_action_filters(self):

        assert sanity_check.find_check(
            'CheckAssetHierarchy', task='model')
        assert not sanity_check.find_check(
            'CheckAssetHierarchy', task='lookdev', catch=True)
        assert sanity_check.find_check(
            'CheckAssetHierarchy', task='lookdev', action='ModelPublish')

        assert sanity_check.find_check(
            'CheckShaders', task='lookdev')
        assert not sanity_check.find_check(
            'CheckShaders', task='model', catch=True)
        assert not sanity_check.find_check(
            'CheckShaders', task='model', action='BasicPublish', catch=True,
            filter_='CheckShaders')
        assert not sanity_check.find_check(
            'CheckShaders', task='model', action='BasicPublish', catch=True)

        assert not sanity_check.find_check(
            'CheckModelGeo', task='rig', catch=True)
        assert not sanity_check.find_check(
            'CheckModelGeo', task='rig', action='BasicPublish', catch=True)
        assert not sanity_check.find_check(
            'CheckModelGeo', task='rig', action='BasicPublish', catch=True)

    def test_basic_checks_import(self):

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

    def test_check_asset_hierarchy(self):

        dcc.new_scene(force=True)

        _work_dir = pipe.CACHE.obt(testing.TEST_ASSET).find_work_dir(
            'rig', dcc_=dcc.NAME)
        _work = _work_dir.to_work(tag='tmp')
        _work.save(force=True)
        _check = sanity_check.find_check(
            'CheckAssetHierarchy', action='BasicPublish')
        _LOGGER.info('CHECK %s', _check)
        _req_nodes = {'RIG': {'ABC': None}}

        # Check empty scene
        _check.reset_and_run(req_nodes=_req_nodes)
        assert len(_check.fails) == 2
        assert _check.fails[0].msg == 'Missing node "|RIG"'
        assert _check.fails[1].msg == 'Missing node "|RIG|ABC"'

        # Check single non-tfm
        cmds.polySphere()
        _check.reset_and_run(req_nodes=_req_nodes)
        pprint.pprint(_check.fails)
        assert len(_check.fails) == 1
        _fail = single(_check.fails)
        assert _fail.msg == 'No top level "RIG" group'
        assert not cmds.objExists('RIG')
        _fail.fix()
        assert cmds.objExists('RIG')
        assert cmds.objExists('pSphere1')

        # Check single tfm
        cmds.delete('RIG')
        assert not pom.find_nodes(default=False, top_node=True)
        cmds.group(empty=True, name='blah')
        _check.reset_and_run(req_nodes=_req_nodes)
        pprint.pprint(_check.fails)
        assert len(_check.fails) == 1
        _fail = single(_check.fails)
        assert _fail.msg == 'Badly named top node "blah" (should be "RIG")'
        assert not cmds.objExists('RIG')
        _fail.fix()
        assert cmds.objExists('RIG')

        # Check build hierarchy
        _check.reset_and_run(req_nodes=_req_nodes)
        pprint.pprint(_check.fails)
        assert len(_check.fails) == 1
        _fail = single(_check.fails)
        assert _fail.msg == 'Missing node "|RIG|ABC"'
        assert not cmds.objExists('ABC')
        _fail.fix()
        assert cmds.objExists('ABC')

        # Check top nodes outside grp
        cmds.group(empty=True, name='blah')
        _check.reset_and_run(req_nodes=_req_nodes)
        pprint.pprint(_check.fails)
        assert len(_check.fails) == 1
        _fail = single(_check.fails)
        assert _fail.msg == 'Top node "blah" outside "RIG"'
        assert cmds.objExists('|blah')
        _fail.fix()
        assert not cmds.objExists('|blah')
        assert cmds.objExists('|RIG|blah')

    def test_check_cache_set(self):

        dcc.new_scene(force=True)

        _ety = pipe.CACHE.obt(testing.TEST_ASSET)
        _mdl_pub = pipe.CACHE.obt(testing.TEST_JOB).find_publish(
            task='model', ver_n='latest', asset=testing.TEST_ASSET.asset,
            tag=pipe.DEFAULT_TAG, asset_type='char', extn='ma',
            versionless=False)
        _mdl = pipe.CACHE.obt(_mdl_pub)
        _work_dir = _ety.find_work_dir(
            'rig', dcc_=dcc.NAME)
        _work = _work_dir.to_work(tag='tmp')
        _work.save(force=True)
        _check = sanity_check.find_check(
            'CheckCacheSet', action='BasicPublish')
        _LOGGER.info('CHECK %s', _check)

        # Check empty scene
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert _fail.msg == 'Missing cache set'

        # Check multiple top nodes
        for _ in range(2):
            _cube = pom.CMDS.polyCube()
            _cube.add_to_set('cache_SET')
            _cube.add_to_grp('RIG')
        _check.reset_and_run()
        assert len(_check.fails) == 2
        assert_eq(
            _check.fails[0].msg,
            'Node "pCube1" has badly named shape node "pCubeShape1" (should be '
            '"pCube1Shape")')
        for _fail in _check.fails:
            _fail.fix()
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert 'multiple top nodes' in _fail.msg

        # Check referenced geo in cache set
        export.set_pub_refs_mode(export.PubRefsMode.REMOVE)
        cmds.delete('cache_SET')
        _mdl_ref = dcc.create_ref(_mdl, namespace='model', group='RIG')
        _ref_set = _mdl_ref.to_node('cache_SET')
        _grp = pom.CMDS.polyCube().add_to_grp('LGT')
        _grp.add_to_grp('RIG')
        _grp.add_to_set(_ref_set)
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert _fail.msg == 'Missing cache set'
        _fail.fix()
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert _fail.msg == 'Empty cache set'
        _fail.fix()
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert_eq(
            _fail.msg,
            'Referenced geo in cache set but references mode is set to '
            '"Remove" (should be "Import into root namespace")')
        _fail.fix()
        assert export.get_pub_refs_mode() == export.PubRefsMode.IMPORT_TO_ROOT
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert_eq(_fail.msg, 'Node "pCube3" has badly named shape node "pCubeShape1" (should be "pCube3Shape")')
        _fail.fix()
        _check.reset_and_run()
        assert not _check.fails

        # Check mutliple top nodes in refd cache set
        cmds.delete('cache_SET')
        assert export.get_pub_refs_mode() == export.PubRefsMode.IMPORT_TO_ROOT
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert _fail.fix
        _fail.fix()
        assert cmds.sets('model:cache_SET', query=True) == ['ABC']
        _check.reset_and_run()
        assert not _check.fails

        # Check dup nodes
        _cube, _ = cmds.polyCube(name='pCube3')
        _LOGGER.info('CUBE %s', _cube)
        assert '|' in _cube
        cmds.parent(_cube, 'ABC')
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert_eq(_fail.msg, 'Duplicate name "pCube3" in "model:cache_SET". This will cause errors on abc export.')
        _fail.fix()
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        assert not _check.fails

        # Check empty cset
        assert not cmds.objExists('cache_SET')
        cmds.select(clear=True)
        cmds.sets(name='cache_SET')
        assert not cmds.sets('cache_SET', query=True)
        _check.reset_and_run()
        pprint.pprint(_check.fails)
        _fail = single(_check.fails)
        assert_eq(_fail.msg, 'Empty cache set')
        _check.reset_and_run(top_node_priority=['ABC', 'RIG'])
        _fail = single(_check.fails)
        assert_eq(_fail.msg, 'Empty cache set')
        _fail.fix()
        assert cmds.sets('cache_SET', query=True) == ['ABC']

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
