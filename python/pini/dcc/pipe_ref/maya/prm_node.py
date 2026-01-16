"""Tools for managing pipelined node references in maya."""

import logging

from maya import cmds

from pini import dcc, pipe
from pini.utils import single, Seq, file_to_seq, to_seq, abs_path

from maya_pini import open_maya as pom, ui, ref
from maya_pini.utils import load_redshift_proxy

from . import prm_base, prm_utils

_LOGGER = logging.getLogger(__name__)


class _CMayaNodeRef(prm_base.CMayaPipeRef):
    """Base class for any pipelined node reference."""

    TYPE = None
    ref = None

    def __init__(self, path, namespace, node, top_node):
        """Constructor.

        Args:
            path (str): path to reference
            namespace (str): namespace (eg. node name)
            node (CNode): shape node
            top_node (CTransform): transform node
        """
        super().__init__(path=path, namespace=namespace)
        self.node = node
        self.top_node = top_node
        assert self.TYPE

    def delete(self, force=False):
        """Delete this node.

        Args:
            force (bool): delete without confirmation
        """
        if not force:
            raise NotImplementedError
        if cmds.objExists(self.top_node):
            cmds.delete(self.top_node)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutput|CPOutputSeq): new standin to apply
        """
        raise NotImplementedError


class CMayaAiStandIn(_CMayaNodeRef):
    """Represents a pipeline ass/usd reference in an aiStandIn node."""

    TYPE = 'aiStandIn'

    def __init__(self, node, path=None):
        """Constructor.

        Args:
            node (CTransform): aiStandIn node
            path (str): override path - to accommodate arnold delayed update
        """
        _LOGGER.debug('INIT CMayaAiStandIn %s %s', node, path)
        assert isinstance(node, pom.CTransform)
        assert node.shp.object_type() == 'aiStandIn'

        # Update path to %04d format
        _path = node.shp.plug['dso'].get_val()
        _path = _path.replace('.####.', '.%04d.')
        if '.%04d.' not in _path:
            _seq = file_to_seq(_path, catch=True)
            if _seq:
                _path = _seq.path

        _LOGGER.debug(' - PATH %s', _path)
        super().__init__(
            path or _path, namespace=str(node), node=node.shp,
            top_node=node)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutput|CPOutputSeq): new standin to apply
        """
        _LOGGER.debug(' - UPDATE %s -> %s', self, out)

        _mtx = self._to_mtx()
        _grp = self._to_parent()

        if out.extn in ['ass', 'abc', 'usd', 'gz']:
            _path = out.path.replace('.%04d.', '.####.')
            self.node.shp.plug['dso'].set_val(_path)
            return CMayaAiStandIn(self.node)

        if out.extn in ('ma', 'mb'):
            _ns = self.namespace
            self.delete(force=True)
            _ref = dcc.create_ref(out, namespace=_ns, group=_grp)
            _mtx.apply_to(_ref.ref.top_node)
            return _ref

        raise NotImplementedError(out)


class CMayaAiVolume(_CMayaNodeRef):
    """Represents a pipeline vdb reference in an aiVolume node."""

    TYPE = 'aiVolume'
    ref = None

    def __init__(self, node, path=None):
        """Constructor.

        Args:
            node (CTransform): aiVolume transform
            path (str): override path - maya seems to only read the
                vdb if useFileSequence is disabled but then it seems
                to update it in a deferred thread; this allows the path
                to be hacked so a valid vdb ref can be built on create
        """
        assert isinstance(node, pom.CTransform)
        assert node.shp.object_type() == 'aiVolume'
        _path = node.shp.plug['filename'].get_val() or ''
        if not _path:
            raise ValueError('Empty path')
        _path = abs_path(_path)
        _path = to_seq(_path)

        super().__init__(
            path or _path, namespace=str(node), node=node.shp,
            top_node=node)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutputSeq): new volume to apply
        """
        assert isinstance(out, Seq)
        _path = out.path.replace('.%04d.', '.####.')
        self.node.shp.plug['filename'].set_val(_path)


class CMayaFileRef(_CMayaNodeRef):
    """Represents an file node referencing a pipelined path."""

    TYPE = 'file'

    def __init__(self, file_):
        """Constructor.

        Args:
            file_ (CNode): file node
        """
        _LOGGER.debug('INIT CMayaFileRef %s', file_)
        _file = file_.plug['fileTextureName']
        _LOGGER.debug(' - FILE %s', _file)
        self.ref = ref.AttrRef(str(_file))
        _LOGGER.debug(' - PATH %s', self.ref.path)
        super().__init__(
            node=file_, path=self.ref.path, namespace=str(file_),
            top_node=file_)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutputFile|CPOutputSeq): new output
        """
        self.ref.update(out)


