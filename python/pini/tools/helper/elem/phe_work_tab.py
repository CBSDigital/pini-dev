"""Tools for manging the pini helper work tab."""

# pylint: disable=no-member

import getpass
import logging
import operator
import pprint
import time

from pini import qt, pipe, icons, dcc
from pini.tools import usage
from pini.utils import (
    strftime, copy_text, str_to_seed, plural, ints_to_str, EMPTY,
    wrap_fn, add_indent)

from ..ph_utils import output_to_icon, work_to_icon

_STAR = icons.find('Star')
_LOGGER = logging.getLogger(__name__)


class CLWorkTab(object):
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
        if not self.entity:
            return None

        # Existing task
        _work_dir = self.ui.WUser.selected_data()
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
        return self.ui.WWorks.selected_data()

    def _redraw__WTasks(self):

        # Read entity
        _LOGGER.debug('REDRAW TASKS %s (%s)', self.entity, dcc.NAME)
        _items = []
        _select = pipe.cur_task()
        if self.entity:

            # Read tasks
            _work_dirs = self.entity.find_work_dirs(dcc_=dcc.NAME)
            _tasks = sorted(
                {_work_dir.task for _work_dir in _work_dirs} |
                set(self.entity.to_default_tasks(dcc_=dcc.NAME)),
                key=pipe.task_sort)
            _LOGGER.debug(' - TASKS %s', _tasks)

            # Build task items
            for _task in _tasks:
                _task_work_dirs = [
                    _work_dir for _work_dir in _work_dirs
                    if _work_dir.task == _task]
                _task_has_works = [
                    _work_dir for _work_dir in _task_work_dirs
                    if _work_dir.has_works()]
                _col = 'Grey'
                if _task_has_works:
                    _col = None
                    if not _select:
                        _select = _task
                _LOGGER.debug(
                    '   - ADD TASK %s %s', _task, _task_work_dirs)
                _item = qt.CListWidgetItem(
                    _task, col=_col, data=_task_work_dirs)
                _items.append(_item)

        self.ui.WTasks.set_items(_items, select=_select)

    def _redraw__WUser(self):

        # Get list of items
        _work_dirs = self.ui.WTasks.selected_data() or []
        _users = sorted({
            _work_dir.user for _work_dir in _work_dirs
            if _work_dir.works or
            _work_dir.user == pipe.cur_user()})

        # Select user
        _select = pipe.cur_user()
        _cur_work = pipe.cur_work()
        if _cur_work:
            _select = _cur_work.user
        else:
            _with_work = [
                _work_dir for _work_dir in _work_dirs if _work_dir.works]
            if _with_work:
                _select = _with_work[0].user

        # Hide user elements if single user
        _show_users = len(_users) > 1
        for _elem in [
                self.ui.WUserLabel, self.ui.WUser,
                self.ui.WUserLine,
        ]:
            _elem.setVisible(_show_users)

        self.ui.WUser.set_items(_users, select=_select, data=_work_dirs)

    def _redraw__WTags(self):

        _default_tag = self.job.cfg['tokens']['tag']['default']
        _LOGGER.debug('REDRAW TAGS')

        _tags, _select = self._build_tags_list()
        _LOGGER.debug(' - TAGS %s select=%s', _tags, _select)

        # Build items
        _items = []
        for _tag in _tags:
            if not _tag:
                _col = 'Yellow'
            elif _tag == _default_tag:
                _col = 'DeepSkyBlue'
            else:
                _col = None
            _item = qt.CListWidgetItem(
                _tag or '<default>', data=_tag, col=_col)
            _items.append(_item)

        # Update widget
        _LOGGER.debug(' - items=%s', _items)
        self.ui.WTags.set_items(_items, emit=False)
        if _select is not EMPTY:
            _LOGGER.debug(' - select=%s', _select)
            self.ui.WTags.select_data(_select, emit=False)
        self.ui.WTags.itemSelectionChanged.emit()

    def _build_tags_list(self):
        """Build list of tags to display.

        Returns:
            (tuple): tags, selected tag
        """
        _user = self.ui.WUser.selected_text()
        _cur_work = pipe.cur_work()
        _cur_tag = _cur_work.tag if _cur_work else EMPTY
        _ui_tag = self.ui.WTagText.text()
        _default_tag = self.job.cfg['tokens']['tag']['default']

        _select = EMPTY
        if not self.work_dir:
            _tags = []

        else:

            # Build tag list - show all tags avaiable if current user,
            # otherwise just show existing tags
            if _user in (None, pipe.cur_user()):
                _work_dirs = self.ui.WTasks.selected_data()
                _works = sum([
                    list(_work_dir.works) for _work_dir in _work_dirs], [])
            else:
                _works = self.work_dir.works
            _tags = {_work.tag for _work in _works}
            _tags |= {_default_tag}
            _allow_no_tag = self.job.find_template(
                'work', has_key={'tag': False}, catch=True)
            if _allow_no_tag:
                _tags |= {None}
            _tags = sorted(_tags, key=pipe.tag_sort)

            # Determine selected tag
            if _cur_tag in _tags:
                _select = _cur_tag
            elif _ui_tag in _tags:
                _select = _ui_tag
            elif None in _tags:
                _select = None
            elif _tags:
                _select = sorted(_tags)[0]

        return _tags, _select

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

    def _redraw__WWorks(self, force=False, emit=True, select=None):

        _LOGGER.debug('REDRAW WORKS')

        _items, _works = self._build_work_items(force=force)

        # Choose selected work item
        _select_work = select or pipe.cur_work()
        _LOGGER.debug(' - SEL WORK %s', _select_work)
        if _select_work and _select_work in _works:
            _sel = _items[_works.index(_select_work)]
        elif not _items:
            _sel = None
        elif len(_items) == 1 or not self.next_work:
            _sel = _items[0]
        else:
            _sel = _items[1]
        _LOGGER.debug(' - SEL %s', _sel)

        self.ui.WWorks.set_items(_items, select=_sel, emit=emit)
        self._update_badly_named_files_elements()

    def _update_badly_named_files_elements(self):
        """Update elements which warning if badly named files found."""

        # Check for badly named files
        _n_bad_files = (self.work_dir.badly_named_files if self.work_dir
                        else 0)

        # Update element visibility
        for _elem in [self.ui.WWorkBadFilesIconR,
                      self.ui.WWorkBadFilesIconL,
                      self.ui.WWorkBadFilesLabel]:
            _elem.setVisible(bool(_n_bad_files))

        # Update label text
        _text = (
            'Warning - there {} {:d} badly named file{} in this\n'
            'directory which {} not shown in the versions list'.format(
                plural(_n_bad_files, singular='is', plural_='are'),
                _n_bad_files,
                plural(_n_bad_files),
                plural(_n_bad_files, singular='is', plural_='are')))
        self.ui.WWorkBadFilesLabel.setText(_text)
        self.ui.WWorkBadFilesLabel.set_col('Red')

    def _build_work_items(self, force, view_limit=20):
        """Build items for works list.

        Args:
            force (bool): force reread from disk
            view_limit (int): how many works to display in limited view

        Returns:
            (tuple): list wdiget items, work list
        """
        _LOGGER.debug('BUILD WORK ITEMS tag=%s', self.tag)
        _show_all = self.ui.WWorksShowAll.isChecked()
        _user = self.ui.WUser.selected_text()

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
        if self.work_dir and _user in ['', pipe.cur_user()]:
            if not _works:
                _work = self.work_dir.to_work(tag=self.tag)
            else:
                _work = _works[0]
            self.next_work = _work.find_next()
        else:
            self.next_work = None
        if self.next_work:
            self.next_work.set_exists(False)
            assert not self.next_work.exists()
            _works.append(self.next_work)
        _works.reverse()

        # Build items
        _items = []
        _LOGGER.debug(" - WORKS %d %s", len(_works), _works)
        for _work in _works:
            _LOGGER.debug(' - BUILD WORK ITEM %s', _work)
            if _work is self.next_work:
                _icon = icons.find('Hatching')
                _col = 'Chartreuse'
            else:
                _icon = work_to_icon(_work)
                _col = 'White' if _work.find_outputs() else None
            _text = self._get_work_text(_work)
            _item = qt.CListWidgetItem(_text, data=_work, icon=_icon, col=_col)
            _items.append(_item)

        # Add show all
        if _limit_view:
            _star = qt.CPixmap(_STAR).resize(24, 24)
            self.show_all_works_item = qt.CListWidgetItem(
                'double-click to show all work items', icon=_star)
            _items.append(self.show_all_works_item)

        return _items, _works

    def _get_work_text(self, work):
        """Build work text label.

        Args:
            work (CPWork): work file to read

        Returns:
            (str): work text label
        """
        _t_fmt = '%a %b %d %H:%M'

        if work is self.next_work:
            _suffix = ''
            _notes = 'this version will be created if you load/save'
            _mtime = time.time()
            _owner = getpass.getuser()
        else:
            _suffix = '\n - Size: {}'.format(work.nice_size(catch=True))
            _mtime = work.mtime()
            _notes = work.notes or '-'
            _owner = work.user or work.metadata.get('owner')

        # Update notes
        if work in self._notes_stack:
            _notes = self._notes_stack[work]
        _notes = _notes.replace(u'\\n', u'\n')  # Allow newlines hack
        _notes = _notes.strip()
        if u'\n' in _notes:
            _notes = '\n'+add_indent(_notes, indent=' '*6)

        _text = '\n'.join([
            'V{:03d} - {}'.format(work.ver_n, strftime(_t_fmt, _mtime)),
            ' - Notes: '+_notes,
            ' - Owner: {}{}'.format(_owner, _suffix)])

        # Mark outputs
        _o_tags = self._get_work_output_tags(work)
        if _o_tags:
            _text += '\n - '+'/'.join(_o_tags)

        return _text

    def _get_work_output_tags(self, work):
        """Find output tags for the given work file.

        eg. ['Blasted', 'Rendered']

        Args:
            work (CCPWork): work file to read outputs from

        Returns:
            (str list): output tags
        """
        _outs = [] if work is self.next_work else work.find_outputs()

        _o_tags = set()
        for _out in _outs:
            _LOGGER.debug(' - CHECKING OUT %s', _out)
            if (
                    'blast' in _out.type_ or
                    (_out.output_name and 'blast' in _out.output_name)):
                _o_tag = 'Blasted'
            elif _out.type_ == 'publish':
                _o_tag = 'Published'
            elif (
                    _out.extn == 'abc' or
                    _out.type_ in ('cache', 'cache_seq', 'ass_gz')):
                _o_tag = 'Cached'
            elif (
                    _out.type_ in ('render', 'render_mov', 'mov') or
                    _out.output_name == 'render'):
                _o_tag = 'Rendered'
            else:
                _LOGGER.debug('   - FAILED TO CLASSIFY %s', _out.type_)
                _o_tag = 'Outputs'
            _o_tags.add(_o_tag)
        if _outs and not _o_tags:
            _o_tags.add('Outputs')

        if work is not self.next_work and work.metadata.get('submitted'):
            _o_tags.add('Submitted')

        return sorted(_o_tags)

    def _redraw__WWorkPath(self):

        _blocked = self.ui.WWorkPath.signalsBlocked()
        _LOGGER.debug('REDRAW WORK PATH blocked=%d', _blocked)

        # Build list of recent works
        _data = []
        _items = []
        for _work in pipe.CACHE.recent_work():
            _ety = _work.shot or (_work.asset_type+'/'+_work.asset)
            _uid = '{}/{}/{}'.format(_work.job.name, _ety, _work.task)
            if _work.tag:
                _uid += '/'+_work.tag
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

        self._redraw__WUser()

    def _callback__WUser(self):
        self._redraw__WTags()
        _user = self.ui.WUser.selected_text()
        _show_tag_text = _user in ('', pipe.cur_user())
        for _elem in [self.ui.WTagText, self.ui.WTagTextClear]:
            _elem.setVisible(_show_tag_text)

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

        self._flush_notes_stack()
        _work = self.ui.WWorks.selected_data()
        _user = self.ui.WUser.selected_text()

        # Update work elements
        self.ui.WWorkPathCopy.setEnabled(bool(_work))
        self.ui.WWorkPathBrowser.setEnabled(bool(_work))

        _loadable = bool(_work and _work is not self.next_work)
        self.ui.WLoad.setEnabled(_loadable)
        _saveable = bool(_work and _user in ('', pipe.cur_user()))
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
        _item = self.ui.WWorks.selected_item()
        if _work:
            self._notes_stack[_work] = _notes
        if _item:
            _item.setText(self._get_work_text(_work))

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
        _work = _work.save(notes=_notes, parent=self)

        # Update ui
        if _new_task:
            self.ui.WTasks.redraw()
            self.ui.WTasks.select_text(_work.task)
        if _work.tag not in self.ui.WTags.all_data():
            self.ui.WTags.redraw()
            self.ui.WTags.select_data(_work.tag)
        self.ui.WWorks.redraw()
        self.jump_to(_work.path)

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
                tag='/'+_work.tag if _work.tag else '')
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
            msg=_msg, title='Change Stream', parent=self,
            icon=icons.find('Bug'))

    def _flush_notes_stack(self):
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
        menu.add_label('Work: {}'.format(_work.filename))
        menu.add_separator()
        menu.add_file_actions(
            _work, delete_callback=self._callback__WWorksRefresh)
        menu.add_separator()
        self._add_load_ctx_opts(menu=menu, work=_work)
        menu.add_separator()

        menu.add_action('Print metadata', icon=icons.PRINT,
                        func=wrap_fn(pprint.pprint, _work.metadata))
        menu.add_separator()

        # Add backups
        _bkps = _work.find_bkps()
        if not _bkps:
            menu.add_label('No backups found', icon=helper.BKPS_ICON)
        else:
            _bkps_menu = menu.add_menu('Backups', icon=helper.BKPS_ICON)
            for _bkp in _bkps:
                _label = '{} - {}'.format(
                    strftime('%a %d %b %H:%M', _bkp.mtime()), _bkp.reason)
                _rand = str_to_seed(_bkp.reason)
                _icon = icons.find(_rand.choice(icons.FRUIT_NAMES))
                _bkp_menu = _bkps_menu.add_menu(_label, icon=_icon)
                _bkp_menu.add_label('Backup: {}'.format(_bkp.filename))
                _bkp_menu.add_separator()
                _bkp_menu.add_file_actions(_bkp)

        # Add outputs
        _outs = _work.find_outputs()
        if not _outs:
            menu.add_label('No outputs found', icon=helper.OUTS_ICON)
        else:
            _outs_menu = menu.add_menu('Outputs', icon=helper.OUTS_ICON)
            _outs.sort(key=operator.attrgetter('type_'))
            for _out in _outs:
                self._add_out_menu(parent=_outs_menu, out=_out)

        menu.add_separator()

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
        _header = '{}: {}'.format(
            out.type_.capitalize(), out.filename)
        _label = '{} - {}'.format(out.type_, out.filename)
        if out.type_ == 'publish':
            _label = 'publish'
        elif out.type_ == 'cache':
            _label = 'cache - {} ({})'.format(out.output_name, out.extn)
        elif isinstance(out, pipe.CPOutputSeq):
            _header += ' '+ints_to_str(out.frames)
            _label += ' '+ints_to_str(out.frames)

        # Set icon
        _icon = output_to_icon(out)
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
