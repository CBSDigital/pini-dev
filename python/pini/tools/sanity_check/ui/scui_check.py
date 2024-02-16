"""Tools to manage check ui elements."""

import logging

from pini import icons, qt
from pini.utils import val_map, basic_repr, str_to_seed

_LOGGER = logging.getLogger(__name__)
_ICONS = icons.find_grp('animals')


class SCUiCheckItem(qt.CListViewPixmapItem):
    """Represents a sanity check item in the interface."""

    def __init__(self, list_view, check):
        """Constructor.

        Args:
            list_view (CListView): parent list view
            check (SCCheck): check represented by this item
        """
        _rand = str_to_seed(check.label)
        self.icon = _rand.choice(_ICONS)
        self.check = check
        self.default_col = 'CornflowerBlue'
        super(SCUiCheckItem, self).__init__(
            list_view, data=check, col=self.default_col, height=50)

    @property
    def status(self):
        """Obtain status of this element's check.

        Returns:
            (str): check status
        """
        return self.check.status

    def reset(self):
        """Reset this check."""
        self.col = self.default_col
        self.check.reset()
        self.redraw()

    def execute_check(self, checks, update_ui=None):
        """Execute this check.

        Args:
            checks (SCCheck check): other checks being executed - if
                they depend on this check then they are reset if this
                check is re-run
            update_ui (fn): interface update callback
        """
        _LOGGER.debug("EXECUTE CHECK %s", self.check)
        self._reset_dependent_checks(checks=checks, update_ui=update_ui)
        self.check.execute(update_ui=update_ui)
        self.redraw()
        _LOGGER.debug(" - EXECUTE CHECK COMPLETE %s", self.check)

    def _reset_dependent_checks(self, checks, update_ui):
        """Reset any checks which have run and are depended on this check.

        Args:
            checks (SCCheck check): other checks being executed
            update_ui (fn): interface update callback
        """
        _LOGGER.debug(" - RESET DEPENDENT CHECKS %s", self.check)
        _deps = [_check for _check in checks
                 if type(self.check) in _check.depends_on and
                 _check.has_run]
        _LOGGER.debug(' - DEPS %s', _deps)
        for _dep in _deps:
            _dep.reset()
            update_ui(check=_dep)
        _LOGGER.debug(' - RESET %d DEPS', len(_deps))

    def draw_pixmap(self, pix):
        """Draw this check's pixmap.

        Args:
            pix (CPixmap): pixmap to draw on
        """
        self.col = {
            'ready': 'CornflowerBlue',
            'disabled': 'Grey',
            'errored': 'Magenta',
            'failed': 'Crimson',
            'passed': ' Green',
            'running': 'LightSteelBlue',
        }[self.check.status]

        super(SCUiCheckItem, self).draw_pixmap(pix)

        pix.draw_text(
            self.check.label, pos=(45, self.height/3), anchor='L')

        # Draw progress
        if self.check.status in ['disabled', 'errored', 'ready']:
            _pc = 0
            _pc_text = ''
        else:
            _pc = self.check.progress
            _pc_text = '{:.00f}%'.format(self.check.progress)
        pix.draw_text(_pc_text, pos=(45, 2*self.height/3), anchor='L')
        _icon_idx = int(val_map(_pc, in_max=100, out_max=len(icons.MOONS)-1))
        _icon = icons.MOONS[_icon_idx]
        pix.draw_overlay(_icon, pos=(25, 25), anchor='C', rotate=180, size=30)

        pix.draw_overlay(
            self.icon, pos=(pix.width()-30, 25), anchor='C', size=30)
        pix.draw_text(
            self.check.status, pos=(pix.width()-53, self.height/3), anchor='R')

    def __repr__(self):
        return basic_repr(self, self.check.label)
