"""General maya utilies for inputtting/outputting files."""

import logging
import os

from maya import cmds, mel

from pini import icons
from pini.utils import File, wrap_fn, Seq

from . import mu_dec, mu_misc

_LOGGER = logging.getLogger(__name__)


def _apply_auto_workspace_update(file_, update_workspace=None):
    """Update maya workspace for the given file.

    This is only enabled if $PINI_MAYA_MANAGE_WORKSPACE is set. If it is
    enabled, the workspace is set to the same directory as the current
    work file.

    ie. <dir>/file_v001.mb -> <dir>/workspace

    Args:
        file_ (File): current work file
        update_workspace (bool): force update behaviour
            (ie. ignore PINI_MAYA_MANAGE_WORKSPACE)
    """
    _update_ws = update_workspace
    if _update_ws is None:
        _env = os.environ.get('PINI_MAYA_MANAGE_WORKSPACE')
        if _env in ('0', 'False'):
            _update_ws = False
        else:
            _update_ws = True  # Default is True
    if not _update_ws:
        return

    _ws = file_.to_dir().to_subdir('workspace')
    mu_misc.set_workspace(_ws)


def _set_env(key, val):
    """Wrappable function for settings an environment variable.

    Args:
        key (str): name of enviromental variable to set
        val (str): enviromental variable value
    """
    os.environ[key] = val


def _del_env(key):
    """Wrappable function for deleting an enviroment variable.

    Args:
        key (str): name of enviromental variable to delete
    """
    del os.environ[key]


def load_scene(
        file_, force=False, lazy=False, load_refs=True, supress_popups=False):
    """Load the given scene.

    Args:
        file_ (str): file to load
        force (bool): force load without warnings
        lazy (bool): don't load scene if it's already open
        load_refs (bool): load file references
        supress_popups (bool): supress popup warnings on scene load (eg. OCIO)
    """
    from pini import dcc, qt

    # Apply supress popups
    _revert = None
    if supress_popups:
        _val = os.environ.get('MAYA_IGNORE_DIALOGS')
        if _val:
            _revert = wrap_fn(_set_env, 'MAYA_IGNORE_DIALOGS', _val)
        else:
            _revert = wrap_fn(_del_env, 'MAYA_IGNORE_DIALOGS')
        os.environ['MAYA_IGNORE_DIALOGS'] = '1'

    # Prepare load
    _file = File(file_)
    if lazy and _file.path == dcc.cur_file():
        return
    if not force:
        dcc.handle_unsaved_changes()
    if not _file.exists():
        raise OSError('Missing file')

    # Check plugins
    if _file.extn == 'fbx':
        cmds.loadPlugin('fbxmaya', quiet=True)

    _kwargs = {}
    if not load_refs:
        _kwargs['loadReferenceDepth'] = 'none'
    try:
        cmds.file(_file.path, open=True, force=True, prompt=False,
                  ignoreVersion=True, **_kwargs)
    except RuntimeError as _exc:

        # Print error
        _LOGGER.info('ERROR LOADING SCENE %s', _file.path)
        _LOGGER.info('######### LOAD ERROR START #########')
        print()
        print(str(_exc).strip())
        print()
        _LOGGER.info('######### LOAD ERROR END #########')

        # Notify
        _tail = str(_exc).strip().split('\n')[-1]
        qt.notify(
            'Maya errored loading this file:\n\n{}\n\n{}\n\n'
            'See the script editor for more details.'.format(
                _file.path, _tail),
            title='Load Error', icon=icons.find('Hot Pepper'), verbose=0)

    if _revert:
        _revert()
    _apply_auto_workspace_update(_file)


def _run_scanner():
    """Run maya scanner to check for malware."""
    try:
        cmds.loadPlugin('MayaScanner', quiet=True)
    except RuntimeError:
        _LOGGER.info(
            'Failed to load MayaScanner plugin - unable to check for malware')
        return
    cmds.MayaScan()


