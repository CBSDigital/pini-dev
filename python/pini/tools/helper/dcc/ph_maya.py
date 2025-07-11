"""Tools for managing the (dockable) pini helper in maya."""

# pylint: disable=too-many-ancestors

import logging
import platform
import time

from maya import cmds

from pini import icons, qt, pipe, dcc
from pini.dcc import pipe_ref
from pini.tools import usage
from pini.utils import wrap_fn, MaFile

from maya_pini.utils import load_scene

from .. import ui

_LOGGER = logging.getLogger(__name__)


class MayaPiniHelper(qt.CUiDockableMixin, ui.PHUiBase):
    """Pini Helper in maya which docks to the main ui."""

    init_ui = ui.PHUiBase.init_ui

    abc_lookdev_attach = True
    abc_modes = ('Auto', 'aiStandIn')
    abc_cam_plates = True

    def __init__(
            self, admin=None, store_settings=True, jump_to=None,
            parent=None, show=True, reset_cache=True, title=None):
        """Constructor.

        Args:
            admin (bool): launch in admin mode
            store_settings (bool): load settings on launch
            jump_to (str): path to point helper to on launch
            parent (QDialog): override parent dialog
            show (bool): show on launch
            reset_cache (bool): reset pipeline cache on launch
            title (str): override helper window title
        """
        from pini.tools import helper
        helper.MIXIN = self

        _LOGGER.debug('LAUNCH')

        # Set title - linux can't handle unicode emojis
        if platform.system() == 'Linux':
            _title = ui.TITLE
        else:
            _title = ui.EMOJI.to_unicode() + ' ' + ui.TITLE
        super().__init__(
            show=False, ui_file=ui.UI_FILE, store_settings=False,
            parent=parent, title=_title)

        self.vdb_modes = ['Auto', 'aiVolume']
        if 'redshift' in dcc.allowed_renderers():
            self.vdb_modes.append('RedshiftVolume')

        ui.PHUiBase.__init__(
            self, admin=admin, store_settings=store_settings, show=False,
            jump_to=jump_to, reset_cache=reset_cache, title=title)

        if show:
            self.show(dockable=True)
            self.apply_docking()
        _LOGGER.debug(' - LAUNCH COMPLETE')

    def _add_load_ctx_opts(self, menu, work=None):
        """Add load scene context options to the given menu.

        Args:
            menu (CMenu): menu to add to
            work (CPWork): work file to add options for
        """
        super()._add_load_ctx_opts(menu=menu, work=work)

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

    def _create_abc_ref(self, output, namespace):
        """Create abc reference.

        Args:
            output (CPOutput): output being referenced
            namespace (str): reference namespace
        """
        _mode = self.ui.SAbcMode.currentText()
        if _mode == 'Auto':
            _mode = 'Reference'

        if _mode == 'Reference':
            dcc.create_ref(output, namespace=namespace)
        elif _mode == 'aiStandIn':
            pipe_ref.create_ai_standin(output, namespace=namespace)
        else:
            raise NotImplementedError(_mode)

    def _create_cam_ref(self, output, namespace):
        """Create camera reference.

        Args:
            output (CPOutput): output being referenced
            namespace (str): reference namespace
        """
        _plates = self.ui.SCamPlates.isChecked()
        pipe_ref.create_cam_ref(
            output, namespace=namespace, build_plates=_plates)

    def _create_vdb_ref(self, output, namespace):
        """Create vdb reference.

        Args:
            output (CPOutput): output being referenced
            namespace (str): reference namespace
        """
        _mode = self.ui.SVdbMode.currentText()
        if _mode == 'Auto':
            _ren = cmds.getAttr("defaultRenderGlobals.currentRenderer")
            _mode = {
                'arnold': 'aiVolume',
                'redshift': 'RedshiftVolume',
            }[_ren]

        if _mode == 'aiVolume':
            pipe_ref.create_ai_vol(output, namespace=namespace)
        elif _mode == 'RedshiftVolume':
            pipe_ref.create_rs_vol(output, namespace=namespace)
        else:
            raise NotImplementedError(_mode)

    def closeEvent(self, event=None):
        """Triggered by close.

        Args:
            event (QEvent): close event
        """
        super().closeEvent(event)
        ui.PHUiBase.closeEvent(self, event)

    @qt.safe_timer_event
    def timerEvent(self, event):
        """Triggered by timer.

        Args:
            event (QTimerEvent): triggered event
        """
        super().timerEvent(event)
        ui.PHUiBase.timerEvent(self, event)


class _MaWork(pipe.CPWork, MaFile):
    """Pipelined work ma file."""

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (str): path to ma file
        """
        super().__init__(file_)
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
