"""Tools for managing entities in a disk-based pipeline."""

import logging

from pini.utils import Dir, single, File, EMPTY

from ... import cp_template
from . import cp_ety_base

_LOGGER = logging.getLogger(__name__)


class CPEntityDisk(cp_ety_base.CPEntityBase):
    """Represents an entity in a disk-based pipelined."""

    def _read_outputs(self):
        """Read outputs in this entity.

        This uses glob data to construct output file and sequence dir objects.
        The sequence dirs are then used to find output sequences. This is
        constructed like this to facilitate caching (see pini.pipe.cache).

        Returns:
            (CPOutput list): entity outputs
        """

        # Read globs
        _globs = self._read_output_globs()
        _LOGGER.debug(' - FOUND %d GLOBS', len(_globs))

        # Add output file objects
        _files = self._build_output_files(globs=_globs)

        # Add sequence dir outputs
        _seq_dirs = self._build_output_seq_dirs(globs=_globs)
        _seqs = []
        for _seq_dir in _seq_dirs:
            _seqs += _seq_dir.find_outputs()

        _outs = sorted(_files+_seqs)
        _LOGGER.debug(
            'BUILT OUTPUTS %s outs=%d globs=%d files=%d seq_dirs=%d seqs=%d',
            self, len(_outs), len(_globs), len(_files), len(_seq_dirs),
            len(_seqs))

        return _outs

    def _find_root_output_templates(self):
        """Find output templates for the root of this entity.

        This does not include work_dir or seq_dir templates.

        Returns:
            (CPTemplate list): output templates
        """
        from pini import pipe
        _LOGGER.debug('FIND ROOT OUTPUT TMPLS %s', self)

        # Find templates
        _types = ['seq_dir'] + (pipe.OUTPUT_FILE_TYPES +
                                pipe.OUTPUT_VIDEO_TYPES)
        _LOGGER.debug(' - TMPL TYPES %s', _types)
        _all_tmpls = sorted(sum([
            self.find_templates(_type) for _type in _types], []))

        # Remove work_dir + seq_dir templates
        _seq_dir_tmpls = [
            _tmpl for _tmpl in _all_tmpls if _tmpl.name == 'seq_dir']
        _LOGGER.debug(' - SEQ DIR TMPLS %d %s', len(_seq_dir_tmpls),
                      _seq_dir_tmpls)
        _tmpls = []
        for _tmpl in _all_tmpls:
            _LOGGER.debug(' - CHECKING TEMPLATE %s', _tmpl)
            if '{work_dir}' in _tmpl.pattern:
                _LOGGER.debug('   - WORK DIR')
                continue
            if _tmpl_in_seq_dir(_tmpl, seq_dir_tmpls=_seq_dir_tmpls):
                _LOGGER.debug('   - SEQ DIR')
                continue
            _LOGGER.debug('   - ACCEPTED')
            _tmpls.append(_tmpl)

        # Apply data
        _data = {'entity': self.name,
                 'entity_path': self.path}
        _tmpls = [_tmpl.apply_data(**_data) for _tmpl in _tmpls]
        _LOGGER.log(9, ' - FOUND %d TMPLS %s', len(_tmpls), _tmpls)

        return _tmpls

    def _read_output_globs(self):
        """Read globs data for outputs in this entity.

        Returns:
            (tuple): template/path data
        """
        _tmpls = self._find_root_output_templates()
        _globs = cp_template.glob_templates(_tmpls, job=self.job)
        _LOGGER.debug(
            ' FOUND %d GLOBS (%d TEMPLATES)', len(_globs), len(_tmpls))
        return _globs

    def find_output_seq_dir(self, match):
        """Find output sequence directory matching the given criteria.

        Args:
            match (str): token to match with

        Returns:
            (CPOutputSeqDir): matching output sequence directory
        """
        return single([
            _seq_dir for _seq_dir in self.find_output_seq_dirs()
            if _seq_dir.path == match])

    def find_output_seq_dirs(
            self, ver_n=None, tag=EMPTY, task=None, globs=None):
        """Find output sequence directories within this entity.

        Args:
            ver_n (int): filter by version number
            tag (str|None): filter by tag
            task (str): filter by task
            globs (tuple): override glob data

        Returns:
            (CPOutputSeqDir list): output sequence dirs
        """
        _seq_dirs = []
        for _seq_dir in self._build_output_seq_dirs(globs=globs):
            if ver_n and _seq_dir.ver_n != ver_n:
                continue
            if tag is not EMPTY and _seq_dir.tag != tag:
                continue
            if task and _seq_dir.task != task:
                continue
            _seq_dirs.append(_seq_dir)
        return _seq_dirs

    def _build_output_seq_dirs(self, globs=None, seq_dir_class=None):
        """Build outputs sequence directories from glob data.

        Args:
            globs (tuple): override globs data
            seq_dir_class (class): overide output seq dir class

        Returns:
            (CPOutputSeqDir list): output sequence dirs
        """
        from pini import pipe

        _seq_dir_class = seq_dir_class or pipe.CPOutputSeqDir
        _globs = globs or self._read_output_globs()

        # Build globs into output objects
        _seq_dirs = []
        for _tmpl, _path in _globs:
            _LOGGER.log(9, ' - TESTING %s', _path)
            _LOGGER.log(9, '   - TMPL %s', _tmpl)
            if not (isinstance(_path, Dir) and _tmpl.name == 'seq_dir'):
                _LOGGER.log(9, '   - IGNORING')
                continue
            try:
                _seq_dir = _seq_dir_class(_path, entity=self, template=_tmpl)
            except ValueError:
                continue
            _seq_dirs.append(_seq_dir)

        return sorted(_seq_dirs)

    def _build_output_files(
            self, globs=None, file_class=None, video_class=None):
        """Build output objects from glob data.

        Args:
            globs (tuple): override globs data
            file_class (class): override output file class
            video_class (class): override output video class

        Returns:
            (CPOutput list): all outputs in entity
        """
        _LOGGER.debug('BUILD OUTPUT FILES %s', self)
        from pini import pipe

        _file_class = file_class or pipe.CPOutputFile
        _video_class = video_class or pipe.CPOutputVideo
        _globs = globs or self._read_output_globs()
        _outs = []

        # Build globs into output files
        for _tmpl, _path in _globs:

            if not (isinstance(_path, File) and _tmpl.name != 'seq_dir'):
                continue

            # Determine output file class
            if _tmpl.type_ in pipe.OUTPUT_FILE_TYPES:
                _class = _file_class
            elif _tmpl.type_ in pipe.OUTPUT_VIDEO_TYPES:
                _class = _video_class
            else:
                raise ValueError(_tmpl)

            # Build output
            try:
                _out = _class(_path.path, template=_tmpl, entity=self)
            except ValueError:
                continue
            _LOGGER.debug(' - ADDING OUTPUT %s', _out)
            assert _out.cmp_key
            _outs.append(_out)

        return sorted(_outs)

    def _read_publishes(self):
        """Read all publishes in this entity.

        Returns:
            (CPOutput list): all publishes
        """
        _pubs = []
        _work_dirs = self.find_work_dirs()
        for _work_dir in _work_dirs:
            for _out in _work_dir.find_outputs(type_='publish'):
                _pubs.append(_out)
        return _pubs

    def _read_work_dirs(self, class_=None):
        """Read work dirs within this entity.

        Args:
            class_ (class): override work dir class

        Returns:
            (CPWorkDir list): work dirs
        """
        from pini import pipe
        _LOGGER.debug('READ WORK DIRS')
        _class = class_ or pipe.CPWorkDir

        _work_dirs = []
        _tmpls = self._find_work_dir_templates()
        _LOGGER.debug(' - TMPLS %d %s', len(_tmpls), _tmpls)
        _globs = pipe.glob_templates(_tmpls, job=self.job)
        for _tmpl, _dir in _globs:
            _work_dir = _class(_dir, template=_tmpl, entity=self)
            _work_dirs.append(_work_dir)

        return sorted(_work_dirs)


def _tmpl_in_seq_dir(tmpl, seq_dir_tmpls):
    """Test whether the given template falls inside a sequence directory.

    Args:
        tmpl (CPTemplate): template to check
        seq_dir_tmpls (CPTemplate list): sequence directory
            templates for this entity

    Returns:
        (bool): whether the given template is inside a sequence directory
    """
    if '{work_dir}' in tmpl.pattern:
        return False
    if tmpl.name == 'seq_dir':
        return False
    for _sd_tmpl in seq_dir_tmpls:
        if tmpl.pattern.startswith(_sd_tmpl.pattern+'/'):
            return True
    return False
