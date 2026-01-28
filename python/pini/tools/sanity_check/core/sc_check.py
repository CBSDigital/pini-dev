"""Tools for managing the base sanity check class."""

# pylint: disable=too-many-public-methods

import inspect
import logging
import time

from pini import dcc, pipe
from pini.tools import error
from pini.utils import to_nice, strftime, nice_age, check_heart, PyFile

from . import sc_fail

_LOGGER = logging.getLogger(__name__)


class SCCheck:
    """Base class for all sanity checks."""

    _label = None
    _update_ui = None

    log = ''
    status = 'ready'
    error = None
    progress = 0.0
    sort = 50

    # Filters
    enabled = True
    dcc_filter = None
    profile_filter = None  # eg. asset/shot
    task_filter = None  # eg. model/rig
    action_filter = None  # eg. render/cache

    depends_on = ()

    def __init__(self):
        """Constructor."""
        self._log_writes = 0
        self._log_flagged_lazy = False
        self.disable_key = f'Pini.SanityCheck.{type(self).__name__}.Disable'
        self.reset()

    @property
    def has_errored(self):
        """Test whether this check has errored.

        Returns:
            (bool): whether errored
        """
        return bool(self.error)

    @property
    def has_failed(self):
        """Test whether this check has failed.

        Returns:
            (bool): whether failed
        """
        return self.has_run and bool(self.fails)

    @property
    def has_passed(self):
        """Test whether this check has passed.

        Returns:
            (bool): whether passed
        """
        return self.status == 'passed'

    @property
    def has_run(self):
        """Test whether this check has run.

        Returns:
            (bool): whether run
        """
        return self.status != 'ready'

    @property
    def is_disabled(self):
        """Test whether this check has been disabled.

        Returns:
            (bool): whether disabled
        """
        return dcc.get_scene_data(self.disable_key)

    @property
    def is_enabled(self):
        """Test whether this check is enabled.

        Returns:
            (bool): whether enabled
        """
        return not self.is_disabled

    @property
    def label(self):
        """Obtain label for this sanity check.

        If none is set then the label is determined from the name of the check.

        Returns:
            (str): label (eg. Check UVs)
        """
        return self._label or to_nice(self.name).capitalize()

    @property
    def name(self):
        """Obtain name of this sanity check.

        Returns:
            (str): name (eg. CheckUVs)
        """
        return type(self).__name__

    @property
    def settings(self):
        """Obtain settings for this check.

        Returns:
            (dict): check settings
        """
        return self._read_settings()

    @property
    def sort_key(self):
        """Obtain sort key for this check.

        This is a tuple of its sort value and its name.

        Returns:
            (tuple): sort key
        """
        return self.sort, self.name

    def add_fail(self, fail, node=None, fix=None):
        """Add a fail for this check.

        This represents a part of the check having failed, and provides
        information about the failure and how to fix it.

        Args:
            fail (str|SCFail): failure
            node (any): node associated with failure
            fix (fn): function to fix issue

        Returns:
            (SCFail): fail
        """
        if isinstance(fail, str):
            _fail = sc_fail.SCFail(msg=fail, node=node, fix=fix)
        elif isinstance(fail, sc_fail.SCFail):
            _fail = fail
        else:
            raise ValueError(fail)

        self.write_log(
            ' - Adding fail %s node=%s', _fail.msg,
            dcc.to_node_name(node) if node else '-')
        self.fails.append(_fail)

        return _fail

    def edit(self):
        """Edit this check's code."""
        _name = type(self).__name__
        _LOGGER.info('EDIT %s %s', self, _name)
        _path = inspect.getfile(self.run)
        _LOGGER.info(' - PATH %s', _path)
        _check = PyFile(_path).find_class(_name)
        _check.edit()

    def execute(self, catch=True, update_ui=None):
        """Execute this check.

        Args:
            catch (bool): don't error if the check fails
            update_ui (fn): function to update a ui to give
                progress feedback
        """
        _LOGGER.debug('EXECUTE %s update_ui=%s', self, update_ui)
        _start = time.time()

        # Init vars
        self.reset()
        if self.is_disabled:
            self.write_log('Disabled')
            return
        self.status = 'running'
        self._update_ui = update_ui

        # Run the actual check
        self.write_log('Starting check')
        if not catch:
            self.run()
        else:
            try:
                self.run()
            except Exception as _exc:  # pylint: disable=broad-except
                _LOGGER.info(' - ERRORED %s', _exc)
                self.write_log('Errored - %s', str(_exc).strip())
                self.status = 'errored'
                self.error = error.PEError()
                error.TRIGGERED = True
        if not self.error:
            self.status = 'failed' if self.fails else 'passed'

        # Mark completed
        _dur = time.time() - _start
        self.write_log(
            'Completed check - status=%s dur=%s', self.status, nice_age(_dur))
        self.set_progress(100.0)

    def update_progress(self, data):
        """Build a generator to iterate the given data.

        As the generator is iterated, the progress is updated in any ui
        which has been embedded in this check.

        Args:
            data (list): data to iterate

        Returns:
            (generator): generator to iterate
        """
        return _ProgressUpdater(data, check=self)

    def _read_settings(self):
        """Read settings for this check.

        Returns:
            (dict): settings
        """
        _ety_settings = pipe.cur_entity().settings or {}
        return _ety_settings.get('sanity_check').get(self.name, {})

    def reset(self):
        """Reset this check."""
        self.fails = []

        self.error = None
        self.status = 'ready'
        if self.is_disabled:
            self.status = 'disabled'

        self._update_ui = None
        self.log = ''
        self.set_progress(0)

    def reset_and_run(self, **kwargs):
        """Reset this test and then run it."""
        self.reset()
        self.run(**kwargs)

    def run(self):
        """Run this check.

        To be implemented in subclass.
        """
        raise NotImplementedError

    def run_and_fix(self):
        """Run this check and apply any fixes."""
        _LOGGER.info('RUN AND FIX %s', self)
        self.run()

        _iter = 0
        while self.fails:
            check_heart()
            _LOGGER.info('[%d] FOUND %d FAILS', _iter, len(self.fails))

            # Apply fixes
            for _fail in self.fails:
                _LOGGER.info(' - FIXING FAIL %s', _fail)
                _fail.fix()

            self.execute()

            _iter += 1

            if _iter > 10:
                raise RuntimeError

        _LOGGER.info('RUN AND FIX COMPLETE - %d FAILS', len(self.fails))

    def set_disabled(self, disabled=True):
        """Set the disabled state of this check (default is disabled).

        This applies scene data to mark this check as disabled.

        Args:
            disabled (bool): disabled state to apply
        """
        _LOGGER.info(
            'SET CHECK %s %s', self, 'DISABLED' if disabled else 'ENABLED')
        dcc.set_scene_data(self.disable_key, disabled)
        self.reset()

    def set_progress(self, progress):
        """Set current progress of this check.

        If there is a ui embedded in this check, it is updated with the
        new progress value.

        Args:
            progress (float): progress percentage (in range 0 to 100)
        """
        check_heart()
        self.progress = progress
        assert 0.0 <= progress <= 100.0
        if self._update_ui:
            self._update_ui(lazy=True)

    def write_log(self, text, *args, lazy=False):
        """Write log information for this check.

        This information is used to provide information about the check
        progress to the user. It behaves like a Logger object, and arg data
        is passed into the log text using modulo formatting.

        Args:
            text (str): text to log
            lazy (bool): stop writing this log if log has already been
                written to 100 times
        """

        # Handle lazy logging - limited to avoid slowdown
        self._log_writes += 1
        if lazy and self._log_writes > 100:
            if not self._log_flagged_lazy:
                self.write_log(
                    'logging entered lazy mode - not logging low-priority '
                    'information')
            self._log_flagged_lazy = True
            return

        # Write the log
        _text = text
        if args:
            _text = text % args
        _t_stamp = strftime('[%H:%M:%S]')
        self.log += f'{_t_stamp} {_text}\n'

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.sort_key < other.sort_key

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        return f'<SCCheck:{_type}>'


