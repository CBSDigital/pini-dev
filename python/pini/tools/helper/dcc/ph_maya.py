"""Tools for managing the (dockable) pini helper in maya."""

import logging
import platform
import time

from pini import icons, qt, pipe, farm
from pini.tools import usage
from pini.utils import wrap_fn, MaFile

from maya_pini import m_pipe
from maya_pini.utils import load_scene

from .. import ph_base

_LOGGER = logging.getLogger(__name__)


class MayaPiniHelper(qt.CUiDockableMixin, ph_base.BasePiniHelper):
    """Pini Helper in maya which docks to the main ui."""

    def __init__(self, admin=None, load_settings=True, jump_to=None,
                 parent=None, show=True, reset_cache=True):
        """Constructor.

        Args:
            admin (bool): launch in admin mode
            load_settings (bool): load settings on launch
            jump_to (str): path to point helper to on launch
            parent (QDialog): override parent dialog
            show (bool): show on launch
            reset_cache (bool): reset pipeline cache on launch
        """
        from pini.tools import helper
        helper.MIXIN = self

        _LOGGER.debug('LAUNCH')

        # Set title - linux can't handle unicode emojis
        if platform.system() == 'Linux':
            _title = ph_base.TITLE
        else:
            _title = ph_base.EMOJI.to_unicode()+' '+ph_base.TITLE
        super(MayaPiniHelper, self).__init__(
            show=False, ui_file=ph_base.UI_FILE, load_settings=False,
            parent=parent, title=_title)

        ph_base.BasePiniHelper.__init__(
            self, admin=admin, load_settings=load_settings, show=False,
            jump_to=jump_to, reset_cache=reset_cache)

        self.show(dockable=True)
        self.apply_docking()
        _LOGGER.debug(' - LAUNCH COMPLETE')

    def init_ui(self):
        """Setup ui elements."""
        ph_base.BasePiniHelper.init_ui(self)

        # Apply farm option if available
        _locs = ['Local']
        if farm.IS_AVAILABLE:
            _locs.append('Farm')
        self.ui.ECacheLocation.set_items(_locs)

    def _redraw__ECacheRefs(self):

        _cacheables = m_pipe.find_cacheables()
        _cacheables.sort(key=_sort_cacheables)

        _items = []
        for _cacheable in _cacheables:
            _icon = _cacheable.to_icon()
            _item = qt.CListWidgetItem(
                _cacheable.label, data=_cacheable, icon=_icon)
            _items.append(_item)
        self.ui.ECacheRefs.set_items(_items, emit=False)
        self.ui.ECacheRefs.selectAll()
        self._callback__ECacheRefs()

    @usage.get_tracker('PiniHelper.Cache')
    def _callback__ECache(self, force=False, save=True):

        _LOGGER.info('CACHE')

        _cacheables = self.ui.ECacheRefs.selected_datas()
        _farm = self.ui.ECacheLocation.currentText() == 'Farm'
        _format = self.ui.ECacheFormat.currentText()
        _renderable_only = self.ui.ECacheRenderableOnly.isChecked()
        _rng = self.ui.ECacheStart.value(), self.ui.ECacheEnd.value()
        _step = self.ui.ECacheStep.value()
        _uv_write = self.ui.ECacheUvWrite.isChecked()
        _world_space = self.ui.ECacheWorldSpace.isChecked()
        _version_up = self.ui.ECacheVersionUp.isChecked()
        _snapshot = self.ui.ECacheSnapshot.isChecked()
        _LOGGER.info(' - CACHEABLES %s', _cacheables)

        m_pipe.cache(
            _cacheables, format_=_format, world_space=_world_space,
            uv_write=_uv_write, range_=_rng, force=force, save=save,
            step=_step, renderable_only=_renderable_only, use_farm=_farm,
            version_up=_version_up, snapshot=_snapshot)
        self.entity.find_outputs(force=True)

    def _add_load_ctx_opts(self, menu, work=None):
        """Add load scene context options to the given menu.

        Args:
            menu (CMenu): menu to add to
            work (CPWork): work file to add options for
        """
        super(MayaPiniHelper, self)._add_load_ctx_opts(menu=menu, work=work)

        _work = work or self.work

        # Add update ma and load
        menu.add_action(
            'Update ma file and load',
            wrap_fn(_update_and_load_ma, _work),
            icon=icons.LOAD, enabled=bool(_work and _work.extn == 'ma'))

        # Add load scene without refs
        _func = None
        if _work:
            _load_func = wrap_fn(load_scene, _work, load_refs=False)
            _func = wrap_fn(_work.load, load_func=_load_func)
        menu.add_action(
            'Load scene without refs', _func,
            icon=icons.LOAD, enabled=bool(_work))

    def closeEvent(self, event=None):
        """Triggered by close.

        Args:
            event (QEvent): close event
        """
        super(MayaPiniHelper, self).closeEvent(event)
        ph_base.BasePiniHelper.closeEvent(self, event)

    @qt.safe_timer_event
    def timerEvent(self, event):
        """Triggered by timer.

        Args:
            event (QTimerEvent): triggered event
        """
        super(MayaPiniHelper, self).timerEvent(event)
        ph_base.BasePiniHelper.timerEvent(self, event)


class _MaWork(pipe.CPWork, MaFile):
    """Pipelined work ma file."""

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to ma file
        """
        super(_MaWork, self).__init__(file_)
        MaFile.__init__(self, file_)

    def save(self, force=False):  # pylint: disable=arguments-differ
        """Save updated version of this file.

        Make sure existing file is backed up.

        Args:
            force (bool): overwrite without confirmation
        """

        # Check backups
        _bkps = self.find_bkps()
        _file_mtime = self.metadata.get('mtime') or self.mtime()
        _mtime = int(time.time())
        assert _file_mtime != _mtime
        if not _bkps or not _bkps[-1].matches(self):
            self._save_bkp(reason='backup existing')

        # Save this file
        MaFile.save(self, force=force)
        self._save_bkp(reason='ma update')


@usage.get_tracker('UpdateAndLoadMa')
def _update_and_load_ma(file_):
    """Update ma file references to latest versions and then load it.

    Args:
        file_ (str): ma file to update/load
    """
    _LOGGER.info('UPDATE AND LOAD MA %s', file_)
    _ma_work = _MaWork(file_)

    # Update refs
    _exprs = _ma_work.find_exprs(cmd='file')
    for _expr in qt.progress_bar(_exprs, 'Checking {:d} ref{}'):
        _LOGGER.info('%s %s %d', _expr, _expr.read_flag('ns'), _expr.line_n)
        _file = _expr.tokens[-1].strip('"')
        _LOGGER.info(' - FILE %s', _file)
        _out = pipe.to_output(_file)
        if _out:
            _out = pipe.CACHE.obt_output(_out)
            _LOGGER.info(' - OUT %s', _out)
            if not _out.is_latest():
                _new_out = _out.find_latest()
                _LOGGER.info(' - NEEDS UPDATE %s', _new_out)
                _expr.replace(_out.path, _new_out.path)
    _ma_work.save(force=True)

    _ma_work.load()


def _sort_cacheables(cacheable):
    """Sort cacheables alphabetically ignoring case.

    Args:
        cacheable (CPipeRef): cacheable to sort

    Returns:
        (str): sort string
    """
    return cacheable.output_name.lower()
