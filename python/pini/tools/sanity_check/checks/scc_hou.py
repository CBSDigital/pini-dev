"""Houdini checks."""

import logging


from pini import dcc, qt
from pini.utils import wrap_fn, is_camel, to_camel, File

from .. import core

_LOGGER = logging.getLogger(__name__)


class CheckRenderLayers(core.SCCheck):
    """Check current scene render layers."""

    action_filter = 'render'
    task_filter = 'lighting model lookdev fx'

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super().__init__(*args, **kwargs)

        # Setup prefixes
        _prefixes = {'bty', 'mte', 'sdw', 'ref', 'utl'}
        _prefixes |= set(self.settings.get('add_prefixes', []))
        _prefixes = sorted(_prefixes)
        self.prefixes = _prefixes

    def run(self):
        """Run this check."""

        _exp = self.exporter or dcc.find_exporter('FarmRender')
        self.write_log(' - exporter %s', _exp)
        self.write_log(' - prefixes %s', self.prefixes)

        # Check layers
        for _pass in _exp.find_passes():
            _rop = _pass.node
            if _rop.isBypassed():
                continue
            self.write_log(' - checking %s pass=%s', _pass, _rop.name())

            if '_' in _rop.name():
                _prefix, _suffix = _rop.name().split('_', 1)
            else:
                _prefix, _suffix = _rop.name(), None

            # Check prefix
            if _prefix not in self.prefixes:
                _prefixes_s = str(self.prefixes).strip('[]')
                _msg = (
                    f'Render layer "{_rop.name()}" has prefix "{_prefix}" '
                    f'which is not in the list of approved prefixes: '
                    f'{_prefixes_s}')
                _fail = core.SCFail(_msg, fix=wrap_fn(_rename_rop, _rop))
                self.add_fail(_fail)
                continue

            # Check suffix
            if _suffix and not is_camel(_suffix):
                _new_suffix = to_camel(_suffix)
                _new_name = f'{_prefix}_{_new_suffix}'
                _msg = (
                    f'Render layer "{_rop.name()}" has suffix "{_suffix}" '
                    f'which is not camel case (should be "{_new_name}")')
                _fix = wrap_fn(_rename_rop, _new_name)
                self.add_fail(_msg, fix=_fix)
                continue

            # Check path length
            _out = _pass.to_output()
            self.write_log('   - out %s', _out)
            _out_file = File(_out[dcc.t_start(int)])
            _lock = _out_file.to_file(extn=f'{_out.extn}.lock')
            self.write_log('   - lock %s', _lock)
            self.check_path_len(
                _lock, exp_name=_pass.name, output_name=_pass.name,
                exp_type='ROP', output_type='render lock file',
                rename=_pass.rename)


def _rename_rop(rop):
    """Rename a ROP node.

    Args:
        rop (RopNode): rop to rename
    """
    _name = qt.input_dialog(f'Enter new name for ROP "{rop.name()}":')
    rop.setName(_name)


class CheckAOVs(core.SCCheck):
    """Check current scene AOVs match the job template.

    If no job AOV template has been published, the check does nothing.
    """

    profile_filter = 'shot'
    action_filter = 'render'
    task_filter = 'light fx'
    label = 'Check AOVs'
    sort = 40  # Before check render globals

    def run(self):
        """Run this check."""

        _exp = dcc.find_exporter('render')
        _map = {'Depth': 'Z Depth'}
        _aovs = [_map.get(_aov, _aov) for _aov in self.settings['aovs']]

        for _pass in _exp.find_passes():
            _rop = _pass.node
            if _rop.isBypassed():
                continue
            self.write_log('check ROP %s', _rop)

            _aovs_parm = _rop.parm('RS_aov')

            # Read
            _cur_aovs = set()
            for _idx in range(1, 100):
                _parm = _rop.parm(f'RS_aovID_{_idx}')
                if not _parm:
                    break
                _labels = _parm.menuLabels()
                _aov = _labels[_parm.eval()]
                _cur_aovs.add(_aov)
            self.write_log(' - cur AOVs %s', sorted(_cur_aovs))

            _missing_aovs = set(_aovs) - _cur_aovs
            self.write_log(' - missing AOVs %s', sorted(_missing_aovs))
            for _aov in _missing_aovs:

                self.add_fail(
                    f'ROP "{_rop.name()}" is missing AOV "{_aov}"',
                    node=_rop, fix=wrap_fn(_add_aov, rop=_rop, aov=_aov))


def _add_aov(rop, aov):
    """Add the given AOV to the given ROP.

    Args:
        rop (RopNode): rop to update
        aov (str): name of AOV to add
    """
    _LOGGER.info('CREATE AOV %s %s', rop, aov)

    _aovs_parm = rop.parm('RS_aov')

    _aovs_parm.insertMultiParmInstance(_aovs_parm.eval())
    _idx = _aovs_parm.eval()
    _parm = rop.parm(f'RS_aovID_{_idx}')
    _LOGGER.info('     - PARM %s', _parm)
    _labels = _parm.menuLabels()
    assert aov in _labels
    _parm.set(_labels.index(aov))
