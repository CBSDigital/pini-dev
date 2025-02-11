"""Tools for managing maya references.

NOTE: this module is used in pini.dcc so if that module is imported
it will cause a cyclical dependency error.
"""

import logging
import operator

from maya import cmds

from pini.utils import File, single, apply_filter
from maya_pini.utils import restore_ns, del_namespace

from .r_attr_ref import find_attr_refs
from .r_file_ref import FileRef

_LOGGER = logging.getLogger(__name__)


@restore_ns
def create_ref(file_, namespace, force=False):
    """Create reference.

    Args:
        file_ (str): file to reference
        namespace (str): namespace for reference
        force (bool): force replace existing without confirmation

    Returns:
        (FileRef): new reference instance
    """
    from .r_namespace_clash_ui import handle_namespace_clash
    from pini import dcc

    _file = File(file_)
    _rng = dcc.t_range()

    if not _file.exists():
        raise OSError("File does not exist: " + _file.path)

    if _file.extn == 'abc':
        cmds.loadPlugin('AbcImport', quiet=True)
    elif _file.extn.lower() == 'fbx':
        cmds.loadPlugin('fbxmaya', quiet=True)

    # Test for existing
    _namespace = namespace
    _LOGGER.debug(' - NAMESPACE %s', _namespace)
    cmds.namespace(set=":")
    if force:
        _ref = find_ref(namespace=_namespace, unloaded=True, catch=True)
        if _ref:
            _ref.delete(force=True)
        del_namespace(_namespace, force=True)
    while (
            cmds.namespace(exists=_namespace) or
            cmds.objExists(_namespace) or
            find_ref(namespace=_namespace, unloaded=True, catch=True)):
        _LOGGER.debug(
            'REQUEST NEW NAMESPACE %s ns_exists=%d obj_exists=%d ref_exists=%d',
            _namespace, cmds.namespace(exists=_namespace),
            cmds.objExists(_namespace),
            bool(find_ref(namespace=_namespace, unloaded=True, catch=True)))
        _namespace = handle_namespace_clash(file_=file_, namespace=_namespace)

    # Create the reference
    _pre_refs = set(find_refs())
    _LOGGER.debug(' - PRE REFS %s', _pre_refs)
    _type = {'ma': 'mayaAscii',
             'mb': 'mayaBinary',
             'fbx': 'FBX',
             'abc': 'Alembic'}.get(_file.extn)
    cmds.file(_file.path, reference=True, namespace=_namespace,
              options="v=0;p=17", ignoreVersion=True, type=_type)
    _post_refs = set(find_refs())
    _LOGGER.debug(' - POST REFS %s', _post_refs)
    _new_refs = _post_refs.difference(_pre_refs)
    _LOGGER.debug(' - NEW REFS %s', _new_refs)
    _ref = single(_new_refs)

    # Fbx ref seems to update timeline (?)
    if dcc.t_range() != _rng:
        dcc.set_range(*_rng)

    return FileRef(_ref.ref_node)


def find_path_refs():
    """Find all path references in the current scene.

    This includes all file references and attribute references.

    Returns:
        (PathRef list): path references
    """
    return find_refs(unloaded=True) + find_attr_refs()


def find_ref(
        namespace=None, unloaded=False, extn=None, selected=None, catch=True):
    """Find reference matching the given critera.

    Args:
        namespace (str): match by namespace
        unloaded (bool): include unloaded refs (disabled by default)
        extn (str): filter by file extension
        selected (bool): filter by selected state
        catch (bool): no error if reference not found

    Returns:
        (FileRef): matching reference
    """
    _refs = find_refs(
        unloaded=unloaded, selected=selected, extn=extn)
    if namespace:
        _refs = [_ref for _ref in _refs if _ref.namespace == namespace]
    return single(_refs, catch=catch)


def find_refs(
        filter_=None, class_=None, unloaded=False, extn=None, selected=None,
        nested=False, allow_no_namespace=False):
    """Find references in the current scene.

    Args:
        filter_ (str): filter by namespace
        class_ (class): override ref class
        unloaded (bool): include unloaded refs (disabled by default)
        extn (str): filter by file extension
        selected (bool): filter by selected state
        nested (bool): include nested refs (disabled by default)
        allow_no_namespace (bool): include references with no namespace

    Returns:
        (FileRef list): matching references
    """
    _refs = _read_refs(class_=class_, allow_no_namespace=allow_no_namespace)
    if not unloaded:
        _refs = [_ref for _ref in _refs if _ref.is_loaded]
    if nested is not None:
        _refs = [_ref for _ref in _refs if _ref.is_nested == nested]
    if extn:
        _refs = [_ref for _ref in _refs if _ref.extn == extn]
    if selected is not None:
        _refs = [_ref for _ref in _refs if _ref.is_selected == selected]
    if filter_:
        _refs = apply_filter(
            _refs, filter_, key=operator.attrgetter('namespace'))
    return _refs


def _read_refs(class_=None, allow_no_namespace=False):
    """Read all references in the current scene.

    Args:
        class_ (class): override ref class
        allow_no_namespace (bool): include references with no namespace

    Returns:
        (FileRef list): all references
    """
    _refs = []
    for _ref_node in cmds.ls(type='reference'):

        # Check ref node
        try:
            _ref = FileRef(_ref_node, allow_no_namespace=allow_no_namespace)
        except (ValueError, RuntimeError):
            continue

        # Apply type cast
        if class_:
            try:
                _ref = class_(_ref_node)
            except ValueError:
                continue

        _refs.append(_ref)

    return _refs


def get_selected(multi=False):
    """Get selected reference.

    Args:
        multi (bool): allow multiple selections

    Returns:
        (FileRef): selected ref
    """
    _refs = set()
    for _node in cmds.ls(selection=True):
        if cmds.referenceQuery(_node, isNodeReferenced=True):
            _ref_node = cmds.referenceQuery(_node, referenceNode=True)
        elif cmds.objectType(_node) == 'reference':
            _ref_node = _node
        else:
            continue
        try:
            _ref = FileRef(_ref_node)
        except ValueError:
            continue
        _refs.add(_ref)
    if multi:
        return sorted(_refs)
    return single(_refs)


def obtain_ref(file_, namespace, force=False):
    """Obtain a matching reference.

    If the reference doesn't exist then it is created. Otherwise,
    the path of the existing reference is checked.

    Args:
        file_ (str): path to reference
        namespace (str): reference namespace
        force (bool): replace existing reference without warning dialog

    Returns:
        (FileRef): matching reference
    """
    _ref = find_ref(namespace, catch=True)
    if not _ref:
        _ref = create_ref(file_=file_, namespace=namespace)
    _file = File(file_)
    if File(_ref.path) != _file:
        _LOGGER.info(' - REF FILE      %s', _ref.path)
        _LOGGER.info(' - REQUIRED FILE %s', _file.path)
        raise NotImplementedError('File mismatch')
    return _ref