class CMayaImgPlaneRef(_CMayaNodeRef):
    """Represents an image plane referencing a pipelined image sequence."""

    TYPE = 'imagePlane'

    def __init__(self, img):
        """Constructor.

        Args:
            img (CNode): image plane node
        """
        _path = img.plug['imageName'].get_val()
        _LOGGER.debug(' - PATH %s', _path)
        _seq = to_seq(_path)
        if not _seq:
            raise ValueError
        _LOGGER.debug(' - SEQ %s', _seq)
        _out = pipe.to_output(_seq.path)
        if not _out:
            raise ValueError
        _top_node = img.to_parent()
        _name = str(_top_node).rsplit('->', 1)[-1]
        super().__init__(
            node=img, top_node=_top_node, path=_seq.path, namespace=_name)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutputSeq): new images to apply
        """
        _LOGGER.info('UPDATE %s %s', self, out.path)
        assert isinstance(out, Seq)
        _path = out[out.frames[0]]
        _LOGGER.info(' - PATH %s', _path)
        self.node.plug['imageName'].set_val(_path)


class CMayaRsDomeLight(_CMayaNodeRef):
    """A RedshiftDomeLight node referencing a pipelined output."""

    TYPE = 'RedshiftDomeLight'

    def __init__(self, node):
        """Constructor.

        Args:
            node (CNode): CMayaRsDomeLight node
        """
        _LOGGER.debug('INIT CMayaRsDomeLight %s', node)
        _tfm = node.to_parent()
        _path = to_seq(node.plug['tex1'].get_val())
        super().__init__(
            node=node, top_node=_tfm, path=_path, namespace=str(_tfm))

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutput|CPOutputSeq): output to apply
        """
        _path = out[out.frames[0]]
        self.node.plug['tex1'].set_val(_path)


class CMayaRsProxyRef(_CMayaNodeRef):
    """A RedshiftProxyMesh node referencing a pipelined output."""

    TYPE = 'RedshiftProxyMesh'

    def __init__(self, node):
        """Constructor.

        Args:
            node (CNode): RedshiftProxyMesh node
        """
        _LOGGER.debug('INIT CMayaRsProxyRef %s', node)

        _tfm = single(
            node.find_outgoing(plugs=False, connections=False, type_='mesh'))
        _LOGGER.debug(' - TFM %s', _tfm)
        _mesh = pom.CMesh(_tfm)

        _path = node.plug['fileName'].get_val().replace('.####.', '.%04d.')
        _LOGGER.debug(' - PATH %s', _path)
        super().__init__(
            path=_path, namespace=str(_mesh), node=node, top_node=_mesh)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutput|CPOutputSeq): output to apply
        """
        raise NotImplementedError


class CMayaRsVolume(_CMayaNodeRef):
    """A RedshiftProxyMesh node referencing a pipelined output."""

    TYPE = 'RedshiftVolumeShape'

    def __init__(self, node):
        """Constructor.

        Args:
            node (CNode): RedshiftVolumeShape node
        """
        _LOGGER.debug('INIT CMayaRsVolume %s', node)

        _tfm = node.to_parent()
        _LOGGER.debug(' - TFM %s', _tfm)
        _path = node.plug['fileName'].get_val()
        _path = to_seq(_path)
        if not _path:
            raise ValueError('No path set')
        super().__init__(
            path=_path, namespace=str(_tfm), node=node, top_node=_tfm)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutput|CPOutputSeq): output to apply
        """
        raise NotImplementedError


