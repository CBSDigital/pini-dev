"""Tools for managing the MFnReference object wrapper."""

import logging
import time

from maya import cmds
from maya.api import OpenMaya as om

from pini import pipe
from pini.utils import (
    basic_repr, single, check_heart, passes_filter, File)

from maya_pini import ref
from maya_pini.utils import to_namespace, to_clean, bake_results

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
        _LOGGER.log(9, 'CReference INIT %s', node)
        super().__init__()  # pylint: disable=no-value-for-parameter

        # Apply node's reference to this object
        _m_obj = pom_utils.to_mobject(node)
        _iter = om.MItDependencyNodes(om.MFn.kReference)
        while not _iter.isDone():
            check_heart()

            _ref_node = _iter.thisNode()
            self.setObject(_ref_node)

            # Try setting this MFnReference to this ref
            _LOGGER.log(
                9, ' - TESTING REF NODE %s isNull=%d', _ref_node,
                _ref_node.isNull())
            if _ref_node == _m_obj:
                _LOGGER.log(9, ' - MATCHED REF NODE')
                break

            # Check if this ref contains the given node
            try:
                _contained = self.containsNodeExactly(_m_obj)
            except RuntimeError:
                _contained = False
            if _contained:
                _LOGGER.log(9, ' - REF MATCHED CONTAINED NODE')
                break
            _iter.next()

        else:
            raise ValueError(f'Failed to match reference {node}')
        _LOGGER.log(9, ' - LOCATED REF')

        _ref_node = pom_node.CNode(self.name())
        ref.FileRef.__init__(
            self, _ref_node, allow_no_namespace=allow_no_namespace)

    @property
    def anim(self):
        """Obtain list of anim curves for this reference.

        Returns:
            (CAnimCurve list): anim curves
        """
        _anims = []
        for _plug in self.plugs:
            _anim = _plug.to_anim()
            if _anim:
                _anims.append(_anim)
        return _anims

    @property
    def ctrls(self):
        """Obtain list of controls on this reference (from ctrls_SET).

        Returns:
            (CNode list): controls
        """
        from maya_pini import open_maya as pom
        _set = self.to_node('ctrls_SET')
        return [
            pom.cast_node(_node)
            for _node in cmds.sets(_set, query=True)]

    @property
    def namespace(self):
        """Obtain this reference's namespace.

        Returns:
            (str): namespace
        """
        return str(self.associatedNamespace(shortName=True))

    @property
    def plugs(self):
        """Obtain list of animatable plugs on this rig (from ctrls_SET).

        Returns:
            (CPlug list): plugs
        """
        return sum(
            (_ctrl.list_attr(keyable=True) for _ctrl in self.ctrls), [])

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
        return self.find_top_node(catch=True)

    @property
    def top_nodes(self):
        """Obtain this reference's top nodes.

        Returns:
            (CTransform list): top nodes
        """
        return self.find_top_nodes()

    def add_to_grp(self, grp):
        """Add this reference's top node to the given group.

        If the group doesn't exist then it is created.

        Args:
            grp (str): name of group
        """
        _grp = None
        for _top_node in self.find_top_nodes():
            _grp = _top_node.add_to_grp(grp)
        return _grp

    def bake(self, range_=None, simulation=True, add_offs=None):
        """Bake animation onto this reference.

        Args:
            range_ (tuple): override start/end frames
            simulation (bool): bake as simulation (slow but normally required)
            add_offs (CNode): node to add anim offset/mult chans to
        """
        from pini import dcc
        _LOGGER.debug('BAKE RESULTS')
        _rng = range_ or dcc.t_range()
        _LOGGER.debug(' - RNG %s', _rng)
        _start = time.time()
        _LOGGER.debug(' - PLUGS %s', self.plugs)
        bake_results(self.plugs, range_=_rng, euler_filter=True,
                     simulation=simulation, add_offs=add_offs)
        _LOGGER.debug(' - BAKED RESULTS IN %.01fs', time.time() - _start)

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
        _nodes = super().find_nodes(
            type_=type_, dag_only=dag_only, full_path=full_path,
            filter_=filter_)
        return sorted({pom_utils.cast_node(_node) for _node in _nodes})

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
        _root = str(_jnts[0]).rsplit('|', 1)[-1]
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

    def hide(self):
        """Hide this reference."""
        self.top_node.hide()

    def reload(self):
        """Reload this reference."""
        self.unload()
        self.load()

    def select(self):
        """Select this reference."""
        self.top_node.select()

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
        _node = super().to_node(name, clean=clean)

        if fmt == 'str':
            pass

        elif fmt == 'node':
            if catch and not cmds.objExists(_node):
                _node = None
            else:
                try:
                    _node = pom_utils.cast_node(_node)
                except RuntimeError as _exc:
                    if catch:
                        return None
                    raise _exc
        else:
            raise ValueError(fmt)

        return _node

    def to_plug(self, plug):
        """Map a plug name to this reference.

        eg. blah.tx -> thisRef:blah.tx

        Args:
            plug (str): plug to convert

        Returns:
            (str): plug with namespace added
        """
        from maya_pini import open_maya as pom
        _LOGGER.debug('TO PLUG %s', plug)
        _plug = plug
        if isinstance(_plug, pom.CPlug):
            _plug = str(_plug)
        assert '.' in _plug
        return pom.CPlug(f'{self.namespace}:{to_clean(_plug)}')

    def __eq__(self, other):
        return str(self) == str(other)

    def __str__(self):
        return str(self.ref_node)

    def __repr__(self):
        return basic_repr(self, self.namespace or self.ref_node)


