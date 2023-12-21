"""Tools for managing the maya blast handler."""

import logging

from pini import pipe, qt
from maya_pini import m_pipe, open_maya as pom

from . import bh_base

_LOGGER = logging.getLogger(__name__)


class CMayaPlayblast(bh_base.CBlastHandler):
    """Blast handler for maya."""

    NAME = 'Playblast Tool'
    LABEL = 'Playblasts the current scene'
    LABEL_WIDTH = 80

    def build_ui(self, parent=None, layout=None):
        """Build ui elements for this handler.

        Args:
            parent (QWidget): parent widget
            layout (QLayout): parent layout
        """
        super(CMayaPlayblast, self).build_ui(parent=parent, layout=layout)
        self.ui.Camera = self.add_combobox_elem(
            name='Camera',
            items=[str(_cam) for _cam in pom.find_cams()],
            val=str(pom.active_cam()))
        self.ui.Settings = self.add_combobox_elem(
            name='Settings', items=['As is', 'Nice'])
        self.ui.Resolution = self.add_combobox_elem(
            name='Resolution', items=['Full', 'Half', 'Quarter'])
        self.ui.OutputName = self.add_combobox_elem(
            name='OutputName', items=['blast', '<camera>'])

    def _callback__Format(self):
        super(CMayaPlayblast, self)._callback__Format()
        _fmt = self.ui.Format.currentText()
        _tmpl_name = 'blast_mov' if _fmt in ('mp4', ) else 'blast'
        _work = pipe.cur_work()
        _en = False
        if _work:
            _tmpl = _work.find_template(_tmpl_name, catch=True)
            if _tmpl:
                _en = 'output_name' in _tmpl.keys()
        self.ui.OutputName.setEnabled(_en)

    def blast(self):
        """Excute blast."""

        _work = pipe.cur_work()
        if not _work.find_template('blast', catch=True):
            qt.notify(
                'No blast template found in this job:\n\n{}\n\n'
                'Unable to blast.'.format(_work.job.path),
                title='Warning', parent=self.parent)
            return

        m_pipe.blast(
            format_=self.ui.Format.currentText(),
            view=self.ui.View.isChecked(),
            range_=self._read_range(),
            burnins=self.ui.Burnins.isChecked(),
            res=self.ui.Resolution.currentText(),
            camera=self.ui.Camera.currentText(),
            settings=self.ui.Settings.currentText(),
            output_name=self.ui.OutputName.currentText(),
        )
