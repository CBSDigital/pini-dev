import logging
import unittest

from pini import testing
from pini.tools import job_manager
from pini.utils import strftime

_LOGGER = logging.getLogger(__name__)


class TestJobManager(unittest.TestCase):

    pipe_master_filter = 'disk'

    def test_job_manager(self):

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