def create_ref(file_, namespace, parent=None, force=False):
    """Create a reference.

    Args:
        file_ (str): path to reference
        namespace (str): namespace to use
        parent (QDialog): parent dialog for any popups
        force (bool): replace existing without confirmation

    Returns:
        (CReference): new reference
    """
    _file = File(file_)
    if not _file.exists():
        raise OSError(f'Missing file {_file.path}')
    _ref = ref.create_ref(
        file_=_file, namespace=namespace, parent=parent, force=force)
    return CReference(_ref.ref_node)


def find_ref(
        match=None, namespace=None, selected=False, unloaded=False, task=None,
        filter_=None, catch=True):
    """Find a reference in the current scene.

    Args:
        match (str): match by filter or namespace
        namespace (str): refs namespace to match
        selected (bool): filter by selected refs
        unloaded (bool): filter by loaded status (only loaded reference
            are returned by default)
        task (str): filter by task
        filter_ (str): apply namespace filter
        catch (bool): no error if no matching reference found

    Returns:
        (CReference|None): matching reference (if any)
    """
    _refs = find_refs(
        selected=selected, namespace=namespace, unloaded=unloaded,
        task=task, filter_=filter_)

    if len(_refs) == 1:
        return single(_refs)

    _match_refs = [
        _ref for _ref in _refs
        if _ref.namespace in (match, to_namespace(match))]
    if len(_match_refs) == 1:
        return single(_match_refs)

    _filter_refs = [
        _ref for _ref in _refs
        if passes_filter(_ref.namespace, match)]
    if len(_filter_refs) == 1:
        return single(_filter_refs)

    if catch:
        return None
    raise ValueError(match)


def find_refs(
        namespace=None, selected=False, unloaded=False, task=None,
        allow_no_namespace=False, filter_=None):
    """Find references in the current scene.

    Args:
        namespace (str): filter by namespace
        selected (bool): return only selected references
        unloaded (bool): filter by loaded status (only loaded reference
            are returned by default)
        task (str): filter by task
        allow_no_namespace (bool): include references with no namespace
        filter_ (str): apply namespace filter

    Returns:
        (CReference list): references
    """
    _LOGGER.debug('FIND REFS')

    # Get full list of refs using non-OpenMaya ref module
    if selected:
        _refs = ref.get_selected(multi=True)
    else:
        _refs = ref.find_refs(
            unloaded=unloaded, allow_no_namespace=allow_no_namespace)
    _LOGGER.debug(' - REFS %s', _refs)

    # Convert to
    _p_refs = []
    for _ref in _refs:

        _LOGGER.debug(' - CHECKING %s', _ref)

        # Apply filters
        if namespace and _ref.namespace != namespace:
            _LOGGER.debug('   - BAD NAMESPACE')
            continue
        if filter_ and not passes_filter(_ref.namespace, filter_):
            _LOGGER.debug('   - FAILS FILTER')
            continue
        if task:
            _out = pipe.to_output(_ref.path, catch=True)
            if not _out or _out.task != task:
                _LOGGER.debug('   - FAILS TASK FILTER %s', _out)
                continue

        # Build pom ref
        try:
            _p_ref = CReference(
                _ref.ref_node, allow_no_namespace=allow_no_namespace)
        except ValueError:
            _LOGGER.debug('   - FAILED TO BUILD pom NODE')
            continue
        _p_refs.append(_p_ref)
        _LOGGER.debug('   - ADDED %s', _p_ref)

    return _p_refs


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
