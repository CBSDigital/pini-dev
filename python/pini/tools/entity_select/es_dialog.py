"""Tools for managing the entity select dialog."""

import logging

from pini import pipe, qt
from pini.utils import File

_LOGGER = logging.getLogger(__name__)
_ENTITY_SELECT_UI = File(__file__).to_file('entity_select.ui')


class EntitySelectUi(qt.CUiDialog):
    """Dialog for selecting an entity."""

    def __init__(self, execute='Execute', title='Select Entity', target=None):
        """Constructor.

        Args:
            execute (str): label for execute button
            title (str): dialog title
            target (CPEntity): dialog target
        """
        _LOGGER.debug('INIT target=%s', target)
        self.target = target
        self.executed = False

        super().__init__(_ENTITY_SELECT_UI)

        self.setWindowTitle(title)
        self.ui.Execute.setText(execute)

        _trg_asset = isinstance(self.target, pipe.CPAsset)
        _profile = 'Assets' if _trg_asset else 'Shots'
        self.ui.Profile.select_text(_profile)
        self.ui.Job.redraw()

        self.setModal(True)
        self.exec_()

    def _redraw__Job(self):
        _items = [_job.name for _job in pipe.CACHE.jobs]
        _select = self.target.job if self.target else None
        self.ui.Job.set_items(
            _items, data=pipe.CACHE.jobs, select=_select, emit=True)

    def _redraw__Profile(self):
        _job = self.ui.Job.selected_data()
        _cur_text = self.ui.Profile.currentText()
        _seqs = [_seq.name for _seq in _job.sequences]
        self.ui.Profile.set_items(
            ['Assets', 'Shots'], emit=True, data=[_job.asset_types, _seqs])

    def _redraw__EntityType(self):

        _job = self.ui.Job.selected_data()
        _profile = self.ui.Profile.currentText()
        _ety_types = self.ui.Profile.selected_data()

        if not _ety_types:
            return

        _label = 'Sequence' if _profile == 'Shots' else 'Category'
        self.ui.EntityTypeLabel.setText(_label)

        _data = [_job.find_entities(entity_type=_ety_type)
                 for _ety_type in _ety_types]
        _sel = self.target.entity_type if self.target else None
        self.ui.EntityType.set_items(
            _ety_types, data=_data, select=_sel, emit=True)

    def _redraw__Entity(self):
        _etys = self.ui.EntityType.selected_data()
        _labels = [_ety.name for _ety in _etys]
        self.ui.Entity.set_items(
            _labels, data=_etys, select=self.target)

    def _callback__Job(self):
        self.ui.Profile.redraw()

    def _callback__Profile(self):
        self.ui.EntityType.redraw()

    def _callback__EntityType(self):
        self.ui.Entity.redraw()

    def _callback__Execute(self):
        self.executed = True
        self.close()
