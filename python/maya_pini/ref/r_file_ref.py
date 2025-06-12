"""Tools for managing the FileRef reference object in maya."""

# pylint: disable=too-many-public-methods

import logging

from maya import cmds

from pini.utils import (
    File, single, passes_filter, safe_zip, EMPTY, basic_repr,
    split_base_index)
from maya_pini.utils import (
    to_namespace, set_namespace, del_namespace, to_clean)

from . import r_path_ref

_LOGGER = logging.getLogger(__name__)


class FileRef(r_path_ref.PathRef):
    """Represents a file reference."""

    def __init__(self, ref_node):
        """Constructor.

        Args:
            ref_node (str): reference node
        """
        _LOGGER.debug('INIT FileRef %s', ref_node)
        self.ref_node = ref_node
        self.node = ref_node

        _name = self.namespace or self.prefix
        self.cmp_key = split_base_index(_name)

    @property
    def extn(self):
        """Obtain file extension for this reference.

        Returns:
            (str): extension
        """
        return File(self.path).extn

    @property
    def is_loaded(self):
        """Test whether this reference is loaded.

        Returns:
            (bool): whether loaded
        """
        return cmds.referenceQuery(self.ref_node, isLoaded=True)

    @property
    def is_nested(self):
        """Test whether this reference is nested.

        ie. it has a parent reference

        Returns:
            (bool): whether nested
        """
        _parent = cmds.referenceQuery(
            self.ref_node, referenceNode=True, parent=True)
        return bool(_parent)

    @property
    def is_referenced(self):
        """Test whether this reference is referenced (aka nested).

        Returns:
            (bool): whether referenced
        """
        return cmds.referenceQuery(self.ref_node, isNodeReferenced=True)

    @property
    def is_selected(self):
        """Check if this reference is currently selected.

        Returns:
            (bool): whether selected
        """
        _nodes = [
            _node for _node in cmds.ls(selection=True)
            if cmds.referenceQuery(_node, isNodeReferenced=True) and
            to_namespace(_node) == self.namespace]
        _LOGGER.debug('IS SELECTED ref=%s nodes=%s', self, _nodes)
        return bool(_nodes)

    @property
    def namespace(self):
        """Get this reference's namespace.

        Returns:
            (str): namespace
        """
        return self._read_ns()

    @property
    def path(self):
        """Get path to this reference.

        Returns:
            (str): reference path
        """
        return File(self.path_uid.split('{', 1)[0])

    @property
    def path_uid(self):
        """Get the path uid for this reference.

        This includes the copy number which maya uses to make all
        reference paths unique.

        Returns:
            (str): path with copy number
        """
        return str(cmds.referenceQuery(self.ref_node, filename=True))

    @property
    def prefix(self):
        """Obtain prefix for this reference.

        This only has a value if the reference has been created using no
        namespace and a string prefix has been applied to all its nodes.

        Returns:
            (str): node name prefix
        """
        if self.namespace:
            return None
        _parent_ns = to_namespace(self.ref_node)
        _file_ns = cmds.file(
            self.path_uid, query=True, namespace=True).lstrip(':')
        if _parent_ns:
            return f'{_parent_ns}:{_file_ns}'
        return _file_ns

    def delete(self, force=False, delete_foster_parent=True):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
            delete_foster_parent (bool): also remove any leftover
                foster parent node
        """
        from pini import qt

        if not force:
            _ns_s = self.namespace or '<no namespace>'
            qt.ok_cancel(
                f'Delete existing {_ns_s} reference?',
                title='Remove reference')

        self.unload()
        cmds.file(self.path_uid, removeReference=True)

        if delete_foster_parent:
            _foster_parent = str(self.ref_node) + 'fosterParent1'
            if cmds.objExists(_foster_parent):
                cmds.delete(_foster_parent)

    def exists(self):
        """Test whether the target of this reference exists.

        Returns:
            (bool): whether file exists
        """
        return File(self.path).exists()

    def find_nodes(
            self, type_=None, full_path=False, dag_only=False, filter_=None):
        """Search nodes within this reference.

        Args:
            type_ (str): filter by type
            full_path (bool): return full node path
            dag_only (bool): return only dag nodes
            filter_ (str): apply filter to node name

        Returns:
            (str list): matching nodes
        """
        _LOGGER.debug('FIND NODES %s type=%s', self, type_)

        _all_nodes = cmds.referenceQuery(
            self.ref_node, nodes=True,
            dagPath=True, showFullPath=full_path) or []
        _LOGGER.debug(' - FOUND %d NODES', len(_all_nodes))

        _nodes = []
        for _node in _all_nodes:

            _LOGGER.debug(' - CHECKING NODE %s', _node)

            if filter_ and not passes_filter(_node, filter_):
                continue

            # Apply type match
            if type_:
                _type = cmds.objectType(_node)
                _type_match = _type == type_
                _is_anim_curve = _type.startswith('animCurve')
                _anim_curve_match = _is_anim_curve and type_ == 'animCurve'
                if not (_type_match or _anim_curve_match):
                    continue

            if dag_only:
                _is_dag = 'dagNode' in cmds.nodeType(_node, inherited=True)
                if not _is_dag:
                    continue
            if full_path:
                _node = single(cmds.ls(_node, long=True))

            _node = str(_node)
            _nodes.append(_node)

        return _nodes

    def find_top_node(self, class_=None, catch=False):
        """Find top node of this reference.

        Args:
            class_ (class): cast top node to this class
            catch (bool): no error if exactly one top node isn't found

        Returns:
            (str): top node

        Raises:
            (ValueError): if reference does not have exactly one top node
        """
        _node = single(
            self.find_top_nodes(), catch=catch,
            zero_error=f'Reference {self.namespace} has no top node',
            multi_error=f'Reference {self.namespace} has multiple top nodes')
        if class_ and _node:
            _node = class_(_node)
        return _node

    def find_top_nodes(self):
        """Find top nodes of this reference.

        Returns:
            (str list): top nodes
        """
        _LOGGER.debug('FIND TOP NODES')

        # Read nodes + paths
        _nodes = self.find_nodes(dag_only=True)
        if not _nodes:
            return []
        _paths = self.find_nodes(dag_only=True, full_path=True)
        assert len(_nodes) == len(_paths)
        _min_depth = min(str(_path).count('|') for _path in _paths)

        _top_nodes = []
        for _node, _path in safe_zip(_nodes, _paths):
            _LOGGER.debug(' - CHECKING %s %s', _node, _path)
            assert _path.endswith(_node)
            if str(_path).count('|') > _min_depth:
                continue
            _top_nodes.append(_node)

        return _top_nodes

    def import_(self, namespace=EMPTY):
        """Import this reference.

        Args:
            namespace (str): override node namespace
        """
        _ns = self.namespace
        cmds.file(self.path_uid, importReference=True)

        # Update namespace
        if namespace is EMPTY:
            pass
        elif not namespace:
            cmds.namespace(moveNamespace=(_ns, ':'), force=True)
        else:
            raise NotImplementedError(namespace)

    def load(self):
        """Load this reference."""
        cmds.file(self.path_uid, loadReference=True)

    def _read_ns(self):
        """Read namespace of this reference.

        Returns:
            (str): namespace
        """
        _LOGGER.debug(' - NAMESPACE %s', self.ref_node)
        _ref_ns = str(cmds.referenceQuery(self.ref_node, namespace=True))
        _LOGGER.debug('   - REF NS %s', _ref_ns)

        if not self.is_loaded:
            if _ref_ns != 'unknown':
                return _ref_ns
            _node_ns = str(self.ref_node)
            if _node_ns.endswith('RN'):
                _node_ns = _node_ns[:-2]
            return _node_ns

        # If the referenceQuery result is ":" then that means that this ref
        # has been created using prefixes rather that namespaces
        if _ref_ns == ':':
            return None

        _file_ns = str(cmds.file(self.path_uid, query=True, namespace=True))
        _LOGGER.debug('   - FILE NS %s', _file_ns)

        # Remove prefix nodes

        _ns = _file_ns
        _parent_ns = to_namespace(self.ref_node)
        if _parent_ns:
            _ns = f'{_parent_ns}:{_ns}'

        return _ns

    def set_namespace(self, namespace, update_ref_node=True):
        """Update this reference's namespace.

        Args:
            namespace (str): namespace to apply
            update_ref_node (bool): update ref node name

        Returns:
            (FileRef): updated ref
        """

        # Update namespace
        if namespace != self.namespace:
            set_namespace(":")
            del_namespace(':' + namespace)
            cmds.file(self.path_uid, edit=True, namespace=namespace)

        # Update ref node
        if update_ref_node:
            cmds.lockNode(self.ref_node, lock=False)
            self.ref_node = cmds.rename(self.ref_node, namespace + "RN")
            cmds.lockNode(self.ref_node, lock=True)

        return self

    def size(self):
        """Obtain size of this reference's file.

        Returns:
            (int): size in bytes
        """
        return File(self.path).size()

    def to_node(self, name, clean=True):
        """Get a node from this reference.

        Args:
            name (str): node name
            clean (bool): strip namespaces from name (enabled by default)

        Returns:
            (str): node with namespace added
        """
        _name = name
        if clean:
            _name = to_clean(name)
        _name = _name.split('.')[0]
        return f'{self.namespace}:{_name}'

    def to_plug(self, plug):
        """Map a plug name to this reference.

        eg. blah.tx -> thisRef:blah.tx

        Args:
            plug (str): plug to convert

        Returns:
            (str): plug with namespace added
        """
        assert '.' in plug
        return f'{self.namespace}:{plug}'

    def unload(self):
        """Unload this reference."""
        cmds.file(self.path_uid, unloadReference=True)

    def update(self, path):
        """Update this reference's path.

        Args:
            path (str): path to apply
        """
        _file = File(path)
        if not _file.exists():
            raise OSError(f"Missing file: {_file.path}")
        try:
            cmds.file(
                _file.path, loadReference=self.ref_node, ignoreVersion=True,
                options="v=0", force=True)
        except RuntimeError as _exc:
            if str(_exc) == 'Maya command error':
                raise RuntimeError(
                    'Maya errored on opening file ' + _file.path) from _exc
            raise _exc

    def __eq__(self, other):
        if isinstance(other, FileRef):
            return self.path_uid == other.path_uid
        return False

    def __hash__(self):
        return hash(self.path_uid)

    def __repr__(self):
        _name = None
        _ns = self.namespace
        if not _name:
            _name = _ns
        if not _name:
            _prefix = self.prefix
            if _prefix:
                _name = f'{_prefix}[P]'
        if not _name:
            _name = f'{self.ref_node}[R]'
        return basic_repr(self, _name, separator='|')
