"""Tools for managing the basic shotgrid submit tool."""

import logging
import pprint

from pini import icons, qt
from pini.dcc import export
from pini.pipe import shotgrid
from pini.tools import helper
from pini.utils import wrap_fn, copy_text

_LOGGER = logging.getLogger(__name__)


class CBasicSubmitter(export.CExportHandler):
    """Managing basic shotgrid version submission."""

    NAME = 'Basic Shotgrid Submit'
    TYPE = 'Submit'
    ACTION = 'BasicSubmit'
    ICON = icons.find('Briefcase')

    LABEL = 'Submit renders to shotgrid.'

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        self.ui.add_list_widget('Render', redraw=False, multi=False)

        self.ui.add_combo_box(
            'Task', ['Apple', 'Orange', 'Banana'], ui_only=True)
        self.ui.add_check_box(
            'HideSubmitted', val=True, ui_only=True)
        self.ui.add_check_box(
            'Latest', val=True, label='Show latest only', ui_only=True)

        self._redraw__Task()
        self._redraw__Render()

    def build_ui(self, add_notes=True):
        """Build interface.

        Args:
            add_notes (bool): add notes element
        """
        _ety = helper.DIALOG.entity
        self._all_outputs = sorted([
            _out for _out in _ety.outputs
            if _out.content_type in ('Video', 'Blast', 'Render')],
            key=_submit_out_sort)

        super().build_ui(
            add_version_up=False, add_snapshot=False, exec_label='Submit',
            add_notes=add_notes)

    def _redraw__Task(self):
        _tasks = sorted({_out.task_label for _out in self._all_outputs})
        _select = None
        if helper.DIALOG.work_dir:
            _select = helper.DIALOG.work_dir.task_label
        self.ui.Task.set_items(['all'] + _tasks, select=_select)

    def _redraw__Render(self):

        _hide_submitted = self.ui.HideSubmitted.isChecked()
        _latest = self.ui.Latest.isChecked()
        _task = self.ui.Task.currentText()

        # Build items list
        _items = []
        for _out in self._all_outputs:

            # Apply filters
            if _task not in ('all', _out.task_label):
                continue
            if _latest and not _out.is_latest():
                continue
            if _hide_submitted:
                _work = _out.find_work()
                if _work and _work.metadata.get('submitted'):
                    continue

            # Build list item
            _icon = helper.output_to_icon(_out)
            _item = qt.CListWidgetItem(
                _out.filename, icon=_icon, data=_out, icon_scale=0.8)
            _items.append(_item)

        self.ui.Render.set_items(_items)

    def _callback__Task(self):
        self.ui.Render.redraw()

    def _callback__HideSubmitted(self):
        self.ui.Render.redraw()

    def _callback__Latest(self):
        self.ui.Render.redraw()

    def _context__Render(self, menu):
        _ren = self.ui.Render.selected_data()
        if _ren:
            menu.add_action(
                'Print metadata',
                wrap_fn(pprint.pprint, _ren.metadata, width=200),
                icon=icons.PRINT)
            menu.add_action(
                'Copy path', wrap_fn(copy_text, _ren.path), icon=icons.COPY)
            _work = _ren.find_work()

    def set_settings(self, **kwargs):
        """Apply exec settings."""
        super().set_settings(**kwargs)
        self.settings.update(dict(
            version_up=False,
            check_work=False,
            save=False,
            snapshot=False,
            sanity_check_=False))

    def export(self, render, notes=None, force=False):
        """Execute submission.

        Args:
            render (CPOutputBase): render to submit
            notes (str): submit notes
            force (bool): force update any existing submission
        """
        shotgrid.create_ver(render, comment=notes, force=force)


def _submit_out_sort(output):
    """Sort function for submittable outputs.

    Args:
        output (CPOutputBase): output to sort

    Returns:
        (tuple): sort key
    """
    return output.to_stream(), -output.ver_n
