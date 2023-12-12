import logging
import unittest

from pini import pipe, dcc, testing
from pini.tools import helper, job_manager
from pini.utils import strftime

_LOGGER = logging.getLogger(__name__)


class TestPiniHelper(unittest.TestCase):

    def test(self):

        _helper = helper.launch()
        dcc.new_scene(force=True)
        _helper._callback__ToggleAdmin(True)

        _job = testing.TEST_JOB
        _seq_name = strftime('Tmp_%y%m%d_%H%M%S')

        # Test create seq
        _shot = _job.find_shots()[0]
        assert _shot.exists()
        _LOGGER.info('JUMP TO %s', _shot)
        _helper.jump_to(_shot.path)
        assert not _helper.ui.EntityTypeCreate.isEnabled()
        _helper.ui.EntityType.setEditText(_seq_name)
        assert _helper.ui.EntityTypeCreate.isEnabled()
        assert not _helper.ui.EntityCreate.isEnabled()
        _helper.ui.Entity.setEditText('shot010')
        assert _helper.ui.EntityCreate.isEnabled()
        _helper._callback__EntityCreate(force=True, shotgrid_=False)
        _seq = _helper.ui.EntityType.selected_data()
        assert _seq
        assert _seq.name == _seq_name
        assert _helper.entity.exists()
        _helper.entity.set_setting(disable_shotgrid=True)
        assert _helper.entity.settings.get('disable_shotgrid')

        # Test save/load
        _work = _helper.ui.WWorks.selected_data()
        assert _work.sequence == _seq_name
        assert len(_helper.ui.WWorks.all_data()) == 1
        _helper._callback__WSave(force=True)
        assert pipe.cur_work() == _work
        _works = _helper.ui.WWorks.all_data()
        assert len(_works) == 2
        _helper.ui.WWorks.select_data(_works[0])
        assert _helper.ui.WWorks.selected_data().ver_n == 2
        _helper._callback__WSave(force=True)
        assert pipe.cur_work().ver_n == 2
        assert _work.ver_n == 1
        _helper.ui.WWorks.select_data(_work)
        _helper._callback__WLoad(force=True)
        assert pipe.cur_work().ver_n == 1

        # Test create new task
        _tasks = _helper.ui.WTasks.all_text()
        _task = 'groom'
        assert _task not in _tasks
        _helper.ui.WTaskText.setText(_task)
        assert _helper.work.task == _task
        assert not _helper.work.exists()
        assert _helper.work is _helper.next_work
        assert len(_helper.ui.WWorks.all_items()) == 1
        assert not _helper.ui.WTasks.selected_text()
        _helper._callback__WSave(force=True)
        assert _helper.ui.WTasks.selected_text() == _task
        assert _helper.ui.WTaskText.text() == _task
        assert _helper.work.exists()

        # Test create shot in existing seq
        if not helper.DIALOG:
            _helper = helper.launch()
        _helper._callback__ToggleAdmin(True)
        _seq = _job.to_sequence(_seq_name)
        _shot = _seq.to_shot('shot020')
        assert not _shot.exists()
        _helper.ui.EntityType.select_text(_shot.sequence, catch=False)
        assert _shot.name not in _helper.ui.Entity.all_text()
        _LOGGER.info('CREATE SHOT %s', _shot)
        _helper.ui.Entity.setEditText(_shot.name)
        _helper._callback__EntityCreate(force=True, shotgrid_=False)
        assert _shot.name in _helper.ui.Entity.all_text()

        # Clean up
        _seq.delete(force=True)
        pipe.CACHE.reset()
        dcc.new_scene(force=True)


class TestJobManager(unittest.TestCase):

    def test(self):

        _seq_name = strftime('Tmp_%y%m%d_%H%M%S')
        _job = testing.TEST_JOB

        _sm = job_manager.launch(job=_job)
        _sm.ui.Job.select_data(_job)
        assert _sm.ui.Job.selected_data() == _job

        _seq = _job.find_sequences()[0]
        _sm.ui.CSequence.select_data(_seq, catch=False)
        _sm.ui.CShotsText.setText('')
        _n_items = len(_sm.ui.ShotsTree.all_items())
        assert not _job.to_sequence(_seq_name).exists()
        _sm.ui.CSequence.setEditText(_seq_name)
        _sm.ui.CShotsText.setText('10-100')
        assert _n_items + 11 == len(_sm.ui.ShotsTree.all_items())
        assert not _sm.ui.CSequence.selected_data()
        assert _sm.ui.CPrefix.text() == 'tmp'
        assert _sm._valid_prefix
        assert not _sm.ui.CPrefixWarning.isVisible()
        _sm.ui.CPrefix.setText('temp')
        assert _sm.ui.CPrefixWarning.isVisible()
        assert _n_items + 1 == len(_sm.ui.ShotsTree.all_items())
        _sm.close()