def _fix_viewport_callbacks():
    """Fix viewport callbacks CgAbBlastPanelOptChangeCallback error."""
    _LOGGER.info('FIXING VIEWPORT CALLBACKS')
    for _model_panel in cmds.getPanel(typ="modelPanel"):
        _callback = cmds.modelEditor(
            _model_panel, query=True, editorChanged=True)
        if _callback == "CgAbBlastPanelOptChangeCallback":
            _LOGGER.info(' - REMOVED CALLBACK %s %s', _model_panel, _callback)
            cmds.modelEditor(_model_panel, edit=True, editorChanged="")


def load_redshift_proxy(path, name='proxy'):
    """Load a redshift proxy file.

    Args:
        path (str): path to proxy file
        name (str): node name

    Returns:
        (CMesh): proxy mesh
    """
    _LOGGER.info('LOAD REDSHIFT PROXY %s', path)
    from maya_pini import open_maya as pom, ui

    _name = mu_misc.to_unique(name)
    _pxy_name = mu_misc.to_unique(name+'Proxy')
    _shp_name = mu_misc.to_unique(name+'Shape')

    # Check path
    if isinstance(path, Seq):
        _path = path
        _anim = True
    else:
        _path = File(path)
        _anim = False
    _LOGGER.info(' - PATH %s', _path)
    assert _path.exists()

    # Create proxy node
    cmds.loadPlugin('redshift4maya', quiet=True)
    cmds.select(clear=True)
    _cmd = (
        'redshiftProxyDoCreate("{proxy}", "{shape}", "{path}", '
        '"{transform}")'.format(
            path=_path.path.replace('.%04d.', '.####.'),
            transform=_name, proxy=_pxy_name, shape=_shp_name))
    _LOGGER.debug(' - CMD %s', _cmd)
    _pxy, _shp = mel.eval(_cmd)
    _LOGGER.debug(' - PXY %s', _pxy)

    # Clean up
    _mesh = pom.CMesh(mu_misc.to_parent(_shp))
    _mesh = _mesh.rename(name)
    _LOGGER.debug(' - MESH %s', _mesh)
    _mesh.proxy = pom.CNode(_pxy)
    assert hasattr(_mesh, 'proxy')
    _mesh.set_outliner_col('Coral')
    assert isinstance(_mesh, pom.CMesh)

    # Setup anim
    if _anim:
        _mesh.proxy.plug['useFrameExtension'].set_val(True)
        cmds.select(_mesh.proxy)
        ui.raise_attribute_editor()  # force callback
        cmds.refresh()

    return _mesh


def save_scene(file_=None, selection=False, revert=None, force=False):
    """Save scene.

    Args:
        file_ (str): save path
        selection (bool): export selection
        revert (bool): revert filename
        force (bool): overwrite existing file without warning dialog
    """
    from pini import qt, dcc

    _revert = revert
    if _revert is None:
        _revert = selection

    # Get file object
    _cur_file = dcc.cur_file()
    _file = file_ or _cur_file
    if not _file:
        raise RuntimeError('Unable to determine save path')
    _file = File(_file)
    _file.test_dir()
    _file.delete(wording='Replace', force=force)

    _apply_auto_workspace_update(_file)

    # Apply save
    if not force and _file.exists():
        qt.ok_cancel('Overwrite existing file?\n\n{}'.format(_file.path))
    _type = {'ma': 'mayaAscii', 'mb': 'mayaBinary'}[_file.extn]
    cmds.file(rename=_file.path)
    if selection:
        cmds.file(exportSelected=True, type=_type)
    else:
        cmds.file(save=True, type=_type)
    if _revert:
        cmds.file(rename=_cur_file)


