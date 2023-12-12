"""Tools for managing shotgrid sequences."""

import logging

from pini import pipe, qt
from pini.utils import single, get_result_cacher

from . import sg_job, sg_utils, sg_handler

_LOGGER = logging.getLogger(__name__)


def create_sequence(sequence, check_id=True, force=False):
    """Register sequence on shotgrid.

    Args:
        sequence (CPSequence): sequence to register
        check_id (bool): check sequence doesn't already exist first
        force (bool): register without confirmation

    Returns:
        (dict): sequence metadata
    """
    from pini.pipe import shotgrid

    _sg = shotgrid.to_handler()

    _seq = pipe.CPSequence(sequence)
    if check_id and to_sequence_id(_seq, force=force):
        _LOGGER.info(' - SEQUENCE ALREADY EXISTS ON SHOTGRID %s', _seq.path)
        return to_sequence_data(_seq)

    if not force:
        qt.ok_cancel(
            'Register sequence {}/{} on shotgrid?\n\n{}'.format(
                _seq.job.name, _seq.name, _seq.path),
            icon=sg_utils.ICON)
    _data = {
        'project': sg_job.to_job_data(_seq.job),
        'code': _seq.name,
    }
    return [_sg.create('Sequence', _data)]


def find_sequences(job, template):
    """Find sequences in this job.

    Args:
        job (CPJob): job to read sequences from
        template (CPTemplate): sequence template

    Returns:
        (CPSequence list): sequences
    """
    _results = sg_handler.find(
        'Sequence',
        filters=[
            sg_job.to_job_filter(job),
            ('sg_status_list', 'not_in', ('omt', ))
        ],
        fields=['code'])

    _seqs = []
    for _data in _results:
        _path = template.format(sequence=_data['code'])
        try:
            _seq = pipe.CPSequence(_path, template=template)
        except ValueError:
            continue
        _LOGGER.debug(' - SEQ %s %s', _seq, _data)
        _seq_to_data(_seq, data=[_data], force=True)  # Update cache
        _seqs.append(_seq)

    return sorted(_seqs)


@get_result_cacher(use_args=['sequence'])
def _seq_to_data(sequence, data=None, force=False):
    """Obtain shotgrid data for the given sequence.

    Args:
        sequence (CPSequence): sequence to read
        data (dict): force shotgrid data into cache
        force (bool): rewrite cache

    Returns:
        (dict): shotgrid sequence data
    """

    # Search shotgrid
    _results = data
    if not _results:
        _LOGGER.info('READING SEQ DATA %s', sequence)
        _results = sg_handler.find(
            'Sequence',
            filters=[
                sg_job.to_job_filter(sequence.job),
                ('code', 'is', sequence.name),
                ('sg_status_list', 'not_in', ('omt', ))],
            fields=['id', 'code'])
    assert len(_results) in (0, 1)

    if not _results and pipe.MASTER == 'disk':
        _results = create_sequence(sequence, check_id=False, force=force)

    return single(
        _results, items_label='results',
        zero_error='Failed to find sequence in shotgrid '+sequence.path)


def to_sequence_data(sequence=None, data=None, force=False):
    """Obtain shotgrid data for the given sequence.

    Args:
        sequence (str): path to sequence
        data (dict): force shotgrid data into cache
        force (bool): rewrite cache

    Returns:
        (dict): shotgrid sequence data
    """
    _seq = sequence or pipe.cur_sequence()
    if not isinstance(_seq, pipe.CPSequence):
        _seq = pipe.CPSequence(_seq)
    assert isinstance(_seq, pipe.CPSequence)
    return _seq_to_data(_seq, data=data, force=force)


def to_sequence_id(sequence, force=False):
    """Obtain shotgrid id for the given sequence.

    Args:
        sequence (str): path to sequence
        force (bool): register sequence without confirmation

    Returns:
        (int): sequence id
    """
    _data = to_sequence_data(sequence, force=force)
    return _data['id'] if _data else None


def to_sequence_filter(sequence=None):
    """obtain shotgrid filter for the given sequence.

    Args:
        sequence (str): path to sequence

    Returns:
        (tuple): sequence filter
    """
    return 'sg_sequence', 'is', [to_sequence_data(sequence)]
