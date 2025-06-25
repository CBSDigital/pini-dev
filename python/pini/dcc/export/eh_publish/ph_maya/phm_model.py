"""Tools for managing maya publish handlers."""

import logging


from pini import icons
from maya_pini import m_pipe
from maya_pini.utils import to_long

from . import phm_basic

_LOGGER = logging.getLogger(__name__)


class CMayaModelPublish(phm_basic.CMayaBasicPublish):
    """Manages maya model publish."""

    NAME = 'Maya Model Publish'
    ACTION = 'ModelPublish'
    TYPE = 'Publish'

    ICON = icons.find('Ice')
    COL = 'Cornflower Blue'

    LABEL = (
        'Copies this scene to the publish directory - make sure there '
        'is only one top node named MDL and that it has a cache set named '
        'cache_SET')

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        super()._add_custom_ui_elems()
        self.ui.add_separator()
        self.ui.add_check_box(
            val=True, name='FreezeTfms', label="Freeze transforms")
        self.ui.add_check_box(
            val=True, name='DelHistory', label='Delete history')

    def export(  # pylint: disable=unused-argument
            self, notes=None, version_up=True, snapshot=True, bkp=True,
            progress=True, abc=True, fbx=True, references='Remove',
            remove_alayers=True, remove_dlayers=True, remove_junk=True,
            remove_sets=True, freeze_tfms=True, del_history=True, force=False):
        """Execute this publish.

        Args:
            notes (str): export notes
            version_up (bool): version up after export
            snapshot (bool): take thumbnail snapshot on export
            bkp (bool): save bkp file
            progress (bool): show progress bar
            abc (bool): whether to export rest cache abc
            fbx (bool): whether to export rest cache fbx
            references (str): how to handle references (eg. Remove)
            remove_alayers (bool): remove anim layers
            remove_dlayers (bool): remove display layers
            remove_junk (bool): remove JUNK group
            remove_sets (bool): remove unused sets
            freeze_tfms (bool): freeze transforms on geo
            del_history (bool): delete history on geo
            force (bool): force overwrite without confirmation

        Returns:
            (CPOutput): publish file
        """

        # Execute basic publish with model-specific opts removed
        _basic_kwargs = locals()
        for _name in ('del_history', 'freeze_tfms', 'self', '__class__'):
            _basic_kwargs.pop(_name)
        return super().export(**_basic_kwargs)

    def _clean_scene(self):
        """Apply clean scene options to prepare for publish."""
        _del_hist = self.settings['del_history']
        _freeze_tfms = self.settings['freeze_tfms']

        super()._clean_scene()

        # Clean geos
        _tfms = m_pipe.read_cache_set(mode='tfm')
        _LOGGER.info(' - TFMS %s', _tfms)
        for _tfm in sorted(_tfms, key=to_long, reverse=True):
            if not _tfm.exists():
                continue
            if _del_hist:
                _tfm.delete_history()
            if _freeze_tfms:
                _tfm.freeze_tfms(force=True)