@mu_dec.hide_img_planes
def save_abc(  # pylint: disable=too-many-branches
        abc=None, geo=None, job_arg=None, mode='export', format_='Ogawa',
        uv_write=True, world_space=True, write_visibility=True, range_=None,
        check_geo=True, step=None, write_col_sets=True, renderable_only=True,
        strip_namespaces=True, attrs=(), force=False):
    """Save an abc to disk.

    Args:
        abc (str): path to abc
        geo (str list): geo to export
        job_arg (str): override job_arg (all other args are ignored)
        mode (str): execute mode
            export - save abc to disk
            job_arg - just return job arg
        format_ (str): export format (Ogawa/HDF)
        uv_write (bool): write uvs
        world_space (bool): export in world space
        write_visibility (bool): write visibility channel
        range_ (tuple): override export range
        check_geo (bool): check geometry in list exists
        step (float): step size in frames
        write_col_sets (bool): apply -writeColorSets flag
        renderable_only (bool): export only renderable (visible) geometry
        strip_namespaces (bool): remove namespaces in abc
        attrs (list): additional attributes to export
        force (bool): replace existing without confirmation

    Returns:
        (File): exported abc
        (str): job arg (if in job_arg mode)
    """
    _LOGGER.debug('EXPORT ABC')
    assert format_ in ('Ogawa', 'HDF')

    # Determine abc file
    _abc = None
    if abc:
        _abc = File(abc)

    # Build job arg
    if job_arg:
        _job_arg = job_arg
    else:
        _job_arg = ""
        _geos = geo if isinstance(geo, list) else [geo]
        _LOGGER.debug(' - GEOS %s', _geos)
        _job_arg += "-dataFormat {} ".format(format_)
        _job_arg += '-eulerFilter '
        if strip_namespaces:
            _job_arg += '-stripNamespaces '
        if range_:
            _start, _end = range_
            _start -= 1
            _end += 1
            _job_arg += '-frameRange {:d} {:d} '.format(_start, _end)
        if uv_write:
            _job_arg += '-uvWrite '
        if write_visibility:
            _job_arg += '-writeVisibility '
        if world_space:
            _job_arg += '-worldSpace '
        if write_col_sets:
            _job_arg += '-writeColorSets '
        if renderable_only:
            _job_arg += '-renderableOnly '
        if step:
            _job_arg += '-step {:f} '.format(step)
        for _attr in attrs:
            _job_arg += '-attr {} '.format(_attr)
        for _geo in _geos:
            _job_arg += "-root {} ".format(_geo)
            if check_geo:
                assert cmds.objExists(_geo)
        _job_arg += "-file '{}'".format(_abc.path)
        _job_arg = _job_arg.strip()
    _LOGGER.debug(' - JOB ARG %s', _job_arg)

    # Apply execution mode
    if mode == 'job_arg':
        return _job_arg
    if mode == 'export':
        return _generate_abc(job_arg=_job_arg, abc=_abc, force=force)
    raise ValueError(mode)


def _generate_abc(job_arg, abc, force=False):
    """Write abc to disk.

    Args:
        job_arg (str): AbcExport job arg
        abc (File): abc to generate
        force (bool): replace existing without confirmation

    Returns:
        (File): abc that was generated
    """
    cmds.loadPlugin('AbcExport', quiet=True)

    abc.delete(wording='Replace', force=force)
    abc.test_dir()

    _LOGGER.info('cmds.AbcExport(jobArg="%s")', job_arg)
    cmds.AbcExport(jobArg=job_arg)
    if abc:
        assert abc.exists()

    return abc


def save_ass(geo, ass, force=False):
    """Save ass file to disk.

    Args:
        geo (str list): geometry to export
        ass (str): path to ass file to write to
        force (bool): overwrite existing without confirmation
    """
    cmds.loadPlugin('mtoa', quiet=True)

    _ass = File(ass)
    if ass.extn == 'ass':
        _compressed = False
    elif ass.filename.endwith('.ass.gz'):
        _compressed = True
    else:
        raise ValueError(ass)
    cmds.select(geo)

    _ass.delete(wording='Replace', force=force, icon=icons.find('Peach'))
    assert not _ass.exists()
    _ass.test_dir()
    cmds.arnoldExportAss(
        filename=_ass.path,
        selected=True,
        shadowLinks=False,
        mask=6399,
        lightLinks=False,
        compressed=_compressed,
        boundingBox=True,
        cam='perspShape')
    assert _ass.exists()


def _mel(cmd):
    """Execute mel command.

    Args:
        cmd (str): mel command
    """
    _LOGGER.info(cmd)
    mel.eval(cmd)


def _bool_to_mel(val):
    """Convert a boolean value to mel.

    Args:
        val (bool): value to convert

    Returns:
        (str): mel value
    """
    return {True: 'true', False: 'false'}[val]


