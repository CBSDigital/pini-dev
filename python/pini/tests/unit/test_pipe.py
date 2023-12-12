import logging
import time
import unittest

from pini import pipe, testing, dcc
from pini.pipe import cache
from pini.utils import File, single, flush_caches

_LOGGER = logging.getLogger(__name__)


class TestPipe(unittest.TestCase):

    def test_templates(self):

        assert testing.TEST_JOB

        _pattern = '{blah}/{blue}/{blee}'
        _tmpl = pipe.CPTemplate('test', _pattern)
        _tmpl = _tmpl.apply_data(blue='BLUE')
        assert 'blue' in _tmpl.embedded_data
        _tmpl = _tmpl.apply_data(blee='BLEE')
        assert 'blue' in _tmpl.embedded_data
        _data = _tmpl.parse('BLAH/BLUE/BLEE')
        assert 'blue' in _data

        # Test tag as vertical - this was causing bad template to be selected
        # as it was being matched as a version
        if testing.TEST_JOB.find_templates('publish'):
            _tmpls = [
                testing.TEST_JOB.find_template(
                    'publish', profile='asset',
                    has_key={'tag': True, 'ver': True, 'output_type': False}),
                testing.TEST_JOB.find_template(
                    'publish', profile='asset', catch=True,
                    has_key={'tag': True, 'ver': False, 'output_type': False}),
            ]
            _tmpls = [_tmpl for _tmpl in _tmpls if _tmpl]
            assert _tmpls
            for _tmpl in _tmpls:
                _LOGGER.info('TMPL %s', _tmpl)
                _out = testing.TEST_SHOT.to_output(
                    _tmpl, task='anim', tag='vertical', output_name='test')
                _LOGGER.info('OUT %s', _out)
                _out = pipe.CPOutput(_out.path)
                _LOGGER.info('OUT %s', _out)
        else:
            _LOGGER.info('NO PUBLISH TEMPLATES FOUND')

    def test_output_seq_dirs(self):

        testing.enable_file_system(True)

        if not testing.TEST_JOB.find_templates('render'):
            _LOGGER.info('NO RENDER TEMPLATES SET UP')
            return

        _shot = testing.TMP_SHOT
        _shot.flush(force=True)

        _work = _shot.to_work(tag='SeqCacheTest', task='lighting')
        _work.touch()
        _seq = _work.to_output('render', output_name='masterLayer', extn='exr')
        assert not _seq.work_dir
        _seq.delete(force=True)
        assert not _seq.exists()
        _frame_1 = File(_seq[1])
        _frame_2 = File(_seq[2])

        flush_caches()
        pipe.CACHE.reset()
        assert _work.exists()
        _work_c = pipe.CACHE.obt_work(_work)
        _shot_c = pipe.CACHE.obt_entity(_shot)
        assert _work_c.entity is _shot_c
        assert not _shot.find_outputs()
        assert not _shot.find_output_seq_dirs()
        assert not _work_c.find_outputs(force=True)
        assert not _work_c.find_outputs()

        # Make seq dir to allow cache to build
        _frame_1.to_dir().mkdir()
        assert _shot.find_output_seq_dirs()
        _seq_dir = single(_shot.find_output_seq_dirs())
        assert _seq_dir.ver_n == 1
        assert _seq_dir.task == 'lighting'
        assert _seq_dir.tag == 'SeqCacheTest'
        _LOGGER.info('SEQ DIR %s', _seq_dir)
        assert not _shot.find_outputs()
        assert not _work.find_outputs()
        assert not _work_c.find_outputs()
        assert not _shot_c._read_output_globs()
        _LOGGER.info('FORCE FIND OUTPUTS %s', _work_c)
        assert not _work_c.find_outputs(force=True)
        assert _shot._read_output_globs()
        assert _shot.find_output_seq_dirs()
        assert _shot_c._read_output_globs()
        _LOGGER.info('GLOBS %s', _shot_c._read_output_globs())
        assert _shot.find_output_seq_dirs()
        assert _shot_c.find_output_seq_dirs()

        # Create frame so seq exists
        _frame_1.touch()
        assert _seq.exists(force=True)
        assert _shot.find_outputs()
        assert _work.find_outputs()
        assert _shot_c.find_output_seq_dirs()
        assert not _shot_c.find_outputs()
        assert not _work_c.find_outputs()
        _LOGGER.info('WORK C %s', _work_c)
        _LOGGER.info('SEQ DIRS %s', _shot_c.find_output_seq_dirs())
        assert _shot_c.find_output_seq_dirs(force=True)
        _seq_dir_c = single(_shot_c.find_output_seq_dirs())
        _LOGGER.info('SEQ DIR C %s', _seq_dir_c)
        assert isinstance(_seq_dir_c, cache.CCPOutputSeqDir)
        assert _seq_dir_c.entity is _shot_c
        assert not _work_c.find_outputs()
        assert _shot_c is _work_c.entity
        assert _seq_dir.find_outputs()
        assert not _seq_dir_c.find_outputs()

        # Update cache
        assert _work_c.entity is _shot_c
        _LOGGER.info('FORCE FIND OUTPUTS %s', _work_c)
        assert _work_c is pipe.CACHE.obt_work(_work)
        assert _work_c.find_outputs(force=True)
        assert _frame_1.exists()
        assert _seq.exists(force=True)
        _LOGGER.info('SEQ %s', _seq)
        assert not _seq.work_dir
        assert _seq.find_vers()
        testing.enable_file_system(False)
        _seq_c = single(_work_c.find_outputs())
        _LOGGER.info('SEQ C %s', _seq_c)
        assert isinstance(_seq_c, cache.CCPOutputSeq)
        assert len(_seq_c.frames) == 1
        assert _seq_c.exists()
        assert _seq_c.find_vers()
        assert _seq_c.is_latest()

        # Try reading cache from disk
        testing.enable_file_system(True)
        _cache = pipe.CACHE
        _shot_c = _cache.obt_entity(_shot)
        _LOGGER.info('SHOT C %s', _shot_c)
        _seq_dir_c = single(_shot_c.find_output_seq_dirs())
        assert isinstance(_seq_dir_c, cache.CCPOutputSeqDir)
        _LOGGER.info('SEQ DIR C %s', _seq_dir_c)
        _seq_c = single(_seq_dir_c.find_outputs())
        assert isinstance(_seq_c, cache.CCPOutputSeq)

        # Delete frame
        testing.enable_file_system(True)
        _frame_1.delete(force=True)
        testing.enable_file_system(False)
        _LOGGER.info('DELETED FRAME 1')
        assert len(_seq_c.frames) == 1
        assert _work_c.find_outputs()
        assert _shot_c.find_outputs()
        assert _shot_c.find_output_seq_dirs()
        testing.enable_file_system(True)
        assert not _work.find_outputs()
        assert not _shot.find_outputs()
        _LOGGER.info('FORCE FIND OUTPUTS %s', _work_c)
        assert not _work_c.find_outputs(force=True)
        assert not _shot_c.find_outputs()
        assert _shot_c.find_output_seq_dirs()

        _shot.delete(force=True)

    def test_update_publish_cache(self):

        if not testing.TEST_JOB.find_templates('publish'):
            _LOGGER.info('NO PUBLISH TEMPLATES SET UP')
            return

        _shot = testing.TMP_SHOT
        _shot.flush(force=True)
        _cache = pipe.CACHE
        _shot_c = _cache.obt_entity(_shot)

        # Test mem caching
        _work_dir = _shot.to_work_dir(task='rig')
        _LOGGER.info('WORK DIR %s', _work_dir)
        _work = _work_dir.to_work()
        _out = _work.to_output('publish', output_type=None)
        assert not _shot.find_publishes()
        assert not _shot_c.find_publishes(force=True)
        _out.touch()
        assert _shot.find_publishes()
        assert not _shot_c.find_publishes()
        _LOGGER.info('FORCE RECACHE')
        assert _shot_c.find_publishes(force=True)
        _out.delete(force=True)
        assert not _shot.find_publishes()
        assert _shot_c.find_publishes()
        assert not _shot_c.find_publishes(force=True)

        # Test disk caching
        assert not pipe.CACHE.obt_entity(_shot).find_publishes()
        _out.touch()
        assert _shot_c.find_publishes(force=True)
        _yml = File(_shot_c.cache_fmt.format(func='_read_publishes_disk'))
        assert _yml.exists()
        assert _yml.read_yml()
        _LOGGER.info('YML %s', _yml.path)
        flush_caches()
        assert pipe.CACHE.obt_entity(_shot).find_publishes()
        _pub_c = single(pipe.CACHE.obt_entity(_shot).find_publishes())
        assert isinstance(_pub_c, cache.CCPOutput)
        _out.delete(force=True)
        flush_caches()
        assert pipe.CACHE.obt_entity(_shot).find_publishes()
        _pub_c = single(pipe.CACHE.obt_entity(_shot).find_publishes())
        assert isinstance(_pub_c, cache.CCPOutput)
        assert not pipe.CACHE.obt_entity(_shot).find_publishes(force=True)

        _shot.delete(force=True)

    def test_restore_output_cache_from_yml(self):

        if not testing.TEST_JOB.find_templates('publish'):
            _LOGGER.info('NO PUBLISH TEMPLATES SET UP')
            return

        _pub = testing.TMP_SHOT.to_output(
            'publish', output_type=None, task='rig')
        _pub.touch()
        pipe.CACHE.reset()
        _pub_c = pipe.CACHE.obt_output(_pub)
        assert isinstance(_pub_c.work_dir, cache.CCPWorkDir)
        testing.TEST_YML.write_yml(_pub_c, force=True)
        _pub_c = testing.TEST_YML.read_yml()
        assert isinstance(_pub_c.work_dir, cache.CCPWorkDir)

    def test_output_seqs(self):

        if not testing.TEST_JOB.find_templates('render'):
            _LOGGER.info('NO RENDER TEMPLATES SET UP')
            return

        # Reset test shot
        testing.enable_file_system(True)
        _shot = testing.TMP_SHOT
        _shot.flush(force=True)
        pipe.CACHE.reset()
        flush_caches()

        # Setup output
        _out = _shot.to_output(
            'render', task='anim', output_name='masterLayer')
        File(_out[1]).touch()
        assert _out.exists()
        _out.set_metadata({'blah': 1})

        # Make sure caches are set up
        _ety_c = pipe.CACHE.obt_entity(_out.path)
        _seq_dir_c = single(_ety_c.find_output_seq_dirs())
        _out_c = _ety_c.find_output(_out)
        assert _out_c is single(_seq_dir_c.find_outputs())
        assert _out_c.metadata

        # Make sure data is cached
        testing.enable_file_system(False)
        assert _seq_dir_c is single(_ety_c.find_output_seq_dirs(task=_out.task, ver_n=_out.ver_n))
        assert _ety_c.find_output(_out) is _out_c
        assert _out_c.metadata

        testing.enable_file_system(True)
        _shot.flush(force=True)

    def test_settings(self):

        testing.enable_file_system(True)
        assert testing.TEST_ASSET
        assert testing.TEST_SHOT
        pipe.CACHE.reset()

        # Check cache + settings parenting
        _job = pipe.CACHE.obt_job(testing.TEST_JOB)
        _seq = pipe.CACHE.obt_sequence(testing.TEST_SEQUENCE)
        assert _seq.job is _job
        assert _seq._settings_parent is _job
        _shot = pipe.CACHE.obt_entity(testing.TEST_SHOT)
        assert _shot.job is _job
        assert _shot.to_sequence() is _seq
        assert _seq._settings_parent is _job
        assert _shot._settings_parent is _seq
        _asset = pipe.CACHE.obt_entity(testing.TEST_ASSET)
        assert _asset.job is _job
        assert _asset._settings_parent is _job

        # Reset
        for _lvl in [_job, _seq, _shot]:
            _lvl.del_setting('blah')
            _lvl.flush_settings_bkps(force=True)

        assert 'blah' not in _job.settings
        assert 'blah' not in _shot.settings
        _job.set_setting(blah='hello')
        assert _job.settings['blah'] == 'hello'
        assert _shot.settings['blah'] == 'hello'

        _job.set_setting(blah='blee')
        assert _job.settings['blah'] == 'blee'
        assert _shot.settings['blah'] == 'blee'
        _seq.set_setting(blah='wow')
        assert _job.settings['blah'] == 'blee'
        assert _seq.settings['blah'] == 'wow'
        assert _shot.settings['blah'] == 'wow'
        _shot.set_setting(blah='waaar')
        assert _job.settings['blah'] == 'blee'
        assert _seq.settings['blah'] == 'wow'
        assert _shot.settings['blah'] == 'waaar'

        testing.enable_file_system(False)
        assert _job.settings
        assert _seq.settings
        assert _shot.settings
        testing.enable_file_system(True)