def create_ai_standin(path, namespace, group=None):
    """Create aiStandIn reference from the given path.

    Args:
        path (File|Seq): path to apply
        namespace (str): namespace to use
        group (str): override parent group

    Returns:
        (CMayaAiStandIn): reference
    """
    cmds.loadPlugin('mtoa', quiet=True)

    _shp = pom.CMDS.createNode('aiStandIn', name=namespace + 'Shape')
    _is_seq = isinstance(path, Seq)
    if _is_seq:
        _path = path[path.frames[0]]
    else:
        _path = path.path
    _shp.plug['dso'].set_val(_path)
    _tfm = _shp.to_parent().rename(namespace)
    _ns = str(_tfm)
    _shp.plug['useFrameExtension'].set_val(_is_seq or path.extn == 'abc')
    _ref = CMayaAiStandIn(_tfm, path=path)

    # Force expression update - still doesn't work for more than
    # one standin node
    if _is_seq:
        ui.raise_attribute_editor()
        cmds.refresh()

    prm_utils.apply_grouping(top_node=_tfm, output=_ref.output, group=group)

    return _ref


def create_ai_vol(output, namespace, group=None):
    """Create vdb reference.

    Args:
        output (CPOutput): output to reference in vdb
        namespace (str): node name
        group (str): override parent group

    Returns:
        (CMayaAiVolume): vdb reference
    """
    assert isinstance(output, Seq)
    cmds.loadPlugin('mtoa', quiet=True)
    _seq = output
    _shp = pom.CMDS.createNode('aiVolume', name=namespace + 'Shape')
    _path = _seq[_seq.frames[0]]
    _shp.plug['filename'].set_val(_path)
    _tfm = _shp.to_parent().rename(namespace)
    _ns = str(_tfm)
    _shp.plug['useFrameExtension'].set_val(True)
    _ref = CMayaAiVolume(_tfm, path=_seq.path)

    prm_utils.apply_grouping(top_node=_tfm, output=_ref.output, group=group)

    return _ref


def create_rs_pxy(output, namespace, group=None):
    """Create redshift proxy reference.

    Args:
        output (CPOutput): path to proxy
        namespace (str): name for transform
        group (str): override parent group

    Returns:
        (CMayaRsProxyRef): proxy reference
    """
    _LOGGER.info('CREATE RS PXY %s', output)
    _node = load_redshift_proxy(output, name=namespace)
    _ref = CMayaRsProxyRef(_node.proxy)
    _LOGGER.info(' - NODE %s', _node)
    prm_utils.apply_grouping(
        top_node=_ref.top_node, output=_ref.output, group=group)

    return _ref


def create_rs_vol(output, namespace):
    """Create redshift proxy reference.

    Args:
        output (CPOutput): path to proxy
        namespace (str): name for transform

    Returns:
        (CMayaRsProxyRef): proxy reference
    """
    cmds.loadPlugin('redshift4maya', quiet=True)
    _vol = pom.CMDS.createNode("RedshiftVolumeShape")
    _vol.plug['fileName'].set_val(output.path.replace('.%04d.', '.####.'))
    _vol.plug['useFrameExtension'].set_val(True)

    # Fix name
    _vol = _vol.rename(f'{namespace}Shape')
    _vol.to_parent().rename(namespace)

    ui.raise_attribute_editor()
    cmds.refresh()

    return CMayaRsVolume(_vol)


def _find_type_nodes(class_, selected=False, referenced=None):
    """Read nodes of the given class in the current scene.

    Args:
        class_ (class): type of node to search for
        selected (bool): apply selected nodes filter
        referenced (bool): apply referenced state filter

    Returns:
        (CMayaNodeRef list): matching node ref objects
    """
    _LOGGER.debug('READ TYPE NODES %s', class_)
    if class_.TYPE not in cmds.allNodeTypes():
        return []
    _sel = cmds.ls(selection=True)

    _refs = []
    assert class_.TYPE
    for _node in pom.find_nodes(type_=class_.TYPE, referenced=referenced):
        _LOGGER.debug(' - ADDING NODE %s', _node)
        try:
            _ref = class_(_node)
        except (ValueError, RuntimeError) as _exc:
            _LOGGER.debug('   - FAILED TO BUILD REF %s', _exc)
            continue
        if selected and _ref.top_node not in _sel and _ref.node not in _sel:
            _LOGGER.debug('   - SELECTION FILTER REJECTED %s', _ref)
            continue
        _LOGGER.debug('   - CREATED REF %s', _ref)
        _refs.append(_ref)

    return _refs


