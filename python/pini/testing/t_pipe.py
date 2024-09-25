"""Tools for testing pipeline."""

import logging
import os

from pini import pipe, dcc
from pini.utils import File

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


def _check_model(force):
    """Check test model publish.

    Args:
        force (bool): lose current scene without confirmation

    Returns:
        (CPOutputFile): model publish
    """
    from maya_pini import open_maya as pom

    _asset_c = pipe.CACHE.obt(TEST_ASSET)
    _mod_task = os.environ.get('PINI_PIPE_MODEL_TASK', 'model')

    # Check work
    _mdl_work = _asset_c.to_work(task=_mod_task)
    if not _mdl_work.exists():
        dcc.new_scene(force=force)
        _cube = pom.CMDS.polyCube(name='cube_GEO')
        _grp = _cube.add_to_grp('MDL')
        _grp.add_to_set('cache_SET')
        _mdl_work.save(force=True)
    assert File(_mdl_work).exists()

    # Check publish
    _pubs = [
        _pub for _pub in _asset_c.find_publishes(task=_mod_task, force=True)
        if File(_pub).exists()]
    if not _pubs:
        _mdl_work.load(lazy=True)
        _pub = dcc.find_export_handler(action='publish', filter_='model')
        _pub.publish(force=True)
    _mdl_pub_g = _asset_c.find_publish(
        task=_mod_task, ver_n='latest', tag=pipe.DEFAULT_TAG, versionless=False,
        type_='publish')
    _mdl_pub = pipe.CACHE.obt(_mdl_pub_g)
    assert _mdl_pub
    assert _mdl_pub.exists()
    _LOGGER.info(' - MODEL PUB %s', _mdl_pub)
    assert File(_mdl_pub.path).exists()

    return _mdl_work, _mdl_pub


def _check_lookdev(force, model_pub):
    """Check test lookdev publish.

    Args:
        force (bool): lose current scene without confirmation
        model_pub (CPOutputFile): model publish
    """
    from maya_pini import tex
    _LOGGER.info('CHECK LOOKDEV')

    _asset_c = pipe.CACHE.obt(TEST_ASSET)
    _work_dir = _asset_c.find_work_dir('lookdev', dcc_=dcc.NAME, catch=True)
    if not _work_dir:
        _work_dir = _asset_c.to_work_dir('lookdev')
    _LOGGER.info(' - WORK DIR %s', _work_dir)

    # Check lookdev
    _ld_work = _work_dir.to_work()
    _LOGGER.info(' - LD WORK %s', _ld_work)
    if not _ld_work.exists():
        dcc.new_scene(force=force)
        _ref = dcc.create_ref(model_pub, namespace='model', group='MODEL')
        _shd = tex.create_lambert(col='CornflowerBlue', name='blue_MTL')
        _shd.assign_to(_ref.ref.to_node('cube_GEO'))
        _ld_work.save(force=True)

    _ld_pub = _asset_c.find_publish(
        task='lookdev', ver_n='latest', tag=pipe.DEFAULT_TAG, versionless=False,
        output_type='lookdev')
    if not _ld_pub:
        _ld_work.load(lazy=True)
        _pub = dcc.find_export_handler('lookdev')
        _pub.publish(force=True, version_up=False)
        _ld_pub = _asset_c.find_publishes(
            task='lookdev', ver_n='latest', tag=pipe.DEFAULT_TAG,
            versionless=False)
        dcc.new_scene(force=True)
    assert _ld_pub


def check_test_asset(force=False):
    """Check test asset publishes and outputs exist.

    Args:
        force (bool): lose current scene without confirmation
    """
    from maya_pini import open_maya as pom
    _LOGGER.info('CHECK TEST ASSET %s', TEST_ASSET)

    _asset_c = pipe.CACHE.obt(TEST_ASSET)

    _mdl_work, _mdl_pub = _check_model(force=force)

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
        task='rig', ver_n='latest', tag=pipe.DEFAULT_TAG, versionless=False)

    _check_lookdev(force=force, model_pub=_mdl_pub)
