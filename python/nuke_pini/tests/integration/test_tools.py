import logging
import unittest

import nuke

from pini import dcc, pipe, testing

from nuke_pini.tools import autowrite2


_LOGGER = logging.getLogger(__name__)


class TestTools(unittest.TestCase):

    def test_autowrite2(self):

        # Check test shots exist
        _job = testing.TEST_JOB
        for _idx in range(1, 4):
            for _seq in ['TestingA', 'TestingB']:
                _suffix = _seq[-1].lower()
                _name = 'test{}{:03d}'.format(_suffix, _idx*10)
                _shot = _job.to_shot(sequence=_seq, shot=_name)
                if not _shot.exists():
                    _shot.create(force=True, shotgrid_=False)
                _shot.set_setting(disable_shotgrid=True)
                assert _shot.settings['disable_shotgrid']
        _job.find_shot('testa020').to_work_dir('plastic').mkdir()
        _job.find_shot('testa010').to_work(task='comp', tag='mytag').touch()

        _shot_a1 = _job.find_shot('testa010')
        _shot_a2 = _job.find_shot('testa020')
        _shot_b1 = _job.find_shot('testb010')
        _work_a1 = _shot_a1.to_work(task='comp')
        _work_a1_mytag = _shot_a1.to_work(task='comp', tag='mytag')
        _work_b1 = _shot_b1.to_work(task='comp')

        # Set up test scene
        dcc.new_scene(force=True)
        _work_a1.save(force=True)
        pipe.CACHE.reset()
        _const = nuke.createNode('Constant')
        _const['color'].setValue([1, 1, 0, 1])
        _node = autowrite2.build()
        assert _node['name'].value() == 'main'
        dcc.set_range(1001, 1005)
        assert _node['ety_mode'].value() == 'Linked'
        assert isinstance(_node.output, pipe.CPOutputSeq)
        assert _node.output.entity == _shot_a1

        # Test switch shot
        _work_b1.save(force=True)
        assert _node.output.entity == _shot_b1
        _work_a1.save(force=True)
        assert _node.output.entity == _shot_a1

        # Try override seq
        _node['ety_type_mode'].setValue('Select')
        assert _node['ety_mode'].value() == 'Linked'
        assert _node['ety_mode'].enabled()
        _node['ety_type'].setValue('TestingB')
        assert _node['ety_mode'].value() == 'Select'
        assert not _node['ety_mode'].enabled()
        assert _node['ety'].value() == 'testb010'
        assert _node.output.entity.name == 'testb010'
        _node.reset()
        assert _node['file_type'].value() == 'exr'

        # Test compounded task list
        assert not _shot_a1.find_work_dir('plastic', catch=True)
        assert _shot_a2.find_work_dir('plastic')
        _node['ety_mode'].setValue('Select')
        assert 'plastic' not in _node['task'].values()
        _node['ety'].setValue('testa020')
        assert 'plastic' in _node['task'].values()
        _node['task_mode'].setValue('Select')
        _node['task'].setValue('plastic')
        assert _node.output.task == 'plastic'
        _node.reset()

        # Test mov
        _node['file_type'].setValue('mov')
        assert _node.output.extn == 'mov'
        assert isinstance(_node.output, pipe.CPOutput)
