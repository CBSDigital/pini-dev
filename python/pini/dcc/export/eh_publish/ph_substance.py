"""Tools for managing texture publishing from substance."""

# pylint: disable=unused-argument

import logging

from substance_painter import textureset

from pini import icons, qt

from substance_pini import s_pipe

from . import ph_basic

_LOGGER = logging.getLogger(__name__)


class CSubstanceTexturePublish(ph_basic.CBasicPublish):
    """Manages a substance texture publish."""

    NAME = 'Substance Texture Publish'
    ICON = icons.find('Framed Picture')
    COL = 'Salmon'
    TYPE = 'Publish'

    LABEL = '\n'.join([
        'Saves textures to disk',
    ])

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""

        # Add texture sets
        _emoji = qt.CPixmap(icons.find('Diamond Suit'))
        _sets = []
        for _set in textureset.all_texture_sets():
            _icon = qt.CPixmap(30, 30)
            _icon.fill('Transparent')
            _icon.draw_overlay(
                _emoji, _icon.center(), size=20, anchor='C')
            _item = qt.CListWidgetItem(
                _set.name, icon=_icon, data=_set.name)
            # _item = qt.CListWidgetItem(_set.name)
            _sets.append(_item)
        self.ui.add_list_widget(
            name='Sets', items=_sets, select=_sets, label='Texture sets')

        self.ui.add_check_box(
            name='Browser', val=False, label='Open texture dir in browser')

    def export(
            self, notes=None, snapshot=True, version_up=True,
            progress=True, browser=False, sets=None, force=False):
        """Execute texture publish.

        Args:
            notes (str): publish notes
            snapshot (bool): take snapshot on publish
            version_up (bool): version up on publish
            progress (bool): show publish progress
            browser (bool): open export folder in brower
            sets (str list): export only the given texture sets
            force (bool): replace existing without confirmation
        """
        return s_pipe.export_textures(
            work=self.work, browser=browser, force=force, sets=sets,
            progress=self.progress)
