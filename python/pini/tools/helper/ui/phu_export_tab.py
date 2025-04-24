"""Tools for managing the pini helper export tab."""

# pylint: disable=no-member

import collections
import logging

from pini import qt, pipe, dcc, testing
from pini.qt import QtWidgets
from pini.tools import error
from pini.utils import single, passes_filter

from . import phu_output_item

_LOGGER = logging.getLogger(__name__)


class PHExportTab:
    """Class for grouping together elements of the carb helper Export tab."""

    pipe = None

    def init_ui(self):
        """Inititate this tab's interface - triggered by selecting this tab."""
        _LOGGER.debug('INIT UI')

        for _elem in [
                self.ui.EExportPane,
                self.ui.EPublishHandler,
                self.ui.EBlastHandler,
                self.ui.ECacheHandler,
                self.ui.ERenderHandler,
        ]:
            _elem.set_save_policy(qt.SavePolicy.SAVE_IN_SCENE)

        # Disable tabs if no handlers found
        for _type, _tab in [
                ('Publish', self.ui.EPublishTab),
                ('Blast', self.ui.EBlastTab),
                ('Render', self.ui.ERenderTab),
                ('Cache', self.ui.ECacheTab),
                ('Submit', self.ui.ESubmitDevTab),
        ]:
            _handlers = dcc.find_export_handlers(type_=_type)
            _LOGGER.debug(' - CHECKING TAB %s %s', _tab, _handlers)
            self.ui.EExportPane.set_tab_enabled(_tab, bool(_handlers))
            _LOGGER.debug(' - CHECKED TAB %s', _tab)
        self._init_submit_tab()
        _tabs = self.ui.EExportPane.find_tabs(enabled=True)
        _LOGGER.debug(' - TABS %s', _tabs)

        # Select default tab
        _tab = single(_tabs, catch=True)
        if not _tab:  # Use only available tab
            _tab = single(_tabs, catch=True)
            _LOGGER.debug(' - SELECT TAB (A) %s', _tab)
        if self.ui.EExportPane.has_scene_setting():  # Use scene setting
            _scene_tab = self.ui.EExportPane.get_scene_setting()
            _LOGGER.debug(' - SCENE TAB %s', _scene_tab)
            if _scene_tab in _tabs:
                _tab = _scene_tab
        if not _tab:  # Select default based on cur work
            _work = pipe.cur_work()
            if _work and _work.entity.profile == 'asset':
                _tab = 'Publish'
            else:
                _task = pipe.map_task(_work.task if _work else None)
                _tab = {
                    'previs': 'Cache',
                    'anim': 'Cache',
                    'lighting': 'Render',
                }.get(_task)
                _LOGGER.debug(' - SELECT TAB (B) %s task=%s', _tab, _task)
        if not _tab and _work:
            _tab = {'asset': 'Publish', 'shot': 'Cache'}[_work.profile]
        if _tab:
            _LOGGER.debug(' - SELECT TAB (Z) %s', _tab)
            self.ui.EExportPane.select_tab(_tab, emit=False)

        if not testing.dev_mode():
            self.ui.EExportPane.set_tab_visible('Submit Dev', False)

        self._callback__EExportPane()

    def _init_submit_tab(self):
        """Setup submit tab."""
        self.ui.EExportPane.set_tab_enabled('Submit', pipe.SUBMIT_AVAILABLE)
        if not pipe.SUBMIT_AVAILABLE:
            return
        from pini.pipe import shotgrid

        # Set up comments
        self.ui.ESubmitComment.set_save_policy(qt.SavePolicy.NO_SAVE)
        for _elem in [
                self.ui.ESubmitComment,
                self.ui.ESubmitCommentLabel,
                self.ui.ESubmitCommentLine,
        ]:
            _elem.setVisible(shotgrid.SUBMITTER.supports_comment)

        # Apply selection mode to outputs list
        if shotgrid.SUBMITTER.supports_multi:
            _mode = QtWidgets.QAbstractItemView.ExtendedSelection
        else:
            _mode = QtWidgets.QAbstractItemView.SingleSelection
        self.ui.ESubmitOutputs.setSelectionMode(_mode)

    def _redraw__EPublishTab(self):
        self.ui.EPublishHandler.redraw()
        self.ui.EPublishHandlerIcon.redraw()

    def _redraw__EPublishHandler(self):

        _handlers = dcc.find_export_handlers('Publish')

        # Determine default publish handler to select
        _select = None
        _scene_data = dcc.get_scene_data('PiniQt.EPublishTab.EPublishHandler')
        if _scene_data:
            _select = _scene_data
        if not _select:
            _select = dcc.find_export_handler(
                'publish', filter_='basic', catch=True)
        _work = pipe.CACHE.cur_work
        if _work:
            _task = pipe.map_task(_work.task, step=_work.step)
            _LOGGER.debug(' - PUB HANDLER TASK "%s"', _task)
            _handler = dcc.find_export_handler(_task, catch=True)
            _LOGGER.debug(' - PUB HANDLER %s', _handler)
            if _handler:
                _select = _handler

        _LOGGER.debug(' - SELECT PUB HANDLER %s', _select)
        self.ui.EPublishHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers, select=_select, emit=True)

    def _redraw__EPublishHandlerIcon(self):
        _exp = self.ui.EPublishHandler.selected_data()
        if _exp:
            self.ui.EPublishHandlerIcon.setIcon(qt.obt_icon(_exp.ICON))

    def _redraw__EBlastTab(self):
        self.ui.EBlastHandler.redraw()
        self.ui.EBlastHandlerIcon.redraw()

    def _redraw__EBlastHandler(self):
        _handlers = dcc.find_export_handlers('Blast')
        self.ui.EBlastHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers)

    def _redraw__EBlastHandlerIcon(self):
        _exp = self.ui.EBlastHandler.selected_data()
        if _exp:
            self.ui.EBlastHandlerIcon.setIcon(qt.obt_icon(_exp.ICON))

    def _redraw__ECacheTab(self):
        self.ui.ECacheHandler.redraw()
        self.ui.ECacheHandlerIcon.redraw()

    def _redraw__ECacheHandlerIcon(self):
        _exp = self.ui.ECacheHandler.selected_data()
        if _exp:
            self.ui.ECacheHandlerIcon.setIcon(qt.obt_icon(_exp.ICON))

    def _redraw__ECacheHandler(self):
        _handlers = dcc.find_export_handlers('Cache')
        _labels = [_handler.NAME for _handler in _handlers]
        self.ui.ECacheHandler.set_items(
            data=_handlers, labels=_labels, emit=True)

    def _redraw__ERenderTab(self):
        self.ui.ERenderHandler.redraw()
        self.ui.ERenderHandlerIcon.redraw()

    def _redraw__ERenderHandler(self):
        _handlers = sorted(dcc.find_export_handlers('Render'))
        self.ui.ERenderHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers)
        _LOGGER.debug(
            ' - BUILD RENDER HANDLERS %s',
            self.ui.ERenderHandler.selected_data())

    def _redraw__ERenderHandlerIcon(self):
        _exp = self.ui.ERenderHandler.selected_data()
        if _exp:
            self.ui.ERenderHandlerIcon.setIcon(qt.obt_icon(_exp.ICON))

    def _redraw__ESubmitTemplate(self):
        _LOGGER.debug('REDRAW ESubmitTemplate %s', self.entity)
        _outs = self.entity.find_outputs() if self.entity else []
        _outs = [_out for _out in _outs if _out.submittable]
        _work = pipe.CACHE.cur_work or self.work

        # Determine selection
        _select = 'render'
        if _work:
            if _work.find_outputs('render'):
                _select = 'render'
            elif _work.find_outputs('blast'):
                _select = 'blast'
        _LOGGER.debug(' - SELECT %s %s', _select, self.work)

        _tmpls, _data = _sort_by_attr(_outs, attr='basic_type')
        self.ui.ESubmitTemplate.set_items(
            _tmpls, data=_data, select=_select, emit=True)
        self.ui.ESubmitTemplate.setEnabled(len(_tmpls) > 1)

    def _redraw__ESubmitTask(self):

        _outs = self.ui.ESubmitTemplate.selected_data() or []
        _tasks, _data = _sort_by_attr(_outs, attr='task')

        # Apply default selection
        _select = None
        if self.work:
            _select = self.work.task
        elif dcc.NAME == 'maya':
            _select = 'lighting'
        elif dcc.NAME == 'hou':
            _select = 'fx'
        elif dcc.NAME == 'nuke':
            _select = 'comp'

        self.ui.ESubmitTask.set_items(
            _tasks, data=_data, select=_select, emit=True)
        self.ui.ESubmitTask.setEnabled(len(_tasks) > 1)

    def _redraw__ESubmitTag(self):

        _outs = self.ui.ESubmitTask.selected_data() or []
        _tags, _data = _sort_by_attr(_outs, attr='tag')
        _work = pipe.CACHE.cur_work or self.work

        # Apply default selection
        _select = None
        if _work and _work.tag in _tags:
            _select = _work.tag
        if not _select and pipe.DEFAULT_TAG in _tags:
            _select = pipe.DEFAULT_TAG

        self.ui.ESubmitTag.set_items(
            _tags, data=_data, select=_select, emit=True)
        self.ui.ESubmitTag.setEnabled(len(_tags) > 1)

    def _redraw__ESubmitFormat(self):

        _LOGGER.debug('REDRAW ESubmitFormat')

        _type = self.ui.ESubmitFormat.currentText()
        _outs = self.ui.ESubmitTag.selected_data() or []
        _fmts, _data = _sort_by_attr(_outs, attr='extn')

        # Determine selection
        _LOGGER.debug(' - TYPE %s', _type)
        _select = None
        if self.work:
            for _fmt in _fmts:
                _outs = self.work.find_outputs(_type, extn=_fmt)
                _LOGGER.debug('   - FMT OUTS %s %s', _fmt, _outs)
                if _outs:
                    _select = _fmt
                    break
        _LOGGER.debug(' - SELECT %s', _select)

        self.ui.ESubmitFormat.set_items(
            _fmts, data=_data, select=_select, emit=True)
        self.ui.ESubmitFormat.setEnabled(len(_fmts) > 1)

    def _redraw__ESubmitOutputs(self):

        _ver = self.ui.ESubmitVersion.currentText()
        _outs = self.ui.ESubmitFormat.selected_data() or []
        _hide_submitted = self.ui.ESubmitHideSubmitted.isChecked()
        _filter = self.ui.ESubmitFilter.text()

        _items = []
        for _out in sorted(_outs, key=pipe.output_clip_sort):

            if not passes_filter(_out.filename, _filter):
                continue
            _submitted = _out.metadata.get('submitted')
            if _submitted and _hide_submitted:
                continue

            # Apply ver filter
            if _ver == 'latest':
                if not _out.is_latest():
                    continue
            elif _ver == 'all':
                pass
            else:
                raise ValueError(_ver)

            # Add output
            _LOGGER.debug(' - BUILD PHOutputItem %s', _out)
            _item = phu_output_item.PHOutputItem(
                list_view=self.ui.ESubmitOutputs,
                output=_out, helper=self, highlight=not _submitted)
            _items.append(_item)

        self.ui.ESubmitOutputs.set_items(_items)

    def _redraw__ESubmitDevTab(self):
        self.ui.ESubmitHandler.redraw()
        self.ui.ESubmitHandlerIcon.redraw()

    def _redraw__ESubmitHandler(self):
        _handlers = sorted(dcc.find_export_handlers('Submit'))
        self.ui.ESubmitHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers)
        _LOGGER.debug(
            ' - BUILD SUBMIT HANDLERS %s',
            self.ui.ESubmitHandler.selected_data())

    def _redraw__ESubmitHandlerIcon(self):
        _exp = self.ui.ESubmitHandler.selected_data()
        if _exp:
            self.ui.ESubmitHandlerIcon.setIcon(qt.obt_icon(_exp.ICON))

    def _callback__EExportPane(self):
        _tab = self.ui.EExportPane.currentWidget()
        _LOGGER.debug('CALLBACK EExportPane %s', _tab)
        if _tab == self.ui.EPublishTab:
            self.ui.EPublishTab.redraw()
        elif _tab == self.ui.EBlastTab:
            self.ui.EBlastTab.redraw()
        elif _tab == self.ui.ECacheTab:
            self.ui.ECacheTab.redraw()
        elif _tab == self.ui.ERenderTab:
            self.ui.ERenderTab.redraw()
        elif _tab == self.ui.ESubmitLegacyTab:
            self.ui.ESubmitTemplate.redraw()
        elif _tab == self.ui.ESubmitDevTab:
            self.ui.ESubmitDevTab.redraw()
        else:
            raise ValueError(_tab)

    def _callback__EPublishHandler(self):
        _handler = self.ui.EPublishHandler.selected_data()
        _LOGGER.debug('UPDATE PUBLISH HANDLER %s', _handler)
        if _handler:
            _handler.update_ui(parent=self, layout=self.ui.EPublishLyt)
        self.ui.EPublishHandlerIcon.redraw()

    def _callback__EBlastHandler(self):
        _handler = self.ui.EBlastHandler.selected_data()
        _LOGGER.debug('UPDATE BLAST HANDLER %s', _handler)
        if _handler:
            _catch = error.get_catcher(qt_safe=True, parent=self)
            _update_func = _catch(_handler.update_ui)
            _update_func(parent=self, layout=self.ui.EBlastLyt)

    def _callback__ECacheHandler(self):
        _handler = self.ui.ECacheHandler.selected_data()
        if _handler:
            _handler.update_ui(parent=self, layout=self.ui.ECacheLyt)
        self.ui.ECacheHandlerIcon.redraw()

    def _callback__ERenderHandler(self):
        _handler = self.ui.ERenderHandler.selected_data()
        if _handler:
            _handler.update_ui(parent=self, layout=self.ui.ERenderLyt)
        self.ui.ERenderHandlerIcon.redraw()

    def _callback__ESubmitTemplate(self):
        self.ui.ESubmitTask.redraw()

    def _callback__ESubmitTask(self):
        self.ui.ESubmitTag.redraw()

    def _callback__ESubmitTag(self):
        self.ui.ESubmitFormat.redraw()

    def _callback__ESubmitFormat(self):
        self.ui.ESubmitOutputs.redraw()

    def _callback__ESubmitVersion(self):
        self.ui.ESubmitOutputs.redraw()

    def _callback__ESubmitHideSubmitted(self):
        self.ui.ESubmitOutputs.redraw()

    def _callback__ESubmitFilter(self):
        self.ui.ESubmitOutputs.redraw()

    def _callback__ESubmitView(self):
        _out = self.ui.ESubmitOutputs.selected_data()
        _out.view()

    def _callback__ESubmitRefresh(self):
        self._reread_entity_outputs()

    def _callback__ESubmitFilterClear(self):
        self.ui.ESubmitFilter.setText('')
        self.ui.ESubmitOutputs.redraw()

    def _callback__ESubmitOutputs(self):
        _out = self.ui.ESubmitOutputs.selected_data()
        self.ui.ESubmitView.setEnabled(bool(_out))

    def _callback__ESubmit(self, force=False):

        from pini.pipe import shotgrid

        _outs = self.ui.ESubmitOutputs.selected_datas()
        _comment = self.ui.ESubmitComment.text()

        _LOGGER.info('SUBMIT %d %s', len(_outs), _outs)
        _LOGGER.info(' - COMMENT %s', _comment)

        # Submit
        _kwargs = {}
        if shotgrid.SUBMITTER.supports_comment:
            _kwargs = {'comment': _comment}
        if shotgrid.SUBMITTER.is_direct:
            _kwargs = {'force': force}
        for _out in _outs:
            shotgrid.SUBMITTER.run(_out, **_kwargs)

        # Notify
        if not force and shotgrid.SUBMITTER.is_direct:
            qt.notify(
                f'Submitted {len(_outs):d} versions to shotgrid.\n\n'
                f'See script editor for details.',
                title='Versions Submitted', icon=shotgrid.ICON)

        self.ui.ESubmitOutputs.redraw()

    def _callback__ESubmitHandler(self):
        _handler = self.ui.ESubmitHandler.selected_data()
        _LOGGER.debug('UPDATE SUBMIT HANDLER %s', _handler)
        if _handler:
            _handler.update_ui(parent=self, layout=self.ui.ESubmitLyt)
        self.ui.ESubmitHandlerIcon.redraw()

    def _context__ESubmitOutputs(self, menu):
        _out = self.ui.ESubmitOutputs.selected_data()
        if _out:
            self._add_output_opts(
                menu=menu, output=_out, parent=self.ui.ESubmitOutputs)


def _sort_by_attr(items, attr, key=None):
    """Sort items by attribute.

    eg. if a list of outputs is sorted by their task attribute, the result
    would be a dictionary with tasks as keys, and then the values would be
    the list of outputs with that task.

    This is useful for sorting items into a display key and a list of
    matching values for a CCombobBox.

    Args:
        items (any): items to sort
        attr (str): attribute to read
        key (func): sort key (eg. to apply task sorting)

    Returns:
        (dict): attribute/items
    """
    _bins = collections.defaultdict(list)
    for _item in items:
        _val = getattr(_item, attr) or ''
        _bins[_val].append(_item)
    _vals, _data = [], []
    for _val in sorted(_bins, key=key):
        _vals.append(_val)
        _data.append(_bins[_val])
    return _vals, _data
