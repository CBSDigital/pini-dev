import logging
import os
import pprint
import time
import unittest

from pini import pipe, testing, dcc
from pini.pipe import cache, cp_template
from pini.utils import File, single, flush_caches, assert_eq, Seq

_LOGGER = logging.getLogger(__name__)


class TestPipe(unittest.TestCase):

    def test_cast_work_dcc(self):

        _work_ma = testing.TEST_SHOT.to_work_dir('light').to_work()
        _LOGGER.info(_work_ma)
        _work_nk = _work_ma.to_work(dcc_='nuke', tag='slapcomp', extn='nk')
        _LOGGER.info(_work_nk)
        pprint.pprint(_work_nk.data)
        assert _work_nk.extn == 'nk'
        assert_eq(_work_nk.dcc, 'nuke')
        _work_nk = _work_nk.find_next()
        _LOGGER.info(_work_nk)
        assert _work_nk.extn == 'nk'

    def test_output_video_metadata_caching(self):

        testing.enable_file_system(True)

        # Find video with metadata
        _shot = pipe.CACHE.obt(testing.TEST_SHOT)
        for _out in _shot.find_outputs(extns=('mp4', 'mov')):
            if _out.metadata:
                break
        else:
            raise RuntimeError
        _path = _out.path
        assert File(_path).exists()

        # Read metadata to check cache
        _out = pipe.CACHE.obt_output(_path)
        assert _out.exists()
        assert _out.metadata
        assert isinstance(_out, cache.CCPOutputBase)
        assert isinstance(_out, cache.CCPOutputFile)
        assert isinstance(_out, cache.CCPOutputVideo)

        # Check access metadata wiht file system disabled
        testing.enable_file_system(False)
        assert _out.get_metadata()
        assert _out.metadata

        testing.enable_file_system(True)

    def test_output_seq_hash(self):

        _shot = pipe.CACHE.obt(testing.TEST_SHOT)
        _path = _shot.find_outputs(extn='vdb')[0].path
        _seq = Seq(_path)
        assert hash(_seq)
        _out = pipe.to_output(_path)
        assert hash(_out)
        assert hash(_out) == hash(_seq)

        _out_c = pipe.CACHE.obt_output(_path)
        assert _out_c.__hash__
        assert hash(_out_c)
        assert not _out_c.is_media()
        _ghost = _out_c.to_ghost()
        assert _out_c.path == _ghost.path
        assert hash(_out_c) == hash(_ghost)
        assert _ghost == _out_c
        assert not hasattr(_ghost, 'cmp_key')
        assert _out_c.__eq__(_ghost)
        assert _out_c == _ghost
        assert _out_c in [_out_c.to_ghost()]

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

    def test_task_sort(self):

        assert pipe.task_sort('ani/anim') > pipe.task_sort('ani/lay')

    def test_templates(self):

        assert testing.TEST_JOB

        _pattern = '{blah}/{blue}/{blee}'
        _tmpl = pipe.CPTemplate(name='test', pattern=_pattern)
        _tmpl = _tmpl.apply_data(blue='BLUE')
        assert 'blue' in _tmpl.embedded_data
        _tmpl = _tmpl.apply_data(blee='BLEE')
        assert 'blue' in _tmpl.embedded_data
        _data = _tmpl.parse('BLAH/BLUE/BLEE')
        assert 'blue' in _data

        # Test tag as vertical - this was causing bad template to be selected
        # as it was being matched as a version
        if testing.TEST_JOB.find_templates('publish'):
            for _ety in [testing.TEST_ASSET, testing.TEST_SHOT]:
                _tmpls = [
                    testing.TEST_JOB.find_template(
                        'publish', profile=_ety.profile,
                        has_key={'tag': True, 'ver': True, 'output_type': False}),
                    testing.TEST_JOB.find_template(
                        'publish', profile=_ety.profile, catch=True,
                        has_key={'tag': True, 'ver': False, 'output_type': False}),
                ]
                _tmpls = [_tmpl for _tmpl in _tmpls if _tmpl]
                assert _tmpls
                for _tmpl in _tmpls:
                    _LOGGER.info('TMPL %s', _tmpl)
                    _out = _ety.to_output(
                        _tmpl, task='anim', tag='vertical', output_name='test',
                        dcc_='maya')
                    _LOGGER.info('OUT %s', _out)
                    _out = pipe.CPOutputFile(_out.path)
                    _LOGGER.info('OUT %s', _out)
        else:
            _LOGGER.info('NO PUBLISH TEMPLATES FOUND')

        # Test alt from template name
        assert cp_template._extract_alt_from_name('blah') == ('blah', 0)
        assert cp_template._extract_alt_from_name('blah_alt1') == ('blah', 1)
        assert cp_template._extract_alt_from_name('alt_blah_alt3') == ('alt_blah', 3)

        # Test apply data to tag with regex
        _tmpl = pipe.CPTemplate(name='test', pattern='{task}/{tag:[^_]+}_v{ver}/{output_name}')
        assert _tmpl.apply_data(tag='blah').pattern == '{task}/blah_v{ver}/{output_name}'

    def test_work_to_output(self):

        # Check caches can have underscores in output name
        _ety = pipe.CACHE.obt(testing.TEST_SHOT)
        _work_dir = _ety.find_work_dir(task='anim', dcc_=dcc.NAME)
        _work = _work_dir.to_work()
        _out = _work.to_output('cache', output_name='blah_2', extn='abc')
        assert _out
        assert _out.task == 'anim'
        assert _out.output_name == 'blah_2'

        # Check asset pubs can have optional output_type
        _ety = pipe.CACHE.obt(testing.TEST_ASSET)
        _work_dir = _ety.find_work_dir('model', dcc_=dcc.NAME)
        assert _work_dir.to_output('publish', output_type=None, extn=dcc.DEFAULT_EXTN)
        assert _work_dir.to_output('publish', output_type='vrmesh', extn=dcc.DEFAULT_EXTN)

        _blast = _work.to_output(
            'blast_mov', output_name='blah', extn='mov')
        assert _blast.extn == 'mov'
        _blast = _work.to_output(
            'blast_mov', output_name='blah', extn='mov', dcc_='hou')
        assert _blast.extn == 'mov'


