"""Base class for any cache export handler."""

import logging
import pprint

from pini import qt, farm, dcc
from pini.utils import wrap_fn, to_str, single, plural, Seq

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CCacheHandler(eh_base.CExportHandler):
    """Base class for any cache handler."""

    TYPE = 'Cache'

    block_update_metadata = False

    add_range = True
    add_substeps = False
    add_use_farm = False

    cacheables = None

    def _add_custom_ui_elems(self):
        """Add custom elements for this cache handler."""

    def build_ui(self):
        """Build cache interface."""
        _LOGGER.debug('BUILD UI')
        self._build_ui_header()

        self.ui.add_list_widget(name='Cacheables')
        if self.add_substeps:
            self.ui.add_spin_box('Substeps', 1, min_=1, max_=20)
        if farm.IS_AVAILABLE and self.add_use_farm:
            self.ui.add_check_box('UseFarm', False)
        self._add_custom_ui_elems()
        self._build_ui_footer()

    def set_settings(self, *args, **kwargs):
        """Setup settings dict."""
        super().set_settings(*args, **kwargs)

        # Fix cacheables as kwarg if exec from ui
        if not self.cacheables:
            self.cacheables = self.settings['cacheables']

        # Handled in m_pipe to allow embed asset path
        if self.block_update_metadata:
            if not self.settings['update_metadata']:
                raise NotImplementedError
            self.settings['update_metadata'] = False

    def find_cacheable(self, match):
        """Find a cacheable in the current scene.

        Args:
            match (str): match by name/node

        Returns:
            (CCacheable): matching cacheable
        """
        _cbls = self.find_cacheables()
        _matches = [
            _cbl for _cbl in _cbls
            if match and match in (_cbl.node, _cbl.output_name, _cbl.label)]
        if len(_matches) == 1:
            return single(_matches)

        raise ValueError(match)

    def find_cacheables(self):
        """Find cacheables in the current scene."""
        raise NotImplementedError

    def _redraw__Cacheables(self):
        _LOGGER.debug('REDRAW Cacheables')
        _items = []
        for _cbl in self.find_cacheables():
            _icon = qt.CPixmap(30, 30)
            _icon.fill('Transparent')
            _icon.draw_overlay(
                _cbl.icon, _icon.center(), size=20, anchor='C')
            _item = qt.CListWidgetItem(_cbl.label, icon=_icon, data=_cbl)
            _items.append(_item)
        self.ui.Cacheables.set_items(_items, select=_items, emit=False)
        self.ui.Cacheables.load_setting()

    def _callback__Cacheables(self):
        self.ui.Execute.setEnabled(bool(self.ui.Cacheables.selected_datas()))

    def _context__Cacheables(self, menu):
        _cbl = self.ui.Cacheables.selected_data()
        _out = None
        if _cbl.output:
            _out = _cbl.output
        if _out:
            menu.add_action(
                'Print metadata', wrap_fn(pprint.pprint, _out.metadata))
        menu.add_action(
            'Select', wrap_fn(dcc.select_node, _cbl.node))

    def export(self, cacheables, **kwargs):
        """Execute this cache.

        Args:
            cacheables (CCacheable list): cacheables to export
        """
        raise NotImplementedError

    def _check_for_overwrite(self, cacheables=None):
        """Check for existing files that will be overwritten.

        Args:
            cacheables (CCacheable list): override list of cacheables
                to check (allows for combined cache tools)
        """
        _cbls = cacheables or self.settings['cacheables']
        _force = self.settings['force']
        _LOGGER.info('CHECK FOR OVERWRITE force=%d', _force)

        _existing = []
        for _cbl in _cbls:
            _LOGGER.info(' - CBL %s', _cbl)
            _LOGGER.info('   - OUTPUT %s', _cbl.output)
            if _cbl.output.exists():
                _existing.append(_cbl.output)

        if not _force and _existing:
            _extns = {_out.extn for _out in _existing}
            _label = single(_extns, catch=True) or 'file'
            _out = _existing[0]
            if isinstance(_out, Seq):
                _desc = f'{_label} sequence'
            else:
                _desc = _label
            _desc += plural(_existing)
            _lines = [f'Overwrite {len(_existing)} existing {_desc}?']
            _lines += [f'\n{_out}' for _out in _existing]
            qt.ok_cancel(
                '\n'.join(_lines), icon=self.ICON,
                title='Confirm overwrite')

    def _update_metadata(self, content_type=None):
        """Update outputs metadata.

        Args:
            content_type (str): apply content type
        """
        super()._update_metadata()

        _cbls = self.settings['cacheables']
        for _cbl in _cbls:
            _LOGGER.info(' - CBL %s -> %s', _cbl, _cbl.output)
            assert _cbl.output_name == _cbl.output.output_name
            if _cbl.src_ref:
                _cbl.output.add_metadata(src_ref=to_str(_cbl.src_ref.path))
            if content_type:
                _cbl.output.add_metadata(content_type=content_type)
