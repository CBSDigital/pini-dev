"""Tools for manging the pini helper work tab."""

# pylint: disable=no-member

import logging
import pprint
import os

from pini import qt, pipe, icons, dcc
from pini.tools import usage
from pini.utils import (
    strftime, copy_text, str_to_seed, plural, ints_to_str, EMPTY, to_nice,
    wrap_fn, get_user)

from .. import ph_utils
from . import phu_work_item

_LOGGER = logging.getLogger(__name__)

_STAR = icons.find('Star')
_WARNING_RED = qt.CColor('Red').whiten(0.45)


class PHWorkTab:
    """Class for grouping together elements of the carb helper Work tab."""

    entity = None
    job = None
    next_work = None
    ui = None

    show_all_works_item = None

    def init_ui(self):
        """Inititate this tab's interface - triggered by selecting this tab."""
        self.ui.WTasks.redraw()
        if not self.ui.WWorkPath.signalsBlocked():
            self.ui.WWorkPath.redraw()

    @property
    def tag(self):
        """Obtain selected tag.

        Returns:
            (str): tag
        """
        _tag = self.ui.WTagText.text()
        if not _tag:
            _tag = None
        return _tag

    @property
    def work_dir(self):
        """Obtain selected work dir.

        Returns:
            (CPWorkDir): work dir (if any)
        """
        _LOGGER.log(9, 'WORK DIR %s', self.entity)
        if not self.entity:
            return None

        # Existing task
        _work_dir = self.ui.WTasks.selected_data()
        if _work_dir and not self.entity.contains(_work_dir):
            self.ui.WTasks.redraw()
            _work_dir = self.ui.WTasks.selected_data()
        if _work_dir:
            return _work_dir

        # New task
        _task = self.ui.WTaskText.text()
        _new_work_dir = self.entity.to_work_dir(
            task=_task, dcc_=dcc.NAME, catch=True)
        if _new_work_dir:
            _new_work_dir.set_badly_named_files(0)

        return _new_work_dir

    @property
    def work(self):
        """Obtain selected work.

        Returns:
            (CPWork): selected work
        """
        _work = self.ui.WWorks.selected_data()
        if not self.work_dir:
            return None
        if _work and not self.work_dir.contains(_work):
            self.ui.WWorks.redraw()
            _work = self.ui.WWorks.selected_data()
        return _work

    def _redraw__WTasks(self):
        _LOGGER.debug('REDRAW TASKS %s (%s)', self.entity, dcc.NAME)

        _items = []
        _select = _task_in_use = None

        if self.entity:

            # Build task items
            _work_dirs = self.entity.find_work_dirs(dcc_=dcc.NAME)
            for _work_dir in sorted(_work_dirs):
                _col = 'Grey'
                _LOGGER.debug(
                    ' - ADDING WORK DIR %d %s', _work_dir.has_works(),
                    _work_dir)
                if _work_dir.has_works():
                    _col = None
                    if not _task_in_use:
                        _task_in_use = _work_dir.task_label
                _item = qt.CListWidgetItem(
                    _work_dir.task_label, col=_col, data=_work_dir)
                _items.append(_item)

            # Determine initial selection
            if self.target:
                _work_dir = pipe.to_work_dir(self.target)
                _LOGGER.debug(' - APPLYING TARGET %s', self.target)
                if _work_dir:
                    _select = _work_dir.task_label
                    _LOGGER.debug(' - USING TARGET TASK')
            _cur_task = pipe.cur_task(fmt='full')
            if not _select and _cur_task and not _select:
                _select = _cur_task
                _LOGGER.debug(' - USING CURRENT TASK')
            if not _select and _task_in_use:
                _select = _task_in_use
                _LOGGER.debug(' - USING TASK IN USE')

        _LOGGER.debug(' - SELECT TASK %s', _select)
        self.ui.WTasks.set_items(_items, select=_select)

    def _to_default_tag(self):
        """Obtain default tag for the current job.

        Returns:
            (str): default tag
        """
        if pipe.DEFAULT_TAG:
            return pipe.DEFAULT_TAG
        if self.job:
            return self.job.cfg['tokens']['tag']['default']
        return None

    def _redraw__WTags(self):

        _default_tag = self._to_default_tag()
        _LOGGER.debug('REDRAW TAGS default=%s', _default_tag)

        _tags, _select, _default_exists = self._build_tags_list()
        _LOGGER.debug(' - TAGS %s select=%s', _tags, _select)

        # Build items
        _items = []
        for _tag in _tags:
            if not _tag:
                _col = 'Yellow'
            elif _tag == _default_tag:
                if _default_exists:
                    _col = 'DeepSkyBlue'
                else:
                    _col = 'LightSkyBlue'
            else:
                _col = None
            _item = qt.CListWidgetItem(
                _tag or '<default>', data=_tag, col=_col)
            _items.append(_item)

        # Update widget
        _LOGGER.debug(' - items=%s', _items)
        self.ui.WTags.set_items(_items, select=_select, emit=True)

    def _build_tags_list(self):
        """Build list of tags to display.

        Returns:
            (tuple): tags, selected tag
        """
        _cur_work = pipe.cur_work()
        _ui_tag = self.ui.WTagText.text()
        _default_tag = self._to_default_tag()
        _existing_tags = set()

        # Build tag list
        _default_exists = None
        if not self.work_dir:
            _tags = []
        else:
            _tags = set()
            _works = self.work_dir.find_works(extns=dcc.VALID_EXTNS)
            _existing_tags = {_work.tag for _work in _works}
            _tags |= _existing_tags
            if _default_tag:
                _default_exists = _default_tag in _existing_tags
                _tags |= {_default_tag}
            _allow_no_tag = self.job.find_template(
                'work', has_key={'tag': False}, catch=True)
            if _allow_no_tag:
                _tags |= {None}
            _tags = sorted(_tags, key=pipe.tag_sort)

        # Apply default selection
        _select = None
        _trg_work = pipe.to_work(self.target)
        if _trg_work:
            _select = _trg_work.tag
        elif _cur_work:
            _select = _cur_work.tag
        elif _ui_tag in _tags and _ui_tag in _existing_tags:
            _select = _ui_tag
        elif None in _tags:
            _select = None
        elif _existing_tags:
            _select = sorted(_existing_tags)[0]
        elif _tags:
            _select = sorted(_tags)[0]

        return _tags, _select, _default_exists

    def _redraw__WTagError(self):

        _tooltip = ''
        _invalid = False
        if self.tag:
            try:
                pipe.validate_token(value=self.tag, token='tag', job=self.job)
            except ValueError as _exc:
                _tooltip = str(_exc)
                _invalid = True
        self.ui.WTagError.setVisible(_invalid)
        self.ui.WTagError.setToolTip(_tooltip)

    def _update_badly_named_files_elements(self):
        """Update elements which warning if badly named files found."""

        # Check whether to show badly named files warning
        if not os.environ.get('PINI_WARN_ON_BADLY_NAMED_FILES'):
            _n_bad_files = 0
        else:
            # Check for badly named files
            _n_bad_files = (
                self.work_dir.badly_named_files if self.work_dir else 0)

        # Update element visibility
        for _elem in [self.ui.WWorkBadFilesIconR,
                      self.ui.WWorkBadFilesIconL,
                      self.ui.WWorkBadFilesLabel]:
            _elem.setVisible(bool(_n_bad_files))

        # Update label text
        _verb = plural(_n_bad_files, singular='is', plural_='are')
        _text = (
            f'Warning - there {_verb} {_n_bad_files:d} badly named '
            f'file{plural(_n_bad_files)} in this\ndirectory which '
            f'{_verb} not shown in the versions list')
        self.ui.WWorkBadFilesLabel.setText(_text)
        self.ui.WWorkBadFilesLabel.set_col(_WARNING_RED)

    def _get_works(self, force, view_limit=20):
        """Get list of work files to display.

        Args:
            force (bool): force reread from disk
            view_limit (int): how many works to display in limited view

        Returns:
            (tuple): list wdiget items, work list
        """
        _show_all = self.ui.WWorksShowAll.isChecked()

        # Get list of works
        _limit_view = False
        _existing_work_dir = self.ui.WTasks.selected_data()
        _LOGGER.debug(' - EXISTING WORK DIR %s', _existing_work_dir)
        if _existing_work_dir and self.work_dir:
            _works = self.work_dir.find_works(
                tag=self.tag, force=force, dcc_=dcc.NAME)
            if not _show_all and len(_works) > view_limit:
                _limit_view = True
                _works = _works[-view_limit:]
        else:
            _works = []

        # Create dummy next work item
        _LOGGER.debug(' - WORK DIR %s', self.work_dir)
        self.next_work = None
        if self.work_dir:
            if not _works:
                _work = self.work_dir.to_work(
                    tag=self.tag, user=pipe.cur_user(), catch=True)
            else:
                _work = _works[0]
            _LOGGER.debug(' - WORK %s', _work)
            if _work:
                self.next_work = _work.find_next()
        if self.next_work:
            self.next_work.set_exists(False)
            assert not self.next_work.exists()
            _works.append(self.next_work)
        _works.reverse()

        _LOGGER.debug(' - GET WORKS %d', len(_works))
        return _works, _limit_view

    def _redraw__WWorks(self, select=EMPTY, force=False):

        _LOGGER.debug('REDRAW WORKS WWorks')
        _items = []
        _cur_work = pipe.CACHE.cur_work
        _works, _limit_view = self._get_works(force=force)
        _LOGGER.debug(' - FOUND %d WORKS', len(_works))

        # Build items
        for _work in _works:
            _item = phu_work_item.PHWorkItem(
                list_view=self.ui.WWorks, work=_work, helper=self)
            _items.append(_item)

        # Determine selection
        _trg_work = pipe.to_work(self.target)
        _cur_work = pipe.cur_work()
        if select:
            _select = select
        elif _trg_work and _trg_work in _works:
            _select = _trg_work
        elif _cur_work and _cur_work in _works:
            _select = _cur_work
        elif len(_works) > 1:
            _select = _works[1]
        elif _works:
            _select = _works[0]
        else:
            _select = None

        _LOGGER.debug(' - SELECT WORK %s', _select)
        self.ui.WWorks.set_items(_items, select=_select)
        self._update_badly_named_files_elements()

    def _redraw__WWorkPath(self):

        _blocked = self.ui.WWorkPath.signalsBlocked()
        _LOGGER.debug('REDRAW WORK PATH blocked=%d', _blocked)

        # Build list of recent works
        _data = []
        _items = []
        for _work in ph_utils.obt_recent_work():
            _ety = _work.shot or (_work.asset_type + '/' + _work.asset)
            _uid = f'{_work.job.name}/{_ety}/{_work.task}'
            if _work.tag:
                _uid += '/' + _work.tag
            if _uid in _items:
                continue
            _items.append(_uid)
            _data.append(_work)

        # Update ui element
        self.ui.WWorkPath.blockSignals(True)
        _LOGGER.debug(' - BLOCKED WORK PATH SIGNALS (blocked=%d)',
                      self.ui.WWorkPath.signalsBlocked())
        self.ui.WWorkPath.set_items(_items, data=_data)
        _LOGGER.debug(' - SET ITEMS (blocked=%d)',
                      self.ui.WWorkPath.signalsBlocked())
        _work_path = self.work.path if self.work else ''
        self.ui.WWorkPath.setEditText(_work_path)
        _LOGGER.debug(
            ' - UPDATED TEXT (blocked=%d) %s',
            self.ui.WWorkPath.signalsBlocked(), _work_path)
        self.ui.WWorkPath.blockSignals(_blocked)

    def _callback__WTasks(self):
        _LOGGER.debug('CALLBACK TASKS')
        self.ui.WTaskText.setText(self.ui.WTasks.selected_text())
        self._callback__WTaskText()

    def _callback__WTaskText(self):
        _task = self.ui.WTaskText.text()
        _tasks = self.ui.WTasks.all_text()
        _LOGGER.debug('CALLBACK TASK TEXT %s', _task)

        self.ui.WTasks.blockSignals(True)
        if _task in _tasks:
            self.ui.WTasks.select_text(_task)
        else:
            self.ui.WTasks.clearSelection()
        self.ui.WTasks.blockSignals(False)

        self._redraw__WTags()

    def _callback__WTags(self):

        _tag = self.ui.WTags.selected_data()
        if not _tag and self.work_dir:
            _tag = self.job.cfg['tokens']['tag']['default']
        _text = _tag or ''
        _LOGGER.debug('CALLBACK TAGS tag=%s text=%s', _tag, _text)
        _blocked = self.ui.WTagText.signalsBlocked()
        self.ui.WTagText.blockSignals(True)
        self.ui.WTagText.setText(_text)
        self.ui.WTagText.blockSignals(_blocked)
        self.ui.WTagText.textChanged.emit(_text)

    def _callback__WTagText(self):

        _LOGGER.debug('CALLBACK TAG TEXT tag=%s', self.tag)

        # Update tags list (tags test is master)
        self.ui.WTags.blockSignals(True)
        if self.tag in self.ui.WTags.all_data():
            self.ui.WTags.select_data(self.tag)
        else:
            self.ui.WTags.clearSelection()
        self.ui.WTags.blockSignals(False)

        self.ui.WTagError.redraw()
        self.ui.WWorks.redraw()

    def _callback__WTagTextClear(self):
        self.ui.WTagText.setText('')

    def _callback__WWorks(self):

        self.flush_notes_stack()
        _work = self.ui.WWorks.selected_data()

        # Update work elements
        self.ui.WWorkPathCopy.setEnabled(bool(_work))
        self.ui.WWorkPathBrowser.setEnabled(bool(_work))

        # Update load button
        _loadable = bool(_work)
        _load_text = "Load" if _work is not self.next_work else "New Scene"
        self.ui.WLoad.setEnabled(_loadable)
        self.ui.WLoad.setText(_load_text)

        _saveable = bool(
            _work and _work.user in (None, get_user(), pipe.cur_user()))
        self.ui.WSave.setEnabled(_saveable)

        if _work:
            _notes = _work.notes or ''
        else:
            _notes = None
        self.ui.WWorkNotes.blockSignals(True)
        self.ui.WWorkNotes.setText(_notes)
        self.ui.WWorkNotes.blockSignals(False)

        self.ui.WWorkPath.redraw()

    def _callback__WWorksRefresh(self):
        _LOGGER.info('REFRESH WORKS')
        if not self.work_dir:
            _LOGGER.info('NO WORKDIR TO REFRESH')
            return
        _work = self.work
        self.work_dir.find_works(force=True)
        self.ui.WTagText.setText('')
        self.ui.WTags.redraw()
        if _work and _work.exists():
            self.jump_to(_work)

    def _callback__WWorksShowAll(self):
        self.ui.WWorks.redraw()

    def _callback__WWorkNotes(self):

        _work = self.ui.WWorks.selected_data()
        _notes = self.ui.WWorkNotes.text()
        if _work:
            self._notes_stack[_work] = _notes
        _item = self.ui.WWorks.selected_item()
        if _item:
            _item.set_notes(_notes)

    def _callback__WWorkPath(self):
        _work = self.ui.WWorkPath.selected_data()
        _LOGGER.debug('CALLBACK WORK PATH %s', _work)
        if not _work:
            return
        _LOGGER.debug(' - SELECT RECENT %s', _work)
        self.ui.WWorkPath.blockSignals(True)
        self.jump_to(_work.path)
        self.ui.WWorkPath.blockSignals(False)
        _LOGGER.debug(' - SELECT RECENT COMPLETE %s', _work)

    def _callback__WWorkPathBrowser(self):
        _work = self.ui.WWorks.selected_data()
        _work.to_dir().browser()

    def _callback__WWorkPathCopy(self):
        _work = self.ui.WWorks.selected_data()
        copy_text(_work.path)

    def _callback__WWorkRefresh(self):
        _LOGGER.debug('REFRESH WORK %s', self.work)
        if self.work is self.next_work:
            return
        self.work.find_outputs(force=True)
        self.ui.WWorks.redraw(select=self.work)

    @usage.get_tracker('PiniHelper.Load', write_after=True)
    def _callback__WLoad(self, force=False):
        _item = self.ui.WWorks.selected_item()

        if _item is self.show_all_works_item:
            self.ui.WWorksShowAll.setChecked(True)
            self.ui.WWorks.redraw()
            return

        _work = _item.data()
        _new = not _work.exists()
        _LOGGER.debug('LOAD %s', _work)
        _work.load(parent=self, force=force)
        if _new:
            self._callback__WWorksRefresh()

    @usage.get_tracker('PiniHelper.Save', write_after=True)
    def _callback__WSave(self, force=False):

        _work = self.ui.WWorks.selected_data()
        _new = not _work.exists()
        _notes = self.ui.WWorkNotes.text()
        _new_task = not self.work_dir.exists()

        # Execute save
        _LOGGER.debug('SAVE %s', _work)
        if not force:
            self._warn_on_switch_stream()
        _work = _work.save(notes=_notes, parent=self, force=force)

        # Update ui
        if _new_task:
            self.ui.WTasks.redraw()
            self.ui.WTasks.select_text(_work.task)
        if _work.tag not in self.ui.WTags.all_data():
            self.ui.WTags.redraw()
            self.ui.WTags.select_data(_work.tag)
        self.ui.WWorks.redraw()
        self.jump_to(_work.path)

    def _callback__WVersionUp(self):
        pipe.version_up()

    def _warn_on_switch_stream(self):
        """Pop up a warning dialog if we switch stream."""
        _LOGGER.debug('WARN ON SWITCH STREAM')
        _sel_work = self.ui.WWorks.selected_data()
        _cur_work = pipe.cur_work()
        _LOGGER.debug(' - SEL %s', _sel_work)
        _LOGGER.debug(' - CUR %s', _cur_work)

        if not _cur_work:
            return
        if (
                _cur_work.dir == _sel_work.dir and
                _cur_work.tag == _sel_work.tag):
            return

        _sel_label, _cur_label = [
            '{work.entity.label}/{work.task}{tag}'.format(
                work=_work,
                tag='/' + _work.tag if _work.tag else '')
            for _work in (_sel_work, _cur_work)]
        _msg = '\n'.join([
            'Are you sure you want to save in a different version stream?',
            '',
            'Current:',
            _cur_label,
            '',
            'Selected:',
            _sel_label,
        ])
        qt.ok_cancel(
            msg=_msg, title='Change stream', parent=self,
            icon=icons.find('Bug'))

    def flush_notes_stack(self):
        """Write notes changes to disk.

        This is triggered by the timer function (every 5s) so that
        the notes can be typed without constantly writing to disk
        which would cause lag in the ui.
        """
        if not self._notes_stack:
            return
        _items = list(self._notes_stack.items())  # For copy + py3
        for _work, _notes in _items:
            if _work is self.next_work:
                continue
            if _work.notes != _notes:
                _LOGGER.debug('UPDATE NOTES %s', _work)
                _work.set_notes(_notes)

            del self._notes_stack[_work]

    def _context__WWorks(self, menu):
        from pini.tools import helper

        _work = self.ui.WWorks.selected_data()
        menu.add_label(f'Work: {_work.filename}')
        menu.add_separator()
        menu.add_file_actions(
            _work, delete_callback=self._callback__WWorksRefresh)
        menu.add_separator()
        self._add_load_ctx_opts(menu=menu, work=_work)
        menu.add_separator()

        menu.add_action('Print metadata', icon=icons.PRINT,
                        func=wrap_fn(pprint.pprint, _work.metadata, width=200))
        menu.add_separator()

        # Add backups
        _bkps = _work.find_bkps()
        if not _bkps:
            menu.add_label('No backups found', icon=helper.BKPS_ICON)
        else:
            _bkps_menu = menu.add_menu('Backups', icon=helper.BKPS_ICON)
            for _bkp in _bkps:
                _t_stamp = strftime('%a %d %b %H:%M', _bkp.mtime())
                _label = f'{_t_stamp} - {_bkp.reason}'
                _rand = str_to_seed(_bkp.reason)
                _icon = icons.find(_rand.choice(icons.FRUIT_NAMES))
                _bkp_menu = _bkps_menu.add_menu(_label, icon=_icon)
                _bkp_menu.add_label(f'Backup: {_bkp.filename}')
                _bkp_menu.add_separator()
                _bkp_menu.add_file_actions(_bkp)

        # Add outputs
        _outs = _work.find_outputs()
        if not _outs:
            menu.add_label('No outputs found', icon=helper.OUTS_ICON)
        else:
            _outs_menu = menu.add_menu('Outputs', icon=helper.OUTS_ICON)
            _outs.sort(key=_menu_out_sort)
            for _out in _outs:
                self._add_out_menu(parent=_outs_menu, out=_out)

        menu.add_separator()

    def _load_latest_tag_version(self):
        """Load latest version of currently selected tag."""
        _latest = self.work.find_latest()
        self.jump_to(_latest)
        self._callback__WLoad()

    def _load_scene_version_up(self, work=None):
        """Load the current work and version up.

        Args:
            work (CPWork): work file to load/increment
        """
        _work = work or self.work
        _work.load()
        pipe.version_up()

    def _add_out_menu(self, parent, out, submenu=True):
        """Add menu items for the given output.

        Args:
            parent (QMenu): output parent menu
            out (CPOutput): output to add items for
            submenu (bool): use submenu (not needed if only one output)
        """
        _LOGGER.debug('ADD OUTPUT MENU %s', out)

        # Set label/header
        _icon = None
        _header = f'{out.type_.capitalize()}: {out.filename}'
        _label = f'{out.basic_type.capitalize()} - {out.filename}'
        if out.type_ in ('publish', 'publish_seq'):
            _label = to_nice(out.content_type).capitalize()
            _icon = ph_utils.output_to_type_icon(out)
        elif out.type_ == 'cache':
            _name = out.output_name or out.dcc_
            _label = f'Cache - {_name} ({out.extn})'
        elif isinstance(out, pipe.CPOutputSeq):
            _header += ' ' + ints_to_str(out.frames)
            _label += ' ' + ints_to_str(out.frames)

        # Set icon
        _icon = _icon or ph_utils.output_to_icon(out)
        if submenu:
            _out_menu = parent.add_menu(_label, icon=_icon)
        else:
            _out_menu = parent

        self._add_output_opts(
            menu=_out_menu, output=out, find_work=False, ignore_ui=True,
            parent=self.ui.WWorks, delete_callback=self._callback__WWorkRefresh)

    def _context__WWorkRefresh(self, menu):
        menu.add_action(
            'Reread all outputs', self._reread_all_outputs, icon=icons.REFRESH)

    def _reread_all_outputs(self):
        """Reread all work file outputs."""
        for _idx, _work in qt.progress_bar(
                enumerate(self.ui.WWorks.all_data()),
                'Reading {:d} work{}'):
            _work.find_outputs(force=True)
        self.ui.WWorks.redraw()

    def _context__WLoad(self, menu):
        self._add_load_ctx_opts(menu)

    def _add_load_ctx_opts(self, menu, work=None):
        """Add load scene context options to the given menu.

        Args:
            menu (CMenu): menu to add to
            work (CPWork): work file to add options for
        """
        _work = work or self.work
        menu.add_action(
            'Load scene + version up',
            wrap_fn(self._load_scene_version_up, _work),
            icon=icons.LOAD)


def _menu_out_sort(out):
    """Sort function for output context menu.

    Args:
        out (CPOutput): output to sort

    Returns:
        (tuple): sort key
    """
    _type = out.basic_type
    return _type != 'publish', _type, out.path
