"""Tools for manging the pini helper outputs tab."""  # pylint: disable=too-many-lines

# pylint: disable=no-member

import logging
import operator

from pini import qt, pipe, dcc, icons
from pini.dcc import pipe_ref
from pini.tools import usage
from pini.utils import (
    wrap_fn, plural, chain_fns, strftime, clip, passes_filter, safe_zip,
    apply_filter, single, split_base_index, to_nice)

from .phe_output_item import PHOutputItem
from .phe_scene_ref_item import PHSceneRefItem
from ..ph_utils import UPDATE_ICON, CURRENT_ICON, output_to_namespace

_LOGGER = logging.getLogger(__name__)
_LATEST_ICON = icons.find('Light Bulb')
_REPLACE_ICON = icons.find('Right Arrow Curving Left')


class CLSceneTab(object):
    """Class for grouping together elements of pini helper Outputs tabs."""

    all_outs = ()

    def __init__(self):
        """Constructor."""

        self._staged_imports = []
        self._staged_deletes = set()
        self._staged_updates = {}
        self._staged_renames = {}

        self.ui.SOutputs.doubleClicked.connect(
            self._doubleClick__SOutputs)

    def init_ui(self, switch_tabs=True):
        """Inititate this tab's interface - triggered by selecting this tab.

        Args:
            switch_tabs (bool): whether we are switching to this tab
                (this can be disabled if the tab is being re-initiated
                internally)
        """
        _LOGGER.debug('INIT UI switch=%d', switch_tabs)

        # Choose selected tab
        _tab = None
        if self.target and isinstance(self.target, pipe.CPOutputBase):
            _LOGGER.debug(' - TARGET %s', self.target)
            if self.target.nice_type == 'publish':
                _tab = 'Asset'
        elif switch_tabs:
            _task = pipe.cur_task(fmt='pini')
            _map = {'anim': 'Asset',
                    'fx': 'Cache',
                    'lighting': 'Cache',
                    'lsc': 'Render',
                    'comp': 'Render'}
            _tab = _map.get(_task)
        _LOGGER.debug(' - SELECT TAB %s', _tab)
        if _tab:
            self.ui.SOutputsPane.select_tab(_tab)
        else:
            self.settings.apply_to_widget(self.ui.SOutputsPane)

        self.settings.apply_to_widget(self.ui.SLookdev)
        self._callback__SOutputsPane()

        self.ui.SSceneRefs.redraw()

        # Fix OOutputsPane on 4k monitors
        _tab_height = self.ui.MainPane.tabBar().height()
        self.ui.SOutputsPane.setFixedHeight(_tab_height+1)

    def _read_all_outs(self):
        """Read outputs for the current outputs tab selection.

        ie. read all Asset/Cache/Render ouputs.

        Returns:
            (CPOutput list): outputs
        """
        _tab = self.ui.SOutputsPane.current_tab_text()

        _outs = []
        if _tab == 'Asset':
            _outs = self.job.find_publishes(extns=dcc.REF_EXTNS)
        elif _tab == 'Cache':
            if self.entity:
                _outs += self.entity.find_outputs('cache')
                _outs += self.entity.find_outputs('cache_seq')
                _outs += self.entity.find_outputs('ass_gz')
        elif _tab == 'Render':
            if self.entity:
                _outs += self.entity.find_outputs('render')
                _outs += self.entity.find_outputs('render_mov')
                _outs += self.entity.find_outputs('plate')
                _outs += self.entity.find_outputs('blast')
        else:
            raise ValueError(_tab)

        return _outs

    def _redraw__SOutputType(self):

        # Set lists + data based on outputs mode
        _mode = self.ui.SOutputsPane.current_tab_text()
        _add_all = True
        if _mode == 'Asset':
            _label, _types, _data, _select = self._redraw_out_type_asset()
        elif _mode == 'Cache':
            _label = 'Type'
            _types = sorted({_out.output_type for _out in self.all_outs})
            _data = [
                [_out for _out in self.all_outs if _out.output_type == _type]
                for _type in _types]
            _select = 'all'
        elif _mode == 'Render':
            _label = 'Template'
            _types = sorted({_out.type_ for _out in self.all_outs})
            _data = [
                [_out for _out in self.all_outs if _out.type_ == _type]
                for _type in _types]
            _add_all = False
            _select = 'render'
        else:
            raise ValueError(_mode)

        # Add all
        if _add_all and len(_types) > 1:
            _types.insert(0, 'all')
            _data.insert(0, self.all_outs)
            assert isinstance(self.all_outs, (list, tuple))

        # Update ui
        self.ui.SOutputType.set_items(
            _types, data=_data, emit=False, select=_select)
        self.ui.SOutputType.setEnabled(len(_types) > 1)
        self.ui.SOutputTypeLabel.setText(_label)

        self.ui.SOutputTask.redraw()

    def _redraw_out_type_asset(self):
        """Build redraw output type elements in assets mode.

        Returns:
            (tuple): output type elements
        """
        _LOGGER.debug(' - REDRAW OUT TYPE ASSET %s', self.target)
        _label = 'Category'
        _outs = [_out for _out in self.all_outs if _out.asset]
        _types = sorted({
            _out.asset_type for _out in _outs})
        _data = [
            [_out for _out in _outs if _out.asset_type == _type]
            for _type in _types]

        # Determine selection
        _LOGGER.debug(
            '   - SELECTION %d %s',
            isinstance(self.target, pipe.CPOutputBase), _types)
        if (
                self.target and
                isinstance(self.target, pipe.CPOutputBase) and
                self.target.asset_type in _types):
            _select = self.target.asset_type
        else:
            _select = 'rig'
        _LOGGER.debug('   - SELECT OUT TYPE ASSET %s', _select)

        return _label, _types, _data, _select

    def _redraw__SOutputTask(self):

        _LOGGER.debug(' - REDRAW SOutputTask')

        _mode = self.ui.SOutputsPane.current_tab_text()
        _type = self.ui.SOutputType.selected_text()
        _outs = self.ui.SOutputType.selected_data() or []

        # Build list of tasks/data
        _tasks, _data = [], []
        for _task in sorted({_output_to_task_label(_out) for _out in _outs},
                            key=pipe.task_sort):
            _tasks.append(_task or '<None>')
            _data.append([
                _out for _out in _outs if _output_to_task_label(_out) == _task])

        # Select default
        if self.target in _outs:
            _select = single([
                _task for _task, _task_outs in safe_zip(_tasks, _data)
                if self.target in _task_outs])
            _LOGGER.debug(
                '   - FIND SELECTED TASK FROM TARGET %s %s', _select,
                self.target)
        elif _mode == 'render':
            _select = 'lighting'
        elif 'rig' in _tasks:  # Select default before add all
            _select = 'rig'
        elif _tasks:
            _select = _tasks[0]
        else:
            _select = None
        if not _select:
            _select = {'anim': 'rig'}.get(pipe.cur_task(), _select)
        _LOGGER.debug('   - SELECT %s', _select)

        if len(_tasks) > 1:
            _tasks.insert(0, 'all')
            _data.insert(0, _outs)

        # Update ui
        self.ui.SOutputTask.set_items(
            _tasks, data=_data, emit=False, select=_select)
        self.ui.SOutputTask.setEnabled(bool(_tasks))
        for _elem in [self.ui.SOutputTask, self.ui.SOutputTaskLabel]:
            _elem.setVisible(_type != 'plate')
        self.ui.SOutputTask.setEnabled(len(_tasks) > 1)
        if not _select:
            self.settings.apply_to_widget(self.ui.SOutputTask, emit=False)

        self.ui.SOutputTag.redraw()

    def _redraw__SOutputTag(self):

        _select = None
        _outs = self.ui.SOutputTask.selected_data() or []
        _tags = sorted({_out.tag for _out in _outs}, key=pipe.tag_sort)
        _data = [
            [_out for _out in _outs if _out.tag == _tag]
            for _tag in _tags]
        if len(_tags) > 1:
            _tags.insert(0, 'all')
            _data.insert(0, _outs)
            _select = 'all'
        if (
                isinstance(self.target, pipe.CPOutputBase) and
                self.target.tag in _tags):
            _select = self.target.tag
        _labels = [{None: '<default>'}.get(_tag, _tag) for _tag in _tags]

        self.ui.SOutputTag.set_items(
            _labels, data=_data, emit=True, select=_select)
        self.ui.SOutputTag.setEnabled(len(_labels) > 1)

    def _redraw__SOutputFormat(self):

        _select = None
        _outs = self.ui.SOutputTag.selected_data() or []
        _extns = sorted({_out.extn for _out in _outs})
        _data = [
            [_out for _out in _outs if _out.extn == _extn]
            for _extn in _extns]
        if len(_extns) > 1:
            _extns.insert(0, 'all')
            _data.insert(0, _outs)
            _select = 'all'

        self.ui.SOutputFormat.set_items(
            _extns, data=_data, emit=True, select=_select)
        self.ui.SOutputFormat.setEnabled(len(_extns) > 1)

    def _redraw__SOutputVers(self):

        _cur = self.ui.SOutputVers.currentText()
        _outs = self.ui.SOutputFormat.selected_data() or []

        # Build opts list
        _opts = []
        if [_out for _out in _outs if not _out.ver_n]:
            _opts.append("versionless")
        _opts.append("latest")
        _opts.append("all")

        _sel = _cur if _cur in _opts else "latest"
        self.ui.SOutputVers.set_items(_opts, select=_sel, emit=True)
        self.ui.SOutputVers.setEnabled(bool(_outs))

    def _redraw__SOutputs(self):

        _LOGGER.debug(' - REDRAW OOutputs')

        _filter = self.ui.SOutputsFilter.text()
        _outs = self.ui.SOutputFormat.selected_data() or []
        _scene_outs = sorted({
            _ref.to_output(use_cache=False) for _ref in dcc.find_pipe_refs()})
        _version_mode = self.ui.SOutputVers.currentText()

        # Get list of outputs
        if _filter:
            _outs = apply_filter(
                _outs, _filter, key=operator.attrgetter('path'))
        if _version_mode == 'versionless':
            _outs = [_out for _out in _outs if not _out.ver_n]
        elif _version_mode == 'latest':
            _outs = [_out for _out in _outs
                     if _out.is_latest() and _out.ver_n]
        elif _version_mode == 'all':
            pass
        else:
            raise ValueError(_version_mode)
        _LOGGER.debug('   - FOUND %d OUTS', len(_outs))

        # Determine selection
        _select = None
        if self.target in _outs:
            _select = self.target
        _LOGGER.debug('   - SELECT %s', _select)

        # Build items
        _items = []
        for _out in sorted(_outs):
            _item = PHOutputItem(
                helper=self, output=_out, list_view=self.ui.SOutputs,
                highlight=_out in _scene_outs)
            _items.append(_item)
        self.ui.SOutputs.set_items(_items, select=_select)

        # Update dependent elements
        self.ui.SOutputInfo.redraw()
        self.ui.SViewer.redraw()

    def _redraw__SViewer(self):

        _out = self.ui.SOutputs.selected_data(catch=True)
        _enabled = False
        _plays_seqs = None
        if isinstance(_out, (clip.Seq, clip.Video)):
            _enabled = True
            _plays_seqs = isinstance(_out, clip.Seq)
        _viewer = clip.find_viewer()
        _viewers = clip.find_viewers(plays_seqs=_plays_seqs)
        _enabled = _enabled and bool(_viewers)

        self.ui.SViewer.set_items(
            labels=[_viewer.NAME for _viewer in _viewers],
            data=_viewers, select=_viewer)
        for _elem in [self.ui.SViewer, self.ui.SView]:
            _elem.setEnabled(_enabled)

    def _redraw__SOutputInfo(self):

        _out = self.ui.SOutputs.selected_data(catch=True)
        _text = ''
        if _out:

            _LOGGER.debug(' - READ OUTPUT %s', _out)
            _owner = _out.metadata.get('owner')
            if _owner:
                _text += 'Owner: {}\n'.format(_owner)
            _mtime = _out.metadata.get('mtime')
            if _mtime:
                _text += 'Exported: {}\n'.format(
                    strftime('%a %d %b %H:%M', _mtime))

            # Add range
            _rng = _out.metadata.get('range')
            if not _rng:
                _fmt = None
            elif len(_rng) == 1:
                _fmt = 'Range: {:.00f}\n'
            elif len(_rng) == 2:
                _fmt = 'Range: {:.00f}-{:.00f}\n'
            else:
                raise ValueError(_rng)
            if _fmt:
                _text += _fmt.format(*_rng)

        _text = _text.strip()
        self.ui.SOutputInfo.setVisible(bool(_text))
        self.ui.SOutputInfo.setText(_text)

    def _redraw__SReset(self):

        # Update 'reset' button
        _resettable = bool(
            self._staged_imports or
            self._staged_updates or
            self._staged_renames or
            self._staged_deletes)
        self.ui.SReset.setEnabled(_resettable)

    def _redraw__SAdd(self):
        _outs = [_out for _out in self.ui.SOutputs.selected_datas()
                 if dcc.can_reference_output(_out)]
        _mode = self.ui.SOutputsPane.current_tab_text()
        self.ui.SAdd.setText('Add {:d} {}{}'.format(
            len(_outs), _mode.lower(), plural(_outs)))
        self.ui.SAdd.setEnabled(bool(_outs))

    def _redraw__SSceneRefs(self):

        _LOGGER.debug('REDRAW SCENE REFS')

        # Build items list
        _items = []
        for _ref in self._build_scene_refs_display_list():
            _output = _namespace = None
            if isinstance(_ref, _StagedRef):
                _status = 'new'
            elif _ref in self._staged_updates:
                _status = 'update'
                _output = self._staged_updates[_ref]
            elif _ref in self._staged_renames:
                _status = 'rename'
                _namespace = self._staged_renames[_ref]
            elif _ref in self._staged_deletes:
                _status = 'delete'
            elif not _ref.output:
                _status = 'missing from cache'
                _output = _ref.to_output(use_cache=False)
            else:
                _status = None
            _LOGGER.debug(' - ADDING REF %s status=%s', _ref, _status)
            _item = PHSceneRefItem(
                self.ui.SSceneRefs, ref=_ref, status=_status, output=_output,
                helper=self, namespace=_namespace)
            _items.append(_item)

        # NOTE: better not to apply viewport selection as most common use
        # case is probably update everything - viewport selection is most
        # likely arbitrary in most cases
        self.ui.SSceneRefs.set_items(_items, select=None)
        self.ui.SApply.redraw()

    def _build_scene_refs_display_list(self):
        """Build list of scene references to display.

        Returns:
            (CPipeRef list): scene refs to display
        """
        _scene_refs = dcc.find_pipe_refs()
        _LOGGER.debug(' - SCENE REFS %s', _scene_refs)
        _LOGGER.debug(' - STAGED IMPORTS %s', self._staged_imports)

        # Read filters
        _filter = self.ui.SSceneRefsFilter.text()
        _show_models = self.ui.SSceneRefsShowModels.isChecked()
        _show_rigs = self.ui.SSceneRefsShowRigs.isChecked()
        _show_shaders = self.ui.SSceneRefsShowLookdevs.isChecked()
        _show_abcs = self.ui.SSceneRefsShowAbcs.isChecked()
        _type_filter = any([
            _show_models,
            _show_rigs,
            _show_shaders,
            _show_abcs,
        ])
        _LOGGER.debug(
            ' - TYPE FILTER %d show_models=%d', _type_filter, _show_models)

        _refs = []
        for _ref in sorted(
                _scene_refs + self._staged_imports, key=_sort_scene_ref):
            if not passes_filter(_ref.namespace, _filter):
                continue
            if _type_filter:
                if _show_models and pipe.map_task(_ref.task) == 'model':
                    pass
                elif _show_rigs and pipe.map_task(_ref.task) == 'rig':
                    pass
                elif _show_shaders and _ref.output.metadata.get('shd_yml'):
                    pass
                elif _show_abcs and _ref.extn == 'abc':
                    pass
                else:
                    _LOGGER.debug(
                        ' - REJECTED %s task=%s extn=%s', _ref,
                        _ref.task, _ref.extn)
                    continue
            _refs.append(_ref)

        return _refs

    def _redraw__SApply(self):
        _updates = (len(self._staged_imports) +
                    len(self._staged_deletes) +
                    len(self._staged_updates) +
                    len(self._staged_renames))
        self.ui.SApply.setEnabled(bool(_updates))
        self.ui.SApply.setText('Apply {:d} update{}'.format(
            _updates, plural(_updates)))

    def _callback__SOutputsPane(self):

        self.settings.save_widget(self.ui.SOutputsPane)

        _tab = self.ui.SOutputsPane.current_tab_text()
        self.all_outs = self._read_all_outs()

        _viewer = _tab == 'Render'
        _maya_cache = dcc.NAME == 'maya' and _tab == 'Cache'
        for _tgl, _elems in [
                (_maya_cache, [
                    self.ui.SLookdev, self.ui.SLookdevSpacer,
                    self.ui.SLookdevLabel, self.ui.SBuildPlates,
                    self.ui.SAbcMode, self.ui.SAbcModeSpacer,
                    self.ui.SAbcModeLabel]),
                (_viewer, [self.ui.SViewer, self.ui.SView])]:
            for _elem in _elems:
                _elem.setVisible(_tgl)

        self.ui.SOutputType.redraw()

    def _callback__SOutputType(self):
        self.ui.SOutputTask.redraw()

    def _callback__SOutputTask(self):
        self.settings.save_widget(self.ui.SOutputTask)
        self.ui.SOutputTag.redraw()

    def _callback__SOutputTag(self):
        self.ui.SOutputFormat.redraw()

    def _callback__SOutputFormat(self):
        self.ui.SOutputVers.redraw()

    def _callback__SOutputVers(self):
        self.ui.SOutputs.redraw()

    def _callback__SOutputs(self):
        self.ui.SAdd.redraw()
        self.ui.SOutputInfo.redraw()
        if self.ui.SOutputsPane.current_tab_text() == 'Render':
            self.ui.SViewer.redraw()

    def _callback__SOutputsFilter(self):
        self.ui.SOutputs.redraw()

    def _callback__SOutputsFilterClear(self):
        self.ui.SOutputsFilter.setText('')

    def _callback__SLookdev(self):
        self.settings.save_widget(self.ui.SLookdev)

    def _callback__SView(self):
        _viewer = self.ui.SViewer.selected_data()
        _out = self.ui.SOutputs.selected_data()
        _viewer.view(_out)

    def _callback__SAdd(self, outs=None):
        _outs = outs or self.ui.SOutputs.selected_datas()
        for _out in _outs:
            if not dcc.can_reference_output(_out):
                continue
            self._stage_import(_out)
        self.ui.SSceneRefs.redraw()

    def _callback__SUpdateToLatest(self):

        _refs = (self.ui.SSceneRefs.selected_datas() or
                 self.ui.SSceneRefs.all_data())
        _updateables = [
            _ref for _ref in _refs
            if _ref.output and not _ref.output.is_latest()]
        for _ref in _updateables:
            self._stage_update(_ref, _ref.output.find_latest())

    def _callback__SDelete(self):

        for _ref in self.ui.SSceneRefs.selected_datas():
            self._stage_delete(_ref, redraw=False)
        self.ui.SSceneRefs.redraw()

    def _callback__SReset(self):

        self._staged_updates = {}
        self._staged_imports = []
        self._staged_renames = {}
        self._staged_deletes = set()

        self.ui.SSceneRefs.redraw()

    def _callback__SInfo(self):
        self.ui.SOutputs.redraw()
        self.ui.SSceneRefs.redraw()

    def _callback__SRefresh(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefs(self):

        _refs = self.ui.SSceneRefs.selected_datas()
        self.ui.SDelete.setEnabled(bool(_refs))
        self.ui.SReset.redraw()

        # Update 'Update to latest' button
        _updateables = _refs or self.ui.SSceneRefs.all_data()
        _not_latest = [_ref for _ref in _updateables
                       if _ref.output and not _ref.output.is_latest()]
        self.ui.SUpdateToLatest.setEnabled(bool(_not_latest))

        # Force redraw list - fixes a weird bug where multi select
        # fails to show central elements as selected
        self.setFocus()

    def _callback__SSceneRefsShowModels(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsShowRigs(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsShowLookdevs(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsShowAbcs(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsTypeFilterReset(self):
        for _elem in [
                self.ui.SSceneRefsShowRigs,
                self.ui.SSceneRefsShowLookdevs,
                self.ui.SSceneRefsShowAbcs,
        ]:
            _elem.setChecked(False)
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsFilter(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsFilterClear(self):
        self.ui.SSceneRefsFilter.setText('')

    @usage.get_tracker(name='PiniHelper.RefOutputs')
    def _callback__SApply(self, force=False):

        # Build list of updates
        _updates = []
        while self._staged_deletes:
            _ref = self._staged_deletes.pop()
            _delete_fn = wrap_fn(_ref.delete, force=True)
            _updates.append(_delete_fn)
        _updates += self._build_import_updates()
        while self._staged_updates:
            _ref = list(self._staged_updates.keys())[0]
            _out = self._staged_updates.pop(_ref)
            _update_fn = wrap_fn(_ref.update, _out)
            _updates.append(_update_fn)
        while self._staged_renames:
            _ref = list(self._staged_renames.keys())[0]
            _name = self._staged_renames.pop(_ref)
            _updates.append(wrap_fn(_ref.rename, _name))

        # Execute updates
        if not force:
            qt.ok_cancel(
                'Apply {:d} scene update{}?'.format(
                    len(_updates), plural(_updates)),
                parent=self, icon=icons.find('Gear'))
        for _update in qt.progress_bar(
                _updates, 'Applying {:d} update{}', parent=self):
            _update()

        self.ui.SOutputs.redraw()
        self.ui.SSceneRefs.redraw()

    def _build_import_updates(self):
        """Build import updates from staged import list.

        NOTE: lookdev updates need to be run after any parent ref imports,
        but it should be find to just sort by namespace.

        Returns:
            (func list): list of import action functions
        """
        _updates = []
        self._staged_imports.sort(key=operator.attrgetter('namespace'))
        while self._staged_imports:

            _ref = self._staged_imports.pop(0)
            if _ref.ignore_on_apply:
                continue

            _lookdev = self.ui.SLookdev.currentText()
            _abc_mode = self.ui.SAbcMode.currentText()
            _build_plates = self.ui.SBuildPlates.isChecked()

            _LOGGER.info(' - BUILDING IMPORT UPDATE %s', _ref)
            if (
                    dcc.NAME == 'maya' and
                    _ref.output.extn == 'abc' and
                    _lookdev != 'None'):
                _import_fn = wrap_fn(
                    dcc.create_cache_ref, namespace=_ref.namespace,
                    cache=_ref.output, attach_mode=_lookdev,
                    build_plates=_build_plates, abc_mode=_abc_mode)
            elif _ref.attach:
                _import_fn = wrap_fn(
                    _apply_lookdev, ref=_ref.attach, lookdev=_ref.output)
            else:
                _import_fn = wrap_fn(
                    dcc.create_ref, namespace=_ref.namespace, path=_ref.output)
            _updates.append(_import_fn)

        return _updates

    def _context__SOutputs(self, menu):

        _out = self.ui.SOutputs.selected_data(catch=True)
        _outs = self.ui.SOutputs.selected_datas()
        if _out:

            self._add_output_opts(
                menu=menu, output=_out, parent=self.ui.SOutputs)
            menu.add_separator()

            # Add replace options
            _view_refs = dcc.find_pipe_refs(selected=True)
            _helper_refs = self.ui.SSceneRefs.selected_datas()
            for _label, _refs in [
                    ('viewport', _view_refs),
                    ('helper', _helper_refs),
            ]:
                menu.add_action(
                    'Swap {} selection to {}'.format(
                        _label, _out.output_name or _out.asset),
                    wrap_fn(self._stage_replace_refs, output=_out, refs=_refs),
                    enabled=bool(_refs), icon=_REPLACE_ICON)

    def _context__SSceneRefs(self, menu):

        _LOGGER.debug(' - CTX SCENE REFS')
        _ref = self.ui.SSceneRefs.selected_data(catch=True)
        _refs = self.ui.SSceneRefs.selected_datas()
        _LOGGER.debug(' - READ %s %s', _ref, _refs)
        if _ref:
            self._ctx_scene_ref_add_opts(menu, ref=_ref)
        elif _refs:
            self._ctx_scene_refs_add_opts(menu, refs=_refs)

    def _ctx_scene_ref_add_opts(self, menu, ref):
        """Add context options for a single output reference.

        Args:
            menu (QMenu): menu to add items to
            ref (CPipeRef): selected reference
        """
        _LOGGER.debug(' - CTX SCENE REF ADD OPTS %s', ref)
        _out = ref.to_output(use_cache=False)
        _out_c = pipe.CACHE.obt(_out)
        if ref.namespace == _out.output_name:
            _base = _out.output_name
        else:
            _base, _ = split_base_index(ref.namespace)

        menu.add_label('Ref: '+ref.namespace)
        menu.add_separator()
        if isinstance(ref, pipe_ref.CPipeRef):  # Not if staged ref
            menu.add_action(
                'Select in scene', ref.select_in_scene, icons.FIND)
        menu.add_action(
            'Remove', wrap_fn(self._stage_delete, ref),
            icon=icons.find('Cross Mark'))
        menu.add_action(
            'Rename', chain_fns(
                wrap_fn(ref.rename_using_dialog, parent=self),
                self._callback__SRefresh),
            icon=icons.EDIT)
        menu.add_action(
            'Duplicate',
            wrap_fn(self._stage_import, _out_c, base=_base, redraw=True),
            icon=icons.DUPLICATE)
        menu.add_separator()

        # Update options
        _LOGGER.debug('   - ADD UPDATE OPTS %s', ref.output)
        if not ref.output:
            _ety_c = pipe.CACHE.obt_entity(_out.entity)
            menu.add_action(
                'Rebuild cache',
                chain_fns(
                    wrap_fn(_ety_c.find_outputs, force=2),
                    self._callback__Refresh,
                    self._callback__MainPane),
                icon=icons.REFRESH)
        else:
            _out = ref.output
            _latest = ref.output.find_latest()
            menu.add_action(
                'Update to latest',
                wrap_fn(self._stage_update, ref, _latest),
                icon=_LATEST_ICON, enabled=not _out.is_latest())
            menu.add_action(
                'Update name to match tag',
                wrap_fn(self._rename_ref, ref=ref, namespace=_out.tag),
                icon=UPDATE_ICON, enabled=bool(_out.tag))
            self._ctx_scene_refs_add_update_tag_opts(menu, refs=[ref])
            self._ctx_scene_ref_add_update_ver_opts(menu, ref=ref)
            self._ctx_scene_ref_add_update_rep_opts(menu, refs=[ref])
            menu.add_separator()

            self._add_output_opts(
                menu=menu, output=_out, header=False, delete=False,
                add=False, ref=ref, parent=self.ui.SSceneRefs)

    def _ctx_scene_refs_add_update_tag_opts(self, menu, refs):
        """Add options relating to swapping to a different tag.

        Args:
            menu (QMenu): menu to add actions to
            refs (CPipeRef list): selected references
        """
        _out = single({_ref.output for _ref in refs}, catch=True)
        if not _out:
            return
        _tags_menu = menu.add_menu('Update tag', enabled=bool(_out.work_dir))
        if not _out.work_dir:
            return

        # Add tag opts
        _outs = _out.work_dir.find_outputs(
            output_type=_out.output_type, ver_n='latest')
        _tags = sorted({_out.tag for _out in _outs}, key=pipe.tag_sort)
        for _tag in _tags:

            # Find latest version for this tag
            _latest = _out.work_dir.find_output(
                tag=_tag, ver_n='latest', output_type=_out.output_type,
                catch=True)
            if not _latest:
                _latest = _out.work_dir.find_output(
                    tag=_tag, ver_n='latest', output_type=_out.output_type,
                    extn=_out.extn, catch=True)
            if not _latest:
                continue

            # Determine icon/enabled
            if _tag == _out.tag:
                _icon = CURRENT_ICON
                _enabled = False
            else:
                _icon = UPDATE_ICON
                _enabled = True

            # Build update func
            _funcs = []
            for _ref in refs:
                _fn = wrap_fn(self._stage_update, ref=_ref, output=_latest)
                _funcs.append(_fn)

            _tags_menu.add_action(
                _tag or '<default>', chain_fns(*_funcs),
                icon=_icon, enabled=_enabled)

            if _tag in ('main', 'default', None):
                _tags_menu.add_separator()

    def _ctx_scene_ref_add_update_ver_opts(self, menu, ref):
        """Add options relating to swapping to a different version.

        Args:
            menu (QMenu): menu to add actions to
            ref (CPipeRef): selected reference
        """
        _out = ref.output

        _vers_menu = menu.add_menu('Update version')
        _vers = sorted(_out.find_vers(), key=pipe.ver_sort, reverse=True)
        for _idx, _ver in enumerate(_vers):
            _icon = UPDATE_ICON
            _enabled = True
            if _ver == _out:
                _icon = CURRENT_ICON
                _enabled = False
            if not _ver.ver_n:
                _label = 'versionless'
            else:
                _label = 'v{:03d}'.format(_ver.ver_n)
            _fn = wrap_fn(self._stage_update, ref=ref, output=_ver)
            _vers_menu.add_action(_label, _fn, icon=_icon, enabled=_enabled)
            if not _idx and not _ver.ver_n:
                _vers_menu.add_separator()

    def _ctx_scene_ref_add_update_rep_opts(self, menu, refs):
        """Add context options for swapped to different rep of a scene ref.

        Args:
            menu (QMenu): menu to add actions to
            refs (CPipeRef list): selected references
        """
        _out = single({_ref.output for _ref in refs}, catch=True)
        if not _out:
            return
        _reps = _out.find_reps()
        _reps_menu = menu.add_menu('Update rep', enabled=bool(_reps))
        for _rep in _reps:
            _label = to_nice(_rep.content_type)
            _fns = []
            for _ref in refs:
                _fn = wrap_fn(self._stage_update, ref=_ref, output=_rep)
                _fns.append(_fn)
            _reps_menu.add_action(_label, chain_fns(*_fns), icon=UPDATE_ICON)

    def _ctx_scene_refs_add_opts(self, menu, refs):
        """Add context options for a list out output references.

        Args:
            menu (QMenu): menu to add items to
            refs (CPipeRef list): references
        """
        menu.add_label('{:d} refs selected'.format(len(refs)))
        menu.add_separator()

        # Add delete option
        _actions = [wrap_fn(self._stage_delete, _ref, redraw=False)
                    for _ref in refs]
        _actions += [self.ui.SSceneRefs.redraw]
        _fn = chain_fns(*_actions)
        menu.add_action('Delete', _fn, icon=icons.find('Cross Mark'))

        self._ctx_scene_refs_add_update_tag_opts(menu, refs=refs)
        self._ctx_scene_ref_add_update_rep_opts(menu, refs=refs)

        # Add update option
        _actions = []
        for _ref in refs:
            if (
                    not _ref.output or
                    not _ref.output.ver_n or
                    _ref.is_latest()):
                continue
            _latest = _ref.output.find_latest()
            _fn = wrap_fn(self._stage_update, ref=_ref, output=_latest)
            _actions.append(_fn)
        if _actions:
            _actions += [self.ui.SSceneRefs.redraw]
        _fn = chain_fns(*_actions)
        menu.add_action('Update to latest', _fn,
                        icon=_LATEST_ICON, enabled=bool(_actions))

    def _stage_import(self, output, attach=None, redraw=False, base=None):
        """Stage a reference to be imported.

        Args:
            output (CPOutput): output to be referenced
            attach (CPipeRef): attach the given output to this
                existing scene reference (ie. attach a lookdev
                to an existing abc in the scene)
            redraw (bool): update scene refs list
            base (str): override namespace base
        """
        _LOGGER.debug('STAGE IMPORT')

        _ignore = [_ref.namespace for _ref in self._staged_imports]
        _ns = output_to_namespace(
            output, attach=attach, ignore=_ignore, base=base)
        _ref = _StagedRef(output=output, namespace=_ns, attach=attach)
        if attach:
            _existing = dcc.find_pipe_ref(_ns, catch=True)
            if _existing:
                self._stage_delete(_existing, redraw=False)
        self._staged_imports.append(_ref)

        # Add lookdev attach
        _lookdev_mode = self.ui.SLookdev.currentText()
        if (
                dcc.NAME == 'maya' and
                output.type_ == 'cache' and
                _lookdev_mode == 'Reference'):

            _LOGGER.debug(' - CHECKING FOR LOOKDEV')

            # Apply abc mode filter
            _abc_mode = self.ui.SAbcMode.currentText()
            if _abc_mode == 'Auto':
                _abc_mode = 'aiStandIn' if output.task == 'fx' else 'Reference'

            # Add lookdev if available
            _lookdev = output.find_lookdev_shaders()
            if _lookdev and _abc_mode == 'Reference':
                _lookdev_ns = _ns+'_shd'
                _lookdev_ref = _StagedRef(
                    output=_lookdev, namespace=_lookdev_ns,
                    ignore_on_apply=True)
                self._staged_imports.append(_lookdev_ref)

        if redraw:
            self.ui.SSceneRefs.redraw()

    def _stage_delete(self, ref, redraw=True):
        """Stage a reference to be deleted.

        Args:
            ref (CPipeRef): ref to stage for deletion
            redraw (bool): update scene refs list
        """
        _LOGGER.debug('STAGE DELETE %s', ref)
        if ref in self._staged_imports:
            self._staged_imports.remove(ref)
        else:
            if ref in self._staged_updates:
                del self._staged_updates[ref]
            self._staged_deletes.add(ref)
        if redraw:
            self.ui.SSceneRefs.redraw()

    def _stage_rename(self, ref, namespace):
        """Stage a rename for the given reference.

        Args:
            ref (CPipeRef): reference to update
            namespace (str): new namespace to apply
        """
        self._staged_renames[ref] = namespace

    def _stage_replace_refs(self, output, refs):
        """Stage replacing the given references with the given output.

        Args:
            output (CPOutput): output to replace with
            refs (CPipeRef list): references to update
        """
        for _ref in refs:
            self._stage_update(ref=_ref, output=output)

    def _stage_update(self, ref, output):
        """Stage a reference update.

        Args:
            ref (CPipeRef): reference to update
            output (CPOutput): path to update to
        """
        _LOGGER.debug('STAGE UPDATE %s %s', ref, output)
        if isinstance(ref, _StagedRef):
            ref.set_output(output)
        else:
            if ref in self._staged_deletes:
                self._staged_deletes.remove(ref)
            self._staged_updates[ref] = output
        self.ui.SSceneRefs.redraw()

    def _rename_ref(self, ref, namespace):
        """Apply a name update to the given reference.

        Staged references are renamed immediately but scene updates to
        references are staged.

        Args:
            ref (CPipeRef|StagedRef): reference to update
            namespace (str): namespace to apply
        """
        _namespace = dcc.get_next_namespace(namespace, mode='cache')
        if isinstance(ref, _StagedRef):
            ref.namespace = _namespace
        else:
            self._stage_rename(ref, _namespace)
        self.ui.SSceneRefs.redraw()

    def _doubleClick__SOutputs(self):  # pylint: disable=invalid-name
        """Triggered by double-click SOutputs element."""
        _out = self.ui.SOutputs.selected_data()
        _LOGGER.info('DOUBLE CLICK %s', _out)
        if _out:
            self._callback__SAdd(outs=[_out])


def _apply_lookdev(ref, lookdev):
    """Apply lookdev to the given reference.

    NOTE: the parent reference (to apply lookdev to) could be a staged
    reference, but we can assume that if it is then it's already been
    imported.

    Args:
        ref (CPipeRef|StagedRef): reference to apply
        lookdev (CPOutput): lookdev to apply
    """
    _LOGGER.info('APPLY LOOKDEV %s %s', ref, lookdev)
    _ref = dcc.find_pipe_ref(ref.namespace)
    _ref.attach_shaders(lookdev)


def _sort_asset_type(type_):
    """Sort asset type attribute.

    Args:
        type_ (str|None): asset type to sort

    Returns:
        (str): sort key
    """
    return type_ or ''


def _sort_outputs(output):
    """Sort for outputs list.

    Args:
        output (CPOutput): output to sort

    Returns:
        (tuple): sort key
    """
    return output.asset or '', output.path or ''


def _sort_scene_ref(ref):
    """Build sort key for the given scene ref.

    This makes sure that lookdev references are always sorted after their
    attached reference.

    Args:
        ref (CPipeRef): scene ref to sort

    Returns:
        (tuple): sort key
    """
    if dcc.NAME == 'maya':
        if ref.namespace.endswith('_shd'):
            return ref.namespace[:-4], 1
        return ref.namespace, 0
    return ref.cmp_str


def _output_to_label(out):
    """Get a label for the given output.

    This detemines how is should be displayed in the outputs list.

    Args:
        out (CPOutput): output object

    Returns:
        (str): label
    """
    _LOGGER.debug('OUTPUT TO LABEL %s', out.path)
    if out.extn == 'abc':
        _label = out.output_name or out.type_
    else:
        _label = out.asset or out.output_name or out.type_
    _fmt = ''
    if out.tag:
        _label += ' '+out.tag
    if isinstance(out, pipe.CPOutputSeq):
        _fmt = ' ({})'.format(out.extn)
    if out.ver_n:
        _label += ' v{:03d}{}'.format(out.ver_n, _fmt)
    return _label


def _output_to_task_label(out):
    """Obtain task label for the given output.

    Args:
        out (CPOutput): output to read

    Returns:
        (str): task label (eg. rig, surf/dev)
    """
    if out.step:
        return '{}/{}'.format(out.step, out.task)
    return out.task


class _StagedRef(pipe_ref.CPipeRef):  # pylint: disable=abstract-method
    """Represents a reference ready to be brought into the current scene."""

    def __init__(self, output, namespace, attach=None, ignore_on_apply=False):
        """Constructor.

        Args:
            output (CPOutput): output to reference
            namespace (str): namespace to use
            attach (CPipeRef): mark this output as one to be attached
                to this scene ref (only relevant to a lookdev being
                applied to an existing abc in the scene)
            ignore_on_apply (bool): ignore this reference when apply is
                executed (this is used to display lookdev attaches which
                will be imported as part of an abc import)
        """
        super(_StagedRef, self).__init__(output, namespace=namespace)
        self.attach = attach
        self.ignore_on_apply = ignore_on_apply

    def rename(self, namespace):
        """Rename this reference.

        Args:
            namespace (str): new name
        """
        self.namespace = namespace

    def set_output(self, output):
        """Set output for this staged reference.

        Args:
            output (CPOutput): output to apply
        """
        self._out = output
        self._out_c = output
