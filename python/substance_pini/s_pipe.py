"""Pipeline tools for substance."""

import logging

import substance_painter

from pini import qt, pipe
from pini.utils import File, Dir, abs_path


_LOGGER = logging.getLogger(__name__)


def export_textures(
        work=None, browser=False, extn='png', progress=None, force=False):
    """Export textures from current scene.

    Args:
        work (CCPWork): work file
        browser (bool): open export folder in brower
        extn (str): texture image format
        progress (ProgressDialog): progress bar
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): texture outputs
    """

    # Find text template
    _work = work or pipe.CACHE.obt_cur_work()
    assert _work
    _tmpl_name = 'texture_seq'
    _tmpl = _work.job.find_template(_tmpl_name, dcc_='substance', catch=True)
    if not _tmpl:
        raise RuntimeError(
            f'No "{_tmpl_name}" template found in job "{_work.job.name}" - '
            'unable to export textures')

    _pub_dir = _to_pub_dir(work=_work, template=_tmpl)
    _cfg = _to_export_cfg(pub_dir=_pub_dir, extn=extn)

    # Run export
    _pub_dir.mkdir()
    _pub_dir.flush(force=force)
    if browser:
        assert _pub_dir.exists()
        _pub_dir.browser()
    _result = substance_painter.export.export_project_textures(_cfg)
    if _result.status != substance_painter.export.ExportStatus.Success:
        _LOGGER.error(' - EXPORT ERROR %s', _result.message)
        raise RuntimeError('Export textures failed')
    if progress:
        progress.set_pc(50)
    _LOGGER.info(' - EXPORT COMPLETE')

    # Find exported textures to rename
    _to_rename = []
    _outs = []
    for _shd, _paths in _result.textures.items():
        _LOGGER.info(" - SHD %s", _shd)
        _shd, _ = _shd
        _LOGGER.info("   - SHD %s", _shd)
        for _path in _paths:
            _LOGGER.info('   - TEX FILE %s', _path)

            # Parse filename
            _orig_file = File(_path)
            _orig_root, _suffix = _orig_file.filename.split(f'_{_shd}_')
            _chan_l, _udim, _extn = _suffix.split('.')
            _orig_seq = _orig_file.to_dir().to_seq(
                f'{_orig_root}_{_shd}_{_chan_l}.<UDIM>.{_orig_file.extn}')
            _LOGGER.info('   - ORIG SEQ %s', _orig_seq)
            assert _orig_seq[int(_udim)] == _path
            assert len(_udim) == 4
            assert _udim.isdigit()

            # Build output filename
            _chan = ''.join(_chr for _chr in _chan_l if _chr.isupper())
            _out_seq = _work.to_output(
                _tmpl, output_name=_shd, output_type=_chan, extn=_extn)
            if _out_seq in _outs:
                _LOGGER.info('     (ALREADY HANDLED)')
                continue
            _outs.append(_out_seq)
            _LOGGER.info('     -> TEX OUT %s', _out_seq)
            _to_rename.append((_orig_seq, _out_seq))

    # Rename to apply naming conventions
    _LOGGER.info('APPLY RENAME')
    for _orig_seq, _out_seq in qt.progress_bar(
            _to_rename, 'Renaming {:d} texture set{}'):
        _LOGGER.info(' - RENAME %s', _orig_seq)
        _LOGGER.info('    - TARGET %s', _out_seq)
        assert _orig_seq.exists()
        _orig_seq.move_to(_out_seq)
    _LOGGER.info(' - RENAME COMPLETE')

    return sorted(_outs)


def _to_pub_dir(work, template):
    """Obtain publish dir for the given work file.

    NOTE: substance texture export handle see // mounts

    Args:
        work (CCPWork): work file
        template (CPTemplate): texture file template

    Returns:
        (Dir): publish dir
    """
    _pub_dir = work.to_output(
        template, output_name='null', output_type='C',
        udim_u='10', udim_v='01', extn='png').to_dir()
    _LOGGER.info(" - PUB DIR %s", _pub_dir)
    _pub_dir = Dir(abs_path(_pub_dir, mode='drive'))
    assert not _pub_dir.path.startswith('//')
    return _pub_dir


# def _to_disk_path(path):
#     # assert _pub_dir.path.startswith('//phoenix/Projects')

#     # # Convert to mount
#     # for _mount in MOUNTS:
#     #     _path = _pub_dir.path.replace('//phoenix/Projects', _mount)
#     #     _LOGGER.debug(' - CHECKING %s', _path)
#     #     if os.path.exists(_path):
#     #         _pub_dir = Dir(_path)
#     #         break
#     # else:
#     #     raise RuntimeError(f'Failed to find mount {_pub_dir}')
#     # assert _pub_dir.exists()
#     # _LOGGER.info(f' - PUB DIR {_pub_dir}')

#     return _pub_dir


def _to_export_cfg(pub_dir, extn, size=2048):
    """Build export config dict.

    Args:
        pub_dir (Dir): publish dir
        extn (str): export format
        size (int): export size (in pixels)

    Returns:
        (dict): export config
    """
    _name = "PBR Metallic Roughness"
    _preset = substance_painter.resource.ResourceID(
        context="starter_assets", name=_name)

    _shds = []
    _export_list = []
    for _shd in substance_painter.textureset.all_texture_sets():
        _shds.append(_shd)
        _export_list.append({"rootPath": _shd.name})

    _cfg = {
        "exportShaderParams": False,
        "exportPath": pub_dir.path,
        "defaultExportPreset": _preset.url(),
        "exportList": _export_list,
        "exportParameters": [{
            "parameters": {
                "fileFormat": extn,
                "bitDepth": "8",
                "dithering": True,
                "paddingAlgorithm": "infinite",
                'size': size,
            }}]}

    return _cfg
