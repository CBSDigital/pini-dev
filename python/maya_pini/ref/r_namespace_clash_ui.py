"""Tools for managing the namespace clash interface."""

import logging

from maya import cmds

from pini import qt
from pini.utils import File

from maya_pini.utils import del_namespace

_LOGGER = logging.getLogger(__name__)
_DIALOG = None
_DIR = File(__file__).to_dir()
_UI_FILE = _DIR.to_file('namespace_clash.ui')


class _NamespaceClashUi(qt.CUiDialog):
    """Dialog which is raise when a namespace clash occurs.

    This allows the user to either replace the existing node in the namespace
    or select a different namespace to use for a reference.
    """

    def __init__(self, namespace, file_):
        """Constructor.

        Args:
            namespace (str): namespace causing clash
            file_ (str): path to reference file
        """
        cmds.namespace(set=':')
        self.namespace = None
        self.input_namespace = namespace
        self.file_ = File(file_)
        super(_NamespaceClashUi, self).__init__(
            modal=True, ui_file=_UI_FILE, load_settings=False)

    def init_ui(self):
        """Initiate ui element."""
        self.ui.Namespace.setText(self.input_namespace)
        self._callback__Namespace()

    def _callback__Namespace(self):

        _ns = self.ui.Namespace.text()
        _valid = _is_valid_namespace(_ns)
        self.ui.WarningIcon.setVisible(not _valid)

        if not _valid:
            _text = 'Select a valid namespace'
        elif cmds.namespace(exists=_ns):
            _text = 'Replace existing nodes in {} namespace'.format(_ns)
        elif cmds.objExists(_ns):
            _text = 'Replace existing {} node'.format(_ns)
        else:
            _text = 'Reference file using {} namespace'.format(_ns)
        self.ui.Execute.setText(_text)
        self.ui.Execute.setEnabled(_is_valid_namespace(_ns))

    def _callback__Execute(self):
        _LOGGER.debug('EXECUTE')
        _ns = self.ui.Namespace.text()
        if cmds.namespace(exists=_ns):
            try:
                del_namespace(_ns, force=True)
            except qt.DialogCancelled:
                return
            if cmds.namespace(exists=_ns):
                return
        if cmds.objExists(_ns):
            cmds.delete(_ns)
        self.namespace = _ns
        _LOGGER.debug(' - NAMESPACE %s', self.namespace)
        self.close()


def _is_valid_namespace(namespace):
    """Check if the given namespace is valid.

    Args:
        namespace (str): namespace to check

    Returns:
        (bool): whether namespace is valid
    """
    for _chr in ' :,;':
        if _chr in namespace:
            return False
    return True


def handle_namespace_clash(file_, namespace):
    """Handle a reference import where the namespace is already in use.

    Args:
        file_ (str): file being referenced
        namespace (str): namespace causing clash

    Returns:
        (str): updated namespace
    """
    _LOGGER.info('HANDLE NAMESPACE CLASH %s', namespace)
    global _DIALOG
    _DIALOG = _NamespaceClashUi(file_=file_, namespace=namespace)
    if not _DIALOG.namespace:
        raise qt.DialogCancelled
    _LOGGER.debug(' - OBTAINED RESULT %s', _DIALOG.namespace)
    return _DIALOG.namespace
