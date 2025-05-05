"""Tools for testing pipeline."""

import logging
import os
import pprint

from pini import pipe, dcc
from pini.dcc import export
from pini.utils import File, cache_result

_LOGGER = logging.getLogger(__name__)

_PINI_TEST_JOB = os.environ.get('PINI_TEST_JOB', 'Testing')
_PINI_TEST_SEQUENCE = os.environ.get('PINI_TEST_SEQUENCE', 'Testing')
_PINI_TEST_SHOT = os.environ.get('PINI_TEST_SHOT', 'test000')
_PINI_TMP_SHOT = os.environ.get('PINI_TMP_SHOT', 'test999')
_PINI_TEST_ASSET = os.environ.get('PINI_TEST_ASSET', 'test')
_PINI_TMP_ASSET = os.environ.get('PINI_TMP_ASSET', 'tmp')

# Setup test entities
TEST_JOB = TEST_SEQUENCE = TMP_SHOT = TEST_SHOT = TEST_ASSET = TMP_ASSET = None
if _PINI_TEST_JOB:
    TEST_JOB = pipe.to_job(_PINI_TEST_JOB)
if TEST_JOB.exists():
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
        export.model_publish(export_abc=True, export_fbx=True, force=True)
    _mdl_pub_g = _asset_c.find_publish(
        task=_mod_task, ver_n='latest', tag=_mdl_work.tag, versionless=False,
        type_='publish', extn='ma')
    _mdl_pub = pipe.CACHE.obt(_mdl_pub_g)
    assert _mdl_pub.path == _mdl_pub_g.path
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

    # Find publish
    _kwargs = dict(  # pylint: disable=use-dict-literal
        task='lookdev', ver_n='latest', tag=_to_default_tag(),
        versionless=False, output_type='lookdev', extn='ma')
    _ld_pubs = _asset_c.find_publishes(**_kwargs)
    if len(_ld_pubs) > 1:
        pprint.pprint(_ld_pubs)
        raise RuntimeError
    _ld_pub = _asset_c.find_publish(catch=True, **_kwargs)
    if not _ld_pub:
        _ld_work.load(lazy=True)
        export.lookdev_publish(force=True, version_up=False)
        _ld_pub = _asset_c.find_publish(
            task='lookdev', ver_n='latest', tag=_to_default_tag(),
            versionless=False)
        assert _ld_pub
        dcc.new_scene(force=True)

    assert _ld_pub


def _check_test_assets(force=False):
    """Check test asset publishes and outputs exist.

    Args:
        force (bool): lose current scene without confirmation
    """
    from maya_pini import open_maya as pom
    _LOGGER.info('CHECK TEST ASSET %s', TEST_ASSET)

    _test_entity(TEST_ASSET)
    _test_entity(TMP_ASSET)

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
        _pub = dcc.find_export_handler('publish', filter_='basic')
        _pub.publish(force=True)
    assert _asset_c.find_publish(
        task='rig', ver_n='latest', tag=_rig_work.tag, versionless=False,
        extn='ma')

    _check_lookdev(force=force, model_pub=_mdl_pub)


def check_test_paths(force=False):
    """Check all test asset and shot components have been created.

    Args:
        force (bool): lost unsaved data without confirmation
    """
    if not TEST_JOB.exists():
        TEST_JOB.create()
        pipe.CACHE.reset()

    if dcc.NAME == 'maya':
        _check_test_assets(force=force)
        _check_test_shots(force=force)


def _check_test_shots(force=False):
    """Check test asset publishes and outputs exist.

    Args:
        force (bool): lose current scene without confirmation
    """

    _test_entity(TEST_SHOT)
    _test_entity(TMP_SHOT)
    _shot = pipe.CACHE.obt(TEST_SHOT)
    assert _shot

    # Check test abc
    for _cam in (True, False):
        assert find_test_abc(camera=_cam)
    find_test_vdb(force=force)

    # Check test render
    find_test_render()


def _build_test_abcs(work, force):
    """Build test abcs.

    Args:
        work (CPWork): work file to export from
        force (bool): lose unsaved changes without confirmation
    """
    from maya_pini import m_pipe, open_maya as pom

    _LOGGER.info(' - WORK %s', work)
    _rig = find_test_rig()
    dcc.new_scene(force=force)
    dcc.set_range(1001, 1005)

    # Setup rig
    _ref = dcc.create_ref(_rig, namespace='test01')

    # Setup camera
    _cam = pom.CMDS.camera(name='renderCam')
    if _cam != 'renderCam':
        _cam = _cam.rename('renderCam')
    assert _cam == 'renderCam'

    work.save(force=True)
    _cbls = m_pipe.find_cacheables()
    assert len(_cbls) == 2
    export.cache(_cbls)


