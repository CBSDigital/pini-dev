"""Tools for managing PiniHelper interface."""

# pylint: disable=no-member

import logging
import os
import pprint
import webbrowser

from pini import pipe, icons, dcc, qt
from pini.dcc import pipe_ref
from pini.qt import QtGui
from pini.tools import usage
from pini.utils import (
    File, wrap_fn, chain_fns, copied_path, get_user, strftime, Video, Seq,
    VIDEO_EXTNS)

from .elem import CLWorkTab, CLExportTab, CLSceneTab
from .ph_utils import LOOKDEV_BG_ICON, obt_recent_work, obt_pixmap

_DIALOG = None
_DIR = File(__file__).to_dir()
_LOGGER = logging.getLogger(__name__)

TITLE = os.environ.get('PINI_HELPER_TITLE', 'Pini Helper')
_EMOJI_NAME = os.environ.get('PINI_HELPER_EMOJI', "Front-Facing Baby Chick")
EMOJI = icons.find_emoji(_EMOJI_NAME)
ICON = EMOJI.path

UI_FILE = _DIR.to_file('pini_helper.ui').path

_OPEN_URL_ICON = icons.find('Globe Showing Europe-Africa')
_ARCHIVE_ICON = icons.find('Skull')
BKPS_ICON = icons.find('Package')
OUTS_ICON = icons.find('Dove')


