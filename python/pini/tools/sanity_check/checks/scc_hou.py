"""Maya render checks."""

import logging

from pini import dcc, qt
from pini.utils import wrap_fn, is_camel, to_camel


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
            self.write_log('Checking %s pass=%s', _pass, _rop.name())

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


def _rename_rop(rop):
    """Rename a ROP node.

    Args:
        rop (RopNode): rop to rename
    """
    _name = qt.input_dialog(f'Enter new name for ROP "{rop.name()}":')
    rop.setName(_name)
