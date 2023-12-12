"""Tools for managing the ui container class.

This is an empty namespace used to store widgets.
"""

from pini.utils import single, passes_filter, File, abs_path

from .q_mgr import QtCore


class CUiContainer(object):
    """Container class for holding widgets.

    This is basically an empty namespace, and then widgets are added
    manually as attributes.
    """

    def __init__(self, settings_file=None):
        """Constructor.

        Args:
            settings_file (str): path to settings file
        """
        from pini import qt

        # Setup settings
        self.settings = None
        if settings_file:
            _file = File(abs_path(settings_file))
            _file.touch()  # Check settings writable
            self.settings = qt.CSettings(_file.path)

    def find_widget(self, name, catch=False, case_sensitive=False):
        """Find a widget within this ui.

        Args:
            name (str): object name to match
            catch (bool): no error if object not found
            case_sensitive (bool): ignore case (this is enabled by default
                as windows saves QSettings keys with unreliable case)

        Returns:
            (QWidget): matching widget
        """
        if case_sensitive:
            return single([_widget for _widget in self.find_widgets()
                           if _widget.objectName() == name], catch=catch)
        return single([
            _widget for _widget in self.find_widgets()
            if _widget.objectName().lower() == name.lower()], catch=catch)

    def find_widgets(self, filter_=None, type_=None):
        """Find widgets stored in this ui.

        Args:
            filter_ (str): filter by widget name
            type_ (class): filter by object type

        Returns:
            (QWidget list): widgets
        """
        _widgets = []
        for _name in dir(self):
            if filter_ and not passes_filter(_name, filter_):
                continue
            _attr = getattr(self, _name)
            if not isinstance(_attr, QtCore.QObject):
                continue
            if type_ and not isinstance(_attr, type_):
                continue
            _widgets.append(_attr)
        return _widgets

    def save_settings(self):
        """Save widget settings to file."""
        self.settings.save_ui(self)

    def load_settings(self, filter_=None):
        """Load widget settings from file.

        Args:
            filter_ (str): apply widget name filter
        """
        self.settings.apply_to_ui(self, filter_=filter_)
