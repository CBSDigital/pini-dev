"""Pipeline tools for substance."""

import logging
import os

import substance_painter

from pini import qt, pipe
from pini.utils import File, Dir, abs_path, single

_LOGGER = logging.getLogger(__name__)


def export_textures(
        work=None, browser=False, extn='png', size=4096, sets=None,
        progress=None, force=False):
    """Export textures from current scene.

    Args:
        work (CCPWork): work file
        browser (bool): open export folder in brower
        extn (str): texture image format
        size (int): texture size (in pixels)
        sets (str list): export only the given texture sets
        progress (ProgressDialog): progress bar
        force (bool): replace existing without confirmation

    Returns:
        (CPOutput list): texture outputs
    """
    _LOGGER.info('EXPORT TEXTURES %s', sets)

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
    _cfg = to_export_cfg(
        pub_dir=_pub_dir, extn=extn, size=size, sets=sets)
    _LOGGER.info(' - CFG %s', _cfg)

    # Run export
    _result = _exec_export_textures(
        pub_dir=_pub_dir, cfg=_cfg, browser=browser)
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
            _LOGGER.info('     - ROOT / SUFFIX %s %s', _orig_root, _suffix)

            # Handle udim option disabled
            if _suffix.count('.') < 2:
                # _chan_l, _extn = _suffix.rsplit('.', 2)
                raise RuntimeError(f'Failed to find UDIM in path {_path}')

            _chan_l, _udim, _extn = _suffix.rsplit('.', 2)
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


def to_export_cfg(pub_dir, extn, preset=None, size=4096, sets=None):
    """Build export config dict.

    Args:
        pub_dir (Dir): publish dir
        extn (str): export format
        preset (str): export preset url
        size (int): export size (in pixels)
        sets (str list): export only the given texture sets

    Returns:
        (dict): export config
    """

    # Determine preset
    _preset_url = preset
    if not _preset_url:
        _preset_url = os.environ.get('PINI_SUBSTANCE_EXPORT_PRESET')
    if not _preset_url:
        _preset_url = "starter_assets/PBR Metallic Roughness"
    _LOGGER.info(' - EXPORT PRESET %s', _preset_url)
    _ctx, _name = _preset_url.split('/')
    _preset = substance_painter.resource.ResourceID(
        context=_ctx, name=_name)

    _shds = []
    _export_list = []
    for _shd in substance_painter.textureset.all_texture_sets():
        if sets and _shd.name not in sets:
            continue
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


def to_export_data(sets=None):
    """Build dict of export data for the current scene.

    Args:
        sets (str list): export only these sets

    Returns:
        (dict): texture set / list of export files data
    """
    _pub_dir = Dir(abs_path('~/tmp'))
    _cfg = to_export_cfg(_pub_dir, extn='png')
    _parms = single(_cfg['exportParameters'])['parameters']
    _res = _parms['size']
    _bits = _parms['bitDepth']
    _sets = [_item['rootPath'] for _item in _cfg['exportList']]

    # Build export data
    _raw_exports = substance_painter.export.list_project_textures(_cfg)
    _exports = {}
    for _set in _sets:
        if sets and _set not in sets:
            continue
        _files = _raw_exports[(_set, '')]
        _data = []
        for _file in _files:
            _data.append({
                'filename': File(_file).filename,
                'res': _res,
                'bits': _bits})
        _exports[_set] = _data

    return _exports


def _exec_export_textures(pub_dir, cfg, browser=False, force=False):
    """Execute texture export.

    Args:
        pub_dir (Dir): publish dir
        cfg (dict): export config
        browser (bool): open export folder in brower
        force (bool): replace existing without confirmation

    Returns:
        (dict): export result
    """

    pub_dir.mkdir()
    pub_dir.flush(force=force)
    if browser:
        assert pub_dir.exists()
        pub_dir.browser()
    _result = substance_painter.export.export_project_textures(cfg)
    if _result.status != substance_painter.export.ExportStatus.Success:
        _LOGGER.error(' - EXPORT ERROR %s', _result.message)
        raise RuntimeError('Export textures failed')

    return _result