class TestDiskPipe(unittest.TestCase):

    pipe_master_filter = 'disk'

    def test_badly_named_dirs(self):

        testing.TMP_ASSET.flush(force=True)
        _work_dir = testing.TMP_ASSET.to_work_dir(task='model')
        _LOGGER.info(' - WORK DIR %s', _work_dir)
        _work_dir.flush(force=True)

        _ver_1 = _work_dir.to_work(tag='blah', ver_n=1)
        _ver_2 = _work_dir.to_work(tag='blah', ver_n=2)
        if dcc.NAME == 'hou':
            _extn = dcc.DEFAULT_EXTN
        else:
            _extn = 'hip'
        _hip = _work_dir.to_work(tag='blah', ver_n=2, extn=_extn)
        for _ver in [_ver_1, _ver_2, _hip]:
            _LOGGER.info(' - TOUCH WORK %s', _ver)
            _ver.touch()
        _job = _work_dir.job
        assert _job.exists()
        assert _job.cfg['templates']
        assert _work_dir.exists()
        _job_c = pipe.CACHE.obt_job(_job)
        assert _job_c
        assert _work_dir.exists()
        _work_dir_c = pipe.CACHE.obt_work_dir(_work_dir, catch=True)
        if not _work_dir_c:
            _work_dir_c = pipe.CACHE.obt_work_dir(_work_dir, force=True)
        _LOGGER.info(' - WORKS %s', _work_dir_c.works)
        assert len(_work_dir_c.works) == 2
        assert not _work_dir_c.badly_named_files
        _work_dir.to_file('blah.' + dcc.DEFAULT_EXTN).touch()
        assert not _work_dir_c.badly_named_files
        _work_dir_c.find_works(force=True)
        assert _work_dir_c.badly_named_files == 1

        _work_dir.delete(force=True)

    def test_output_get_metadata(self):

        testing.TMP_ASSET.flush(force=True)
        pipe.CACHE.reset()

        _out = testing.TMP_ASSET.to_output('publish', task='model')
        _out.touch()
        _out_c = pipe.CACHE.obt_output(_out)
        assert isinstance(_out_c, pipe.cache.CCPOutputFile)
        _data = {'mtime': time.time()}
        _out.set_metadata(_data)
        assert _out.metadata == _data
        assert _out_c.metadata == _data
        _data = {'mtime': time.time() + 1}
        _out.set_metadata(_data)
        assert _out.metadata == _data
        testing.enable_file_system(False)
        assert _out_c.metadata != _data
        assert _out_c.get_metadata() != _data
        testing.enable_file_system(True)
        assert _out_c.get_metadata(force=True) == _data

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
            'render', task='anim', output_name='masterLayer', user=pipe.cur_user())
        _LOGGER.info('OUT %s', _out)
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

    def test_output_seq_dirs(self):

        testing.enable_file_system(True)

        if not testing.TEST_JOB.find_templates('render'):
            _LOGGER.info('NO RENDER TEMPLATES SET UP')
            return

        _shot = testing.TMP_SHOT
        _shot.flush(force=True)

        # Find test work
        _step = os.environ.get('PINI_TEST_STEP', 'lighting')
        _task = os.environ.get('PINI_TEST_TASK', 'lighting')
        _work = _shot.to_work(tag='SeqCacheTest', task=_task, step=_step)
        _LOGGER.info('WORK %s', _work)
        _work.touch()

        # Build test seq
        _seq = _work.to_output('render', output_name='masterLayer', extn='exr')
        _LOGGER.info('SEQ %s', _seq)
        _tmpl = _shot.find_template('render')
        assert_eq(bool(_seq.work_dir), 'work_dir' in _tmpl.keys())
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
        testing.obt_image('exr').copy_to(_frame_1)
        _seq.add_metadata(src=_work.path)
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
        _seq_g = single(_work_c.find_outputs())
        _seq_c = pipe.CACHE.obt_output(_seq_g)
        _seq_c = pipe.CACHE.obt(_seq_g)
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

    def test_validate_token(self):

        _LOGGER.info('JOBS ROOT %s', pipe.ROOT)
        _LOGGER.info('JOBS %s', pipe.find_jobs())
        _job = pipe.find_job('Testing')
        _LOGGER.info('JOB %s', _job)
        assert pipe.is_valid_token(
            token='output_name', value='aaa', job=_job)
        assert not pipe.is_valid_token(
            token='output_name', value='aaa.aaa', job=_job)

    def test_update_publish_cache(self):

        if not testing.TEST_JOB.find_templates('publish'):
            _LOGGER.info('NO PUBLISH TEMPLATES SET UP')
            return

        _shot = testing.TMP_SHOT
        _shot.flush(force=True)
        _shot_c = pipe.CACHE.obt(_shot)

        # Test mem caching
        _work_dir = _shot.to_work_dir(task='rig')
        _LOGGER.info('WORK DIR %s', _work_dir)
        _work = _work_dir.to_work()
        _out = _work.to_output('publish', output_type=None)
        assert not _work_dir.find_outputs()
        assert not _shot.find_outputs()
        assert not _shot_c.find_publishes(force=True)
        _out.touch()
        assert _work_dir.find_outputs()
        # pprint.pprint(_shot
        # assert not _shot.find_outputs()
        assert not _shot_c.find_publishes()
        _LOGGER.info('FORCE RECACHE %s', _shot_c)
        _pubs = _shot_c.find_publishes(force=True)
        _LOGGER.info(' - PUBS %s', _pubs)
        assert _pubs
        _out.delete(force=True)
        assert not _work_dir.find_outputs()
        assert not _shot.find_outputs()
        assert _shot_c.find_publishes()
        assert not _shot_c.find_publishes(force=True)

        # Test disk caching
        assert not pipe.CACHE.obt_entity(_shot).find_publishes()
        _out.touch()
        assert _shot_c.find_publishes(force=True)
        _yml = File(_shot_c.cache_fmt.format(func='_read_publishes'))
        assert _yml.exists()
        assert _yml.read_yml()
        _LOGGER.info('YML %s', _yml.path)
        flush_caches()
        assert pipe.CACHE.obt_entity(_shot).find_publishes()
        _pub_g = pipe.CACHE.obt_entity(_shot).find_publish()
        assert isinstance(_pub_g, cache.CCPOutputGhost)
        _out.delete(force=True)
        flush_caches()
        assert pipe.CACHE.obt_entity(_shot).find_publishes()
        _pub_g = pipe.CACHE.obt_entity(_shot).find_publish()
        assert isinstance(_pub_g, cache.CCPOutputGhost)
        assert not pipe.CACHE.obt_entity(_shot).find_publishes(force=True)

        _shot.delete(force=True)


