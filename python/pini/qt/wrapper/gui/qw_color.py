"""Tools for managing QColor wrapper."""

import six

from pini.utils import val_map, basic_repr, single

from ...q_mgr import QtGui

_EXTENDED_COLS = {
    'bottlegreen': (0, 106, 78),
    'plumred': (124, 41, 70),
}


class CColor(QtGui.QColor):
    """Wrapper for QColor object."""

    def __init__(self, *args, **kwargs):
        """Constructor."""

        _alpha = kwargs.pop('alpha', None)

        # Apply extended colour names
        _args = args
        _arg = single(_args, catch=True)
        if isinstance(_arg, six.string_types):
            _name = _arg.lower()
            _args = _EXTENDED_COLS.get(_name, _args)

        super(CColor, self).__init__(*_args, **kwargs)
        if _alpha:
            self.setAlphaF(_alpha)

    @staticmethod
    def col_names():
        """Obtain list of valid colour names.

        Returns:
            (str list): colour names
        """
        return sorted(CColor.colorNames() + list(_EXTENDED_COLS.keys()))

    def blacken(self, val):
        """Blacken this colour.

        Args:
            val (float): degree of blackness - 1.0 will return black

        Returns:
            (QColor): whitened colour
        """
        return CColor(
            int(val_map(val, out_min=self.red(), out_max=0)),
            int(val_map(val, out_min=self.green(), out_max=0)),
            int(val_map(val, out_min=self.blue(), out_max=0)),
            self.alpha())

    def to_tuple(self, type_=float):
        """Obtain tuple of this colour's float values.

        Args:
            type_ (class): type of data to return
                float - floating point rgb values
                int - return 0-255 integer rgb values

        Returns:
            (float tuple): rgb floats
        """
        if type_ is float:
            return self.redF(), self.greenF(), self.blueF()
        if type_ is int:
            return self.red(), self.green(), self.blue()
        raise ValueError(type_)

    def whiten(self, val):
        """Whiten this colour.

        Args:
            val (float): degree of whiteness - 1.0 will return white

        Returns:
            (QColor): whitened colour
        """
        return CColor(
            int(val_map(val, out_min=self.red(), out_max=255)),
            int(val_map(val, out_min=self.green(), out_max=255)),
            int(val_map(val, out_min=self.blue(), out_max=255)),
            self.alpha())

    def __hash__(self):
        return hash(self.to_tuple(int))

    def __repr__(self):
        _label = ', '.join([str(_int) for _int in self.to_tuple(int)])
        return basic_repr(self, _label)
