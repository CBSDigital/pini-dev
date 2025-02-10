"""Tools for managing option menu elements."""

import logging

from maya import cmds

_LOGGER = logging.getLogger(__name__)


def create_option_menu(options, select=None):
    """Create option menu element.

    Args:
        options (str list): options to add
        select (str): item to select

    Returns:
        (str): field uid
    """
    _field = cmds.optionMenu()
    _LOGGER.debug('CREATE OPTION MENU %s', _field)
    _menu = OptionMenu(_field)
    _menu.set_opts(options)
    if select:
        _menu.set_val(select)
    return _menu


class OptionMenu:
    """Represent an option menu ui element."""

    def __init__(self, field):
        """Constructor.

        Args:
            field (str): field uid
        """
        self.field = field

    def get_val(self):
        """Read text of currently item.

        Returns:
            (str): selected text
        """
        _sel = cmds.optionMenu(self.field, query=True, select=True)
        _items = cmds.optionMenu(self.field, query=True, itemListLong=True)
        _item = _items[_sel - 1]
        return cmds.menuItem(_item, query=True, label=True)

    def set_val(self, value, catch=True):
        """Set current value of this option menu.

        Args:
            value (str): item to select
            catch (bool): no error if fail to apply value
        """
        _items = cmds.optionMenu(self.field, query=True, itemListLong=True)
        _labels = [
            cmds.menuItem(_item, query=True, label=True) for _item in _items]
        if value not in _labels:
            if catch:
                return
            raise ValueError(value)
        _idx = _labels.index(str(value))
        cmds.optionMenu(self.field, edit=True, select=_idx + 1)

    def set_opts(self, options):
        """Apply menu item options.

        Args:
            options (str list): option names
        """
        cmds.optionMenu(self.field, edit=True, deleteAllItems=True)
        for _choice in options:
            cmds.menuItem(label=_choice, parent=self.field)
