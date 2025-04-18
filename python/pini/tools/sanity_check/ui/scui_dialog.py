"""Tools for managing the sanity check dialog class."""

import logging

from pini import qt, dcc, icons, pipe
from pini.tools import error
from pini.utils import File, plural, single

from . import scui_fail, scui_check

_LOGGER = logging.getLogger(__name__)
_DIR = File(__file__).to_dir()
ICON = icons.find("Health Worker: Medium-Dark Skin Tone")
UI_FILE = _DIR.to_file('sanity_check.ui')


class SanityCheckUi(qt.CUiDialog):
    """Interface for sanity check."""

    results = None
    error_ui = None

    def __init__(
            self, mode='standalone', checks=None, run=True,
            close_on_success=None, filter_=None, task=None, action=None,
            modal=None, parent=None, force=False):
        """Constructor.

        Args:
            mode (str): run in standalone or export mode
            checks (SCCheck list): override checks
            run (bool): automatically run checks on launch
            close_on_success (bool): close dialog on all checks passed
            filter_ (str): apply filter based on check name
            task (str): task to apply checks filter to
            action (str): export action (eg. publish/render)
            modal (bool): override default modal state
            parent (QDialog): parent dialog
            force (bool): in export mode force export ignoring any issues
        """
        from pini.tools import sanity_check
        sanity_check.DIALOG = self

        self.mode = mode
        self.task = task or pipe.cur_task(fmt='pini')
        self.action = action
        self.close_on_success = close_on_success
        if self.close_on_success is None:
            self.close_on_success = mode != 'standalone'
        self.checks = checks or sanity_check.find_checks(
            filter_=filter_, task=self.task, action=action)

        super().__init__(ui_file=UI_FILE, show=False, parent=parent)

        # Embed error catcher
        self.error_ui = error.launch_ui(
            parent=self.ui.ErrorTab, show=False, stack_key='SanityCheckError')
        self.ui.ErrorTab.setLayout(self.error_ui.ui.MainLyt)
        self.error_ui.close()

        self.ui.Checks.redraw()
        self.ui.TaskLabel.redraw()

        # Apply modal
        _modal = modal
        if _modal is None:
            _modal = self.mode != 'standalone'
        self.setModal(_modal)

        self.show()
        self.load_settings()

        if run:
            self._callback__RunChecks(force=force)

        if _modal and self.isVisible():
            _LOGGER.debug(' - EXEC MODAL force=%d', force)
            self.exec_()

    def init_ui(self):
        """Initiate ui elements."""

        _title = 'SanityCheck'
        if self.mode != 'standalone':
            _title = 'Export SanityCheck'
        self .setWindowTitle(_title)

        for _elem in [
                self.ui.Continue,
                self.ui.CancelAndKeep,
                self.ui.CancelAndClose,
                self.ui.PublishSeparator,
        ]:
            _elem.setVisible(self.mode != 'standalone')

    @property
    def check(self):
        """Obtain currently selected check (if any).

        Returns:
            (SCCheck): selected check
        """
        _check_ui = self.ui.Checks.selected_item()
        if not _check_ui:
            return None
        return _check_ui.check

    def reset_checks(self):
        """Reset all checks."""
        for _check in self.checks:
            _check.reset()
        self.ui.Checks.redraw()

    def _update_ui(self, check=None):
        """Update the ui.

        This method is passed to checks to allow them to provide progress
        feedback as they are being executed.

        Args:
            check (SCCheck): force check to update
        """
        _LOGGER.log(9, 'UPDATE UI')
        dcc.refresh()

        if check:
            _check_ui = single([
                _item for _item in self.ui.Checks.all_items()
                if _item.data() == check], catch=True)
        else:
            _check_ui = self.ui.Checks.selected_item()
        _LOGGER.log(9, ' - CHECK TO UPDATE %s', _check_ui)

        if _check_ui:
            _check_ui.redraw()

        self.ui.Log.redraw()
        dcc.refresh()

    def _build_results(self):
        """Build results dict.

        Returns:
            (dict): results
        """
        _results = {}
        for _check in self.checks:
            _results[_check.name] = _check.status
        return _results

    def _check_for_success(self, force=False):
        """Check whether all checks have completed and close (if applicable).

        Args:
            force (bool): force continue with export ignoring any issues
        """
        _LOGGER.debug('CHECK FOR SUCCESS')

        # Check whether there are failed checks
        _checks = self.ui.Checks.all_items()
        _errored = [_check for _check in _checks if _check.status == 'errored']
        _failed = [_check for _check in _checks if _check.status == 'failed']
        _success = not _errored and not _failed
        _LOGGER.debug(
            ' - READ CHECKS close_on_success=%d success=%d errored=%d '
            'failed=%d', bool(self.close_on_success), _success,
            len(_errored), len(_failed))
        if force or (self.close_on_success and _success):
            _LOGGER.debug(' - CLOSING DUE TO SUCCESS')
            self.results = self._build_results()
            self.close()

        # Update export button labels
        if self.action:
            _msg = 'ignore '
            if _failed:
                _msg += f'{len(_failed):d} fail{plural(_failed)} '
            if _errored:
                if _failed:
                    _msg += 'and '
                _msg += f'{len(_errored):d} error{plural(_errored)} '
            _msg = _msg.strip()
            for _fmt, _elem in [
                    ('{action_label} ({msg})', self.ui.Continue),
                    (
                        'Cancel {action_label} and keep SanityCheck',
                        self.ui.CancelAndKeep),
                    ('Cancel {action_label}', self.ui.CancelAndClose),
            ]:
                if self.action.endswith('Publish'):
                    _action_label = 'Publish'
                else:
                    _action_label = self.action
                _label = _fmt.format(
                    action_label=_action_label, action=self.action,
                    count=len(_checks), plural=plural(_checks), msg=_msg)
                _elem.setText(_label)

        _LOGGER.debug(" - CHECK FOR SUCCESS COMPLETE %s", self.check)

    def _redraw__ErrorTab(self):
        if self.check and self.check.error:
            _LOGGER.debug(
                ' - APPLYING ERROR %s %s', self.check, self.check.error)
            self.error_ui.set_error(self.check.error)

    def _redraw__Checks(self, autorun=False):

        _LOGGER.debug('REDRAW Checks')

        _items = []
        _show_passed = self.ui.ShowPassed.isChecked()
        _show_disabled = self.ui.ShowDisabled.isChecked()

        _could_autorun = False
        _sel = None
        for _check in self.checks:

            # Apply filters
            if not _show_disabled and _check.is_disabled:
                continue
            if not _show_passed and _check.has_passed:
                continue

            _item = scui_check.SCUiCheckItem(
                list_view=self.ui.Checks, check=_check)
            _items.append(_item)

            if not _sel:
                if not _check.has_run:
                    _sel = _item
                    _could_autorun = True
                elif _check.has_failed:
                    _sel = _item

        self.ui.Checks.set_items(_items, select=_sel, emit=True)

        if autorun and _could_autorun:
            _LOGGER.debug(' - APPLYING AUTORUN %s %s', _sel, self.check)
            self._callback__RunCheck()

        _LOGGER.debug(' - REDRAW Checks COMPLETE')

    def _redraw__ToggleDisabled(self):
        if self.check:
            _en = True
            _text = 'Enable' if self.check.is_disabled else 'Disable'
        else:
            _en = False
            _text = 'Disable'
        self.ui.ToggleDisabled.setText(_text)
        self.ui.ToggleDisabled.setEnabled(_en)

    def _redraw__Log(self):
        self.ui.Log.setText(self.check.log if self.check else '')

    def _redraw__Fails(self):

        _items = []
        _fixes = 0
        _fails = self.check.fails if self.check else []
        for _fail in _fails:
            _item = scui_fail.SCUiFailItem(
                list_view=self.ui.Fails, fail=_fail,
                run_check=self._callback__RunCheck)
            _items.append(_item)
            if _fail.fix:
                _fixes += 1
        self.ui.Fails.set_items(_items)
        self.ui.FixAll.setEnabled(bool(_fixes))
        self.ui.FailInfo.setText(
            f'Found {len(_fails):d} fail{plural(_fails)} with '
            f'{_fixes:d} fix{plural(_fixes, plural_="es")}')

    def _redraw__TaskLabel(self):
        _label = 'NONE'
        if self.task:
            _label = pipe.map_task(self.task).upper()
        self.ui.TaskLabel.setText(' Task: ' + _label)

    def _callback__ShowPassed(self):
        self.ui.Checks.redraw()

    def _callback__ShowDisabled(self):
        self.ui.Checks.redraw()

    def _callback__ToggleDisabled(self):
        self.check.set_disabled(not self.check.is_disabled)
        self.ui.Checks.selected_item().redraw()
        if self.check.is_enabled:
            self._callback__RunCheck()
        elif not self.ui.ShowDisabled.isChecked():
            self.ui.Checks.redraw()
        else:
            self._callback__Checks()
        self._check_for_success()

    def _callback__Checks(self):

        _tab = 'Log'
        _error = _fails = False
        if self.check:
            _msg = f'Selected check: {self.check.label}'
            if self.check.status == 'failed':
                _tab = 'Fails'
                _fails = True
            elif self.check.status == 'errored':
                _tab = 'Error'
                _error = True

        self.ui.ToggleDisabled.redraw()

        self.ui.ResultsPane.set_tab_enabled('Error', _error)
        self.ui.ResultsPane.set_tab_enabled('Fails', _fails)
        self.ui.ResultsPane.select_tab(_tab, emit=True)

    def _callback__ResultsPane(self):
        _tab = self.ui.ResultsPane.current_tab_text()
        if _tab == 'Error':
            self.ui.ErrorTab.redraw()
        elif _tab == 'Fails':
            self.ui.Fails.redraw()
        elif _tab == 'Log':
            self.ui.Log.redraw()
        else:
            raise ValueError(_tab)

    def _callback__RunChecks(self, force=False):

        _LOGGER.debug('RUN CHECKS')

        self.reset_checks()

        _show_passed = self.ui.ShowPassed.isChecked()
        _sel = None

        for _item in self.ui.Checks.all_items():

            self.ui.Checks.select_item(_item)
            dcc.refresh()

            _item.execute_check(update_ui=self._update_ui, checks=self.checks)

            if not _show_passed and _item.check.has_passed:
                self.ui.Checks.remove_item(_item)
            if not _sel and _item.check.has_failed:
                _sel = _item

        if _sel:
            self.ui.Checks.select_item(_sel)

        self._callback__Checks()
        self._check_for_success(force=force)

    def _callback__RunCheck(self):

        # Run selected check
        _check_ui = self.ui.Checks.selected_item()
        if _check_ui:
            _check_ui.execute_check(
                update_ui=self._update_ui, checks=self.checks)
        self._callback__Checks()

        # Update checks in case this check passed
        if (
                self.check and
                not self.check.fails and
                not self.ui.ShowPassed.isChecked()):
            self.ui.Checks.redraw(autorun=True)

        self._check_for_success()

    def _callback__FixAll(self):
        _fail_uis = [_fail_ui for _fail_ui in self.ui.Fails.all_items()
                     if _fail_ui.fail.fix]
        for _fail_ui in qt.progress_bar(
                _fail_uis, 'Running {:d} fix{}', plural_='es', parent=self,
                show=len(_fail_uis) > 1):
            _fail_ui.fail.fix()
            self.ui.Fails.remove_item(_fail_ui)
        self._callback__RunCheck()

    def _callback__Continue(self):
        self.results = self._build_results()
        self.delete()

    def _callback__CancelAndKeep(self):
        self.close()
        self.setModal(False)
        self.mode = 'standalone'
        self.init_ui()
        self.show()

    def _callback__CancelAndClose(self):
        self.delete()

    def _context__Checks(self, menu):
        _check = self.ui.Checks.selected_data()
        if _check:
            menu.add_action(
                'Edit check code', _check.edit, icon=icons.EDIT)