class SCPipeCheck(SCCheck):
    """Base class for any check which requires reading the pipeline."""

    def check_cache_up_to_date(self):
        """Check this cache is not more than 20 minutes old.

        Returns:
            (bool): whether cache is outdated
        """
        _max_age = 20
        _age = time.time() - pipe.CACHE.ctime
        self.write_log('Found cache %s age=%s', pipe.CACHE, nice_age(_age))
        if _age > _max_age * 60:
            self.add_fail(
                f'Cache is more than {_max_age:d} minutes old',
                fix=pipe.CACHE.reset)
            return False
        return True

    def run(self):
        """Run this check.

        To be implemented in subclass.
        """
        raise NotImplementedError


class _ProgressUpdater:
    """Iterator for updating check progress."""

    def __init__(self, items, check):
        """Constructor.

        Args:
            items (list): items to iterate
            check (SCCheck): check to update progress on
        """
        self.items = items
        self.check = check
        self.counter = 0

    def __iter__(self):
        return self

    def __len__(self):
        return len(self.items)

    def __next__(self):

        check_heart()

        # Apply progress
        if len(self.items) <= 1:
            _pc = 100
        else:
            _pc = min(100.0, 100.0 * self.counter / (len(self.items) - 1))
        self.check.set_progress(_pc)

        # Increment iteration
        try:
            _result = self.items[self.counter]
        except IndexError as _exc:
            raise StopIteration from _exc
        self.counter += 1
        return _result

    next = __next__
