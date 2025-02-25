"""Tools for managing the header elements in pini helper.

These are the job, entity type and entity elements above the main pane.
"""

# pylint: disable=no-member

import logging
import os

from pini import pipe, icons, qt, dcc
from pini.tools import usage
from pini.utils import wrap_fn, chain_fns, copied_path, get_user, strftime

from ..ph_utils import obt_recent_work

_LOGGER = logging.getLogger(__name__)

_ARCHIVE_ICON = icons.find('Skull')


class PHHeader:
    """Manages header elements of pini helper."""

    def __init__(self, admin):
        """Constructor.

        Args:
            admin (bool): launch in admin mode with create entity/task options
        """

        # Init admin mode
        self._admin_mode = admin
        if self._admin_mode is None:
            self._admin_mode = pipe.admin_mode()
        self.ui.ToggleAdmin.setVisible(self._admin_mode)

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
            size=0.5 * pix.width())

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
            _profile = _trg_ety.profile + 's'
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
            if pipe.MASTER == 'shotgrid':
                menu.add_action(
                    'Open in shotgrid',
                    self.entity.sg_entity.browser,
                    icon=icons.URL)
            menu.add_separator()

        # Add copied shot
        _c_ety = pipe.to_entity(copied_path(), catch=True)
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
            title='Archive ' + self.entity.profile.capitalize())

        # Record who archived
        _t_str = strftime('%y%m%d_%H%M%S')
        _file = self.entity.to_file(
            f'.pini/archived/{_t_str}_{get_user()}.file')
        _file.touch()

        # Execute the archiving
        _path = self.entity.to_dir().to_subdir('_' + self.entity.name).path
        _LOGGER.info(' - PATH %s', _path)
        self.entity.move_to(_path, force=True)
        self.ui.Refresh.click()

    def _context__JumpToCurrent(self, menu):

        menu.add_label('Jump to')
        menu.add_separator()

        # Add copied work
        _c_path = copied_path()
        _c_work = pipe.to_work(_c_path, catch=True)
        _c_out = pipe.to_output(_c_path, catch=True)
        if _c_work:
            self._add_jump_to_work_action(menu=menu, work=_c_work)
        elif _c_out:
            self._add_jump_to_output_action(menu=menu, output=_c_out)
        else:
            menu.add_label('No copied work/output', icon=icons.COPY)
        _cur_work = pipe.cur_work()
        if _cur_work:
            menu.add_action(
                'Take snapshot', self._take_snapshot,
                icon=icons.find('Camera with Flash'))
        else:
            menu.add_label('No current work to snapshot')
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

    def _add_jump_to_output_action(self, menu, output):
        """Add jump to output action to the given menu.

        Args:
            menu (QMenu): menu to add to
            output (CPOutput): output to jump to
        """
        _action = wrap_fn(self.jump_to, output)
        _tokens = [output.job.name] + output.base.split('_')[:-1]
        _label = '/'.join(_tokens)
        menu.add_action(
            _label, _action, icon=icons.find('Magnet'))

    def _take_snapshot(self):
        """Take snapshot of the current scene and save as work thumbnail."""
        _work = pipe.CACHE.obt_cur_work()
        assert _work
        self._callback__JumpToCurrent()
        dcc.take_snapshot(_work.image)
        _work.update_outputs()
