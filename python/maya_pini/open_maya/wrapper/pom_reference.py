"""Tools for managing the MFnReference object wrapper."""

import logging

from maya import cmds
from maya.api import OpenMaya as om

from pini import pipe
from pini.utils import basic_repr, single, check_heart, passes_filter
from maya_pini import ref

from . import pom_node, pom_transform
from .. import pom_utils

_LOGGER = logging.getLogger(__name__)


class CReference(om.MFnReference, ref.FileRef):
    """Represents a file reference."""

    def __init__(self, node, allow_no_namespace=False):
        """Constructor.

        Args:
            node (str): reference node or node in a reference
            allow_no_namespace (bool): no error if ref has no namespace
        """
        _LOGGER.debug('CReference INIT %s', node)
        super(CReference, self).__init__()  # pylint: disable=no-value-for-parameter

        # Apply node's reference to this object
        _m_obj = pom_utils.to_mobject(node)
        _iter = om.MItDependencyNodes(om.MFn.kReference)
        while not _iter.isDone():
            check_heart()

            _ref_node = _iter.thisNode()
            self.setObject(_ref_node)

            # Try setting this MFnReference to this ref
            _LOGGER.debug(
                ' - TESTING REF NODE %s isNull=%d', _ref_node,
                _ref_node.isNull())
            if _ref_node == _m_obj:
                _LOGGER.debug(' - MATCHED REF NODE')
                break

            # Check if this ref contains the given node
            try:
                _contained = self.containsNodeExactly(_m_obj)
            except RuntimeError:
                _contained = False
            if _contained:
                _LOGGER.debug(' - REF MATCHED CONTAINED NODE')
                break
            _iter.next()

        else:
            raise ValueError('Failed to match reference {}'.format(node))
        _LOGGER.debug(' - LOCATED REF')

        _ref_node = pom_node.CNode(self.name())
        ref.FileRef.__init__(
            self, _ref_node, allow_no_namespace=allow_no_namespace)

    @property
    def namespace(self):
        """Obtain this reference's namespace.

        Returns:
            (str): namespace
        """
        return str(self.associatedNamespace(shortName=True))

    @property
    def skel(self):
        """Obtain this reference's skeleton.

        Returns:
            (CSkeleton): skeleton
        """
        return self.find_skeleton(catch=True)

    @property
    def top_node(self):
        """Obtain this reference's top node.

        Returns:
            (CTransform): top node
        """
        return self.find_top_node()

    def add_to_grp(self, grp):
        """Add this reference's top node to the given group.

        If the group doesn't exist then it is created.

        Args:
            grp (str): name of group
        """
        self.top_node.add_to_grp(grp)

    def find_node(self, type_=None):
        """Find a node in this reference.

        Args:
            type_ (str): filter by type

        Returns:
            (CBaseNode): matching node
        """
        return single(self.find_nodes(type_=type_))

    def find_nodes(
            self, type_=None, full_path=False, dag_only=False, filter_=None):
        """Find nodes in this reference.

        Args:
            type_ (str): filter by type
            full_path (bool): use full node path
            dag_only (bool): return only dag nodes
            filter_ (str): apply filter to node name

        Returns:
            (CBaseNode list): nodes
        """
        _nodes = super(CReference, self).find_nodes(
            type_=type_, dag_only=dag_only, full_path=full_path,
            filter_=filter_)
        return [pom_utils.cast_node(_node) for _node in _nodes]

    def find_skeleton(self, catch=True):
        """Find this node's skeleton.

        Args:
            catch (bool): no error if no skeleton found

        Returns:
            (CSkeleton|None): skeleton (if any)
        """
        from maya_pini import open_maya as pom
        _jnts = sorted(self.find_nodes(type_='joint', full_path=True))
        if not _jnts:
            if catch:
                return None
            raise ValueError(self)
        assert str(_jnts[0]).count('|') != str(_jnts[1]).count('|')
        _root = str(_jnts[0]).split('|')[-1]
        return pom.CSkeleton(_root)

    def find_top_nodes(self):
        """Find top nodes of this reference.

        Returns:
            (CTransform list): top nodes
        """

        # NOTE: super gives bad results (?)
        _top_nodes = ref.FileRef(self.ref_node).find_top_nodes()
        _LOGGER.debug('FIND TOP NODES %s', _top_nodes)

        return [pom_transform.CTransform(_node) for _node in _top_nodes]

    def to_node(self, name, clean=True, fmt='node', catch=False):
        """Obtain a node from this reference.

        Args:
            name (str): node name
            clean (bool): strip namespaces from name (enabled by default)
            fmt (str): format of result (node/str)
            catch (bool): no error if node does not exist

        Returns:
            (CBaseNode|str): matching node
        """
        _node = super(CReference, self).to_node(name, clean=clean)

        if fmt == 'str':
            pass

        elif fmt == 'node':
            if catch and not cmds.objExists(_node):
                _node = None
            else:
                _node = pom_utils.cast_node(_node)
        else:
            raise ValueError(fmt)

        return _node

    def __str__(self):
        return str(self.ref_node)

    def __repr__(self):
        return basic_repr(self, self.namespace or self.ref_node)


