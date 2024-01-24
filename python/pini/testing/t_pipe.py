"""Tools for testing pipeline."""

import logging
import os
import unittest

from pini import pipe, dcc

from .t_tools import TEST_DIR

_LOGGER = logging.getLogger(__name__)

_PINI_TEST_JOB = os.environ.get('PINI_TEST_JOB')
_PINI_TEST_SEQUENCE = os.environ.get('PINI_TEST_SEQUENCE', 'Testing')
_PINI_TEST_SHOT = os.environ.get('PINI_TEST_SHOT', 'test000')
_PINI_TMP_SHOT = os.environ.get('PINI_TMP_SHOT', 'test999')
_PINI_TEST_ASSET = os.environ.get('PINI_TEST_ASSET', 'test')
_PINI_TMP_ASSET = os.environ.get('PINI_TMP_ASSET', 'tmp')

# Setup test entities
TEST_JOB = TEST_SEQUENCE = TMP_SHOT = TEST_SHOT = TEST_ASSET = TMP_ASSET = None
if _PINI_TEST_JOB:
    TEST_JOB = pipe.to_job(_PINI_TEST_JOB)
    if _PINI_TEST_SEQUENCE:
        TEST_SEQUENCE = TEST_JOB.to_sequence(_PINI_TEST_SEQUENCE, catch=True)
    if TEST_SEQUENCE and _PINI_TEST_SHOT:
        TEST_SHOT = TEST_SEQUENCE.to_shot(_PINI_TEST_SHOT)
    if TEST_SEQUENCE and _PINI_TMP_SHOT:
        TMP_SHOT = TEST_SEQUENCE.to_shot(_PINI_TMP_SHOT)
    if _PINI_TEST_ASSET:
        TEST_ASSET = TEST_JOB.to_asset(
            asset_type='char', asset=_PINI_TEST_ASSET)
    if _PINI_TMP_ASSET:
        TMP_ASSET = TEST_JOB.to_asset(
            asset_type='char', asset=_PINI_TMP_ASSET)


class CTmpPipeTestCase(unittest.TestCase):
    """Test case which sets pini to a jobs root in TMP for testing."""

    _tmp_jobs_root = TEST_DIR.to_subdir('Projects')
    _tmp_job_dir = _tmp_jobs_root.to_subdir('Test Pluto')
    _tmp_job = None

    def setUp(self):
        """Executed on begin test."""
        _LOGGER.info('BEGIN TmpJobTestCase')
        self._jobs_root = pipe.JOBS_ROOT
        pipe.set_jobs_root(self._tmp_jobs_root.path)
        self._tmp_job = pipe.CPJob(self._tmp_job_dir)
        self._tmp_job.flush(force=True)
        self._tmp_job.setup_cfg('Pluto')
        self._tmp_job.set_setting(shotgrid={'disable': True})

    def tearDown(self):
        """Executed on complete test."""
        pipe.set_jobs_root(self._jobs_root)


def check_test_asset(force=False):
    """Check test asset publishes and outputs exist.

    Args:
        force (bool): lose current scene without confirmation
    """
    from maya_pini import open_maya as pom, tex
    _LOGGER.info('CHECK TEST ASSET %s', TEST_ASSET)

    _asset_c = pipe.CACHE.obt(TEST_ASSET)
    _tag = _asset_c.job.cfg['tokens']['tag']['default']
    _mod_task = os.environ.get('PINI_PIPE_MODEL_TASK', 'model')
    _ld_task = os.environ.get('PINI_PIPE_LOOKDEV_TASK', 'lookdev')

    # Check model
    _mdl_work = _asset_c.to_work(task=_mod_task)
    if not _mdl_work.exists():
        dcc.new_scene(force=force)
        _cube = pom.CMDS.polyCube(name='cube_GEO')
        _grp = _cube.add_to_grp('MDL')
        _grp.add_to_set('cache_SET')
        _mdl_work.save(force=True)
    if not _asset_c.find_publishes(task=_mod_task):
        _mdl_work.load(lazy=True)
        _pub = dcc.find_export_handler(action='publish', filter_='model')
        _pub.publish(force=True)
    _mdl_pub = _asset_c.find_publish(
        task=_mod_task, ver_n='latest', tag=_tag, versionless=False)
    assert _mdl_pub

    # Check rig
    _rig_work = _asset_c.to_work(task='rig')
    if not _rig_work.exists():
        dcc.new_scene(force=force)
        _mdl_work.load()
        _geo = pom.CTransform('MDL').rename('GEO')
        _ctrl = pom.CMDS.circle(name='cube_CTRL', normal=pom.Y_AXIS)
        _geo.parent(_ctrl)
        _ctrl.add_to_grp('RIG')
        _rig_work.save(force=True)
    if not _asset_c.find_publishes(task='rig'):
        _rig_work.load(lazy=True)
        _pub = dcc.find_export_handler(action='publish', filter_='basic')
        _pub.publish(force=True)
    assert _asset_c.find_publish(
        task='rig', ver_n='latest', tag=_tag, versionless=False)

    # Check lookdev
    _ld_work = _asset_c.to_work(task=_ld_task)
    _LOGGER.info(' - LD WORK %s', _ld_work)
    if not _ld_work.exists():
        dcc.new_scene(force=force)
        _ref = dcc.create_ref(_mdl_pub, namespace='model', group='MODEL')
        _shd = tex.create_lambert(col='CornflowerBlue', name='blue_MTL')
        _shd.apply_to(_ref.ref.to_node('cube_GEO'))
        _ld_work.save(force=True)
    _ld_pub = _asset_c.find_publish(
        task=_ld_task, ver_n='latest', tag=_tag, versionless=False)
    if not _ld_pub:
        _ld_work.load(lazy=True)
        _pub = dcc.find_export_handler(action='publish', filter_='lookdev')
        _pub.publish(force=True, version_up=False)
        _ld_pub = _asset_c.find_publishes(
            task=_ld_task, ver_n='latest', tag=_tag, versionless=False)
        dcc.new_scene(force=True)
    assert _ld_pub
