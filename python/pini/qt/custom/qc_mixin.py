"""Tools for managing the dockable mixin class.

This is a dialog which can be docked to maya's ui.
"""

import logging

from maya import OpenMayaUI, cmds, mel
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin, MayaQDockWidget

from pini.utils import wrap_fn

from ..q_mgr import QtWidgets, Qt, shiboken

_LOGGER = logging.getLogger(__name__)


class CDockableMixin(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    """Dialog which can be docked to maya's ui."""

    def __init__(self, title=None, tool_name=None, parent=None, show=True):
        """Constructor.

        Args:
            title (str): title for tab
            tool_name (str): force tool name
            parent (QDialog): parent ui
            show (bool): show on launch
        """
        _LOGGER.debug('INIT CDockableMixin')
        _title = title or type(self).__name__.strip('_')
        self.tool_name = tool_name or type(self).__name__.strip('_')
        _LOGGER.debug(' - TOOL NAME %s', self.tool_name)
        self.ws_name = self.tool_name + 'WorkspaceControl'

        # Delete any previous instances that is detected. Do this
        # before parenting self to main window
        self.delete_existing_instances()

        super().__init__(parent=parent)
        self.setObjectName(self.tool_name)

        # Setup window properties
        self.setWindowFlags(Qt.Window)
        self.resize(200, 200)
        self._title = title

        if show:
            self.show(dockable=True)
            self.apply_docking()

    def set_title(self, title):
        """Set tab title.

        Args:
            title (str): title to apply
        """
        _LOGGER.debug('SET TITLE %s', title)

        self.setWindowTitle(title)

        # Fix tab name
        _LOGGER.debug(' - BUILDING SET TITLE COMMAND')

        _rename_ws = wrap_fn(
            cmds.workspaceControl, self.ws_name, edit=True, label=title)
        cmds.evalDeferred(_rename_ws)

    def delete_existing_instances(self):
        """Delete any instances of this class."""
        _LOGGER.debug('DELETE EXISTING INSTANCES')

        # Delete workspace control
        if cmds.workspaceControl(self.ws_name, query=True, exists=True):
            _LOGGER.debug(' - DELETE WORKSPACE CONTROL')
            cmds.deleteUI(self.ws_name)

        # Important that it's QMainWindow, and not QWidget/QDialog
        _main_win_ptr = int(OpenMayaUI.MQtUtil.mainWindow())
        _main_win = shiboken.wrapInstance(
            _main_win_ptr, QtWidgets.QMainWindow)

        # Go through main window's children to find any previous instances
        _LOGGER.debug(' - REMOVE CHILDREN')
        for _obj in _main_win.children():
            if (
                    isinstance(_obj, MayaQDockWidget) and
                    _obj.widget().objectName() == self.tool_name):
                _LOGGER.debug('DELETING INSTANCE %s', _obj)
                _main_win.removeDockWidget(_obj)
                _obj.setParent(None)
                _obj.deleteLater()

    def apply_docking(self):
        """Dock this widget to the main maya ui."""
        _LOGGER.debug('APPLY DOCKING')

        try:
            self.show(dockable=True)
        except RuntimeError as _exc:
            _LOGGER.info(' - DOCKING FAILED %s ^^^ %s ^^^', self.ws_name, _exc)
            if str(_exc) == f"Object's name '{self.ws_name}' is not unique.":
                raise _MixinError(_exc) from _exc
            raise _exc

        _channel_box = mel.eval(
            'getUIComponentDockControl("Channel Box / Layer Editor", '
            'false)')
        cmds.workspaceControl(
            self.ws_name, edit=True, tabToControl=[_channel_box, 1],
            retain=False, initialWidth=100, width=100,
            label=self.tool_name, loadImmediately=True)

        if self._title:
            self.set_title(self._title)

    def delete(self):
        """Delete this interface."""
        self.delete_existing_instances()

    def dockCloseEventTriggered(self):
        """Triggered by close tab.

        If it's floating or docked, this will run and delete it self when it
        closes. You can choose not to delete it here so that you can still
        re-open it through the right-click menu, but do disable any
        callbacks/timers that will eat memory
        """
        _LOGGER.debug('DOCK CLOSE EVENT TRIGGERED')
        self.delete_existing_instances()
        _LOGGER.debug(' - DOCK CLOSE EVENT COMPLETE')


class _MixinError(RuntimeError):
    """Raise when mixin fails to dock to maya interface."""
