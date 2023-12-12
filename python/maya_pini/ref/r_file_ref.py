"""Tools for managing the FileRef reference object in maya."""

import logging

from maya import cmds

from pini.utils import six_cmp, File, single, passes_filter, safe_zip
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
        self.ref_node = ref_node
        try:
            assert self.namespace
        except (RuntimeError, AssertionError):
            raise ValueError('Missing namespace {}'.format(self.ref_node))
        self.cmp_str = self.namespace

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
        if not self.is_loaded:
            _ns = str(cmds.file(self.path_uid, query=True, namespace=True))
            if _ns != 'unknown':
                return _ns
            _ns = str(self.ref_node)
            if _ns.endswith('RN'):
                _ns = _ns[:-2]
            return _ns

        _ns = str(cmds.file(self.path_uid, query=True, namespace=True))
        _ref_ns = to_namespace(self.ref_node)
        if _ref_ns:
            _ns = '{}:{}'.format(_ref_ns, _ns)
        return _ns

    @property
    def path(self):
        """Get path to this reference.

        Returns:
            (str): reference path
        """
        return self.path_uid.split('{', 1)[0]

    @property
    def path_uid(self):
        """Get the path uid for this reference.

        This includes the copy number which maya uses to make all
        reference paths unique.

        Returns:
            (str): path with copy number
        """
        return str(cmds.referenceQuery(self.ref_node, filename=True))

    def delete(self, force=False, delete_foster_parent=True):
        """Delete this reference.

        Args:
            force (bool): delete without confirmation
            delete_foster_parent (bool): also remove any leftover
                foster parent node
        """
        from pini import qt

        if not force:
            qt.ok_cancel(
                'Delete existing {} reference?'.format(self.namespace),
                title='Replace Reference')

        self.unload()
        cmds.file(self.path_uid, removeReference=True)

        if delete_foster_parent:
            _foster_parent = str(self.ref_node)+'fosterParent1'
            if cmds.objExists(_foster_parent):
                cmds.delete(_foster_parent)

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
            self.ref_node, nodes=True, dagPath=dag_only or full_path) or []
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
            zero_error='Reference {} has no top node'.format(
                self.namespace),
            multi_error='Reference {} has multiple top nodes'.format(
                self.namespace))
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

    def import_(self):
        """Import this reference."""
        cmds.file(self.path_uid, importReference=True)

    def load(self):
        """Load this reference."""
        cmds.file(self.path_uid, loadReference=True)

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
            del_namespace(':'+namespace)
            cmds.file(self.path_uid, edit=True, namespace=namespace)

        # Update ref node
        if update_ref_node:
            cmds.lockNode(self.ref_node, lock=False)
            self.ref_node = cmds.rename(self.ref_node, namespace+"RN")
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
        return '{}:{}'.format(self.namespace, _name)

    def to_plug(self, plug):
        """Map a plug name to this reference.

        eg. blah.tx -> thisRef:blah.tx

        Args:
            plug (str): plug to convert

        Returns:
            (str): plug with namespace added
        """
        assert '.' in plug
        return '{}:{}'.format(self.namespace, plug)

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
            raise OSError("Missing file: {}".format(_file.path))
        try:
            cmds.file(
                _file.path, loadReference=self.ref_node, ignoreVersion=True,
                options="v=0", force=True)
        except RuntimeError as _exc:
            if str(_exc) == 'Maya command error':
                raise RuntimeError('Maya errored on opening file '+_file.path)
            raise _exc

    def __cmp__(self, other):
        if isinstance(other, FileRef):
            return six_cmp(self.path_uid, other.path_uid)
        return six_cmp(self.path_uid, other)

    def __eq__(self, other):
        return hash(self.path_uid)

    def __hash__(self):
        return hash(self.path_uid)

    def __repr__(self):
        return '<{}|{}>'.format(
            type(self).__name__.strip('_'), self.namespace)
