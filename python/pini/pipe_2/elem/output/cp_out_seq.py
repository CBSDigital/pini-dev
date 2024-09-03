"""Tools for managing output sequences."""

import logging
import subprocess
import time

from pini import icons
from pini.utils import File, Seq, str_to_ints, ints_to_str, Image, find_exe

from . import cp_out_base

_LOGGER = logging.getLogger(__name__)


class CPOutputSeq(Seq, cp_out_base.CPOutputBase):
    """Represents an output file sequence on disk."""

    _dir = None

    yaml_tag = '!CPOutputSeq'
    to_file = Seq.to_file

    def __init__(  # pylint: disable=unused-argument
            self, path, job=None, entity=None, work_dir=None, templates=None,
            template=None, frames=None, dir_=None, types=None, latest=None):
        """Constructor.

        Args:
            path (str): path to output file sequence
            job (CPJob): force parent job
            entity (CPEntity): force the parent entity object
            work_dir (CPWorkDir): force parent work dir
            templates (CPTemplate list): force list of templates to check
            template (CPTemplate): force template to use
            frames (int list): force frame cache
            dir_ (Dir): parent directory (to facilitate caching)
            types (str list): override list of template types to test for
            latest (bool): apply static latest status of this output
        """
        _LOGGER.debug('INIT CPOutputSeq %s', path)
        super().__init__(path=path, frames=frames)
        cp_out_base.CPOutputBase.__init__(
            self, job=job, entity=entity, work_dir=work_dir,
            template=template, templates=templates, latest=latest,
            types=types or cp_out_base.OUTPUT_SEQ_TYPES)
        self._dir = dir_
        self._thumb = File('{}/.pini/{}_thumb.jpg'.format(self.dir, self.base))

    @classmethod
    def from_yaml(cls, loader, node):
        """Build output seq object from yaml.

        Args:
            cls (class): output class
            loader (Loader): yaml loader
            node (Node): yaml data

        Returns:
            (CPOutputSeq): output seq
        """
        del loader  # for linter
        _path, _frames = node.value
        return CPOutputSeq(_path.value, frames=str_to_ints(_frames.value))

    @classmethod
    def to_yaml(cls, dumper, data):
        """Convert this output seq to yaml.

        Args:
            cls (class): output seq class
            dumper (Dumper): yaml dumper
            data (CPOutput): output seq being exported

        Returns:
            (str): output seq as yaml
        """
        _data = [data.path, ints_to_str(data.frames)]
        return dumper.represent_sequence(cls.yaml_tag, _data)

    def to_thumb(self, force=False):
        """Obtain thumbnail for this image sequence, building it if needed.

        Args:
            force (bool): force rebuild thumb

        Returns:
            (File): thumb
        """
        if force or not self._thumb.exists():
            self._build_thumb()
        return self._thumb

    def _build_thumb(self):
        """Build thumbnail for this image sequence using ffmpeg.

        The middle frame is used.
        """
        _LOGGER.info('BUILD THUMB %s', self._thumb.path)

        _frame = self.frames[len(self.frames)/2]
        _LOGGER.debug(' - FRAME %d', _frame)
        _img = Image(self[_frame])
        _LOGGER.debug(' - IMAGE %s', _img)

        # Get thumb res
        _res = self.to_res()
        assert _res
        _aspect = 1.0*_res[0]/_res[1]
        _out_h = 50
        _out_w = int(_out_h*_aspect)
        _out_res = _out_w, _out_h
        _LOGGER.debug(' - RES %s -> %s', _res, _out_res)
        _out_res_s = '{:d}x{:d}'.format(*_out_res)

        # Build ffmpeg cmds
        _ffmpeg = find_exe('ffmpeg')
        _cmds = [_ffmpeg.path, '-y',
                 '-i', _img.path,
                 '-s', _out_res_s,
                 self._thumb.path]
        _LOGGER.debug(' - CMD %s', ' '.join(_cmds))

        # Execute ffmpeg
        _start = time.time()
        if self._thumb.exists():
            self._thumb.delete(force=True)
        assert not self._thumb.exists()
        try:
            subprocess.check_output(
                _cmds, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            _LOGGER.info(' - BUILD THUMB FAILED %s', self.path)
            _write_fail_thumb(file_=self._thumb, res=_out_res)
        assert self._thumb.exists()

        _LOGGER.info(' - BUILD THUMB TOOK %.02fs', time.time() - _start)


def _write_fail_thumb(file_, res):
    """Write fail thumbnail to show that thumb generation failed.

    Args:
        file_ (File): path to write thumb to
        res (tuple): thumb res
    """
    from pini import qt

    _pix = qt.CPixmap(*res)
    _pix.fill('Black')
    _pix.draw_overlay(
        icons.find('Warning'),
        pos=(_pix.width()/2, 3), anchor='T',
        size=_pix.height()*0.4)
    _pix.draw_text(
        'THUMB\nFAILED', pos=(_pix.width()/2, _pix.height()-3),
        anchor='B', col='White', size=7)
    _pix.save_as(file_, force=True)