def create_ref(file_, namespace, force=False):
    """Create a reference.

    Args:
        file_ (str): path to reference
        namespace (str): namespace to use
        force (bool): replace existing without confirmation

    Returns:
        (CReference): new reference
    """
    _ref = ref.create_ref(file_=file_, namespace=namespace, force=force)
    return CReference(_ref.ref_node)


def find_ref(
        match=None, namespace=None, selected=False, unloaded=False, task=None,
        catch=True):
    """Find a reference in the current scene.

    Args:
        match (str): match by filter or namespace
        namespace (str): refs namespace to match
        selected (bool): filter by selected refs
        unloaded (bool): filter by loaded status (only loaded reference
            are returned by default)
        task (str): filter by task
        catch (bool): no error if no matching reference found

    Returns:
        (CReference|None): matching reference (if any)
    """
    _refs = find_refs(
        selected=selected, namespace=namespace, unloaded=unloaded,
        task=task)

    # Try match as filter
    if match and len(_refs) > 1:
        _filter_refs = [_ref for _ref in _refs
                        if passes_filter(_ref.namespace, match)]
        if _filter_refs:
            _refs = _filter_refs

    # Try namespace match
    if match and len(_refs) > 1:
        _ns_refs = [_ref for _ref in _refs if _ref.namespace == match]
        if _ns_refs:
            _refs = _ns_refs

    return single(_refs, catch=catch)


def find_refs(
        namespace=None, selected=False, unloaded=False, task=None,
        allow_no_namespace=False):
    """Find references in the current scene.

    Args:
        namespace (str): filter by namespace
        selected (bool): return only selected references
        unloaded (bool): filter by loaded status (only loaded reference
            are returned by default)
        task (str): filter by task
        allow_no_namespace (bool): include references with no namespace

    Returns:
        (CReference list): references
    """
    _LOGGER.debug('FIND REFS')
    if selected:
        _refs = ref.get_selected(multi=True)
    else:
        _refs = ref.find_refs(
            unloaded=unloaded, allow_no_namespace=allow_no_namespace)
    _LOGGER.debug(' - REFS %s', _refs)
    _c_refs = []
    for _ref in _refs:

        _LOGGER.debug(' - ADDING %s', _ref)
        try:
            _c_ref = CReference(
                _ref.ref_node, allow_no_namespace=allow_no_namespace)
        except ValueError:
            continue
        if namespace and _ref.namespace != namespace:
            continue

        if task:
            _out = pipe.to_output(_ref.path)
            if not _out or _out.task != task:
                continue

        _c_refs.append(_c_ref)
        _LOGGER.debug('   - CREATED %s', _c_ref)

    return _c_refs


def obtain_ref(file_, namespace):
    """Obtain a reference, creating it if needed.

    Args:
        file_ (str): path to reference
        namespace (str): reference namespace

    Returns:
        (CReference): reference
    """
    _ref = ref.obtain_ref(file_, namespace=namespace)
    return CReference(_ref.ref_node)


def selected_ref():
    """Obtain currently selected reference.

    Returns:
        (CReference): reference node
    """
    return find_ref(selected=True)
