"""General tools for shading/texturing."""

import logging

import six

from maya import cmds

from pini import qt
from pini.utils import single, File, Dir, abs_path, EMPTY

from maya_pini import open_maya as pom
from maya_pini.utils import DEFAULT_NODES, to_namespace

_LOGGER = logging.getLogger(__name__)


class _Shader(pom.CNode):
    """Base class for any shader."""

    col_attr = 'color'
    out_col_attr = 'outColor'

    @property
    def col(self):
        """Obtain colour input plug.

        Returns:
            (CPlug): input colour
        """
        return self.plug[self.col_attr]

    @property
    def out_col(self):
        """Obtain output colour plug.

        Returns:
            (CPlug): output colour
        """
        return self.plug[self.out_col_attr]

    def apply_to(self, obj):
        """Assign this shader to the given object.

        Args:
            obj (str): object to apply to
        """
        _obj = obj
        try:
            _obj = pom.to_mesh(obj).shp
        except ValueError:
            pass  # Possible face assignment
        _se = self.to_se(create=True)
        cmds.sets(_obj, edit=True, forceElement=_se)

    def duplicate(self, name=None, upstream_nodes=True):
        """Duplicate this shading network.

        Args:
            name (str): node name
            upstream_nodes (bool): duplicate upstream nodes

        Returns:
            (Shader): duplicated shader
        """
        _dup = super(_Shader, self).duplicate(
            name=name, upstream_nodes=upstream_nodes)
        _shd = to_shd(_dup)
        _shd.to_se(create=True)
        return _shd

    def set_col(self, col):
        """Set colour of this shader.

        Args:
            col (str|File): colour to apply - can be:
             - name of colour (eg. IndianRed)
             - path to file texture to apply
        """
        if isinstance(col, six.string_types):
            _col = qt.to_col(col)
            self.col.set_val(_col)
        elif isinstance(col, File):
            _file = self.to_file(create=True)
            _file.plug['fileTextureName'].set_val(col.path)
        else:
            raise ValueError(col)

    def to_file(self, create=False):
        """Obtain this shader file input.

        Args:
            create (bool): create file node if not found

        Returns:
            (CNode|None): file node (if any)
        """
        _file = self.col.find_incoming(type_='file', plugs=False)
        if not _file and create:
            _file = pom.CMDS.shadingNode('file', asUtility=True)
            _file.plug['outColor'].connect(self.col)
        return _file

    def to_ftn(self):
        """Obtain file texture name for this shader (ie. path to texture).

        Returns:
            (File): file texture name
        """
        _file = self.to_file()
        assert _file
        return File(_file.plug['fileTextureName'].get_val())

    def to_geo(self):
        """Find geometry using this shader.

        Returns:
            (CNode list): nodes
        """
        _geos = []

        for _geo in (cmds.sets(self.to_se(), query=True) or []):
            _LOGGER.info('GEO %s', _geo)
            if '.' in _geo:  # Face assignment
                pass
            else:
                try:
                    _geo = pom.cast_node(_geo)
                except RuntimeError:
                    _LOGGER.warning(
                        ' - FAILED TO BUILD NODE %s (POSSIBLE DUPLICATE)', _geo)
                    continue
            _geos.append(_geo)
        return _geos

    def to_se(self, create=False):
        """To shading engine.

        Args:
            create (bool): create shading engine if one not found

        Returns:
            (CNode): shading group
        """
        _se = single(self.out_col.find_outgoing(plugs=False), catch=True)
        if not _se and create:
            _name = str(self)+"SG"
            _se = cmds.sets(
                name=_name, renderable=True, noSurfaceShader=True,
                empty=True)
            _se = pom.CNode(_se)
            self.out_col.connect(_se.plug['surfaceShader'])
        return _se


class _Lambert(_Shader):
    """Represents a Lambert texture."""


class _SurfaceShader(_Shader):
    """Represents a SurfaceShader texture."""

    col_attr = 'outColor'