def find_ai_standins(selected=False):
    """Find pipelined aiStandIn references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaAiStandIn list): aiStandIn refs
    """
    _LOGGER.log(9, 'READ AISTANDIN PIPE REFS')

    if 'aiStandIn' not in cmds.allNodeTypes():
        return []

    # Get list of aiStandIn nodes
    if selected:
        _ais_ss = []
        for _node in pom.get_selected(multi=True):
            _type = _node.object_type()
            _LOGGER.log(9, ' - CHECKING NODE %s %s', _node, _type)
            if _type == 'aiStandIn':
                _ais_ss.append(_node)
            elif _type == 'transform':
                _shp = _node.to_shp(catch=True)
                if _shp:
                    _shp_type = _shp.object_type()
                    _LOGGER.log(9, '   - CHECKING SHP %s %s', _shp, _shp_type)
                    if _shp_type == 'aiStandIn':
                        _ais_ss.append(_shp)
    else:
        _ais_ss = pom.CMDS.ls(type='aiStandIn', selection=selected)
    _LOGGER.log(9, ' - FOUND %d AISTANDINS %s', len(_ais_ss), _ais_ss)

    # Map to CMayaAiStandIn objects
    _asses = []
    for _ais_s in _ais_ss:
        _ais = _ais_s.to_parent()
        _LOGGER.log(9, ' - TESTING %s', _ais)
        try:
            _ass = CMayaAiStandIn(_ais)
        except ValueError as _exc:
            _LOGGER.log(9, '   - REJECTED %s', _exc)
            continue
        _LOGGER.log(9, '   - ACCEPTED %s', _ass)
        _asses.append(_ass)

    return _asses


def find_ai_vols(selected=False):
    """Read pipeline vdb refs.

    Args:
        selected (bool): only find selected refs

    Returns:
        (CMayaAiVolume list): vdb refs
    """
    _LOGGER.log(9, 'READ VDB PIPE REFS')

    if 'aiVolume' not in cmds.allNodeTypes():
        _LOGGER.log(9, ' - aiVolume NOT AVAILABLE')
        return []

    # Get list of aiVolume nodes
    if selected:
        _aivs = []
        for _node in pom.CMDS.ls(selection=True):
            _type = _node.object_type()
            _LOGGER.log(9, ' - CHECKING NODE %s %s', _node, _type)
            if _type == 'aiVolume':
                _aivs.append(_node)
            elif _type == 'transform':
                _shp = _node.to_shp(catch=True)
                if _shp:
                    _shp_type = _shp.object_type()
                    _LOGGER.log(9, '   - CHECKING SHP %s %s', _shp, _shp_type)
                    if _shp_type == 'aiVolume':
                        _aivs.append(_shp)
    else:
        _aivs = pom.CMDS.ls(type='aiVolume')
    _LOGGER.log(9, ' - FOUND %d aiVolume NODES', len(_aivs))

    # Map to CMayaAiVolume objects
    _vdbs = []
    for _aiv_s in _aivs:
        _aiv = _aiv_s.to_parent()
        try:
            _vdb = CMayaAiVolume(_aiv)
        except ValueError as _exc:
            _LOGGER.log(9, ' - REJECTED %s %s', _aiv, _exc)
            continue
        _vdbs.append(_vdb)
    return _vdbs


def find_img_planes(selected=False):
    """Read image planes from the current scene.

    Args:
        selected (bool): apply selected filter

    Returns:
        (CMayaImgPlaneRef list): image plane refs
    """
    return _find_type_nodes(class_=CMayaImgPlaneRef, selected=selected)


def find_file_nodes(selected=False):
    """Read file from the current scene.

    Args:
        selected (bool): apply selected filter

    Returns:
        (CMayaFileRef list): file refs
    """
    return _find_type_nodes(
        class_=CMayaFileRef, selected=selected, referenced=False)


def find_rs_dome_lights(selected=False):
    """Read RedshiftDomeLight references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaRsProxyRef list): redshift dome lights
    """
    return _find_type_nodes(class_=CMayaRsDomeLight, selected=selected)


def find_rs_pxys(selected=False):
    """Read RedshiftProxyMesh references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaRsProxyRef list): redshift proxy refs
    """
    return _find_type_nodes(class_=CMayaRsProxyRef, selected=selected)


def find_rs_volumes(selected=False):
    """Read RedshiftVolumeShape references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaRsProxyRef list): redshift volumes
    """
    return _find_type_nodes(class_=CMayaRsVolume, selected=selected)
