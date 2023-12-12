import logging
import unittest

from maya import cmds

from pini import dcc, testing
from pini.dcc import pipe_ref

from maya_pini import open_maya as pom

_LOGGER = logging.getLogger(__name__)


class TestDCC(unittest.TestCase):

    def test_swap_refs(self):

        testing.check_test_asset()

        # Clean up
        _ref = dcc.find_pipe_ref('test', catch=True)
        if _ref:
            _ref.delete(force=True)
        for _node in ['CHAR']:
            if cmds.objExists(_node):
                cmds.delete(_node)
        assert not cmds.objExists('CHAR')

        # Test mapping
        _model = testing.TEST_ASSET.find_publish(task='model', versionless=True)
        _LOGGER.info('MODEL %s', _model)
        _ass_gz = _model.find_rep(extn='gz')
        _rig = _ass_gz.find_rep(task='rig')
        _LOGGER.info('MODEL %s', _rig.find_rep(task='model'))
        assert _rig.find_rep(task='model') == _model
        assert _ass_gz.find_rep(task='model') == _model

        # Create model ref
        _ref = dcc.create_ref(_model, namespace='test', group='BLAH')
        pom.CPoint(0, 4, 0).apply_to(_ref.node)
        assert _ref.output == _model
        assert isinstance(_ref, pipe_ref.CMayaReference)
        assert _ref.node.ty.get_val() == 4
        assert _ref.node.to_parent().name() == 'BLAH'
        assert not cmds.objExists('CHAR')

        # Swap to ass gz
        _ass_gz = _ref.find_rep(extn='gz')
        assert _ass_gz
        _ref = _ref.update(_ass_gz)
        assert _ref.output == _ass_gz
        assert isinstance(_ref, pipe_ref.CMayaAiStandIn)
        assert _ref.node.ty.get_val() == 4
        assert _ref.node.to_parent().name() == 'BLAH'
        assert _ref.namespace == 'test'
        assert not cmds.objExists('CHAR')

        # Swap to rig
        _rig = _ref.find_rep(task='rig')
        assert _rig
        _ref = _ref.update(_rig)
        assert _ref.output == _rig
        assert isinstance(_ref, pipe_ref.CMayaReference)
        assert _ref.node.ty.get_val() == 4
        assert _ref.node.to_parent().name() == 'BLAH'
        assert not cmds.objExists('CHAR')
        assert _ref.namespace == 'test'

        # Test no parent
        _ref = dcc.create_ref(_model, namespace='test2', group=None)
        assert not _ref.node.to_parent()
        _ref = _ref.update(_ass_gz)
        assert not _ref.node.to_parent()