def find_test_abc(camera=False, force=False):
    """Find test abc output, creating if needed.

    Args:
        camera (bool): use test camera
        force (bool): lose unsaved changes without confirmation

    Returns:
        (CCPOutputFile): abc
    """

    _ns = 'renderCam' if camera else 'test01'
    _ety = pipe.CACHE.obt(TEST_SHOT)
    _work = _ety.to_work(task='anim', ver_n=1)
    _abc = _ety.find_output(
        task='anim', ver_n='latest', tag=_work.tag, extn='abc',
        output_name=_ns, versionless=False, catch=True)
    if not _abc:
        _build_test_abcs(_work, force=force)
        _abc = _ety.find_output(
            task='anim', ver_n='latest', tag=_work.tag, extn='abc',
            output_name=_ns, versionless=False, catch=True)
        assert _abc
    return _abc


def find_test_lookdev():
    """Find test lookdev output.

    Returns:
        (CCPOutputFile): lookdev publish
    """
    _tag = _to_default_tag()
    _pub = pipe.CACHE.obt(TEST_ASSET).find_publish(
        task='lookdev', ver_n='latest', tag=_tag, extn='ma',
        versionless=False, content_type='ShadersMa')
    return pipe.CACHE.obt(_pub)


def find_test_model():
    """Find test model output.

    Returns:
        (CCPOutputFile): model publish
    """
    _tag = _to_default_tag()
    _pub = pipe.CACHE.obt(TEST_ASSET).find_publish(
        task='model', ver_n='latest', tag=_tag, extn='ma',
        versionless=False)
    return pipe.CACHE.obt(_pub)


def find_test_render(force=False):
    """Find test render output, creating if needed.

    Args:
        force (bool): lose unsaved changes without confirmation

    Returns:
        (CCPOutputSeq): render
    """
    from maya_pini.utils import render
    _ety = pipe.CACHE.obt(TEST_SHOT)
    _ren = _ety.find_output(
        task='lighting', ver_n='latest', tag=_to_default_tag(), extn='jpg',
        versionless=False, catch=True)
    if not _ren:
        dcc.new_scene(force=force)
        _work_dir = _ety.find_work_dir('lighting', catch=True)
        if _work_dir:
            _work = _work_dir.to_work(ver_n=1)
        else:
            _work = _ety.to_work(task='lighting', ver_n=1)
        dcc.set_range(1001, 1005)
        _work.save(force=True)
        _out = _work.to_output('render', output_name='masterLayer', extn='jpg')
        if not _out.exists():
            render(_out)
        if pipe.MASTER == 'shotgrid':
            from pini.pipe import shotgrid
            shotgrid.create_pub_file_from_output(_out)
        _ren = _ety.find_output(
            task='lighting', ver_n='latest', tag=_to_default_tag(), extn='jpg',
            versionless=False, catch=True, force=True)
        assert _ren
    return _ren


def find_test_rig():
    """Find test rig output.

    Returns:
        (CCPOutputFile): rig publish
    """
    _pub = pipe.CACHE.obt(TEST_ASSET).find_publish(
        task='rig', ver_n='latest', tag=_to_default_tag(), versionless=False,
        extn='ma')
    return pipe.CACHE.obt(_pub)


@cache_result
def find_test_vdb(force=False):
    """Find test vdb sequence.

    For now these are just empty files.

    Args:
        force (bool): lose unsaved data without confirmation

    Returns:
        (CPOutputSeq): test vdbs
    """
    _name = 'test'
    _ety = pipe.CACHE.obt(TEST_SHOT)
    _work = _ety.to_work(task='fx', ver_n=1)
    _vdb = _ety.find_output(
        task='fx', ver_n='latest', tag=_work.tag, extn='vdb',
        output_name=_name, versionless=False, catch=True)
    if not _vdb:
        _metadata = export.build_metadata('cache', src=_work)
        _vdb = _work.to_output(
            'cache_seq', output_name=_name, extn='vdb')
        _LOGGER.info(' - VDB %s', _vdb)
        for _frame in range(1001, 1006):
            File(_vdb[_frame]).touch()
        if pipe.MASTER == 'shotgrid':
            from pini.pipe import shotgrid
            shotgrid.create_pub_file_from_output(_vdb)
        _vdb.set_metadata(_metadata)
        pipe.CACHE.reset()
        _vdb = pipe.CACHE.obt(_vdb)
        assert _vdb
    return _vdb


def _test_entity(entity):
    """Test the given entity exists.

    Args:
        entity (CPEntity): entity to check

    Returns:
        (CCPEntity): cacheable version of entity
    """
    _ety_c = pipe.CACHE.obt(entity)
    if not _ety_c:
        entity.create(force=True)
        pipe.CACHE.reset()
        _ety_c = pipe.CACHE.obt(entity)
    assert _ety_c
    return _ety_c


@cache_result
def _to_default_tag():
    """Obtain default tag for test job.

    Returns:
        (str): default tag (eg. main)
    """
    return pipe.DEFAULT_TAG or TEST_JOB.cfg['tokens']['tag']['default']
