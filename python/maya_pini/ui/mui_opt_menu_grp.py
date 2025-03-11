"""Tools for managing option menu elements."""

import logging

from maya import cmds

_LOGGER = logging.getLogger(__name__)


class OptionMenuGrp:
    """Represent an option menu ui element."""

    func = cmds.optionMenuGrp

    def __init__(self, field):
        """Constructor.

        Args:
            field (str): field uid
        """
        self.field = field

    def exists(self):
        """Test whether this element exists.

        Returns:
            (bool): whether element exists
        """
        return self.func(self.field, query=True, exists=True)

    def get_val(self):
        """Read text of currently item.

        Returns:
            (str): selected text
        """
        _sel = self.func(self.field, query=True, select=True)
        _items = self.func(self.field, query=True, itemListLong=True)
        _item = _items[_sel - 1]
        return cmds.menuItem(_item, query=True, label=True)

    def get_vals(self):
        """Get values of this option group.

        Returns:
            (str list): values
        """
        _items = self.func(self.field, query=True, itemListLong=True)
        return [
            cmds.menuItem(_item, query=True, label=True) for _item in _items]

    def set_val(self, value, catch=True):
        """Set current value of this option menu group.

        Args:
            value (str): item to select
            catch (bool): no error if fail to apply value
        """
        _items = self.func(self.field, query=True, itemListLong=True)
        _labels = [
            cmds.menuItem(_item, query=True, label=True) for _item in _items]
        if value not in _labels:
            if catch:
                return
            raise ValueError(value)
        _idx = _labels.index(str(value))
        self.func(self.field, edit=True, select=_idx + 1)

    def set_opts(self, options):
        """Apply menu item options.

        Args:
            options (str list): option names
        """
        self.func(self.field, edit=True, deleteAllItems=True)
        for _choice in options:
            cmds.menuItem(label=_choice, parent=self.field)
