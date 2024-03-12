"""General maya utilies relating to namespaces."""

import logging

from maya import cmds

from pini import icons
from .mu_dec import restore_ns, restore_sel

_LOGGER = logging.getLogger(__name__)


@restore_sel
@restore_ns
def del_namespace(namespace, force=False):
    """Delete a namespace.

    Args:
        namespace (str): namespace to delete
        force (bool): remove nodes without confirmation
    """
    _LOGGER.debug('DEL NAMESPACE %s', namespace)
    from pini import qt
    from maya_pini import ref

    cmds.namespace(set=':')

    _ref = ref.find_ref(namespace=namespace.strip(':'))
    _LOGGER.debug(' - REF %s', _ref)

    # Determine force (only ask force once)
    _force = force
    if cmds.namespace(exists=namespace) and not _force:
        qt.ok_cancel(
            'Delete contents of namespace {}?'.format(namespace),
            icon=icons.CLEAN, title='Flush namespace')
        _force = True

    # Execute deletion
    if _ref:
        _ref.delete(force=_force)
    if cmds.namespace(exists=namespace):
        cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)
    if cmds.namespace(exists=namespace):
        raise RuntimeError('Failed to delete namespace '+namespace)


def set_namespace(namespace, clean=False):
    """Set current namespace.

    Args:
        namespace (str): namespace to apply
        clean (bool): remove existing nodes
    """
    assert namespace.startswith(":")
    assert namespace.count(":") == 1

    if clean:
        del_namespace(namespace, force=True)

    if not cmds.namespace(exists=namespace):
        cmds.namespace(add=namespace)
    cmds.namespace(set=namespace)


def to_namespace(node):
    """Extract namespace from the given node.

    eg. tmp:camera -> tmp

    Args:
        node (str): node to read namespace from

    Returns:
        (str): namespace
    """
    _tail = str(node).split('|')[-1]
    if ':' not in _tail:
        return None
    return _tail.rsplit(':', 1)[0]
