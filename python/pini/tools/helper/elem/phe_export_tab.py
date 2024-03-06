"""Tools for managing the pini helper export tab."""

# pylint: disable=no-member

import collections
import logging

from pini import qt, pipe, icons, dcc
from pini.tools import usage, error
from pini.utils import single, str_to_ints, passes_filter, wrap_fn

from . import phe_output_item

_LOGGER = logging.getLogger(__name__)


class CLExportTab(object):
    """Class for grouping together elements of the carb helper Export tab."""

    pipe = None

    def init_ui(self):
        """Inititate this tab's interface - triggered by selecting this tab."""
        _LOGGER.debug('INIT UI')

        # Disable tabs if no handlers found
        _tabs = []
        for _tab in ['Publish', 'Blast', 'Render']:
            _handlers = dcc.find_export_handlers(_tab.lower())
            _LOGGER.debug(' - CHECKING TAB %s %s', _tab, _handlers)
            self.ui.EExportPane.set_tab_enabled(_tab, bool(_handlers))
            if _handlers:
                _tabs.append(_tab)
        if dcc.NAME == 'maya':
            _tabs.append('Cache')
        else:
            self.ui.EExportPane.set_tab_enabled('Cache', False)
        _tab = single(_tabs, catch=True)
        _LOGGER.debug(' - SELECT TAB (A) %s', _tab)

        # Select default tab
        if not _tab:
            _work = pipe.cur_work()
            if _work and _work.entity.profile == 'asset':
                _tab = 'Publish'
            else:
                _task = pipe.map_task(_work.task if _work else None)
                _tab = {
                    'anim': 'Cache',
                    'lighting': 'Render',
                }.get(_task)
                _LOGGER.debug(' - SELECT TAB (B) %s task=%s', _tab, _task)
        if _tab:
            self.ui.EExportPane.select_tab(_tab, emit=False)

        self._init_submit_tab()
        self._callback__EExportPane()

    def _init_submit_tab(self):
        """Setup submit tab."""
        self.ui.EExportPane.set_tab_enabled('Submit', pipe.SUBMIT_AVAILABLE)
        if not pipe.SUBMIT_AVAILABLE:
            return
        from pini.pipe import shotgrid

        self.ui.ESubmitComment.disable_save_settings = True
        for _elem in [
                self.ui.ESubmitComment,
                self.ui.ESubmitCommentLabel,
                self.ui.ESubmitCommentLine,
        ]:
            _elem.setVisible(shotgrid.SUBMITTER.supports_comment)

    def _redraw__EPublishHandler(self):

        _handlers = dcc.find_export_handlers('publish')

        # Find selected publish handler
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
            data=_handlers, select=_select)

    def _redraw__EBlastHandler(self):

        _handlers = dcc.find_export_handlers('blast')
        self.ui.EBlastHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers)

    def _redraw__ECacheRefs(self):
        self.ui.ECacheRefs.set_items([], emit=False)

    def _redraw__ERenderHandler(self):
        _val = self.settings.value('widgets/ERenderHandler')
        _LOGGER.debug('REDRAW ERenderHandler %s', _val)
        _handlers = dcc.find_export_handlers('render')
        self.ui.ERenderHandler.set_items(
            labels=[_handler.NAME for _handler in _handlers],
            data=_handlers, select=_val)
        _LOGGER.debug(
            ' - BUILD RENDER HANDLERS %s',
            self.ui.ERenderHandler.selected_data())

    def _redraw__ERender(self):
        _handler = self.ui.ERenderHandler.selected_data()
        _frames = self._get_render_frames()
        _enabled = bool(_handler and _frames)
        self.ui.ERender.setEnabled(_enabled)

    def _redraw__ERenderFrames(self):
        _opts = ['From timeline']
        if dcc.NAME == 'maya':
            _opts += ['From render globals', 'Current frame', 'Manual']
        self.ui.ERenderFrames.set_items(_opts)

    def _redraw__ERenderFramesLabel(self):
        _frames = self._get_render_frames()
        _mode = self.ui.ERenderFrames.currentText()
        _text = '  '
        if _mode != 'Manual':
            _visible = True
            if len(_frames) == 1:
                _text += str(single(_frames))
            else:
                _text += '{:d}-{:d}'.format(_frames[0], _frames[-1])
        else:
            _visible = False
        self.ui.ERenderFramesLabel.setVisible(_visible)
        self.ui.ERenderFramesLabel.setText(_text)

    def _redraw__ESubmitTemplate(self):
        _outs = self.entity.find_outputs() if self.entity else []
        _outs = [_out for _out in _outs if _out.submittable]

        # Determine selection
        _select = None
        if self.work:
            if self.work.find_outputs('render'):
                _select = 'render'
            elif self.work.find_outputs('blast'):
                _select = 'blast'

        _tmpls, _data = _sort_by_attr(_outs, attr='nice_type')
        self.ui.ESubmitTemplate.set_items(
            _tmpls, data=_data, select=_select, emit=True)
        self.ui.ESubmitTemplate.setEnabled(len(_tmpls) > 1)

    def _redraw__ESubmitTask(self):

        _outs = self.ui.ESubmitTemplate.selected_data() or []
        _tasks, _data = _sort_by_attr(_outs, attr='task')

        # Apply default selection
        if self.work:
            _select = self.work.task
        elif dcc.NAME == 'maya':
            _select = 'lighting'
        elif dcc.NAME == 'hou':
            _select = 'fx'
        elif dcc.NAME == 'nuke':
            _select = 'comp'
        else:
            _select = None

        self.ui.ESubmitTask.set_items(
            _tasks, data=_data, select=_select, emit=True)
        self.ui.ESubmitTask.setEnabled(len(_tasks) > 1)

    def _redraw__ESubmitFormat(self):

        _LOGGER.debug('REDRAW ESubmitFormat')

        _type = self.ui.ESubmitFormat.currentText()
        _outs = self.ui.ESubmitTask.selected_data() or []
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
        for _out in _outs:

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
            _item = phe_output_item.PHOutputItem(
                list_view=self.ui.ESubmitOutputs,
                output=_out, helper=self, highlight=not _submitted)
            _items.append(_item)

        _items.sort()
        self.ui.ESubmitOutputs.set_items(_items)

    def _callback__EExportPane(self):
        _tab = self.ui.EExportPane.current_tab_text()
        _LOGGER.debug('CALLBACK EExportPane %s', _tab)
        if _tab == 'Publish':
            self.ui.EPublishHandler.redraw()
            self.ui.EPublish.setEnabled(bool(self.entity))
        elif _tab == 'Blast':
            self.ui.EBlastHandler.redraw()
        elif _tab == 'Cache':
            self.ui.ECacheRefs.redraw()
            self._callback__ECacheRangeReset()
        elif _tab == 'Render':
            self.ui.ERenderHandler.redraw()
            self.load_setting(self.ui.ERenderHandler)
            self.ui.ERenderFrames.redraw()
            self.ui.ERenderFramesLabel.redraw()
            self.ui.ERender.redraw()
        elif _tab == 'Submit':
            self.ui.ESubmitTemplate.redraw()
        else:
            raise ValueError(_tab)

    def _callback__EPublishHandler(self):
        _handler = self.ui.EPublishHandler.selected_data()
        _LOGGER.debug('UPDATE PUBLISH HANDLER %s', _handler)
        if _handler:
            _handler.update_ui(parent=self, layout=self.ui.EPublishLayout)

    @usage.get_tracker('PiniHelper.Publish')
    def _callback__EPublish(self, force=False):
        from pini.tools import helper

        _LOGGER.info('PUBLISH SCENE force=%d', force)

        _cur_work = pipe.CACHE.cur_work
        if not _cur_work:
            qt.notify(
                'No current work found.\n\nPlease save your scene using '
                '{}.'.format(helper.TITLE), title='No Current Work',
                icon=icons.find('Vomit'))
            return None

        _handler = self.ui.EPublishHandler.selected_data()
        _LOGGER.info(' - HANDLER %s', _handler)
        _pub = _handler.publish(work=_cur_work, force=force)

        # Update ui
        self.jump_to(_cur_work)
        self.ui.WTasks.redraw()

        return _pub

    def _callback__EBlastHandler(self):
        _handler = self.ui.EBlastHandler.selected_data()
        _LOGGER.debug('UPDATE BLAST HANDLER %s', _handler)
        if _handler:
            _catch = error.get_catcher(qt_safe=True, parent=self)
            _update_func = _catch(_handler.update_ui)
            _update_func(parent=self, layout=self.ui.EBlastLayout)

    @usage.get_tracker('PiniHelper.Blast')
    def _callback__EBlast(self):
        _handler = self.ui.EBlastHandler.selected_data()
        _LOGGER.info('BLAST %s', _handler)
        _handler.blast()

    def _callback__ECacheRefs(self):
        _refs = self.ui.ECacheRefs.selected_items()
        self.ui.ECache.setEnabled(bool(_refs))

    def _callback__ECacheRefsRefresh(self):
        self.ui.ECacheRefs.redraw()

    def _callback__ECacheRangeReset(self):
        try:
            _start, _end = dcc.t_range()
        except NotImplementedError:
            self.ui.ECacheStart.setEnabled(False)
            self.ui.ECacheEnd.setEnabled(False)
        else:
            self.ui.ECacheStart.setValue(_start)
            self.ui.ECacheEnd.setValue(_end)

    def _callback__ECache(self):
        raise NotImplementedError('Implemented in dcc subclass')

    def _callback__ERenderHandler(self):
        _handler = self.ui.ERenderHandler.selected_data()
        self.save_settings()
        _LOGGER.debug('UPDATE RENDER HANDLER %s', _handler)
        if _handler:
            _build_ui = wrap_fn(
                _handler.update_ui, parent=self, layout=self.ui.ERenderLayout)
            _build_ui = error.get_catcher(parent=self, qt_safe=True)(_build_ui)
            _build_ui()
            self.save_settings()
            _icon = _handler.to_icon()
            _desc = _handler.description
        else:
            _icon = icons.find('Dizzy Face')
            _desc = ''
        self.ui.ERenderHandlerIcon.setIcon(qt.to_icon(_icon))
        self.ui.ERenderHandlerDesc.setText(_desc)

    def _callback__ERenderFramesReset(self):
        self.ui.ERenderFramesLabel.redraw()
        _rng = dcc.t_range(int)
        _rng_str = '{:d}-{:d}'.format(*_rng)
        self.ui.ERenderFramesText.setText(_rng_str)

    def _get_render_frames(self):
        """Determine render frame range.

        Returns:
            (int list): render frames (eg. [1, 2, 3, 4, 5])
        """
        _rng_mode = self.ui.ERenderFrames.currentText()
        if not _rng_mode:
            return []
        if _rng_mode == 'From timeline':
            return dcc.t_frames()
        if _rng_mode == 'Current frame':
            return [dcc.cur_frame()]
        if _rng_mode == 'From render globals':
            return dcc.t_frames(mode='RenderGlobals')
        if _rng_mode == 'Manual':
            try:
                return str_to_ints(self.ui.ERenderFramesText.text())
            except ValueError:
                return []
        raise ValueError(_rng_mode)

    def _callback__ERenderFrames(self):
        _frames = self.ui.ERenderFrames.currentText()
        self.ui.ERenderFramesLabel.redraw()
        self.ui.ERenderFramesText.setVisible(_frames == 'Manual')

    def _callback__ERenderFramesText(self):
        self.ui.ERender.redraw()

    @usage.get_tracker('PiniHelper.Render')
    def _callback__ERender(self):
        _handler = self.ui.ERenderHandler.selected_data()
        _handler.render(frames=self._get_render_frames())

    def _callback__ESubmitTemplate(self):
        self.ui.ESubmitTask.redraw()

    def _callback__ESubmitTask(self):
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

    def _callback__ESubmit(self):

        from pini.pipe import shotgrid

        _outs = self.ui.ESubmitOutputs.selected_datas()
        _comment = self.ui.ESubmitComment.text()
        _LOGGER.info('SUBMIT %d %s', len(_outs), _outs)
        _LOGGER.info(' - COMMENT %s', _comment)

        # Submit
        _force = len(_outs) > 1
        for _out in qt.progress_bar(
                _outs, 'Submitting {:d} output{}', stack_key='SubmitOuts',
                show=_force):
            _LOGGER.info(' - SUBMIT %s', _out)
            _kwargs = {}
            if shotgrid.SUBMITTER.supports_comment:
                _kwargs = {'comment': _comment}
            if shotgrid.SUBMITTER.is_direct:
                _kwargs = {'force': _force}
            shotgrid.SUBMITTER.run(_out, **_kwargs)

        # Notify
        if _force and shotgrid.SUBMITTER.is_direct:
            qt.notify(
                'Submitted {:d} versions to shotgrid.\n\nSee script editor '
                'for details.'.format(len(_outs)),
                title='Versions Submitted', icon=shotgrid.ICON)

        self.ui.ESubmitOutputs.redraw()

    def _context__ECacheRefs(self, menu):
        _cacheable = self.ui.ECacheRefs.selected_data(catch=True)
        if _cacheable:
            menu.add_label('Cacheable {}'.format(_cacheable.output_name))
            menu.add_separator()
            menu.add_action('Select in scene', _cacheable.select_in_scene,
                            icon=icons.find('Hook'))
            if _cacheable.path:
                menu.add_separator()
                menu.add_file_actions(_cacheable.path)

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
        _val = getattr(_item, attr)
        _bins[_val].append(_item)
    _vals, _data = [], []
    for _val in sorted(_bins, key=key):
        _vals.append(_val)
        _data.append(_bins[_val])
    return _vals, _data
