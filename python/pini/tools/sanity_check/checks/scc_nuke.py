"""Sanity checks for nuke."""

import platform

import nuke

from pini import dcc, pipe
from pini.utils import wrap_fn, norm_path

from . import scc_generic
from ..core import SCCheck


class CheckColorManagement(SCCheck):
    """Check OCIO Config is set correctly."""

    config = 'aces_1.1'
    label = 'Check OCIO config'
    enabled = False

    def run(self):
        """Run this check."""

        # Check col mgt setting
        _knob = nuke.Root()['colorManagement']
        _val = _knob.value()
        if _val != 'OCIO':
            _fix = wrap_fn(_knob.setValue, 'OCIO')
            self.add_fail(
                'Color management config not set to OCIO',
                fix=_fix)

        # Check OCIO config
        _knob = nuke.Root()['OCIO_config']
        _val = _knob.value()
        if _val != self.config:
            _fix = wrap_fn(_knob.setValue, self.config)
            self.add_fail(
                f'OCIO config not set to {self.config}', fix=_fix)


class CheckConnectedReadsLatest(scc_generic.CheckRefsLatest):
    """Check connected pipeline read nodes are using latest version.

    Unconnected or off-pipeline nodes (ie. reads referencing an image
    sequence which doesn't follow naming conventions) are ignored.
    """

    dcc_filter = None  # To override -nuke filter on parent

    def _find_refs(self):
        """Find connected pipeline read nodes.

        Returns:
            (CNukeReadRef list): read nodes to check
        """
        return [_ref for _ref in dcc.find_pipe_refs()
                if _ref.node in _find_connected_reads()]


class CheckUnmappedPaths(SCCheck):
    """Check for unmapped reference paths.

    These are maps which have been set up on another OS, which can
    be updated using the pipe.map_path function.
    """

    sort = 40

    def run(self):
        """Execute this check."""
        _reads = nuke.allNodes('Read')
        for _read in _reads:

            self.write_log('Checking read %s', _read.name())

            _knob = _read['file']
            _cur_path = norm_path(_knob.value())
            self.write_log(' - cur path %s', _cur_path)
            _map_path = pipe.map_path(_cur_path)
            self.write_log(' - map path %s', _map_path)

            if _cur_path != _map_path:
                _msg = (
                    f'Read node "{_read.name()}" has a path which can be '
                    f'updated for {platform.system()}: {_cur_path}')
                _fix = wrap_fn(_knob.setValue, _map_path)
                self.add_fail(_msg, fix=_fix, node=_read)


class CheckReadsInJob(SCCheck):
    """Check all connected read nodes point to current job."""

    def run(self):
        """Run this check."""
        _cur_job = pipe.cur_job()
        self.write_log('Current job %s', _cur_job.name)
        for _read in _find_connected_reads():
            _file = _read['file'].value()
            self.write_log('Checking Read %s', _read.name())
            try:
                _job = pipe.CPJob(_file)
                self.write_log(' - job %s', _job.name)
            except ValueError:
                _job = None
            if _job != _cur_job:
                _msg = (
                    f'Read node pointing outside current job: '
                    f'{_read.name()}')
                self.add_fail(_msg, node=_read)


def _find_connected_reads():
    """Find connected read nodes.

    Returns:
        (Node list): connect read nodes
    """

    # Find nodes which are inputs to other nodes (nuke seems like it
    # has no way to list node outputs SMH)
    _out_nodes = set()
    for _node in nuke.allNodes():
        _inputs = [_node.input(_idx) for _idx in range(_node.inputs())]
        _out_nodes |= set(_inputs)

    _connected_reads = []
    for _read in nuke.allNodes('Read'):
        if _read not in _out_nodes:
            continue
        _connected_reads.append(_read)

    return _connected_reads
