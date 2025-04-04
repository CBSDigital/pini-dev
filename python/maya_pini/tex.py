"""General tools for shading/texturing."""

import logging

from maya import cmds

from pini import qt
from pini.utils import single, File, Dir, abs_path, EMPTY, Image

from maya_pini import open_maya as pom
from maya_pini.utils import DEFAULT_NODES, to_namespace, to_node

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

    def assign_to(self, obj):
        """Assign this shader to the given object.

        Args:
            obj (str): object to apply to
        """
        _LOGGER.debug('ASSIGN %s TO %s (%s)', self, obj, type(obj).__name__)
        if isinstance(obj, list):
            for _item in obj:
                self.assign_to(_item)
            return

        _obj = obj
        try:
            _obj = pom.to_mesh(obj).shp
        except ValueError:
            pass  # Possible face assignment
        _se = self.to_se(create=True)
        _LOGGER.debug(' - ADD %s TO %s', _obj, _se)
        cmds.sets(_obj, edit=True, forceElement=_se)

    def duplicate(self, name=None, upstream_nodes=True, class_=None):  # pylint: disable=arguments-differ
        """Duplicate this shading network.

        Args:
            name (str): node name
            upstream_nodes (bool): duplicate upstream nodes
            class_ (class): override node class

        Returns:
            (Shader): duplicated shader
        """
        assert not class_
        _dup = super().duplicate(
            name=name, upstream_nodes=upstream_nodes, class_=pom.CNode)
        _LOGGER.info('DUPLICATE %s %s', self, _dup)
        assert _dup
        _shd = _Shader(_dup)
        assert _shd
        _LOGGER.info(' - SHD %s', _shd)
        _shd.to_se(create=True)
        return _shd

    def set_col(self, col, colspace=None):
        """Set colour of this shader.

        Args:
            col (str|File): colour to apply - can be:
                - name of colour (eg. IndianRed)
                - path to file texture to apply
            colspace (str): colourspace for file node (if applicable)
        """
        if isinstance(col, str):
            _col = qt.to_col(col)
            self.col.set_val(_col)
        elif isinstance(col, File):
            self.set_ftn(col, colspace=colspace)
        else:
            raise ValueError(col)

    def set_ftn(self, file_, colspace=None):
        """Apply the given file texture name to this shader (ie. apply file).

        Args:
            file_ (File): texture to apply
            colspace (str): apply colour space
        """
        _ftn = File(file_)
        _file = self.to_file(create=True)
        _file.plug['fileTextureName'].set_val(_ftn.path)
        if colspace:
            _file.plug['colorSpace'].set_val(colspace)

    def to_assignments(self):
        """Read this shader's list of assignments.

        Returns:
            (str list): assigments
        """
        return cmds.sets(self.to_se(), query=True) or []

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
            (Image): file texture name
        """
        _file = self.to_file()
        assert _file
        return Image(_file.plug['fileTextureName'].get_val())

    def to_geo(self, faces=None, node=None):
        """Find geometry using this shader.

        Args:
            faces (bool): filter by face assignments
            node (str): filter by node name

        Returns:
            (CNode list): nodes
        """
        _geos = []
        for _geo in self.to_assignments():
            _LOGGER.debug('GEO %s', _geo)

            if node and node != to_node(_geo):
                continue

            # Check for face assignment
            _is_face = '.' in _geo
            if faces is not None and _is_face != faces:
                continue

            # Cast node
            if not _is_face:
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
        _LOGGER.debug('TO SE %s', self)
        _outs = self.out_col.find_outgoing(plugs=False, type_='shadingEngine')
        _se = single(_outs, catch=True)
        if not _se and create:
            _name = str(self) + "SG"
            _se = cmds.sets(
                name=_name, renderable=True, noSurfaceShader=True,
                empty=True)
            _se = pom.CNode(_se)
            self.out_col.connect(_se.plug['surfaceShader'])
        return _se

    def unassign(self, node=None):
        """Remove this shader from its geometry.

        Args:
            node (str): only remove the given geometry node
        """
        _engine = self.to_se()
        _assigns = self.to_assignments()
        _LOGGER.info('UNAPPLY %s', _assigns)
        for _assign in _assigns:
            if node and node != to_node(_assign):
                continue
            _LOGGER.info(' - UNAPPLY %s', _assign)
            cmds.sets(_assign, edit=True, remove=_engine)


class _Lambert(_Shader):
    """Represents a Lambert texture."""


class _SurfaceShader(_Shader):
    """Represents a SurfaceShader texture."""

    col_attr = 'outColor'


def create_lambert(name='lambert', col=None, colspace='Raw'):
    """Create a lambert texture.

    Args:
        name (str): texture node name
        col (CColor|str|File): colour to apply
        colspace (str): colourspace for file node (if applicable)

    Returns:
        (Lambert): lambert texture
    """
    _LOGGER.debug('CREATE LAMBERT')
    _node = cmds.shadingNode('lambert', asShader=True, name=name)
    _LOGGER.debug(' - NODE %s', _node)
    _shd = _Lambert(_node)
    _LOGGER.debug(' - SHD %s', _shd)
    if col:
        _shd.set_col(col, colspace=colspace)
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
    _LOGGER.debug('CREATE FILE')
    _file = pom.CMDS.shadingNode('file', asUtility=True, name=name)
    _LOGGER.debug(' - FILE %s', _file)
    if ftn:
        _ftn = File(ftn)
        _file.plug['fileTextureName'].set_val(_ftn.path)
        _LOGGER.debug(' - APPLY FTN %s', _ftn.path)
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

        _shd_node = _se.plug['surfaceShader'].find_incoming(plugs=False)
        if not _shd_node:
            _LOGGER.debug('   - NO SHD')
            continue
        _shd = to_shd(_shd_node)
        if not _shd:
            _shd = _Shader(_shd_node)
        if not _shd:
            raise RuntimeError(_shd_node)
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
    _ver = f'_v{ver_n:03d}' if ver_n else ''
    return to_ftn_root().to_file(f'{_base}{_ver}.{extn}')


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
    _se = _shd = None
    if _node.shp:
        _LOGGER.debug(' - SHADED OBJECT')
        _ses = _node.shp.find_outgoing(
            type_='shadingEngine', connections=False, plugs=False)
        _se = single(_ses, catch=True)
        _LOGGER.debug(' - ENGINE %s %s', _se, _ses)
    elif _type == 'lambert':
        _shd = _Lambert(_node)
    elif _type == 'surfaceShader':
        _shd = _SurfaceShader(_node)
    elif _type == 'shadingEngine':
        _se = _node
    elif _type in ['VRayMtl', 'VRayCarPaintMtl', 'VRayBlendMtl', 'phong']:
        _shd = _Shader(_node)

    # Try finding connected shading engines (eg. new type of shading node)
    if not _se and not _shd:
        _ses = _node.find_outgoing(
            type_='shadingEngine', connections=False, plugs=False)
        _se = single(_ses, catch=True)
        _LOGGER.debug(' - ENGINE %s %s', _se, _ses)

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


DEFAULT_SHD = to_shd('lambert1')
