"""Tools for managing PiniHelper interface."""

# pylint: disable=no-member

import logging
import os
import pprint
import webbrowser

from pini import pipe, icons, dcc, qt
from pini.dcc import pipe_ref, export
from pini.utils import (
    File, wrap_fn, chain_fns, strftime, Video, Seq, VIDEO_EXTNS, to_str)

from . import phu_header, phu_work_tab, phu_export_tab, phu_scene_tab
from ..ph_utils import LOOKDEV_BG_ICON, obt_recent_work, obt_pixmap

_LOGGER = logging.getLogger(__name__)

# Gather icons
_EMOJI_NAME = os.environ.get('PINI_HELPER_EMOJI', "Front-Facing Baby Chick")
EMOJI = icons.find_emoji(_EMOJI_NAME)
ICON = EMOJI.path

_DIALOG = None
TITLE = os.environ.get('PINI_HELPER_TITLE', 'Pini Helper')
_DIR = File(__file__).to_dir()
UI_FILE = _DIR.to_file('../pini_helper.ui').path

BKPS_ICON = icons.find('Package')
OUTS_ICON = icons.find('Dove')


class PHUiBase(
        phu_header.PHHeader,
        phu_work_tab.PHWorkTab,
        phu_export_tab.PHExportTab,
        phu_scene_tab.PHSceneTab):
    """Virtual base class for all Pini Helper interfaces."""

    ui = None
    timer = None
    target = None

    _cur_tab = None

    def __init__(
            self, jump_to=None, admin=None, store_settings=True,
            show=True, reset_cache=True, title=None):
        """Constructor.

        Args:
            jump_to (str): path to jump interface to on launch
            admin (bool): launch in admin mode with create entity/task options
            store_settings (bool): load settings on launch
            show (bool): show on launch
            reset_cache (bool): reset pipeline cache on launch
            title (str): override helper window title
        """
        _LOGGER.debug('INIT')
        from pini.tools import helper
        helper.DIALOG = self
        if reset_cache:
            pipe.CACHE.reset()

        self._set_target(jump_to)

        # Init components
        phu_header.PHHeader.__init__(self, admin=admin)
        for _cpnt in [
                phu_work_tab.PHWorkTab,
                phu_export_tab.PHExportTab,
                phu_scene_tab.PHSceneTab]:
            _cpnt.__init__(self)

        # Setup vars
        self.store_settings = store_settings
        self._notes_stack = {}

        # Init ui
        _title = title or TITLE
        self.setWindowTitle(_title)
        self.set_window_icon(ICON)

        self.ui.Job.redraw()
        _LOGGER.debug(' - REDREW JOB %s trg=%s', self.job, self.target)
        _LOGGER.debug(' - TRIGGERING ADMIN trg=%s', self.target)
        self._callback__ToggleAdmin(admin=False)
        _LOGGER.debug(' - TRIGGERED ADMIN trg=%s', self.target)
        self._callback__Profile()
        _LOGGER.debug(' - TRIGGERED PROFILE trg=%s', self.target)
        self._callback__MainPane(save=False)
        _LOGGER.debug(' - RAN CALLBACKS %s', self.target)

        self.ui.WTags.doubleClicked.connect(
            wrap_fn(self._load_latest_tag_version))
        self.ui.WWorks.doubleClicked.connect(
            wrap_fn(self._callback__WLoad))

        if store_settings:
            _LOGGER.debug(' - LOADING SETTINGS %s', self.entity)
            self.load_settings()
            _LOGGER.debug(' - LOADED SETTINGS %s', self.entity)
        self.ui.MainPane.select_tab('Work')
        _LOGGER.debug(' - SELECTED WORK TAB %s', self.entity)
        if show:
            self.show()

        self._start_timer()

        self.target = None
        _LOGGER.debug(' - INIT COMPLETE %s', self.entity)

    def init_ui(self):
        """Build ui elements."""
        _LOGGER.debug('INIT UI')
        self.ui.JobIcon.draw_pixmap_func = self._draw__JobIcon

        # Disable save settings on pipe elements
        for _elem in [
                self.ui.Job,
                self.ui.Profile,
                self.ui.EntityType,
                self.ui.Entity,

                self.ui.WTasks,
                self.ui.WTaskText,
                self.ui.WTags,
                self.ui.WTagText,
                self.ui.WWorks,
                self.ui.WWorkPath,

                self.ui.SOutputsFilter,
                self.ui.SSceneRefsFilter,
        ]:
            _LOGGER.debug(' - DISABLE SAVE %s', _elem)
            _elem.set_save_policy(qt.SavePolicy.NO_SAVE)

        self.ui.EExportPane.set_save_policy(qt.SavePolicy.SAVE_IN_SCENE)
        self.ui.ERenderHandler.set_save_policy(qt.SavePolicy.SAVE_ON_CHANGE)

    def is_active(self):
        """Test whether this helper instance is active.

        Returns:
            (bool): whether active
        """
        return self.isVisible()

    def _start_timer(self):
        """Start timer."""
        _LOGGER.debug('START TIMER')
        self.timer = self.startTimer(5000)

    def _set_target(self, target):
        """Set target project in the ui.

        If a path has been passed on init, this is used. If the dcc has a
        scene currently open, then this is used. If there are recently
        used work files in the list, then the most recent one is used.

        Args:
            target (str): target passed on init ui
        """
        _LOGGER.debug('SET TARGET %s', target)
        self.target = None

        # Apply target
        if target:
            self.target = _to_valid_target(target)
            _LOGGER.debug(' - APPLIED VALID TARGET %s', self.target)

        # Fall back on cur scene
        if not self.target:
            _cur_work = pipe.cur_work()
            if _cur_work:
                self.target = _cur_work
            _LOGGER.debug(' - APPLIED CUR WORK %s', self.target)
        if not self.target:
            _cur_out = pipe.cur_output()
            if _cur_out:
                _src = _cur_out.metadata.get('src')
                if _src:
                    self.target = pipe.to_output(_src, catch=True)
            _LOGGER.debug(' - APPLIED CUR OUTPUT %s', self.target)
        if not self.target:
            _ety = pipe.cur_entity()
            if _ety:
                self.target = _ety
        if not self.target:
            _job = pipe.cur_job()
            if _job:
                self.target = _job
        if not self.target:
            _recent = obt_recent_work()
            if _recent:
                self.target = pipe.to_work(_recent[0].path)
            _LOGGER.debug(' - APPLIED RECENT WORK %s', self.target)
        _LOGGER.debug(' - TARGET %s %s', type(self.target), self.target)

    def jump_to(self, path):
        """Jump interface to the given path.

        Args:
            path (str): path to jump to

        Returns:
            (bool): whether path was successfully applied
        """
        _LOGGER.debug('JUMP TO %s', path)
        _trg, _tab, _trg_ety = self._jump_to_assign_target(path)
        self.target = _trg
        if not self.target:
            return False

        # Update ui
        self.ui.Job.redraw()
        _LOGGER.debug(' - TRG ETY %s', _trg_ety)
        if _trg_ety:
            self.ui.Profile.select_text(_trg_ety.profile + 's', catch=False)
            self.ui.EntityType.select_text(_trg_ety.entity_type)
            self.ui.Entity.select_text(_trg_ety.name)
        if _tab:
            _LOGGER.debug(' - SELECT PANE %s', _tab)
            self.ui.MainPane.select_tab(_tab, emit=True)

        # Determine result
        _LOGGER.debug(' - TARGET %s', self.target)
        if to_str(self.target) != to_str(path):
            _result = False
        elif isinstance(self.target, pipe.CPWork):
            _result = self.target == self.ui.WWorks.selected_data()
        elif isinstance(self.target, pipe.CPOutputBase):
            _out = self.target == self.ui.SOutputs.selected_data()
            _LOGGER.debug(' - OUT %s', _out)
            _result = _out
        else:
            _result = False
        _LOGGER.debug(' - RESULT %s', _result)

        self.target = None

        return _result

    def _jump_to_assign_target(self, path):
        """Assign jump to target.

        Args:
            path (str): path to jump to

        Returns:
            (tuple): target, target tab, target entity
        """
        _trg = _trg_tab = _trg_ety = None

        # Try target as work
        if not _trg:
            _trg = pipe.to_work(path)
            if _trg:
                _trg_tab = 'Work'
                _trg_ety = _trg.entity

        # Try target as output
        if not _trg:
            _out = pipe.to_output(path, catch=True)
            if _out:
                _out = pipe.CACHE.obt(_out)
                _trg = _out
                _trg_tab = 'Scene'
                if _out.profile == 'shot':
                    _trg_ety = _out.entity

        # Try target as entity
        if not _trg:
            _trg = pipe.to_entity(path, catch=True)
            _trg_ety = _trg

        _LOGGER.debug(' - TARGET tab=%s %s %s', _trg_tab, type(_trg), _trg)
        return _trg, _trg_tab, _trg_ety

    def _callback__Refresh(self):
        self.target = self.work
        pipe.CACHE.reset()
        self.ui.Job.redraw()  # Rebuild ui elements
        self.target = None

    def reset(self):
        """Reset pini helper."""
        self.ui.Refresh.click()
        self.jump_to(dcc.cur_file())

    def add_output_opts(
            self, menu, output, find_work=True, header=True, delete=None,
            add=True, ignore_ui=False, ref=None, delete_callback=None):
        """Add menu options for the given output.

        Args:
            menu (QMenu): menu to add options to
            output (CPOutput): output to add options for
            find_work (bool): add find work option
            header (bool): include menu header
            delete (bool): include delete option
            add (bool): include add to current scene option
            ignore_ui (bool): don't add options relating to ui selection
                (eg. apply lookdev to selected scene ref)
            ref (CPipeRef): scene ref associated with this output
            delete_callback (fn): callback to execute on output deletion
        """
        _LOGGER.debug(' - ADD OUT OPTS %s', output)
        _out = output
        _out_c = pipe.CACHE.obt_output(_out, catch=True)
        _LOGGER.debug('   - OUT C %s', _out_c)

        _del = delete
        if _del is None:
            _del = pipe.MASTER != 'shotgrid'

        # Add header
        if header:
            _type = output.type_.capitalize()
            _name = output.asset or output.filename
            menu.add_label(f'{_type}: {_name}')
            menu.add_separator()

        # Add actions based on file type
        self._add_output_path_opts(
            menu=menu, output=_out, output_c=_out_c, delete=_del,
            delete_callback=delete_callback)

        # Add shotgrid opts
        if _out_c and pipe.SHOTGRID_AVAILABLE:
            from pini.pipe import shotgrid
            if _out_c.submittable:
                menu.add_action(
                    'Submit to shotgrid', icon=shotgrid.ICON,
                    func=wrap_fn(export.submit, _out_c))
            _pub = shotgrid.SGC.find_pub_file(_out_c, catch=True)
            if _pub:
                _open_url = wrap_fn(webbrowser.open, _pub.to_url())
                menu.add_action(
                    'Open in shotgrid', icon=icons.URL, func=_open_url)
                _work = pipe.CACHE.obt_work(_out_c.metadata['src'], catch=True)
                _omit = chain_fns(
                    _pub.omit, self._callback__Refresh, _work.update_outputs)
                menu.add_action(
                    'Omit in shotgrid', icon=icons.DELETE, func=_omit)

        if not _out_c:
            return
        menu.add_separator()

        if add:
            _func = chain_fns(
                wrap_fn(self.ui.MainPane.select_tab, 'Scene'),
                wrap_fn(self.stage_import, output),
                self.ui.SSceneRefs.redraw)
            menu.add_action(
                'Add to scene', _func, icon=icons.find('Plus'),
                enabled=dcc.can_reference_output(_out_c))

        # Add find options
        self._add_output_find_opts(
            menu=menu, find_work=find_work, ref=ref, output=output)

        # Add apply range option
        menu.add_separator()
        menu.add_action(
            'Print metadata',
            wrap_fn(_print_metadata, output),
            icon=icons.PRINT)
        if output.range_ and len(set(output.range_)) > 1:
            _start, _end = output.range_
            menu.add_action(
                f'Apply range ({_start:.00f}-{_end:.00f})',
                wrap_fn(dcc.set_range, output.range_[0], output.range_[1]),
                icon=icons.find('Left-Right Arrow'),
                enabled=output.range_ != dcc.t_range(int))

        # Add lookdev opts
        if _apply_lookdev_opts(output, ref):
            self._add_output_lookdev_opts(
                menu, lookdev=output, ref=ref, ignore_ui=ignore_ui)

    def _add_output_path_opts(
            self, menu, output, output_c, delete, delete_callback):
        """Add path-specific output options.

        Args:
            menu (QMenu): menu to add options to
            output (CPOutput): output to add options for
            output_c (CCPOutput): cacheable version of output
            delete (bool): include delete option
            delete_callback (fn): callback to execute on output deletion
        """
        _LOGGER.debug(' - ADD OUTPUT PATH OPTS %s', output)
        _delete_callback = delete_callback or self.ui.SOutputs.redraw

        _path = output_c or output
        if isinstance(_path, Video) or output.extn in VIDEO_EXTNS:
            menu.add_video_actions(
                _path, delete_callback=_delete_callback, delete=delete)
        elif isinstance(_path or output, Seq):
            menu.add_seq_actions(
                _path, delete_callback=_delete_callback, delete=delete)
        elif isinstance(_path, File):
            menu.add_file_actions(
                _path, delete_callback=_delete_callback, delete=delete)
        else:
            raise ValueError(_path)

        if (
                output_c and
                output_c.content_type in ('Render', 'Video') and
                self.work):
            menu.add_action(
                'Set as thumbnail', icon=icons.find('Picture'),
                func=wrap_fn(self._set_work_thumb, output))

        menu.add_separator()

    def _add_output_find_opts(self, menu, find_work, ref, output):
        """Add find options for the given output.

        Args:
            menu (QMenu): menu to add items to
            find_work (bool): add find work option
            ref (CPipeRef): scene ref associated with this output
            output (CPOutput): output to add options for
        """
        menu.add_separator()

        # Add find work
        _asset = None
        if find_work:
            menu.add_action(
                'Find work file',
                wrap_fn(self._jump_to_latest_out_work, output),
                icon=icons.FIND, enabled=bool(output.src))
            _asset = output.src_ref

        # Add find asset
        if (
                not _asset and
                output.basic_type in ('publish', 'publish_seq') and
                output.profile == 'asset'):
            _asset = output
            _asset = pipe.map_path(_asset)
            _LOGGER.info(' - ASSET %s', _asset)
        menu.add_action(
            'Find asset', wrap_fn(self.jump_to, _asset),
            icon=icons.FIND, enabled=bool(_asset))

        # Add lookdev opts
        if ref and isinstance(output, pipe.CPOutputFile):
            _out_c = pipe.CACHE.obt(output)
            _lookdev = _out_c.find_lookdev_shaders()
            menu.add_action(
                'Find lookdev', wrap_fn(self.jump_to, _lookdev),
                icon=icons.FIND, enabled=bool(_lookdev))
            _attach = chain_fns(
                wrap_fn(self.stage_import, _lookdev, attach_to=ref),
                self.ui.SSceneRefs.redraw)
            menu.add_action(
                'Apply lookdev', _attach, icon=LOOKDEV_BG_ICON,
                enabled=bool(_lookdev and ref))

    def _jump_to_latest_out_work(self, output):
        """Jump to latest work file for the given output.

        Args:
            output (CPOutput): output to find work for
        """
        _LOGGER.info('FIND LATEST WORK %s', output.path)
        _src = pipe.map_path(output.src)
        if not _src:
            _LOGGER.info(' - NO WORK FOUND IN METADATA')
            return
        _src_work = pipe.CACHE.obt_work(_src, catch=True)
        if not _src_work:
            _LOGGER.info(' - FAILED TO FIND WORK FILE %s', _src)
            return
        _src_work = _src_work.find_latest(catch=True)
        _LOGGER.info(' - LATEST %s', _src_work)
        self.jump_to(_src_work)

    def _set_work_thumb(self, output):
        """Update current work thumbnail to match the given clip.

        Args:
            output (CPOutputBase): video or image sequence to apply
        """
        _out = pipe.CACHE.obt(output)
        _out.build_thumbnail(self.work.image, force=True)
        obt_pixmap(self.work.image, force=True)
        self.ui.WWorks.redraw()

    def _add_output_lookdev_opts(
            self, menu, lookdev, ignore_ui=False, ref=False):
        """Add output lookdev attach options for abcs.

        Args:
            menu (QMenu): menu to add options to
            lookdev (CPOutput): lookdev to attach
            ignore_ui (bool): don't add options relating to ui selection
                (eg. apply lookdev to selected scene ref)
            ref (CPipeRef): scene ref associated with this output
        """

        # Check for shd yml file
        if not lookdev.content_type == 'ShadersMa':
            return

        # Store shd yml on menu to avoid garbage collection
        menu.add_separator()
        menu.add_action(
            'Edit shaders yaml', wrap_fn(_shd_yml_edit, lookdev),
            icon=icons.EDIT)
        menu.add_action(
            'Print shaders data', wrap_fn(_shd_yml_print, lookdev),
            icon=icons.PRINT)
        menu.add_separator()

        # Add reapply to target option
        _trg = ref.find_target() if ref else None
        if _trg:
            _text = f'Reapply to "{_trg.namespace}"'
        else:
            _text = 'Reapply to target'
        _func = wrap_fn(ref.attach_to, _trg) if ref else None
        menu.add_action(
            _text, _func, enabled=bool(_trg), icon=LOOKDEV_BG_ICON)

        # Find apply options to add
        _vp_refs = dcc.find_pipe_refs(selected=True)
        _ui_refs = self.ui.SSceneRefs.selected_datas()
        _LOGGER.debug(
            'ADD OUTPUT LOOKDEV OPTS vp=%d ui=%d', len(_vp_refs),
            len(_ui_refs))
        _to_add = [('viewport', _vp_refs)]
        if not ignore_ui and not ref:
            _to_add.append(('helper', _ui_refs))

        # Add options to menu
        for _label, _refs in _to_add:

            _refs = [_ref for _ref in _refs
                     if _ref.output and _ref.output.pini_task != 'lookdev']

            if ref:  # Attach existing ref
                _funcs = []
                for _ref in _refs:
                    _funcs += [wrap_fn(_ref.attach_shaders, ref)]
                _func = chain_fns(*_funcs)
                menu.add_action(
                    f'Assign to {_label} selection', _func,
                    icon=LOOKDEV_BG_ICON, enabled=bool(_refs))
            else:  # Bring in new ref
                _select_outs = wrap_fn(self.ui.MainPane.select_tab, 'Scene')
                _funcs = [_select_outs]
                _funcs += [
                    wrap_fn(self.stage_import, lookdev, attach_to=_ref)
                    for _ref in _refs]
                _funcs += [self.ui.SSceneRefs.redraw]
                _func = chain_fns(*_funcs)
                menu.add_action(
                    f'Apply to {_label} selection', _func,
                    icon=LOOKDEV_BG_ICON, enabled=bool(_refs))

    def _callback__MainPane(self, index=None, save=True, switch_tabs=True):

        self.setMinimumWidth(400)
        self.flush_notes_stack()
        _LOGGER.debug(
            'CALLBACK MAIN PANE index=%s blocked=%d save=%d %s',
            index, self.ui.WWorkPath.signalsBlocked(), save, self.target)
        _tab = self.ui.MainPane.current_tab_text()
        if _tab == 'Work':
            phu_work_tab.PHWorkTab.init_ui(self)
        elif _tab == 'Export':
            # No need to update if tab not changed - this causes cache list
            # to redraw (selecting all items) on export (when sanity check
            # resets pipeline cache) which is confusing for artists
            _export_tab = self.ui.EExportPane.current_tab_text()
            if _export_tab == 'Cache' and self._cur_tab == 'Export':
                pass
            else:
                phu_export_tab.PHExportTab.init_ui(self)
        elif _tab == 'Scene':
            phu_scene_tab.PHSceneTab.init_ui(self, switch_tabs=switch_tabs)
        if save:
            self.save_settings()
        self._cur_tab = _tab

    def delete(self):
        """Delete should be implemented on subclass."""
        raise NotImplementedError

    def closeEvent(self, event=None):
        """Triggered by close.

        Args:
            event (QEvent): close event
        """
        _LOGGER.debug('CLOSE EVENT %s %s', event, self.pos())
        self.flush_notes_stack()
        _LOGGER.debug(' - CLOSE COMPLETE %s', self.pos())

    def timerEvent(self, event):
        """Triggered by timer.

        Args:
            event (QTimerEvent): triggered event
        """
        if not self.isVisible():
            self.killTimer(self.timer)
            _LOGGER.debug('KILLED TIMER %s', event)
        self.flush_notes_stack()


