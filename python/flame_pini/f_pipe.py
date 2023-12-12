"""Tools for managing flame's interaction with the pipeline."""

import platform
import logging
import os
import time

import flame

from pini import icons, dcc, pipe, qt
from pini.tools import error, release, usage
from pini.utils import Dir, single, File, plural

_LOGGER = logging.getLogger(__name__)
_PRESETS_DIR = Dir('/opt/Autodesk/shared/export/presets')


def _find_export_preset(out):
    """Find export preset to use for the given output.

    Args:
        out (CPOutput): output being exported

    Returns:
        (File): export preset file
    """
    if out.extn == 'exr':
        _path = _PRESETS_DIR.to_file(
            'file_sequence/'
            'ACES 16-bit EXR Sequence - Start Frame 1001 - For Studio.xml')
        _file = File(_path)
        if not _file.exists():
            raise RuntimeError('Missing preset file '+_file.path)
        return _file

    _presets_dir = Dir(flame.PyExporter.get_presets_dir(
        flame.PyExporter.PresetVisibility.Autodesk,
        flame.PyExporter.PresetType.Image_Sequence))
    _LOGGER.info('PRESETS DIR %s', _presets_dir)
    _fmts = _presets_dir.find(depth=1, full_path=False, type_='d')
    _LOGGER.info('FMTS %s', _fmts)
    _fmt = {'exr': 'OpenEXR'}[out.extn]
    assert _fmt in _fmts
    _fmt_dir = _presets_dir.to_subdir(_fmt)
    _presets = _fmt_dir.find(depth=1, type_='f', full_path=False)
    _LOGGER.info('PRESETS %s', _presets)

    raise NotImplementedError


def _build_tmp_export_preset(out):
    """Build a tmp preset which will export to the given output.

    This makes a copy of the default preset overriding the name tag so that
    it exports to the correct path.

    Args:
        out (CPOutput): output being exported

    Returns:
        (File): export preset file
    """
    _preset = _find_export_preset(out)
    _tmp_preset = File('/tmp/preset.xml')

    # Find current name tag
    _body = File(_preset).read()
    _, _cur_name = _body.split('<namePattern>')
    _cur_name, _ = _cur_name.split('</namePattern>')

    # Update the body
    _new_name = '{base}.'.format(base=out.base)
    _body = _body.replace(_cur_name, _new_name)
    _tmp_preset.write(_body, force=True)

    return _tmp_preset


def _render_sequence(seq, output):
    """Render the given sequence.

    Args:
        seq (PySequence): flame sequence object
        output (CPOutput): output to render to
    """
    _LOGGER.info('   - RENDER SEQ %s %s', seq.name, seq)
    _dir = output.to_dir()
    _LOGGER.info('   - OUT %s', output)
    _LOGGER.info('   - DIR %s', _dir)

    # Set export preset path
    _preset = _build_tmp_export_preset(output)
    _LOGGER.info('   - PRESET %s', _preset)

    # Set exporter
    _exporter = flame.PyExporter()
    _exporter.foreground = True
    _exporter.export_between_marks = True

    # Prepare export dir
    output.delete(wording='Replace')
    assert not _dir.find(catch_missing=True)
    _dir.flush(force=True)
    _dir.mkdir()
    assert not _dir.find_seqs(depth=2)
    assert _dir.exists()

    # Execute export
    _LOGGER.info('   - EXPORTING')
    _exporter.export(seq, _preset.path, _dir.path)
    _seq = single(_dir.find_seqs(depth=2))
    _LOGGER.info('   - SEQ %s', _seq)
    assert output.exists(force=True)

    # Set metadata
    _data = {
        'owner': os.environ['USER'],
        'mtime': time.time(),
        'dcc': dcc.NAME,
        'machine': platform.node(),
        'pini': release.cur_ver().to_str(),
        'platform': release.cur_ver().to_str(),
        'handler': 'Flame Sequence Exporter',
    }
    output.set_metadata(_data)

    # Update cache
    _LOGGER.info('   - UPDATE CACHE')
    _ety_c = pipe.CACHE.obt_entity(output.entity)
    _out_c = _ety_c.obt_output(output, force=True)
    _out_c.to_dir().find_outputs(force=True)

    _LOGGER.info('   - COMPLETE')


@error.catch
@usage.track
def export_sequences_to_plates(seqs):
    """Export the given sequences as plates.

    The shot name is read from the first token in the sequence name.

    eg. shot010_blah_blah -> CPShot('shot010')

    Args:
        seqs (PySequence list): flame sequence nodes
    """
    pipe.CACHE.reset()

    _job = pipe.CACHE.cur_job
    _LOGGER.info("EXPORT SEQS TO %s", _job)

    _plates = []
    _fails = []
    for _seq in qt.progress_bar(seqs, 'Exporting {:d} plate{}'):

        # Find shot + output name from clip name
        _seq_name = str(_seq.name).strip("'")
        _LOGGER.info(" - SEQ %s '%s'", _seq, _seq_name)
        if '_' in _seq_name:
            _shot_name, _output_name = _seq_name.split('_', 1)
            _output_name = _output_name or 'flame'
        else:
            _shot_name = _seq_name
            _output_name = 'flame'
        _LOGGER.info("   - SHOT NAME %s", _shot_name)
        _shot = _job.find_shot(_shot_name, catch=True)
        if not _shot:
            _LOGGER.info("   - NO SHOT FOUND ")
            _fails.append(_seq_name)
            continue
        _LOGGER.info("   - SHOT %s", _shot)

        _plate = _shot.to_output('plate', output_name=_output_name, extn='exr')
        _plate = _plate.find_next()
        _LOGGER.info("   - PLATE %s", _plate)
        # assert not _plate.exists(force=True)
        _render_sequence(seq=_seq, output=_plate)
        _plates.append(_plate.path)

    # Build notification
    _msg = ''
    if _fails:
        _msg += 'Failed to find shots for {:d} sequences:\n\n - {}'.format(
            len(_fails), '\n - '.join(_fails))
    if _plates:
        _msg += '\n\nExported {:d} plate{}:\n\n - {}'.format(
            len(_plates), plural(_plates), '\n - '.join(_plates))
    qt.notify(_msg.strip(), title='Export complete', icon=icons.find('Wolf'))