def create_lambert(name='lambert', col=None):
    """Create a lambert texture.

    Args:
        name (str): texture node name
        col (CColor|str|File): colour to apply

    Returns:
        (Lambert): lambert texture
    """
    _LOGGER.debug('CREATE LAMBERT')
    _node = cmds.shadingNode('lambert', asShader=True, name=name)
    _LOGGER.debug(' - NODE %s', _node)
    _shd = _Lambert(_node)
    _LOGGER.debug(' - SHD %s', _shd)
    if col:
        _shd.set_col(col)
    return _shd


def create_file(ftn=None, colspace='sRGB', name='file'):
    """Create file texture node.

    Args:
        ftn (File): file texture name to apply
        colspace (str): colourspace to apply
        name (str): node name

    Returns:
        (CNode): file node
    """
    _file = pom.CMDS.shadingNode('file', asUtility=True, name=name)
    if ftn:
        _file.plug['fileTextureName'].set_val(ftn.path)
    _file.plug['colorSpace'].set_val(colspace)
    return _file


def create_surface_shader(name='surfaceShader', col=None):
    """Create a surface shader texture.

    Args:
        name (str): texture node name
        col (CColor|str|File): colour to apply

    Returns:
        (SurfaceShader): lambert texture
    """
    _node = cmds.shadingNode('surfaceShader', asShader=True, name=name)
    _shd = _SurfaceShader(_node)
    if col:
        _shd.set_col(col)
    return _shd


def find_shds(default=None, namespace=EMPTY):
    """Find shaders in the current scene.

    Args:
        default (bool): filter by default type (True will return
            only default shaders, False will exclude default shaders)
        namespace (str): filter by namespace

    Returns:
        (Shader list): matching shaders
    """
    _shds = set()
    _LOGGER.debug('FIND SHDS')
    for _se in sorted(set(pom.find_nodes(type_='shadingEngine'))):

        _LOGGER.debug(' - SE %s', _se)

        if default is not None:
            _is_default = _se in DEFAULT_NODES
            _LOGGER.debug('   - IS DEFAULT %d', _is_default)
            if _is_default != default:
                continue
        if namespace is not EMPTY and to_namespace(_se) != namespace:
            continue

        _shd = to_shd(_se)
        if not _shd:
            _LOGGER.debug('   - NO SHD')
            continue
        _LOGGER.debug('   - SHD %s', _shd)
        _shds.add(_shd)

    return sorted(_shds)


def to_ftn(base, ver_n=None, extn='jpg'):
    """Build a file texture name for the current workspace.

    Args:
        base (str): base for filename
        ver_n (int): version number to include
        extn (str): file extension

    Returns:
        (File): file texture name
    """
    _base = base.replace(':', '_')
    return to_ftn_root().to_file('{base}{ver}.{extn}'.format(
        base=_base, extn=extn,
        ver='v{:03d}'.format(ver_n) if ver_n else ''))


def to_ftn_root():
    """Obtain textures root for the current workspace.

    Returns:
        (Dir): textures root
    """
    _tex_ws = cmds.workspace(fileRuleEntry='textures') or 'textures'
    _tex_dir = cmds.workspace(expandName=_tex_ws)
    return Dir(abs_path(_tex_dir))


def to_shd(obj):
    """Obtain shader from the given object.

    If a mesh object is passed, the attached shader is used.

    Args:
        obj (any): object to read

    Returns:
        (Shader): shader
    """
    _node = pom.to_node(obj)
    _type = _node.object_type()
    _LOGGER.debug('TO SHD %s type=%s', obj, _type)

    # Determine shader based on type
    _se = None
    if _node.shp:
        _LOGGER.debug(' - SHADED OBJECT')
        _ses = _node.shp.find_outgoing(
            type_='shadingEngine', connections=False, plugs=False)
        _se = single(_ses, catch=True)
    elif _type == 'lambert':
        _shd = _Lambert(_node)
    elif _type == 'shadingEngine':
        _se = _node
    elif _type in ['VRayMtl']:
        _shd = _Shader(_node)
    else:
        _shd = None

    # Build shader from shading engine
    if _se:
        _LOGGER.debug(' - SE %s', _se)
        _shd = _se.plug['surfaceShader'].find_incoming(plugs=False)
        if _shd:
            _type = _shd.object_type()
            _LOGGER.debug(' - SHD %s', _shd)
            _class = {
                'lambert': _Lambert}.get(_type, _Shader)
            _shd = _class(_shd)

    return _shd