def _apply_lookdev_opts(output, ref):
    """Check whether lookdev options need to be applied.

    Args:
        output (CPOutput): selected output
        ref (CPipeRef): associated reference

    Returns:
        (bool): whether lookdev options should be applied
    """
    if dcc.NAME != 'maya':
        return False

    if output.content_type != 'ShadersMa':
        return False

    if ref and not isinstance(ref, pipe_ref.CMayaShadersRef):
        return False

    return True


def _print_metadata(output):
    """Print metadata for the given output.

    Implemented here to accommodate ghost outputs.

    Args:
        output (CPOutput|CCPOutputGhost): output to print metadata for
    """
    _out = pipe.CACHE.obt_output(output)
    pprint.pprint(_out.metadata, width=300)


def _shd_yml_edit(output):
    """Edit shaders yml file for the given lookdev output.

    Args:
        output (CPOutput): lookdev output
    """
    _out_c = pipe.CACHE.obt(output)
    _shd_yml = _out_c.metadata['shd_yml']
    File(_shd_yml).edit()


def _shd_yml_print(output):
    """Print shaders yml data for the given lookdev output.

    Args:
        output (CPOutput): lookdev output
    """
    _out_c = pipe.CACHE.obt(output)
    _shd_yml = _out_c.metadata['shd_yml']
    _data = File(_shd_yml).read_yml()
    _LOGGER.info(
        strftime('Published at %H:%M:%S on %a %D %b', _out_c.updated_at))
    pprint.pprint(_data, width=200)


def _to_valid_target(path):
    """Obtain a valid helper target from the given path.

    Args:
        path (str): path to check

    Returns:
        (CPWork|CPOutput|CPEntity): target
    """
    _work = pipe.to_work(path, catch=True)
    if _work:
        return _work
    _out = pipe.to_output(path, catch=True)
    if _out:
        return _out
    _ety = pipe.to_entity(path, catch=True)
    if _ety:
        return _ety
    return None