def save_fbx(
        file_, selection=True, constraints=True, animation=False,
        version='FBX201600', range_=None, step=1.0, force=False):
    """Save fbx file to disk.

    Args:
        file_ (File): file to save to
        selection (bool): export selection
        constraints (bool): export constraints
        animation (bool): export animation
        version (str): fbx version
        range_ (tuple): start/end (for complex animation)
        step (float): step size in frames (for complex animation)
        force (bool): replace existing without confirmation
    """
    from pini import dcc
    cmds.loadPlugin("fbxmaya", quiet=True)

    if not selection:
        raise NotImplementedError

    _file = File(file_)
    _file.delete(wording='replace', force=force)
    _file.test_dir()

    _mel('FBXResetExport')

    cmds.FBXProperty('Export|AdvOptGrp|UI|ShowWarningsManager', '-v', 0)

    _mel('FBXExportFileVersion -v "{}"'.format(version))
    _mel('FBXExportSmoothingGroups -v true')
    _mel('FBXExportShapes -v true')
    _mel('FBXExportSkins -v true')
    _mel('FBXExportTangents -v true')
    _mel('FBXExportSmoothMesh -v false')

    _mel('FBXExportBakeComplexAnimation -v {}'.format(_bool_to_mel(animation)))
    _mel('FBXExportConstraints -v {}'.format(_bool_to_mel(constraints)))

    _range = range_ or dcc.t_range()
    _mel('FBXExportBakeComplexStart -v {:f}'.format(_range[0]))
    _mel('FBXExportBakeComplexEnd -v {:f}'.format(_range[1]))
    _mel('FBXExportBakeComplexStep -v {:f}'.format(step))

    _mel('FBXExport -f "{}" -s'.format(_file.path))

    assert _file.exists()


def save_obj(file_, selection=True, materials=True, force=False):
    """Save obj file to disk.

    Args:
        file_ (str): path to save obj to
        selection (bool): export selection
        materials (bool): export materials mtl file
        force (bool): overwrite existing without confirmation
    """
    cmds.loadPlugin("objExport", quiet=True)

    if selection:
        if not cmds.ls(selection=True):
            raise RuntimeError('No geometry selected')
    else:
        raise NotImplementedError

    _file = File(file_)
    _file.delete(force=force)
    _opts = ';'.join([
        'groups={:d}'.format(True),
        'ptgroups={:d}'.format(True),
        'materials={:d}'.format(materials),
        'smoothing={:d}'.format(True),
        'normals={:d}'.format(True),
    ])

    # Export obj
    _file.to_dir().mkdir()
    cmds.file(
        _file.path, force=True, options=_opts, type="OBJexport",
        exportSelected=True)


def save_redshift_proxy(path, selection=True, animation=False):
    """Save redshift proxy.

    Args:
        path (File|Seq): path to save to
        selection (bool): export selection
        animation (bool): export animation

    Returns:
        (File): path to proxy
    """
    _LOGGER.info('SAVE REDSHIFT PROXY %s anim=%d', path, animation)
    from pini import dcc
    cmds.loadPlugin('redshift4maya', quiet=True)

    _opts = "exportConnectivity=0;enableCompression=0;keepUnused=0;"
    if not animation:
        _path = File(path)
        _export_path = _path.path
    else:
        _opts += "startFrame={start:d};endFrame={end:d};frameStep=1".format(
            start=dcc.t_start(int), end=dcc.t_end(int))
        _path = Seq(path)
        assert isinstance(_path, Seq)
        _export_path = '{}/{}.{}'.format(_path.dir, _path.base, _path.extn)
        _export_path = '{}/{}'.format(_path.dir, _path.base)
        _export_path = '{}/{}.####.{}'.format(_path.dir, _path.base, _path.extn)
    _LOGGER.info(' - EXPORT PATH %s', _export_path)

    _path.delete(wording='Replace')
    _path.test_dir()
    assert not _path.exists()
    assert _path.to_dir().exists()
    cmds.file(
         _export_path, force=True, preserveReferences=True, options=_opts,
         exportSelected=selection, type="Redshift Proxy")
    if animation:
        _path.to_frames(force=True)
    _LOGGER.info(' - PATH %s', _path)
    assert _path.exists()
    return _path
