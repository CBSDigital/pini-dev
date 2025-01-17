"""Tools for managing pipelined node references in maya."""

import logging

from maya import cmds

from pini import dcc, pipe
from pini.utils import single, Seq, file_to_seq, to_seq

from maya_pini import open_maya as pom, ui
from maya_pini.utils import load_redshift_proxy

from . import prm_base

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
        _path = _path.replace('.####.', '.%04d.')
        if not _path:
            raise ValueError('Empty path')

        super().__init__(
            path or _path, namespace=str(self.node), node=node.shp,
            top_node=node)

    def update(self, out):
        """Update this node to a new output.

        Args:
            out (CPOutputSeq): new volume to apply
        """
        assert isinstance(out, Seq)
        _path = out.path.replace('.%04d.', '.####.')
        self.node.shp.plug['filename'].set_val(_path)


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


def create_ai_standin(path, namespace):
    """Create aiStandIn reference from the given path.

    Args:
        path (File|Seq): path to apply
        namespace (str): namespace to use

    Returns:
        (CMayaAiStandIn): reference
    """
    cmds.loadPlugin('mtoa', quiet=True)

    _shp = pom.CMDS.createNode('aiStandIn', name=namespace+'Shape')
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

    return _ref


def create_ai_vol(output, namespace):
    """Create vdb reference.

    Args:
        output (CPOutput): output to reference in vdb
        namespace (str): node name

    Returns:
        (CMayaAiVolume): vdb reference
    """
    assert isinstance(output, Seq)
    cmds.loadPlugin('mtoa', quiet=True)
    _seq = output
    _shp = pom.CMDS.createNode('aiVolume', name=namespace+'Shape')
    _path = _seq[_seq.frames[0]]
    _shp.plug['filename'].set_val(_path)
    _tfm = _shp.to_parent().rename(namespace)
    _ns = str(_tfm)
    _shp.plug['useFrameExtension'].set_val(True)
    _ref = CMayaAiVolume(_tfm, path=_seq.path)

    return _ref


def create_rs_pxy(output, namespace):
    """Create redshift proxy reference.

    Args:
        output (CPOutput): path to proxy
        namespace (str): name for transform

    Returns:
        (CMayaRsProxyRef): proxy reference
    """
    _LOGGER.info('CREATE RS PXY %s', output)
    _node = load_redshift_proxy(output, name=namespace)
    _LOGGER.info(' - NODE %s', _node)
    return CMayaRsProxyRef(_node.proxy)


def read_ai_standins(selected=False):
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


def read_ai_vols(selected=False):
    """Read pipeline vdb refs.

    Args:
        selected (bool): only find selected refs

    Returns:
        (CMayaAiVolume list): vdb refs
    """
    _LOGGER.log(9, 'READ VDB PIPE REFS')

    if 'aiVolume' not in cmds.allNodeTypes():
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

    # Map to CMayaAiVolume objects
    _vdbs = []
    for _aiv_s in _aivs:
        _aiv = _aiv_s.to_parent()
        try:
            _vdb = CMayaAiVolume(_aiv)
        except ValueError:
            continue
        _vdbs.append(_vdb)
    return _vdbs


def _read_type_nodes(class_, selected):
    """Read nodes of the given class in the current scene.

    Args:
        class_ (class): type of node to search for
        selected (bool): apply selected nodes filter

    Returns:
        (CMayaNodeRef list): matching node ref objects
    """
    if class_.TYPE not in cmds.allNodeTypes():
        return []
    _sel = cmds.ls(selection=True)

    _pxys = []
    assert class_.TYPE
    for _node in pom.find_nodes(type_=class_.TYPE):
        try:
            _pxy = class_(_node)
        except (ValueError, RuntimeError):
            continue
        if selected and _pxy.top_node not in _sel and _pxy.node not in _sel:
            continue
        _pxys.append(_pxy)

    return _pxys


def read_img_planes(selected=False):
    """Read image planes from the current scene.

    Args:
        selected (bool): apply selected filter

    Returns:
        (CMayaImgPlaneRef list): image plane refs
    """
    return _read_type_nodes(class_=CMayaImgPlaneRef, selected=selected)


def read_rs_pxys(selected=False):
    """Read RedshiftProxyMesh references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaRsProxyRef list): redshift proxy refs
    """
    return _read_type_nodes(class_=CMayaRsProxyRef, selected=selected)


def read_rs_dome_lights(selected=False):
    """Read RedshiftDomeLight references in the current scene.

    Args:
        selected (bool): return selected only

    Returns:
        (CMayaRsProxyRef list): redshift dome lights
    """
    return _read_type_nodes(class_=CMayaRsDomeLight, selected=selected)
