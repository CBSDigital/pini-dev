"""Tools for managing the pini helper export tab."""

# pylint: disable=no-member

import collections
import logging

from pini import qt, pipe, dcc
from pini.qt import QtWidgets, QtGui, Qt
from pini.tools import error
from pini.utils import single


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
                ('Submit', self.ui.ESubmitTab),
        ]:
            _handlers = dcc.find_export_handlers(type_=_type)
            _LOGGER.debug(' - CHECKING TAB %s %s', _tab, _handlers)
            self.ui.EExportPane.set_tab_enabled(_tab, bool(_handlers))
            _LOGGER.debug(' - CHECKED TAB %s', _tab)
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

        self._callback__EExportPane()

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

    def _redraw__ESubmitTab(self):
        self.ui.ESubmitHandler.redraw()
        self.ui.ESubmitHandlerIcon.redraw()

    def _redraw__ESubmitHandler(self):
        _LOGGER.debug('REDRAW ESubmitHandler')

        # Obtain list of submit handlers
        if not self.entity:
            _handlers = []
            _fail = 'No current entity'
        else:
            _handlers = dcc.find_export_handlers(
                'Submit', profile=self.entity.profile)
            _fail = f'No {self.entity.profile} submitters found'
        _LOGGER.debug(' - HANDLERS %d %s', len(_handlers), _handlers)

        # Update ui elements
        self.ui.ESubmitHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers)
        if not _handlers:
            _LOGGER.debug(' - FLUSH SUBMIT LYT')
            qt.flush_layout(self.ui.ESubmitLyt)
            _sep = qt.CHLine(self)
            self.ui.ESubmitLyt.addWidget(_sep)
            _label = QtWidgets.QLabel(self)
            _label.setAlignment(Qt.AlignTop)
            _label.setText(_fail)
            self.ui.ESubmitLyt.addWidget(_label)
            self.ui.ESubmitHandlerIcon.setIcon(QtGui.QIcon())
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
        elif _tab == self.ui.ESubmitTab:
            self.ui.ESubmitTab.redraw()
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

    def _callback__ESubmitHandler(self):
        _handler = self.ui.ESubmitHandler.selected_data()
        _LOGGER.debug('UPDATE SUBMIT HANDLER %s', _handler)
        if _handler:
            _handler.update_ui(parent=self, layout=self.ui.ESubmitLyt)
        self.ui.ESubmitHandlerIcon.redraw()


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
