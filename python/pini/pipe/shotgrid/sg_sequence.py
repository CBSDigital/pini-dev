"""Tools for managing shotgrid sequences."""

import logging

from pini import pipe, qt

from . import sg_utils

_LOGGER = logging.getLogger(__name__)


def create_sequence(sequence, force=False):
    """Register sequence on shotgrid.

    Args:
        sequence (CPSequence): sequence to register
        force (bool): register without confirmation

    Returns:
        (dict): sequence metadata
    """
    from pini.pipe import shotgrid

    _sg = shotgrid.to_handler()
    _seq = pipe.CPSequence(sequence)
    _proj_s = sequence.sg_proj
    _seq_s = _proj_s.find_sequence(_seq, catch=True)

    if _seq_s:
        raise RuntimeError

    if not force:
        qt.ok_cancel(
            f'Register sequence {_seq.job.name}/{_seq.name} on shotgrid?'
            f'\n\n{_seq.path}',
            icon=sg_utils.ICON)
    _data = {
        'project': _proj_s.to_entry(),
        'code': _seq.name,
    }
    return [_sg.create('Sequence', _data)]