class TestCache(unittest.TestCase):

    def test_work_dir_outputs(self):

        if not testing.TEST_JOB.find_templates('publish'):
            _LOGGER.info('NO PUBLISH TEMPLATES SET UP')
            return

        pipe.CACHE.reset()

        _ety_c = pipe.CACHE.obt(testing.TEST_ASSET)
        _pub = _ety_c.find_publishes(task='model', extn='ma')[-1]
        _pub_c = pipe.CACHE.obt(_pub)
        _LOGGER.info('ETY (PUB) %s', _pub_c.entity)
        _LOGGER.info('ETY       %s', _ety_c)
        _LOGGER.info('PUB C %s %s', type(_pub_c), _pub_c)

        assert isinstance(_pub_c, cache.CCPOutputFile)
        assert _pub_c.work_dir
        assert isinstance(_pub_c.work_dir, cache.CCPWorkDir)
        assert isinstance(_pub_c.work_dir.entity, cache.CCPEntity)

        assert isinstance(_pub_c.entity, pipe.ENTITY_TYPES)
        assert isinstance(_pub_c.entity, pipe.CPAsset)
        assert isinstance(_pub_c.entity, cache.CCPAsset)
        assert isinstance(_pub_c.entity, cache.CCPEntity)

        assert _ety_c == pipe.CACHE.obt(_pub_c.entity)
        assert _ety_c is pipe.CACHE.obt(_pub_c.entity)
        assert _pub_c.entity == _ety_c
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

    def test_output_ghost_obj(self):

        _pub = pipe.CACHE.obt(testing.TEST_JOB).find_publishes()[0]
        _LOGGER.info(' - PUB %s', _pub)
        _out = pipe.to_output(_pub.path)
        _out_c = pipe.CACHE.obt(_out)
        _out_g = _out_c.to_ghost()
        assert _out_c == _out_g
        assert _out_c in [_out_g]
        assert _out_g in [_out_c]
