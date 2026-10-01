"""Tools for managing maya selection publish handler."""

import logging

from pini import icons, qt, pipe
from pini.tools import helper
from pini.utils import fr_enumerate, val_map

from maya import cmds

from maya_pini.utils import add_to_set, save_scene, save_fbx

from . import phm_scene

_LOGGER = logging.getLogger(__name__)
_DEFAULT_ICON = icons.find('Cooked Rice')


class _PubSet:
    """Represents a publish set, a set with _PSET suffix."""

    def __init__(self, node):
        """Constructor.

        Args:
            node (str): set node
        """
        assert node.endswith('_PSET')

        self.node = node
        self.name = node[:-5]

        self.out = self.to_output()
        if self.out:
            self.icon = helper.output_to_icon(
                self.out, allow_missing=True, content_type='BasicMa',
                entity=pipe.CACHE.cur_entity)
        else:
            self.icon = _DEFAULT_ICON

    def to_output(self, extn='ma'):
        """Build an output for this pub set.

        Args:
            extn (str): override extn

        Returns:
            (CPOutput): output
        """
        if not pipe.CACHE.cur_work:
            return None
        return pipe.CACHE.cur_work.to_output(
            'publish', output_name=self.name, output_type='pset', extn=extn)


class CMayaSelectionPublish(phm_scene.CMayaScenePublish):
    """Manages maya selection publish."""

    NAME = 'Selection Publish'
    ACTION = 'SelectionPublish'

    ICON = icons.find('Chopsticks')
    COL = 'Indian Red'

    LABEL = '\n'.join([
        'Copies each publish set (eg. wasps_PSET, columns_PSET) to the publish '
        'folder using export selection. This is generally used to pass '
        'unweildy scenes down the pipeline within shots.',
        '',
        'Use the 🔨 button to build a publish set from the selected objects.',
        '',
        'You can use the sanity check tool to check your scene.',
    ])

    priority = 45
    add_remove_junk = False
    add_ma_export = True

    def build_ui(self, *args, **kwargs):
        """Build ui."""
        super().build_ui(*args, **kwargs)
        self._callback__PubSets()

    def _add_custom_ui_elems(self):
        """Add custom ui elements."""
        _build = self.ui.build_icon_btn(
            name='BuildSelSet', icon=icons.BUILD, callback=self._build_pub_set,
            tooltip='Build publish set from selection')
        self.ui.add_list_widget(
            name='PubSets', label='Publish Sets', add_elems=[_build], emit=True)

        super()._add_custom_ui_elems(fbx_label='Export fbx files')

    def _build_pub_set(self):
        """Build pub set from selection."""
        _LOGGER.info('BUILD PSET')
        _name = qt.input_dialog(
            'Enter name for this publish set (eg. wasps)', title='Build PSET')
        if not _name.endswith('_PSET'):
            _name += '_PSET'
        for _node in cmds.ls(selection=True):
            add_to_set(_node, _name)
        self.ui.PubSets.redraw()

    def _redraw__PubSets(self):
        _work = pipe.cur_work()
        _ety = pipe.CACHE.cur_entity
        _items = []
        for _set in _find_psets():
            _item = qt.CListWidgetItem(
                _set.name, data=_set, icon=_set.icon, icon_scale=0.7)
            _items.append(_item)
        self.ui.PubSets.set_items(_items)

    def _redraw__Execute(self):
        _LOGGER.info('REDRAW Execute')
        _pub_sets = self.ui.PubSets.selected_items()
        self.ui.Execute.setEnabled(bool(_pub_sets))

    def _callback__PubSets(self):
        _LOGGER.info('CALLBACK PubSets')
        self._redraw__Execute()

    def export(self, pub_sets, ma=True, fbx=False, **kwargs):  # pylint: disable=unused-argument
        """Execute selection set export.

        Args:
            pub_sets (PubSet list): pub sets to export
            ma (bool): export ma file
            fbx (bool): export fbxs

        Returns:
            (CPOutputFile list): outputs
        """
        _outs = []
        for _fr, _set in fr_enumerate(pub_sets):

            _LOGGER.info(' - EXPORT %s (%.03f)', _set, _fr)

            # Export ma
            if ma:
                cmds.select(_set.node)
                save_scene(_set.out, selection=True)
                _outs.append(_set.out)

            # Export fbx
            if fbx:
                _fbx_out = _set.to_output(extn='fbx')
                save_fbx(_fbx_out, selection=True)
                _outs.append(_fbx_out)

            _pc = val_map(_fr, out_min=20, out_max=80)
            self.progress.set_pc(_pc)

        return _outs


def _find_psets():
    """Find pub sets in the current scene.

    Returns:
        (PubSet list): pub sets
    """
    return [_PubSet(_set) for _set in cmds.ls('*_PSET', type='objectSet')]