class TestCache(unittest.TestCase):

    def test_work_dir_outputs(self):

        if not testing.TEST_JOB.find_templates('publish'):
            _LOGGER.info('NO PUBLISH TEMPLATES SET UP')
            return

        _pub = testing.TEST_ASSET.find_publishes(task='model')[-1]
        _pub_c = pipe.CACHE.obt_output(_pub)
        _ety_c = pipe.CACHE.obt_entity(_pub.entity)
        assert isinstance(_pub_c, cache.CCPOutput)
        assert isinstance(_pub_c.work_dir, cache.CCPWorkDir)
        assert isinstance(_pub_c.work_dir.entity, cache.CCPEntity)
        assert isinstance(_pub_c.entity, cache.CCPEntity)
        assert _pub_c.entity is _ety_c
        assert _pub_c.work_dir.entity is _ety_c

    def test_reset_cache(self):

        _shot = testing.TMP_SHOT
        _shot.flush(force=True)

        pipe.CACHE.reset()
        _shot_c = pipe.CACHE.obt_entity(_shot)
        assert pipe.CACHE.obt_entity(_shot) is _shot_c
        pipe.CACHE.reset()
        assert pipe.CACHE.obt_entity(_shot) is not _shot_c


class CTPTestPipe(testing.CTmpPipeTestCase):

    def test_validate_token(self):

        _LOGGER.info('JOBS ROOT %s', pipe.JOBS_ROOT)
        _LOGGER.info('JOBS %s', pipe.find_jobs())
        _job = pipe.find_job('Testing')
        _LOGGER.info('JOB %s', _job)
        assert pipe.is_valid_token(
            token='output_name', value='aaa', job=_job)
        assert not pipe.is_valid_token(
            token='output_name', value='aaa.aaa', job=_job)

    # def test_pluto(self):

    #     pipe.CACHE.reset()

    #     # Setup test job
    #     _file = self._tmp_jobs_root.to_file(
    #         'Testing/assets/char.cubes/maya/rig/publish/cubes_main_v001.mb')
    #     _job = pipe.CPJob(_file)
    #     _job.flush(force=True)
    #     _job.setup_cfg('Pluto')
    #     _job.set_setting(disable_shotgrid=True)
    #     _LOGGER.info('JOB SETTINGS %s', _job.settings)
    #     _file.touch()
    #     assert _job.exists()
    #     _LOGGER.info('CFG FILE %s', _job.cfg_file.path)
    #     assert _job.cfg_file.exists()
    #     assert _job.cfg_file.read_yml()['templates']
    #     assert _job.cfg['templates']
    #     assert _job.cfg['name'] == 'Pluto'

    #     # Test tokens
    #     assert not pipe.is_valid_token('outputs', token='dcc', job=_job)
    #     assert not pipe.is_valid_token('cache', token='task', job=_job)

    #     # Test generic
    #     _ety = pipe.CPAsset(_file)
    #     _LOGGER.info('JOB %s', _job)
    #     _LOGGER.info('ETY %s', _ety)
    #     _LOGGER.info('ASSETS %s', _job.find_assets())
    #     assert _ety in _job.find_assets()
    #     assert _ety in _job.find_entities()
    #     assert not _job.find_shots()
    #     _asset = single(_job.find_assets())
    #     _LOGGER.info('ASSET %s', _asset)
    #     assert _asset.exists()
    #     _out = pipe.CPOutput(_file)
    #     _LOGGER.info('OUT %s', _out)
    #     assert _out.exists()
    #     _work_dir = pipe.CPWorkDir(_file)
    #     _LOGGER.info('WORK DIR %s', _work_dir)
    #     assert _work_dir.contains(_out)
    #     _LOGGER.info('OUTS %s', _work_dir.find_outputs())
    #     assert len(_work_dir.find_outputs()) == 1

    #     # Test cache
    #     pipe.CACHE.reset()
    #     _LOGGER.info(' - PIPE %s root=%s', pipe.CACHE, pipe.CACHE.jobs_root)
    #     _LOGGER.info(' - JOBS %s', pipe.CACHE.find_jobs())
    #     _LOGGER.info(' - JOBS ROOT %s', pipe.JOBS_ROOT)
    #     _job_c = pipe.CACHE.obt_job(_job)
    #     _LOGGER.info(' - JOB %s', _job_c)
    #     _LOGGER.info(' - ASSETS %s', _job_c.assets)
    #     assert len(_job_c.assets) == 1
    #     assert len(_job_c.entities) == 1
    #     assert len(_job_c.shots) == 0
    #     _ety_c = pipe.CACHE.obt_entity(_ety)
    #     _LOGGER.info(' - ETY %s', _ety_c)
    #     assert File(_file).exists()
    #     assert pipe.CPWorkDir(_file).exists()
    #     _work_dir_c = pipe.CACHE.obt_work_dir(_file)
    #     assert _work_dir_c.outputs
    #     _out_c = pipe.CACHE.obt_output(_file)

    #     # Test paths
    #     _path = _job.path+'/shots/dev000/maya/default/dev000_tag_v001.mb'
    #     _c_shot = _job.to_shot(shot='dev000')
    #     assert _c_shot.name == 'dev000'
    #     assert _c_shot.sequence == 'dev'
    #     assert _c_shot.idx == 0
    #     assert _c_shot.path == _job.path+'/shots/dev000'
    #     _c_shot = pipe.CPShot(_path)
    #     assert _c_shot.name == 'dev000'
    #     assert _c_shot.sequence == 'dev'
    #     assert _c_shot.idx == 0
    #     assert _c_shot.path == _job.path+'/shots/dev000'
    #     _c_work_dir = _c_shot.to_work_dir(task='default', dcc_='maya')
    #     assert _c_work_dir.task == 'default'
    #     assert_eq(_c_work_dir.dcc, 'maya')
    #     assert _c_work_dir.path == _job.path+'/shots/dev000/maya/default'
    #     _c_work = _c_shot.to_work(task='default', tag='tag', ver_n=1, dcc_='maya', extn='mb')
    #     assert _c_work.tag == 'tag'
    #     assert _c_work.ver_n == 1
    #     assert _c_work.extn == 'mb'
    #     assert_eq(_c_work.path, _path)
    #     assert _c_work == pipe.CPWork(_path)
    #     assert _c_work.tag == 'tag'
    #     assert _c_work.ver_n == 1
    #     assert _c_work.extn == 'mb'
    #     assert_eq(_c_work.path, _path)

    #     _path = _job.path+'/shots/common/maya/rig/common_FieldMan_v011.mb'
    #     _c_work = pipe.CPWork(_path)
    #     _c_work.touch()
    #     assert _c_work.task == 'rig'
    #     assert _c_work.tag == 'FieldMan'
    #     assert _c_work.ver_n == 11
    #     assert_eq(_c_work.dcc, 'maya')
    #     assert _c_work.job == _job
    #     _c_shot = pipe.CPShot(_path)
    #     assert _c_shot.sequence == 'common'
    #     assert not _c_shot.idx

    #     _path = _job.path+'/shots/common/maya/anim/common_OkayTest_v001.mb'
    #     _c_work = pipe.CPWork(_path)
    #     assert _c_work.task == 'anim'
    #     assert _c_work.tag == 'OkayTest'

    #     assert _job.find_sequences()
    #     assert _job.find_shots()
    #     assert _job.find_asset_types()
    #     assert _job.find_assets()

    #     _path = _job.path+'/assets/char.dog'
    #     try:
    #         _shot = pipe.CPShot(_path)
    #     except ValueError:
    #         pass
    #     else:
    #         raise ValueError
    #     _asset = pipe.CPAsset(_path)
    #     _LOGGER.info('ASSET SETTINGS %s', _asset.settings)
    #     assert _asset.settings.get('disable_shotgrid')
    #     _asset.create(force=True)
    #     assert _asset.asset_type == 'char'
    #     assert _asset.name == 'dog'
    #     assert _asset.exists()
    #     _job = pipe.CPJob(_path)
    #     _LOGGER.info('ASSET TYPES %s', _job.find_asset_types())
    #     assert 'char' in _job.find_asset_types()
    #     assert _asset in _job._read_assets()
    #     assert _asset in _job.find_assets()
    #     _LOGGER.info('ASSET %s', _asset)
    #     _LOGGER.info('ETYS %s', _job.find_entities())
    #     _LOGGER.info('C ETYS %s', _job_c.find_entities())
    #     pipe.CACHE.reset()
    #     _asset_c = pipe.CACHE.obt_entity(_asset)
    #     assert isinstance(_asset_c, cache.CCPAsset)

    #     _path = _job.path+'/assets/char.cube/nuke/lookdev'
    #     _work_dir = pipe.CPWorkDir(_path)
    #     _work_dir.mkdir()
    #     assert _work_dir.dcc == 'nuke'
    #     _asset = pipe.CPAsset(_path)
    #     _work_dir = _asset.find_work_dirs()[0]
    #     assert _work_dir.dcc == 'nuke'

    #     _path = _job.path+'/shots/dev000'
    #     try:
    #         _asset = pipe.CPAsset(_path)
    #     except ValueError:
    #         pass
    #     else:
    #         raise ValueError
    #     _shot = pipe.CPShot(_path)
    #     assert _shot.name == 'dev000'
    #     assert _shot.idx == 0
    #     assert _shot.sequence == 'dev'

    #     _path = _job.path+'/shots/common/maya/default/publish/common_PiniTest_v003.mb'
    #     _out = pipe.CPOutput(_path)
    #     assert _out.type_ == 'publish'
    #     assert _out.ver_n == 3

    #     # Test cache
    #     _job_c = pipe.CACHE.obt_job(_job)
    #     assert isinstance(_job_c, cache.CCPJob)
    #     assert not _job_c.uses_sequence_dirs
    #     _shots = _job_c.find_shots()
    #     assert isinstance(_shots[0], cache.CCPShot)

    #     # Test find_shots/find_assets w/o asset_type/shot dirs
    #     assert _job.find_sequences()
    #     assert len(_job.find_shots()) == 1
    #     _asset_types = _job.find_asset_types()
    #     assert len(_asset_types) == 1
    #     assert _job.find_assets()

    #     # Test cache
    #     _path = _job.path+'/shots/common/maya/default/common_test_v001.mb'
    #     _work = pipe.CPWork(_path)
    #     _work.touch()
    #     _work_dir = pipe.CPWorkDir(_path)
    #     _shot = pipe.CPShot(_path)
    #     assert _shot.exists()
    #     _job = pipe.CPJob(_path)
    #     assert _job.find_shots()
    #     _job_c = pipe.CACHE.obt_job(_path)
    #     _shot_c = _job_c.find_shot(_path)
    #     _LOGGER.info('SHOT %s', _shot_c)
    #     assert _shot_c.exists()
    #     assert _job_c.find_shots()
    #     assert _job_c.find_shots(sequence='common')
    #     assert _job_c.find_shot(_path) == _shot
    #     assert _work.exists()
    #     assert _work_dir in _shot_c.find_work_dirs()
    #     assert _work_dir.dcc == 'maya'
    #     assert _job.find_templates('work_dir', dcc_='maya')
    #     assert _work_dir in _shot_c.find_work_dirs(dcc_='maya')

    #     # Clean up
    #     _LOGGER.info('TMP JOB %s', _job)
    #     assert _job.name == 'Testing'
    #     _job.delete(force=True)

    # def test_create_shot_pluto(self):

    #     _job = pipe.CACHE.obt_job('Test Pluto')
    #     assert _job.cfg['name'] == 'Pluto'
    #     assert not _job.uses_sequence_dirs
    #     assert isinstance(_job, cache.CCPJob)
    #     _shot = _job.to_shot(sequence='tmp', shot='tmp000')
    #     if _shot.exists():
    #         _shot.delete(force=True)
    #         _job = pipe.CACHE.obt_job('Testing')
    #         _shot = _job.to_shot(sequence='tmp', shot='tmp000')
    #     assert isinstance(_shot, cache.CCPShot)
    #     assert not _shot.exists()
    #     assert _shot not in _job.shots
    #     assert isinstance(_shot.to_sequence(), str)
    #     assert _shot.job is _job
    #     _shot.create(force=True)
    #     assert _shot.exists()
    #     assert _shot in _job.shots

    # def test_create_asset_pluto(self):

    #     _job = pipe.CACHE.obt_job('Test Pluto')
    #     assert not _job.uses_asset_type_dirs
    #     assert isinstance(_job, cache.CCPJob)
    #     _asset = _job.to_asset(asset_type='shorts', asset='dance2')
    #     if _asset.exists():
    #         _asset.delete(force=True)
    #         _job = pipe.CACHE.obt_job('Test Pluto')
    #         _asset = _job.to_asset(asset_type='shorts', asset='dance2')
    #     assert isinstance(_asset, cache.CCPAsset)
    #     assert not _asset.exists()
    #     assert _asset not in _job.assets
    #     assert _asset.job is _job
    #     _asset.create(force=True)
    #     assert _asset.exists()
    #     assert _asset in _job.assets

    def test_output_get_metadata(self):

        testing.enable_file_system(True)

        pipe.CACHE.reset()
        _job = pipe.CACHE.obt_job('Test Pluto')
        _path = _job.to_file('assets/char.cube/maya/rig/publish/cube_main_v001.mb')
        _out = pipe.CPOutput(_path)
        _out.touch()
        _out_c = pipe.CACHE.obt_output(_out)
        assert isinstance(_out_c, pipe.cache.CCPOutput)
        _data = {'mtime': time.time()}
        _out.set_metadata(_data)
        assert _out.metadata == _data
        assert _out_c.metadata == _data
        _data = {'mtime': time.time()+1}
        _out.set_metadata(_data)
        assert _out.metadata == _data
        testing.enable_file_system(False)
        assert _out_c.metadata != _data
        assert _out_c.get_metadata() != _data
        testing.enable_file_system(True)
        assert _out_c.get_metadata(force=True) == _data

    def test_badly_named_dirs(self):

        _path = self._tmp_jobs_root.to_subdir(
            'Test Pluto/shots/common/{}/tmp'.format(dcc.NAME))
        _work_dir = pipe.CPWorkDir(_path)
        _LOGGER.info(' - WORK DIR %s', _work_dir)
        assert _work_dir.task == 'tmp'
        _work_dir.flush(force=True)

        _ver_1 = _work_dir.to_work(tag='blah', ver_n=1)
        _ver_2 = _work_dir.to_work(tag='blah', ver_n=2)
        _hip = _work_dir.to_work(tag='blah', ver_n=2, extn='hip')
        for _ver in [_ver_1, _ver_2, _hip]:
            _LOGGER.info(' - TOUCH WORK %s', _ver)
            _ver.touch()
        _job = pipe.CPJob(_path)
        assert _job.exists()
        assert _job.cfg['templates']
        assert _work_dir.exists()
        _job_c = pipe.CACHE.obt_job(_job)
        assert _job_c
        _work_dir_c = pipe.CACHE.obt_work_dir(_work_dir)
        _LOGGER.info(' - WORKS %s', _work_dir_c.works)
        assert len(_work_dir_c.works) == 2
        assert not _work_dir_c.badly_named_files
        _work_dir.to_file('blah.'+dcc.DEFAULT_EXTN).touch()
        assert not _work_dir_c.badly_named_files
        _work_dir_c.find_works(force=True)
        assert _work_dir_c.badly_named_files == 1

        _work_dir.delete(force=True)