class BasePiniHelper(CLWorkTab, CLExportTab, CLSceneTab):
    """Virtual base class for all Pini Helper interfaces."""

    ui = None
    timer = None
    target = None

    _cur_tab = None

    def __init__(
            self, jump_to=None, admin=None, load_settings=True,
            show=True, reset_cache=True, title=None):
        """Constructor.

        Args:
            jump_to (str): path to jump interface to on launch
            admin (bool): launch in admin mode with create entity/task options
            load_settings (bool): load settings on launch
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

        for _tab in [CLWorkTab, CLExportTab, CLSceneTab]:
            _tab.__init__(self)

        # Setup vars
        self._save_settings = load_settings
        self._notes_stack = {}
        if not pipe.CACHE.jobs:
            raise RuntimeError('No valid jobs found in '+pipe.ROOT.path)

        # Init admin mode
        self._admin_mode = admin
        if self._admin_mode is None:
            self._admin_mode = pipe.admin_mode()
        self.ui.ToggleAdmin.setVisible(self._admin_mode)

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

        if load_settings:
            _LOGGER.debug(' - LOADING SETTINGS')
            self.load_settings()
            _LOGGER.debug(' - LOADED SETTINGS')
        self.ui.MainPane.select_tab('Work')
        if show:
            self.show()

        self._start_timer()

        self.target = None

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

    @property
    def job(self):
        """Obtain selected job.

        Returns:
            (CPJob): selected job
        """
        return self.ui.Job.selected_data()

    @property
    def entity(self):
        """Obtain selected entity.

        Returns:
            (CPEntity): selected entity
        """
        _ety = self.ui.Entity.selected_data()
        return _ety

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
        self.target = target
        if not self.target:
            _cur_work = pipe.cur_work()
            if _cur_work:
                self.target = _cur_work
        if not self.target:
            _cur_out = pipe.cur_output()
            if _cur_out:
                _src = _cur_out.metadata.get('src')
                if _src:
                    self.target = pipe.to_output(_src, catch=True)
        if not self.target:
            _recent = obt_recent_work()
            if _recent:
                self.target = pipe.to_work(_recent[0].path)
        _LOGGER.debug(' - TARGET %s', self.target)

    def jump_to(self, path):
        """Jump interface to the given path.

        Args:
            path (str): path to jump to
        """
        _LOGGER.debug('JUMP TO %s', path)

        # Assign target
        self.target = _tab = _trg_ety = None
        if not self.target:
            self.target = pipe.to_work(path)
            if self.target:
                _tab = 'Work'
                _trg_ety = self.target.entity
        if not self.target:
            _out = pipe.to_output(path, catch=True)
            if _out:
                _out = pipe.CACHE.obt(_out)
                self.target = _out
                _tab = 'Scene'
                if _out.profile == 'shot':
                    _trg_ety = _out.entity
        if not self.target:
            self.target = pipe.to_entity(path, catch=True)
            _trg_ety = self.target
        _LOGGER.debug(' - TARGET tab=%s %s', _tab, self.target)
        if not self.target:
            return

        # Update ui

        self.ui.Job.redraw()
        _LOGGER.debug(' - TRG ETY %s', _trg_ety)
        if _trg_ety:
            self.ui.Profile.select_text(_trg_ety.profile+'s', catch=False)
            self.ui.EntityType.select_text(_trg_ety.entity_type)
            self.ui.Entity.select_text(_trg_ety.name)
        if _tab:
            _LOGGER.debug(' - SELECT PANE  %s', _tab)
            self.ui.MainPane.select_tab(_tab, emit=True)

        self.target = None

    def reset(self):
        """Reset pini helper."""
        self.ui.Refresh.click()
        self.jump_to(dcc.cur_file())

    def _add_output_opts(
            self, menu, output, find_work=True, header=True, delete=True,
            add=True, ignore_ui=False, ref=None, parent=None,
            delete_callback=None):
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
            parent (QWidget): widget to update if outputs change
            delete_callback (fn): callback to execute on output deletion
        """
        _out = output
        _out_c = pipe.CACHE.obt_output(_out, catch=True)

        # Add header
        if header:
            _type = output.type_.capitalize()
            _name = output.asset or output.filename
            menu.add_label(f'{_type}: {_name}')
            menu.add_separator()

        # Add actions based on file type
        self._add_output_path_opts(
            menu=menu, output=_out, output_c=_out_c, delete=delete,
            delete_callback=delete_callback)

        # Add shotgrid opts
        if _out_c and pipe.SHOTGRID_AVAILABLE:
            from pini.pipe import shotgrid
            if _out_c.submittable:
                _submit = wrap_fn(shotgrid.SUBMITTER.run, _out_c)
                _func = chain_fns(_submit, parent.redraw)
                menu.add_action(
                    'Submit to shotgrid', icon=shotgrid.ICON, func=_func)
            _pub = shotgrid.SGC.find_pub_file(_out_c, catch=True)
            if _pub:
                _open_url = wrap_fn(webbrowser.open, _pub.to_url())
                menu.add_action(
                    'Open in shotgrid', icon=_OPEN_URL_ICON, func=_open_url)

        if not _out_c:
            return
        menu.add_separator()

        if add:
            _func = chain_fns(
                wrap_fn(self.ui.MainPane.select_tab, 'Scene'),
                wrap_fn(self._stage_import, output),
                self.ui.SSceneRefs.redraw)
            menu.add_action(
                'Add to scene', _func, icon=icons.find('Plus'),
                enabled=dcc.can_reference_output(output))

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
        _delete_callback = delete_callback or self.ui.SOutputs.redraw

        if isinstance(output, Video) or output.extn in VIDEO_EXTNS:
            menu.add_video_actions(
                output, delete_callback=_delete_callback, delete=delete)
        elif isinstance(output, Seq):
            menu.add_seq_actions(
                output, delete_callback=_delete_callback, delete=delete)
        elif isinstance(output, File):
            menu.add_file_actions(
                output, delete_callback=_delete_callback, delete=delete)
        else:
            raise ValueError(output)

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
                wrap_fn(self._stage_import, _lookdev, attach=ref),
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
                _funcs += [wrap_fn(self._stage_import, lookdev, attach=_ref)
                           for _ref in _refs]
                _funcs += [self.ui.SSceneRefs.redraw]
                _func = chain_fns(*_funcs)
                menu.add_action(
                    f'Apply to {_label} selection', _func,
                    icon=LOOKDEV_BG_ICON, enabled=bool(_refs))

    def _redraw__Job(self):
        _LOGGER.debug('REDRAW JOB')
        _names = [_job.name for _job in pipe.CACHE.jobs]
        _select = pipe.to_job(self.target) if self.target else None
        self.ui.Job.set_items(_names, data=pipe.CACHE.jobs, select=_select)

    def _draw__JobIcon(self, pix):
        """Update job icon pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        _LOGGER.debug('UPDATE JOB ICON %s', self.job)
        pix.fill('Transparent')
        pix.draw_rounded_rect(
            pos=(0, 0), col=self.job.to_col(), outline=None,
            size=pix.size())
        pix.draw_overlay(
            self.job.to_icon(), anchor='C', pos=pix.center(),
            size=0.5*pix.width())

    def _redraw__EntityType(self):

        _cur = self.ui.EntityType.selected_text()
        _job = self.ui.Job.selected_data()
        _profile = self.ui.Profile.selected_text()

        # Read entity types
        _data = None
        if not _job:
            _types = []
        elif _profile == 'assets':
            _types = _job.find_asset_types()
        elif _profile == 'shots':
            _data = _job.find_sequences()
            _types = [
                _seq if isinstance(_seq, str) else _seq.name
                for _seq in _data]
        else:
            raise ValueError(_profile)
        _LOGGER.debug('REDRAW ENTITY TYPE %s %s', _job.name, _types)

        # Determine default selection
        _sel = None
        if self.target:
            _trg_ety = pipe.to_entity(self.target)
            if (  # No need to jump to asset outputs
                    isinstance(self.target, pipe.CPOutputBase) and
                    self.target.profile == 'asset'):
                _trg_ety = None
            _LOGGER.debug(' - TRG ENTITY TYPE %s %s', _trg_ety, self.target)
            if _trg_ety:
                _sel = _trg_ety.entity_type
                _LOGGER.debug(' - APPLY TARGET ETY TYPE %s', _sel)
        if not _sel:
            _sel = _cur

        self.ui.EntityType.setEditable(self._admin_mode)
        self.ui.EntityType.set_items(_types, data=_data, select=_sel)

    def _redraw__EntityTypeCreate(self):
        _LOGGER.debug('REDRAW EntityTypeCreate')
        _job = self.ui.Job.selected_data()
        _type = self.ui.EntityType.currentText()
        _profile = self.ui.Profile.selected_text()
        if not _job:
            _en = False
        elif _profile == 'assets':
            _types = _job.find_asset_types()
            _en = _type not in _types
        elif _profile == 'shots':
            _seq = self.ui.EntityType.selected_data()
            _en = not bool(_seq)
        else:
            raise ValueError(_profile)
        self.ui.EntityTypeCreate.setEnabled(_en)

    def _redraw__Entity(self):

        _cur_ety = self.entity
        _profile = self.ui.Profile.selected_text()
        _type = self.ui.EntityType.selected_text()
        _LOGGER.debug('REDRAW ENTITY job=%s type=%s', self.job, _type)

        # Build entity list
        if not self.job:
            _etys = []
        elif _profile == 'assets':
            _etys = self.job.find_assets(asset_type=_type)
        elif _profile == 'shots':
            _seq = self.ui.EntityType.selected_data()
            _etys = self.job.find_shots(sequence=_seq) if _seq else []
        else:
            raise ValueError(_profile)
        _labels = [_ety.name for _ety in _etys]
        _LOGGER.debug(' - ENTITIES %s', _etys)

        # Determine default selection
        _select = None
        _trg_ety = pipe.to_entity(self.target, catch=True)
        if (  # No need to jump to asset outputs
                isinstance(self.target, pipe.CPOutputBase) and
                self.target.profile == 'asset'):
            _trg_ety = None
        if _trg_ety:
            _select = _trg_ety
        elif pipe.cur_entity():
            _select = pipe.cur_entity()
        elif _cur_ety:
            _select = _cur_ety

        self.ui.Entity.setEditable(self._admin_mode)
        self.ui.Entity.set_items(_labels, data=_etys, select=_select)

    def _redraw__EntityCreate(self):
        _LOGGER.debug('REDRAW ENTITY CREATE')
        _ety = self.ui.Entity.selected_data()
        _job = self.ui.Job.selected_data()
        _ety_type = self.ui.EntityType.currentText()
        if _ety or not _job or not _ety_type:
            _en = False
        else:
            _ety_text = self.ui.Entity.currentText()
            _profile = self.ui.Profile.selected_text()
            if _profile == 'assets':
                _asset = _job.to_asset(asset_type=_ety_type, asset=_ety_text)
                _en = bool(_asset) and _asset not in _job.assets
            elif _profile == 'shots':
                _shot = _job.to_shot(sequence=_ety_type, shot=_ety_text)
                _LOGGER.debug(' - SHOT %s', _shot)
                _en = bool(_shot) and _shot not in _job.shots
            else:
                raise ValueError(_profile)
        self.ui.EntityCreate.setEnabled(_en)

    def _callback__MainPane(self, index=None, save=True, switch_tabs=True):

        self.setMinimumWidth(400)
        self.flush_notes_stack()
        _LOGGER.debug(
            'CALLBACK MAIN PANE index=%s blocked=%d save=%d %s',
            index, self.ui.WWorkPath.signalsBlocked(), save, self.target)
        _tab = self.ui.MainPane.current_tab_text()
        if _tab == 'Work':
            CLWorkTab.init_ui(self)
        elif _tab == 'Export':
            # No need to update if tab not changed - this causes cache list
            # to redraw (selecting all items) on export (when sanity check
            # resets pipeline cache) which is confusing for artists
            _export_tab = self.ui.EExportPane.current_tab_text()
            if _export_tab == 'Cache' and self._cur_tab == 'Export':
                pass
            else:
                CLExportTab.init_ui(self)
        elif _tab == 'Scene':
            CLSceneTab.init_ui(self, switch_tabs=switch_tabs)
        if save:
            self.save_settings()
        self._cur_tab = _tab

    def _callback__Job(self):
        _LOGGER.debug('CALLBACK JOB')

        # Apply target profile
        _trg_ety = None
        if self.target:
            _trg_ety = pipe.to_entity(self.target)
            if (  # No need to jump to asset outputs
                    isinstance(self.target, pipe.CPOutputBase) and
                    self.target.profile == 'asset'):
                _trg_ety = None
        if _trg_ety:
            _profile = _trg_ety.profile+'s'
            _LOGGER.debug(' - APPLY TARGET PROFILE %s', _profile)
            self.ui.Profile.select_text(_profile)

        self.ui.JobIcon.redraw()
        self._redraw__EntityType()

    def _callback__ProfileLabel(self):
        _items = self.ui.Profile.all_text()
        _cur = self.ui.Profile.currentText()
        _next_i = (_items.index(_cur) + 1) % len(_items)
        _next = _items[_next_i]
        self.ui.Profile.setCurrentText(_next)

    def _callback__Profile(self):
        _profile = self.ui.Profile.selected_text()
        _LOGGER.debug('CALLBACK PROFILE %s', _profile)
        if _profile == 'assets':
            _type_label = 'Type'
            _ety_label = 'Asset'
            _create_ety_type_tt = 'Create new category'
            _create_ety_tt = 'Create new asset'
        elif _profile == 'shots':
            _type_label = os.environ.get(
                'PINI_PIPE_SEQUENCE_LABEL', 'Sequence')
            _ety_label = 'Shot'
            _create_ety_type_tt = 'Create new sequence'
            _create_ety_tt = 'Create new shot'
        else:
            raise ValueError(_profile)
        self.ui.EntityTypeLabel.setText(_type_label)
        self.ui.EntityLabel.setText(_ety_label)
        self.ui.EntityTypeCreate.setToolTip(_create_ety_type_tt)
        self.ui.EntityCreate.setToolTip(_create_ety_tt)
        self._redraw__EntityType()

    def _callback__ToggleAdmin(self, admin=None):
        _cur_ety = self.entity
        if admin is not None:
            self._admin_mode = admin
        else:
            self._admin_mode = not self._admin_mode
        for _elem in [self.ui.WTaskText, self.ui.EntityCreate,
                      self.ui.EntityTypeCreate]:
            _elem.setVisible(self._admin_mode)
        if not self.target:
            self._set_target(_cur_ety)
        self.ui.EntityType.redraw()
        self.ui.Entity.redraw()

    def _callback__EntityType(self):
        self._redraw__EntityTypeCreate()
        self._redraw__Entity()

    def _callback__EntityTypeCreate(self):
        _job = self.ui.Job.selected_data()
        _profile = self.ui.Profile.selected_text()
        _type = self.ui.EntityType.currentText()
        _LOGGER.info('CREATE ENTITY TYPE %s %s', _profile, _type)
        if _profile == 'assets':
            _job.create_asset_type(_type, parent=self)
        elif _profile == 'shots':
            _seq = _job.to_sequence(_type)
            _seq.create(_type, parent=self)
        else:
            raise ValueError
        self._callback__Profile()
        self.ui.EntityType.select_text(_type)

    def _callback__Entity(self):
        self._redraw__EntityCreate()
        self._callback__MainPane(save=False, switch_tabs=False)

    def _callback__EntityCreate(self, force=False, shotgrid_=True):

        _job = self.ui.Job.selected_data()
        _profile = self.ui.Profile.selected_text()
        _type = self.ui.EntityType.currentText()
        _ety_text = self.ui.Entity.currentText()

        _LOGGER.info('CREATE ENTITY %s %s/%s', _profile, _type, _ety_text)
        _LOGGER.debug(' - JOB %s %s', _job, id(_job))
        if _profile == 'assets':
            _ety = _job.to_asset(asset_type=_type, asset=_ety_text)
        elif _profile == 'shots':
            _ety = _job.to_shot(sequence=_type, shot=_ety_text)
        else:
            raise ValueError
        _LOGGER.debug(' - ENTITY %s', _ety)
        _ety.create(parent=self, force=force, shotgrid_=shotgrid_)
        assert _ety
        assert _ety in _job.entities

        # Update ui
        self.ui.EntityType.redraw()
        self.ui.Entity.redraw()
        self.jump_to(_ety.path)

    def _callback__JumpToCurrent(self):
        _file = dcc.cur_file()
        if not _file:
            qt.notify(
                'Unable to jump to current scene.\n\nThis scene has not been '
                'saved yet.', title='Warning', icon=icons.find('Magnet'),
                parent=self)
            return
        self.jump_to(_file)

    def _callback__Refresh(self):
        self.target = self.work
        pipe.CACHE.reset()
        self.ui.Job.redraw()  # Rebuild ui elements
        self.target = None

    def _context__JobLabel(self, menu):
        if not self.job:
            return

        menu.add_dir_actions(self.job)
        menu.add_separator()

        if pipe.MASTER == 'disk':
            menu.add_action(
                'Force reread publishes',
                chain_fns(
                    wrap_fn(self.job.find_publishes, force=2),
                    self._callback__Refresh),
                icon=icons.REFRESH)
        elif pipe.MASTER == 'shotgrid':
            menu.add_action(
                'Force rebuild outputs cache',
                chain_fns(
                    wrap_fn(self.job.find_outputs, force=2),
                    self._callback__Refresh),
                icon=icons.REFRESH)
        else:
            raise ValueError(pipe.MASTER)

    def _context__EntityLabel(self, menu):

        if self.entity:
            menu.add_dir_actions(self.entity)
            menu.add_separator()
            menu.add_action(
                'Force reread outputs',
                self._reread_entity_outputs,
                icon=icons.REFRESH)
            menu.add_action(
                f'Archive {self.entity.profile}',
                self._archive_entity, enabled=pipe.admin_mode(),
                icon=_ARCHIVE_ICON)
            menu.add_separator()

        # Add copied shot
        _c_ety = pipe.to_entity(QtGui.QClipboard().text(), catch=True)
        if not _c_ety:
            menu.add_label('No copied entity', icon=icons.COPY)
        else:
            _action = wrap_fn(self.jump_to, _c_ety)
            menu.add_action(
                _c_ety.label, _action, icon=icons.find('Magnet'))
        menu.add_separator()

        # Add recent entities
        _r_etys = []
        for _r_work in obt_recent_work():
            _LOGGER.debug('CHECKING WORK %s', _r_work)
            if _r_work.entity == self.entity:
                continue
            if _r_work.entity in _r_etys:
                continue
            _r_etys.append(_r_work.entity)
            _action = wrap_fn(self.jump_to, _r_work.entity)
            menu.add_action(
                _r_work.entity.label, _action, icon=icons.find('Magnet'))

    def _reread_entity_outputs(self):
        """Reread outputs for the current asset/shot."""
        self.entity.find_outputs(force=2)
        self._callback__MainPane()

    @usage.get_tracker('PiniHelper.Archive')
    def _archive_entity(self):
        """Archive the current shot (ie. add a leading underscore)."""
        _LOGGER.info('ARCHIVE %s', self.entity)

        qt.ok_cancel(
            f"Are you sure you want to archive this {self.entity.profile}?"
            f"\n\n{self.entity.path}\n\n"
            f"It will have an underscore prepended to its name and "
            f"will no longer be visible in the pipeline.",
            icon=_ARCHIVE_ICON,
            title='Archive '+self.entity.profile.capitalize())

        # Record who archived
        _t_str = strftime('%y%m%d_%H%M%S')
        _file = self.entity.to_file(
            f'.pini/archived/{_t_str}_{get_user()}.file')
        _file.touch()

        # Execute the archiving
        _path = self.entity.to_dir().to_subdir('_'+self.entity.name).path
        _LOGGER.info(' - PATH %s', _path)
        self.entity.move_to(_path, force=True)
        self.ui.Refresh.click()

    def _context__JumpToCurrent(self, menu):

        menu.add_label('Jump to')
        menu.add_separator()

        # Add copied work
        _c_work = pipe.to_work(copied_path(), catch=True)
        if not _c_work:
            menu.add_label('No copied work', icon=icons.COPY)
        else:
            self._add_jump_to_work_action(menu=menu, work=_c_work)
        menu.add_separator()

        # Add recent works
        for _r_work in obt_recent_work():
            self._add_jump_to_work_action(menu=menu, work=_r_work)

    def _add_jump_to_work_action(self, menu, work):
        """Add jump to work action to the given menu.

        Args:
            menu (QMenu): menu to add to
            work (CPWork): work file to jump to
        """
        _action = wrap_fn(self.jump_to, work)
        _tokens = [work.job.name] + work.base.split('_')[:-1]
        _label = '/'.join(_tokens)
        menu.add_action(
            _label, _action, icon=icons.find('Magnet'))

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
    _out = pipe.to_output(output)
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
