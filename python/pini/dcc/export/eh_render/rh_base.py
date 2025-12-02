"""Tools for managing the base Render Handler class.

A render handler is a plugin to facilitate rendering to pipeline
by a dcc.
"""

import logging

from pini import qt, pipe, dcc
from pini.utils import single, wrap_fn, copy_text

from .. import eh_base

_LOGGER = logging.getLogger(__name__)


class CRenderHandler(eh_base.CExportHandler):
    """Base class for any render handler."""

    NAME = None
    LABEL = 'Render handler'
    ACTION = 'Render'
    TYPE = 'Render'

    add_range = True
    add_passes = True
    add_cameras = True

    def __init__(self, priority=50, label_w=60):
        """Constructor.

        Args:
            priority (int): sort priority (higher priority handlers
                are sorted to top of option lists)
            label_w (int): label width in ui
        """
        super().__init__(label_w=label_w, priority=priority)

    def build_ui(self):
        """Build basic render interface into the given layout."""
        super().build_ui(
            add_range=self.add_range and 'Frames',
            add_snapshot=False)

    def set_settings(self, *args, **kwargs):
        """Setup settings dict."""
        super().set_settings(*args, snapshot=False, **kwargs)

    def find_cams(self):
        """Find cameras in the scene."""
        raise NotImplementedError

    def find_pass(self, match):
        """Find a render pass in the scene.

        Args:
            match (str): match by name

        Returns:
            (CRenderPass): matching pass
        """
        _passes = self.find_passes()
        _name_matches = [_pass for _pass in _passes if _pass.name == match]
        if len(_name_matches) == 1:
            return single(_name_matches)
        raise ValueError(match)

    def find_passes(self):
        """Find passes in the current scene.

        Returns:
            (CRenderPass list): passes
        """
        raise NotImplementedError

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""

        # Read cams from scene
        if self.add_cameras:
            self.ui.add_separator()
            _cams, _cam = self.find_cams()
            _LOGGER.debug(' - CAM %s %s', _cam, _cam)
            self.ui.add_combo_box(
                name='Camera', items=_cams, val=_cam, label_w=60,
                save_policy=qt.SavePolicy.NO_SAVE)
            _LOGGER.debug(' - CAM UI %s', self.ui.Camera)

        if self.add_passes:
            self.ui.add_list_widget(name='Passes')
            self._redraw__Passes()

    def _redraw__Passes(self):
        """Build render layer selection elements."""
        _work = pipe.cur_work()

        # Build layer items
        _items = []
        _select = []
        for _pass in self.find_passes():
            _item = qt.CListWidgetItem(
                _pass.name, data=_pass, icon=_pass.to_icon())
            if _pass.renderable:
                _select.append(_pass)
            _items.append(_item)
        _LOGGER.debug(' - SELECT PASSES %s', _select)
        self.ui.Passes.set_items(_items, select=_select)

    def _callback__Passes(self):
        _sel_lyrs = self.ui.Passes.selected_datas()
        _LOGGER.debug('CALLBACK PASSES %s', _sel_lyrs)
        for _pass in self.find_passes():
            _ren = _pass in _sel_lyrs
            _LOGGER.debug(' - %s %d', _pass, _ren)
            _pass.set_renderable(_ren)

    def _context__Passes(self, menu):
        _lyr = self.ui.Passes.selected_data()
        if _lyr:
            _out = _lyr.to_output()
            menu.add_action("Select", wrap_fn(dcc.select_node, _lyr.rop))
            if _out:
                menu.add_action("Copy path", wrap_fn(copy_text, _out.path))

    def exec_from_ui(self, ui_kwargs=None, **kwargs):
        """Execuate this export using settings from ui.

        Args:
            ui_kwargs (dict): override interface kwargs
        """
        _ui_kwargs = ui_kwargs or self.ui.to_kwargs()
        if 'range_' in _ui_kwargs:
            _rng = _ui_kwargs.pop('range_')
            _start, _end = _rng
            _frames = list(range(_start, _end + 1))
            _ui_kwargs['frames'] = _frames
        return super().exec_from_ui(ui_kwargs=_ui_kwargs, **kwargs)
