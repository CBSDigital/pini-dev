"""Tools for manging the pini helper outputs tab."""  # pylint: disable=too-many-lines

# pylint: disable=no-member

import logging
import operator
import os

from pini import qt, pipe, dcc, icons
from pini.dcc import pipe_ref
from pini.tools import usage
from pini.utils import (
    wrap_fn, plural, chain_fns, strftime, clip, passes_filter, safe_zip,
    apply_filter, single, split_base_index, to_nice)

from . import phu_output_item, phu_scene_ref_item
from .. import ph_utils
from ..ph_utils import UPDATE_ICON, CURRENT_ICON

_LOGGER = logging.getLogger(__name__)
_LATEST_ICON = icons.find('Light Bulb')
_REPLACE_ICON = icons.find('Right Arrow Curving Left')


class PHSceneTab:
    """Class for grouping together elements of pini helper Outputs tabs."""

    all_outs = ()

    abc_cam_plates = False
    abc_lookdev_attach = False
    abc_modes = ()
    vdb_modes = ()

    def __init__(self):
        """Constructor."""
        self._staged_imports = []
        self._staged_deletes = set()
        self._staged_updates = {}
        self._staged_renames = {}

        self.ui.SOutputs.doubleClicked.connect(
            self._doubleClick__SOutputs)
        self.ui.SSceneRefs.doubleClicked.connect(
            self._doubleClick__SSceneRefs)

    def init_ui(self, switch_tabs=True):
        """Inititate this tab's interface - triggered by selecting this tab.

        Args:
            switch_tabs (bool): whether we are switching to this tab
                (this can be disabled if the tab is being re-initiated
                internally)
        """
        _LOGGER.debug('INIT UI switch=%d', switch_tabs)

        # Apply save policies
        for _elem in [
                self.ui.SOutputType, self.ui.SOutputTask, self.ui.SOutputTag,
                self.ui.SOutputFormat]:
            _elem.set_save_policy(qt.SavePolicy.SAVE_IN_SCENE)

        # Update abc/vdb options based on dcc
        for _elem, _opts in [
                (self.ui.SAbcMode, self.abc_modes),
                (self.ui.SVdbMode, self.vdb_modes),
        ]:
            _elem.set_items(_opts)
            _elem.setVisible(bool(_opts))

        # Update entity tab label based on profile
        if not self.entity:
            _label = '-'
        else:
            _label = self.entity.profile.capitalize()
        self.ui.SOutputsPane.setTabText(1, _label)
        _LOGGER.debug(' - SET ENTITY TAB TEXT %s', _label)

        self._select_default_output_tab(switch_tabs=switch_tabs)

        self._callback__SOutputsPane()
        self.ui.SSceneRefs.redraw()

        # Fix OOutputsPane on 4k monitors
        _tab_height = self.ui.MainPane.tabBar().height()
        self.ui.SOutputsPane.setFixedHeight(_tab_height + 1)

    def _select_default_output_tab(self, switch_tabs):
        """Select default tab for outputs pane.

        Args:
            switch_tabs (bool): whether we are switching to this tab
        """

        # Find a tab to select
        _tab = None
        if self.target and isinstance(self.target, pipe.CPOutputBase):
            _LOGGER.debug(' - TARGET %s', self.target)
            if self.target.profile == 'asset':
                _LOGGER.debug(
                    ' - TARGET COMPARE trg=%s cur=%s', self.target.entity,
                    self.entity)
                if self.target.entity == self.entity:
                    _tab = self.ui.SEntityTab
                else:
                    _tab = self.ui.SAssetsTab
            elif self.target.profile == 'shot':
                if not self.target.is_media():
                    _tab = self.ui.SEntityTab
                else:
                    _tab = self.ui.SMediaTab
            else:
                raise ValueError(self.target)
        elif switch_tabs:
            _task = pipe.cur_task(fmt='pini')
            _map = {'anim': self.ui.SAssetsTab,
                    'fx': self.ui.SEntityTab,
                    'lighting': self.ui.SEntityTab,
                    'lsc': self.ui.SMediaTab,
                    'comp': self.ui.SMediaTab}
            _tab = _map.get(_task)
        _LOGGER.debug(' - SELECT TAB %s', _tab)

        # Apply selection
        if _tab:
            _LOGGER.debug(' - SELECT TAB NAME %s', _tab.objectName())
            self.ui.SOutputsPane.select_tab(_tab)
        else:
            self.settings.apply_to_widget(self.ui.SOutputsPane)

    def _read_all_outs(self):
        """Read outputs for the current outputs tab selection.

        ie. read all Asset/Cache/Render ouputs.

        Returns:
            (CPOutput list): outputs
        """
        _tab = self.ui.SOutputsPane.currentWidget()
        _ren_basic_types = ['render', 'blast', 'plate']
        _filter = os.environ.get('PINI_HELPER_OUTPUT_FILTER')

        _outs = []
        if _tab == self.ui.SAssetsTab:
            _outs = self.job.find_publishes(
                extns=dcc.REF_EXTNS, filter_=_filter)
        elif _tab == self.ui.SEntityTab:
            if self.entity:
                _outs += [
                    _out for _out in self.entity.find_outputs(
                        linked=True, filter_=_filter)
                    if not _out.is_media()]
        elif _tab == self.ui.SMediaTab:
            if self.entity:
                _outs += [
                    _out for _out in self.entity.find_outputs(filter_=_filter)
                    if _out.is_media()]
        else:
            raise ValueError(_tab)

        return _outs

    def _redraw__SOutputType(self):

        _LOGGER.debug(' - REDRAW SOutputType outs=%d', len(self.all_outs))

        # Set lists + data based on outputs mode
        _tab = self.ui.SOutputsPane.currentWidget()
        _add_all = True
        if _tab == self.ui.SAssetsTab:
            _label, _types, _data, _select = self._redraw_out_type_asset()
        elif _tab == self.ui.SEntityTab:
            _label = 'Type'
            _types = {
                _out.output_type for _out in self.all_outs}
            _data = [
                [_out for _out in self.all_outs if _out.output_type == _type]
                for _type in _types]
            _types = sorted({_type or '' for _type in _types})
            _select = 'all'
        elif _tab == self.ui.SMediaTab:
            _label = 'Template'
            _types = sorted({_out.type_ for _out in self.all_outs})
            _data = [
                [_out for _out in self.all_outs if _out.type_ == _type]
                for _type in _types]
            _add_all = False
            _select = 'render'
        else:
            raise ValueError(_tab)
        _LOGGER.debug('   - TYPES %s', _types)
        _scene_select = dcc.get_scene_data(self.ui.SOutputType.settings_key)
        if not self.target and _scene_select in _types:
            _select = _scene_select
        _LOGGER.debug('   - SCENE SELECT %s %s', _scene_select, _select)

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
        _select = None
        if (
                self.target and
                isinstance(self.target, pipe.CPOutputBase) and
                self.target.asset_type in _types):
            _select = self.target.asset_type
        elif _types:
            _select = sorted(_types, key=_sort_asset_type)[0]
        _LOGGER.debug('   - SELECT OUT TYPE ASSET %s', _select)

        return _label, _types, _data, _select

    def _redraw__SOutputTask(self):  # pylint: disable=too-many-branches

        _LOGGER.debug(' - REDRAW SOutputTask')
        _LOGGER.debug('   - TARGET %s', self.target)

        _pane = self.ui.SOutputsPane.currentWidget()
        _type = self.ui.SOutputType.selected_text()
        _outs = self.ui.SOutputType.selected_data() or []
        _LOGGER.debug(
            '   - FOUND %d OUTS (target=%d)', len(_outs), self.target in _outs)

        # Build list of tasks/data
        _tasks, _data = [], []
        for _task in sorted({_output_to_task_label(_out) for _out in _outs},
                            key=pipe.task_sort):
            _tasks.append(_task or '<None>')
            _data.append([
                _out for _out in _outs if _output_to_task_label(_out) == _task])

        # Determine selection
        _sel = None
        if self.target in _outs:
            _sel = single([
                _task for _task, _task_outs in safe_zip(_tasks, _data)
                if self.target in _task_outs])
            _LOGGER.debug(
                '   - FIND SELECTED TASK FROM TARGET %s %s', _sel,
                self.target)
        if not _sel:
            _sel = dcc.get_scene_data(self.ui.SOutputTask.settings_key)
            if _sel not in _tasks:
                _sel = None
        if not _sel:
            if _pane == self.ui.SMediaTab:
                _sel = 'lighting'
            elif 'rig' in _tasks:  # Select default before add all
                _sel = 'rig'
        if not _sel:
            _cur_task = pipe.cur_task()
            _map_task = {'anim': 'rig'}.get(_cur_task, _sel)
            _LOGGER.debug('   - MAP TASK %s %s', _cur_task, _map_task)
            if _map_task in _tasks:
                _sel = _map_task
                _LOGGER.debug('   - SEL MAP TASK')
            if not _sel:
                _filter_task = single(
                    apply_filter(_tasks, _map_task), catch=True)
                if _filter_task in _tasks:
                    _sel = _filter_task
                    _LOGGER.debug('   - SEL FILTER TASK %s', _filter_task)
        if not _sel and _tasks:
            _sel = _tasks[0]
            _LOGGER.debug('   - SELECT FIRST TASK %s', _sel)
        _LOGGER.debug('   - SELECT %s', _sel)

        if len(_tasks) > 1:
            _tasks.insert(0, 'all')
            _data.insert(0, _outs)

        # Update ui
        self.ui.SOutputTask.set_items(
            _tasks, data=_data, emit=False, select=_sel)
        self.ui.SOutputTask.setEnabled(bool(_tasks))
        self.ui.SOutputTask.setEnabled(len(_tasks) > 1)
        if not _sel:
            self.settings.apply_to_widget(self.ui.SOutputTask, emit=False)

        self.ui.SOutputTag.redraw()

    def _redraw__SOutputTag(self):

        _LOGGER.debug(' - REDRAW SOutputTag')
        _outs = self.ui.SOutputTask.selected_data() or []
        _tab = self.ui.SOutputsPane.currentWidget()

        # Build list of tags
        _tags = sorted({_out.tag for _out in _outs}, key=pipe.tag_sort)
        _data = [
            [_out for _out in _outs if _out.tag == _tag]
            for _tag in _tags]
        if len(_tags) > 1:
            _tags.insert(0, 'all')
            _data.insert(0, _outs)
        _labels = [{None: '<default>'}.get(_tag, _tag) for _tag in _tags]

        # Determine selection
        _sel = None
        _scene_sel = dcc.get_scene_data(self.ui.SOutputTag.settings_key)
        _LOGGER.debug('   - SCENE SEL %s', _scene_sel)
        if _scene_sel and _scene_sel in _tags:
            _sel = _scene_sel
        elif pipe.DEFAULT_TAG in _tags and _tab == self.ui.SAssetsTab:
            _sel = pipe.DEFAULT_TAG
        elif len(_tags) > 1:
            _sel = 'all'
        if (
                isinstance(self.target, pipe.CPOutputBase) and
                self.target.tag in _tags):
            _sel = self.target.tag
        _LOGGER.debug('   - SEL %s', _sel)

        self.ui.SOutputTag.set_items(
            _labels, data=_data, emit=True, select=_sel)
        self.ui.SOutputTag.setEnabled(len(_labels) > 1)

    def _redraw__SOutputFormat(self):

        _LOGGER.debug(' - REDRAW SOutputFormat')
        _tab = self.ui.SOutputsPane.currentWidget()

        _outs = self.ui.SOutputTag.selected_data() or []
        _extns = sorted({_out.extn for _out in _outs})
        _data = [
            [_out for _out in _outs if _out.extn == _extn]
            for _extn in _extns]
        if len(_extns) > 1:
            _extns.insert(0, 'all')
            _data.insert(0, _outs)
        _LOGGER.debug('   - FMTS %s', _extns)

        # Apply default format
        _sel = None
        if not _sel and self.target and self.target.extn in _extns:
            _sel = self.target.extn
        _scene_sel = dcc.get_scene_data(self.ui.SOutputFormat.settings_key)
        _LOGGER.debug('   - SCENE SEL %s', _scene_sel)
        if not _sel and _scene_sel in _extns:
            _sel = _scene_sel
        if not _sel:
            _fmts_order = []
            if _tab == self.ui.SAssetsTab:
                _fmts_order = ['ma', 'abc']
            else:
                _fmts_order = ['all', 'abc']
            _LOGGER.debug('   - FMTS ORDER %s', _fmts_order)
            for _fmt in _fmts_order:
                if _fmt in _extns:
                    _sel = _fmt
                    break
        _LOGGER.debug('   - SEL FMT %s', _sel)

        self.ui.SOutputFormat.set_items(
            _extns, data=_data, emit=True, select=_sel)
        self.ui.SOutputFormat.setEnabled(len(_extns) > 1)

    def _redraw__SOutputVers(self):

        _LOGGER.debug('REDRAW SOutputVers')
        _cur = self.ui.SOutputVers.currentText()
        _outs = self.ui.SOutputFormat.selected_data() or []

        # Build opts list
        _opts = []
        if [_out for _out in _outs if _out.ver_n is None]:
            _opts.append("versionless")
        _opts.append("latest")
        _opts.append("all")

        # Determine selection
        _sel = _cur if _cur in _opts else "latest"
        _LOGGER.debug(
            ' - TARGET %s %d', self.target,
            0 if not isinstance(self.target, pipe.CPOutputBase)
            else self.target.is_latest())
        if (
                isinstance(self.target, pipe.CPOutputBase) and
                self.target in _outs):
            if not self.target.is_latest():
                _sel = 'all'
            elif self.target.ver_n:
                _sel = 'latest'

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
        _LOGGER.log(9, '   - CHECKING %d OUTS %s', len(_outs), _outs)
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
            _item = phu_output_item.PHOutputItem(
                helper=self, output=_out, list_view=self.ui.SOutputs,
                highlight=_out in _scene_outs)
            _items.append(_item)
        self.ui.SOutputs.set_items(_items, select=_select, emit=True)

        self._update_out_mode_elems()

    def _update_out_mode_elems(self):
        """Update output mode elements.

        These are elements whose visiblity depends on what outputs are being
        displayed, eg. abc mode, vdb mode, etc.
        """
        _outs = self.ui.SOutputs.all_data()
        _LOGGER.log(9, ' - UPDATE OUT MODE ELEMS %s', _outs)

        _abcs = self.abc_modes and any(
            _out for _out in _outs if _out.extn == 'abc')
        _cams = self.abc_cam_plates and any(
            _out for _out in _outs if _out.content_type == 'CameraAbc')
        _vdbs = self.vdb_modes and any(
            _out for _out in _outs if _out.content_type == 'VdbSeq')
        _media = any(_out for _out in _outs if _out.is_media())

        for _tgl, _elems in [
                (_abcs, [
                    self.ui.SAbcMode, self.ui.SAbcModeSpacer,
                    self.ui.SAbcModeLabel]),
                (_vdbs, [
                    self.ui.SVdbMode, self.ui.SVdbModeSpacer,
                    self.ui.SVdbModeLabel]),
                (_cams, [self.ui.SCamPlates]),
                (_media, [self.ui.SViewer, self.ui.SView])]:
            _LOGGER.log(9, '   - UPDATE ELEMS %d %s', _tgl, _elems)
            for _elem in _elems:
                _elem.setVisible(bool(_tgl))

    def _redraw__SViewer(self):

        _out = self.ui.SOutputs.selected_data(catch=True)
        _enabled = False
        _plays_seqs = None
        if isinstance(_out, (clip.Seq, clip.Video)):
            _enabled = True
        if isinstance(_out, clip.Seq):
            _plays_seqs = True
        _LOGGER.debug(
            'REDRAW SViewer en=%d seq=%s %s', _enabled, _plays_seqs, _out)
        _viewer = clip.find_viewer()
        _viewers = clip.find_viewers(plays_seqs=_plays_seqs)
        _enabled = _enabled and bool(_viewers)
        _LOGGER.debug(' - VIEWERS %s', _viewers)

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
            if _out.owner:
                _text += f'Owner: {_out.updated_by}\n'
            if _out.updated_at:
                _t_str = strftime('%a %d %b %H:%M', _out.updated_at)
                _text += f'Exported: {_t_str}\n'

            # Add range
            if not _out.range_ or _out.range_ == (None, None):
                _fmt = None
            elif len(_out.range_) == 1:
                _fmt = 'Range: {:.00f}\n'
            elif len(_out.range_) == 2:
                _fmt = 'Range: {:.00f}-{:.00f}\n'
            else:
                raise ValueError(_out.range_)
            if _fmt:
                _text += _fmt.format(*_out.range_)

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
        _type = single({_out.content_type for _out in _outs}, catch=True)
        self.ui.SAdd.setText(
            f'Add {len(_outs):d} {_type or "output"}{plural(_outs)}')
        self.ui.SAdd.setEnabled(bool(_outs))

    def _redraw__SSceneRefs(self):

        _LOGGER.debug('REDRAW SSceneRefs')

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
            _LOGGER.debug(
                ' - ADDING REF %s status=%s output=%s', _ref, _status,
                _output or _ref.output)
            _item = phu_scene_ref_item.PHSceneRefItem(
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
        _show_texs = self.ui.SSceneRefsShowTexs.isChecked()
        _type_filter = any([
            _show_models,
            _show_rigs,
            _show_shaders,
            _show_abcs,
            _show_texs
        ])
        _LOGGER.debug(
            ' - TYPE FILTER %d show_models=%d', _type_filter, _show_models)

        # Find list of all refs
        _all_refs = sorted(
            _scene_refs + self._staged_imports, key=_sort_scene_ref)
        _LOGGER.debug(' - BUILD REFS LIST %d %s', len(_all_refs), _all_refs)

        # Build filtered list of display refs
        _refs = []
        for _ref in _all_refs:
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
                elif _show_texs and _ref.output.type_ == 'texture_seq':
                    pass
                else:
                    _LOGGER.debug(
                        ' - REJECTED %s task=%s extn=%s', _ref,
                        _ref.task, _ref.extn)
                    continue
            _LOGGER.debug('   - ADD REF %s %s', _ref, _ref.output)
            _refs.append(_ref)

        return _refs

    def _redraw__SApply(self):
        _updates = (len(self._staged_imports) +
                    len(self._staged_deletes) +
                    len(self._staged_updates) +
                    len(self._staged_renames))
        self.ui.SApply.setEnabled(bool(_updates))
        self.ui.SApply.setText(
            f'Apply {_updates:d} update{plural(_updates)}')

    def _callback__SOutputsPane(self):
        self.settings.save_widget(self.ui.SOutputsPane)
        # _tab = self.ui.SOutputsPane.currentWidget()
        self.all_outs = self._read_all_outs()
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
        if self.ui.SOutputsPane.currentWidget() is self.ui.SMediaTab:
            self.ui.SViewer.redraw()

    def _callback__SOutputsFilter(self):
        self.ui.SOutputs.redraw()

    def _callback__SOutputsFilterClear(self):
        self.ui.SOutputsFilter.setText('')

    def _callback__SView(self):
        _viewer = self.ui.SViewer.selected_data()
        _out = self.ui.SOutputs.selected_data()
        _viewer.view(_out)

    def _callback__SAdd(self, outs=None):
        _outs = outs or self.ui.SOutputs.selected_datas()
        for _out in _outs:
            if not dcc.can_reference_output(_out):
                continue
            self.stage_import(_out, redraw=False)
        self.ui.SSceneRefs.redraw()

    def _callback__SUpdateToLatest(self):

        _refs = (self.ui.SSceneRefs.selected_datas() or
                 self.ui.SSceneRefs.all_data())
        _updateables = [
            _ref for _ref in _refs
            if _ref.output and not _ref.output.is_latest()]
        for _ref in _updateables:
            self.stage_ref_update(_ref, _ref.output.find_latest())

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

    def _callback__SSceneRefsShowTexs(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsShowAbcs(self):
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsTypeFilterReset(self):
        for _elem in [
                self.ui.SSceneRefsShowModels,
                self.ui.SSceneRefsShowRigs,
                self.ui.SSceneRefsShowLookdevs,
                self.ui.SSceneRefsShowAbcs,
                self.ui.SSceneRefsShowTexs,
        ]:
            _elem.setChecked(False)
        self.ui.SSceneRefs.redraw()

    def _callback__SSceneRefsFilter(self):
        self.ui.SSceneRefs.redraw()
        self.ui.SSceneRefsFilter.setFocus()

    def _callback__SSceneRefsFilterClear(self):
        self.ui.SSceneRefsFilter.setText('')

    def _create_abc_ref(self, output, namespace):
        """Create abc reference.

        Args:
            output (CPOutput): output being referenced
            namespace (str): reference namespace
        """
        raise NotImplementedError

    def _create_cam_ref(self, output, namespace):
        """Create camera reference.

        Args:
            output (CPOutput): output being referenced
            namespace (str): reference namespace
        """
        raise NotImplementedError

    def _create_vdb_ref(self, output, namespace):
        """Create vdb reference.

        Args:
            output (CPOutput): output being referenced
            namespace (str): reference namespace
        """
        raise NotImplementedError

    @usage.get_tracker(name='PiniHelper.RefOutputs')
    def _callback__SApply(self):
        self.apply_updates()

    def apply_updates(self, msg=None, force=False):
        """Apply staged updates.

        Args:
            msg (str): override apply message
            force (bool): apply updates without confirmation
        """

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
            _msg = msg or (
                f'Apply {len(_updates):d} scene update{plural(_updates)}?')
            qt.ok_cancel(_msg, parent=self, icon=icons.find('Gear'))
        for _update in qt.progress_bar(
                _updates, 'Applying {:d} update{}', parent=self):
            _LOGGER.debug(' - APPLY UPDATE %s', _update)
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

            _LOGGER.info(' - BUILDING IMPORT UPDATE %s', _ref)
            if dcc.NAME == 'maya' and _ref.output.content_type == 'CameraAbc':
                _import_fn = wrap_fn(
                    self._create_cam_ref, namespace=_ref.namespace,
                    output=_ref.output)
            elif dcc.NAME == 'maya' and _ref.output.extn == 'abc':
                _import_fn = wrap_fn(
                    self._create_abc_ref, namespace=_ref.namespace,
                    output=_ref.output)
            elif dcc.NAME == 'maya' and _ref.output.extn == 'vdb':
                _import_fn = wrap_fn(
                    self._create_vdb_ref, namespace=_ref.namespace,
                    output=_ref.output)
            else:
                _import_fn = wrap_fn(
                    _apply_create_ref, namespace=_ref.namespace,
                    output=_ref.output, attach_to=_ref.attach_to)
            _updates.append(_import_fn)

        return _updates

    def _context__SOutputs(self, menu):

        _out = self.ui.SOutputs.selected_data(catch=True)
        _outs = self.ui.SOutputs.selected_datas()
        if _out:

            self.add_output_opts(menu=menu, output=_out)
            menu.add_separator()

            # Add replace options
            _view_refs = dcc.find_pipe_refs(selected=True)
            _helper_refs = self.ui.SSceneRefs.selected_datas()
            for _label, _refs in [
                    ('viewport', _view_refs),
                    ('helper', _helper_refs),
            ]:
                _trg_label = _out.output_name or _out.asset
                menu.add_action(
                    f'Swap {_label} selection to {_trg_label}',
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
        _out_c = pipe.CACHE.obt_output(_out, catch=True)
        if ref.namespace == _out.output_name:
            _base = _out.output_name
        else:
            _base, _ = split_base_index(ref.namespace)

        menu.add_label('Ref: ' + ref.namespace)
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
            wrap_fn(self.stage_import, _out_c, base=_base, redraw=True),
            icon=icons.DUPLICATE)
        menu.add_separator()

        # Update options
        _LOGGER.debug('   - ADD UPDATE OPTS %s', ref.output)
        if not _out_c:
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
                wrap_fn(self.stage_ref_update, ref, _latest),
                icon=_LATEST_ICON, enabled=not _out.is_latest())
            menu.add_action(
                'Update name to match tag',
                wrap_fn(self._rename_ref, ref=ref, namespace=_out.tag),
                icon=UPDATE_ICON, enabled=bool(_out.tag))
            self._ctx_scene_refs_add_update_tag_opts(menu, refs=[ref])
            self._ctx_scene_ref_add_update_ver_opts(menu, ref=ref)
            self._ctx_scene_ref_add_update_rep_opts(menu, refs=[ref])
        menu.add_separator()

        self.add_output_opts(
            menu=menu, output=_out, header=False, delete=False,
            add=False, ref=ref)

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
                _fn = wrap_fn(self.stage_ref_update, ref=_ref, output=_latest)
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
                _label = f'v{_ver.ver_n:03d}'
            _fn = wrap_fn(self.stage_ref_update, ref=ref, output=_ver)
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
                _fn = wrap_fn(self.stage_ref_update, ref=_ref, output=_rep)
                _fns.append(_fn)
            _reps_menu.add_action(_label, chain_fns(*_fns), icon=UPDATE_ICON)

    def _ctx_scene_refs_add_opts(self, menu, refs):
        """Add context options for a list out output references.

        Args:
            menu (QMenu): menu to add items to
            refs (CPipeRef list): references
        """
        menu.add_label(f'{len(refs):d} refs selected')
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
            _fn = wrap_fn(self.stage_ref_update, ref=_ref, output=_latest)
            _actions.append(_fn)
        if _actions:
            _actions += [self.ui.SSceneRefs.redraw]
        _fn = chain_fns(*_actions)
        menu.add_action('Update to latest', _fn,
                        icon=_LATEST_ICON, enabled=bool(_actions))

    def stage_import(
            self, output, attach_to=None, redraw=True, base=None,
            namespace=None, reset=False, work_dir=None):
        """Stage a reference to be imported.

        Args:
            output (CPOutput): output to be referenced
            attach_to (str): attach the given output to this existing
                scene reference (eg. attach a lookdev to an existing
                abc in the scene)
            redraw (bool): update scene refs list
            base (str): override namespace base
            namespace (str): force namespace of import
            reset (bool): reset imports before adding import
            work_dir (CCPWOrkDir): force context of this import
        """
        _LOGGER.debug('STAGE IMPORT %s', repr(output))

        if reset:
            self._callback__SReset()
        assert isinstance(attach_to, str) or attach_to is None

        # Determine import namespace
        _out = pipe.CACHE.obt(output)
        _LOGGER.debug(' - OUT %s', repr(_out))
        _work_dir = work_dir or self.work_dir

        # Build list of staged refs
        _refs = []
        _ignore = [_ref.namespace for _ref in self._staged_imports]
        _imps = ph_utils.output_to_imports(
            _out, namespace=namespace, ignore=_ignore, base=base,
            work_dir=_work_dir, attach_to=attach_to)
        for _out, _ns, _attach in _imps:
            _LOGGER.debug(' - IMPORT %s %s %s', _out, _ns, _attach)
            _attach_to = attach_to
            if not _attach_to and _attach and _refs:
                _attach_to = _refs[0].namespace
            _LOGGER.debug('   - ATTACH TO %s', _attach_to)
            _ref = _StagedRef(
                output=_out, namespace=_ns, attach_to=_attach_to)
            _existing = dcc.find_pipe_ref(_ns, catch=True)
            if _existing:
                self._stage_delete(_existing, redraw=False)
            _LOGGER.debug('   - ADDING STAGED REF %s %s', _ref, _out)
            self._staged_imports.append(_ref)
            _refs.append(_ref)

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
            self.stage_ref_update(ref=_ref, output=output)

    def stage_ref_update(self, ref, output):
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

    def _doubleClick__SSceneRefs(self):  # pylint: disable=invalid-name
        """Triggered by double-click SSceneRefs element."""
        _ref = self.ui.SSceneRefs.selected_data()
        _LOGGER.info('DOUBLE CLICK %s', _ref)
        if _ref:
            _ref.select_in_scene()


def _apply_create_ref(output, namespace, attach_to):
    """Apply create reference.

    Args:
        output (CCPOutput): output being referenced
        namespace (str): namespace for output
        attach_to (str): namespace of reference to attach this one to
    """
    _LOGGER.info('APPLY CREATE REF %s %s', namespace, output)
    _ref = dcc.create_ref(namespace=namespace, path=output)
    _LOGGER.info(' - REF %s', _ref)
    assert _ref

    _LOGGER.info(' - ATTACH TO %s', attach_to)
    if attach_to:
        assert isinstance(attach_to, str)
        _LOGGER.info(' - APPLY ATTACH %s -> %s', _ref, attach_to)
        _trg = dcc.find_pipe_ref(namespace=attach_to)
        _LOGGER.info(' - TRG %s', _trg)
        if output.content_type == 'CurvesMb':
            _trg.attach_anim(_ref)
        elif output.content_type == 'ShadersMa':
            _trg.attach_shaders(_ref)
        else:
            raise NotImplementedError(output.content_type)


def _sort_asset_type(type_):
    """Sort asset type attribute.

    Args:
        type_ (str|None): asset type to sort

    Returns:
        (str): sort key
    """
    _priority = ['char', 'prop']
    if type_ in _priority:
        return _priority.index(type_), type_
    return len(_priority), type_


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
        for _suffix, _offs in [('_shd', 1), ('_crvs', 2)]:
            if ref.namespace.endswith(_suffix):
                return ref.namespace[:-len(_suffix)], _offs
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
        _label += ' ' + out.tag
    if isinstance(out, pipe.CPOutputSeq):
        _fmt = f' ({out.extn})'
    if out.ver_n:
        _label += f' v{out.ver_n:03d}{_fmt}'
    return _label


def _output_to_task_label(out):
    """Obtain task label for the given output.

    Args:
        out (CPOutput): output to read

    Returns:
        (str): task label (eg. rig, surf/dev)
    """
    if out.step:
        return f'{out.step}/{out.task}'
    return out.task


class _StagedRef(pipe_ref.CPipeRef):  # pylint: disable=abstract-method
    """Represents a reference ready to be brought into the current scene."""

    def __init__(self, output, namespace, attach_to=None):
        """Constructor.

        Args:
            output (CPOutput): output to reference
            namespace (str): namespace to use
            attach_to (StagedRef): reference to lookdev attach this ref to
        """
        super().__init__(output, namespace=namespace)
        self.attach_to = attach_to
        assert isinstance(attach_to, str) or attach_to is None

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
