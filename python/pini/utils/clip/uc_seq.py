"""Tools for managing sequences of files."""

import logging

from ..u_misc import single, ints_to_str
from ..u_text import plural
from ..u_time import strftime

from ..path import Path, norm_path, Dir, File, abs_path

from . import uc_ffmpeg, uc_clip

_LOGGER = logging.getLogger(__name__)


class Seq(uc_clip.Clip):  # pylint: disable=too-many-public-methods
    """Represents a sequence of files.

    The list of frames is only read once and then cached.

    When _frames is None, it means no read has happened. Otherwise, _frame
    should be a set of frame indices.
    """

    def __init__(self, path, frames=None, safe=True):
        """Constructor.

        Args:
            path (str): path to seq (eg. C:/path/to/files/file.%04d.jpg)
            frames (int list): force frames cache
            safe (bool): only allow sequences with <base>.%04d.<extn> format
        """
        _path = path
        _frames = frames
        if isinstance(_path, Seq) and _path.has_frames_cache():
            _path = path.path
            _frames = path.frames
        self.path = norm_path(_path)

        # Determine path vars
        _path = Path(self.path)
        self.dir = _path.dir
        self.filename = _path.filename

        # Split base to extract frame str
        if safe or (
                self.filename.count('.') <= 2 and
                '.%0' in self.filename and
                'd.' in self.filename):
            if self.filename.count('.') < 2:
                raise ValueError(self.path)
            self.base, self.frame_expr, self.extn = self.filename.rsplit('.', 2)
            if self.frame_expr != '%d' and (
                    not len(self.frame_expr) == 4 or
                    not self.frame_expr.startswith('%0') or
                    not self.frame_expr.endswith('d')):
                raise ValueError(
                    f'Bad frame expr {self.frame_expr} - {path}')
        else:
            for _expr in [
                    '%04d', '%d',
                    '%03d', '%02d',
                    '%05d', '%07d', '%09d',

                    '<UDIM>', '<U>_<V>']:

                if self.filename.count(_expr) != 1:
                    continue
                self.frame_expr = _expr
                self.base, _ = self.filename.rsplit(_expr)
                self.base = self.base.strip('.')
                self.extn = _path.extn
                break
            else:
                raise ValueError(self.path)

        self._frames = None
        if _frames:
            self._frames = set(_frames)

    @property
    def frames(self):
        """Obtain list of frames.

        Returns:
            (int list): frame indices
        """
        return self.to_frames()

    @property
    def files(self):
        """Obtain list of file paths.

        Returns:
            (str list): path for each frame
        """
        return [self[_frame] for _frame in self.frames]

    def add_frame(self, frame):
        """Add a frame to the frames cache.

        Args:
            frame (int): frame to add
        """
        assert isinstance(frame, int)
        if self._frames is None:
            self._frames = set()
        self._frames.add(frame)

    def browser(self):
        """Open a browser in this seq's parent directory."""
        Dir(self.dir).browser()

    def build_thumbnail(self, file_, width=100, frame=None, force=False):
        """Build thumbnail for this video.

        Args:
            file_ (str): thumbnail path
            width (int): thumbnail width in pixels
            frame (int): select frame to export (default is middle frame)
            force (bool): overwrite existing without confirmation
        """
        from pini import qt
        from pini.utils import Image, TMP

        _LOGGER.info('BUILD THUMB %s', self.path)
        _thumb = File(file_)
        assert _thumb.extn == 'jpg'
        _res = self._to_thumb_res(width, catch=True)
        if not _res:
            _LOGGER.error(' - FAILED TO READ RES %s', self.path)
            return

        # Build pixmap
        _frame = self.to_frame_file(frame=frame)
        _LOGGER.debug(' - FRAME %s', _frame)
        assert _frame.exists()
        if _frame.extn in qt.PIXMAP_EXTNS:
            _pix = qt.CPixmap(_frame)
        elif _frame.extn in ('exr', ):
            _img = Image(_frame)
            _tmp = TMP.to_file('tmp.jpg')
            _img.convert(_tmp, force=True)
            _pix = qt.CPixmap(_tmp)
        else:
            raise NotImplementedError(self.path)

        _pix = _pix.resize(_res)
        _pix.save_as(_thumb, verbose=0, force=force)

    def contains(self, file_):
        """Test whether this sequence contains the given file.

        eg. Seq('blah.%04d.jpg').contains('blah.0001.jpg') -> True

        Args:
            file_ (str): file to test

        Returns:
            (bool): whether file follows sequence pattern
        """
        _file = File(file_)
        if _file.dir != self.dir:
            return False
        _head, _tail = self.filename.split(self.frame_expr)
        _LOGGER.debug('HEAD/TAIL %s %s', _head, _tail)
        _LOGGER.debug('FILENAME %s', _file.filename)
        if (
                not _file.filename.startswith(_head) or
                not _file.filename.endswith(_tail)):
            return False
        _f_str = _file.filename[len(_head):-len(_tail)]
        _LOGGER.debug('FSTR %s', _f_str)
        if not _f_str.isdigit():
            return False
        _f_idx = int(_f_str)
        return self.frame_expr % _f_idx == _f_str

    def copy_to(self, target, frames=None, check_match=True, progress=True):
        """Copy this file sequence to another location.

        Args:
            target (Seq): target location
            frames (int list): override frames to copy
            check_match (bool): check existing frame match before replacing
            progress (bool): show progress
        """
        from pini import qt

        assert isinstance(target, Seq)
        _frames = frames or self.frames

        # Handle existing
        if target.exists():

            # Check for target matches
            if check_match:
                _LOGGER.info(' - CHECK WHETHER EXISTING FRAMES MATCH')
                for _frame in qt.progress_bar(
                        _frames, 'Checking {:d} frame{}', show=progress,
                        stack_key='CheckFrames'):
                    if not File(self[_frame]).matches(target[_frame]):
                        break
                else:
                    _LOGGER.info(' - ALL FRAMES MATCH')
                    return

            # Replace existing
            qt.ok_cancel(
                f'Replace existing frames {min(_frames):d}-{max(_frames):d}?'
                f'\n\n{target.path}')
            target.delete(frames=_frames, force=True)

        # Apply copy
        for _frame in qt.progress_bar(
                _frames, 'Copying {:d} frame{}', stack_key='CopyFrames',
                show=progress):
            File(self[_frame]).copy_to(target[_frame])
            target.add_frame(_frame)

    def delete(
            self, wording='delete', frames=None, icon=None, parent=None,
            force=False):
        """Delete this image sequence.

        Args:
            wording (str): override wording on warning dialog
            frames (int list): limit list of frames to delete
            icon (str): override icon on warning dialog
            parent (QDialog): parent for warning dialog
            force (bool): delete without confirmation
        """
        from pini import qt, icons

        _frames = frames or self.to_frames(force=True)
        if _frames and not force:
            if len(_frames) == 1:
                _fr_str = str(single(_frames))
            else:
                _fr_str = f'{_frames[0]:d}-{_frames[-1]:d}'
            qt.ok_cancel(
                f'Are you sure you want to {wording.lower()} '
                f'frame{plural(_frames)} {_fr_str} of this '
                f'image sequence?\n\n{self.path}',
                title=f'Confirm {wording}',
                icon=icon or icons.find('Sponge'), parent=parent)
        for _frame in qt.progress_bar(
                _frames, 'Deleting {:d} file{}', stack_key='DeleteFrames',
                show_delay=1):
            _file = File(self[_frame])
            _file.delete(force=True)
        self._frames = set()

    def exists(self, frames=None, force=False):
        """Test whether this sequence exists.

        Args:
            frames (int list): list of frames to check exist - if any
                of these frames are missing then the result is False
            force (bool): force reread from disk

        Returns:
            (bool): whether sequence exists
        """
        _LOGGER.debug("EXISTS %s", self.path)
        _frames = self.to_frames(force=force)
        _LOGGER.debug(" - FRAMES %s", _frames)
        if frames:
            _LOGGER.debug(" - CHECK FRAMES %s", frames)
            _missing = sorted(set(frames) - set(_frames))
            _LOGGER.debug(' - MISSING FRAMES %s', _missing)
            return not _missing
        return bool(_frames)

    def find_range(self, force=False):
        """Find start/end frames of this sequence.

        Args:
            force (bool): force reread from disk

        Returns:
            (tuple): start/end frames
        """
        _frames = self.to_frames(force=force)
        return _frames[0], _frames[-1]

    def has_frames_cache(self):
        """Check whether this sequence has a frames cache.

        Returns:
            (bool): whether frames cache
        """
        return self._frames is not None

    def is_editable(self):
        """Test whether this is editable in a text editor.

        Provided for symmetry with Path object.

        Returns:
            (bool): false
        """
        return False

    def is_missing_frames(self, frames=None):
        """Test whether this sequence's frame range is incomplete.

        Args:
            frames (int list): expected frames

        Returns:
            (bool): whether frames are missing
        """
        _frames = self.to_frames()
        if frames:
            _missing = sorted(set(frames) - set(_frames))
            return bool(_missing)
        if not _frames:
            return True
        for _idx, _this in enumerate(_frames[:-1]):
            _next = _frames[_idx + 1]
            if _this + 1 != _next:
                return True
        return False

    def move_to(self, target, progress=False):
        """Move this sequence.

        Args:
            target (Seq): target sequence
            progress (bool): show progress bar
        """
        _LOGGER.debug('MOVE TO')
        _LOGGER.debug(' - SRC %s', self)
        _LOGGER.debug(' - TRG %s', target)
        _frames = self.to_frames(force=True)
        _LOGGER.debug(' - FRAMES %s', _frames)
        assert not target.exists(frames=_frames)
        assert isinstance(target, Seq)

        # Apply move
        if progress:
            from pini import qt
            _frames = qt.progress_bar(
                _frames, 'Moving {:d} frame{}')
        for _frame in _frames:
            _src_file = File(self[_frame])
            _trg_file = target[_frame]
            _LOGGER.debug(' - FRAMES %s', _frames)
            _src_file.move_to(_trg_file)

        # Update cache
        self.to_frames(frames=[])
        target.to_frames(frames=_frames)

    def mtime(self):
        """Obtain mtime of this sequence using the middle frame.

        Returns:
            (float): mtime
        """
        return self._to_center_path().mtime()

    def nice_size(self):
        """Get size of this file in a readable for (eg. 10GB).

        Returns:
            (str): readable file size
        """
        from pini.utils import nice_size
        return nice_size(self.size())

    def nice_range(self):
        """Get this sequence's frame range in a readable form.

        Returns:
            (str): readable range (eg. 1-100)
        """
        return ints_to_str(self.frames)

    def owner(self):
        """Obtain owner of this sequence using the middle frame.

        Returns:
            (str): owner
        """
        if not self.frames:
            return None
        return self._to_center_path().owner()

    def size(self):
        """Obtain total size of this file sequence.

        Returns:
            (int): size in bytes
        """
        return sum(File(_file).size() for _file in self.files)

    def strftime(self, fmt=None):
        """Get formatted time string using this sequence's mtime.

        Args:
            fmt (str): time format string

        Returns:
            (str): formatted time string
        """
        return strftime(time_=self.mtime(), fmt=fmt)

    def test_dir(self):
        """Test this sequence's parent directory exists."""
        self.to_dir().mkdir()

    def _to_center_path(self):
        """Get central frame file path.

        Returns:
            (File): central frame file
        """
        _ctr_frame = self.frames[int(len(self.frames) / 2)]
        _ctr_file = self[_ctr_frame]
        return File(_ctr_file)

    def to_dir(self, *args, **kwargs):
        """Get this sequence's parent directory.

        Returns:
            (Dir): parent dir
        """
        return File(self.path).to_dir(*args, **kwargs)

    def to_dur(self):
        """Obtain duration (in frames) of this image sequence.

        Returns:
            (int): duration
        """
        return self.to_end() + 1 - self.to_start()

    def to_end(self):
        """Obtain last/end frame of this sequence.

        Returns:
            (int): last frame
        """
        return self.to_range()[1]

    def to_file(self, **kwargs):
        """Map this sequence to a file object.

        Returns:
            (File): file using this seq's attributes
        """
        _path = f'{self.dir}/{self.base}.{self.extn}'
        return File(_path).to_file(**kwargs)

    def to_frame_file(self, frame=None):
        """Obtain the file for the given frame.

        Args:
            frame (int): frame number to request - by default the central
                frame is used

        Returns:
            (File): frame file
        """
        _frame = frame
        if not _frame:
            _frames = self.to_frames()
            if not _frames:
                raise RuntimeError('No frames found')
            _frame = _frames[int(len(_frames) / 2)]
        return File(self[_frame])

    def to_frame_files(self):
        """Build list of all files in this sequence.

        Returns:
            (File list): frame files
        """
        return [self.to_frame_file(_frame) for _frame in self.frames]

    def to_frames(self, frames=None, force=False):
        """Find frames of this sequence.

        This is read from disk the first time, and then subsequently
        the cached value is used. This can be overridden using the
        force flag.

        Args:
            frames (int list): force list of frames into cache
            force (bool): force read from disk

        Returns:
            (int list): list of frame numbers
        """
        if frames is not None:
            self._frames = frames
        if force or self._frames is None:
            self._frames = self._read_frames()
        return sorted(self._frames)

    def _read_frames(self):
        """Read frames of this sequence from disk.

        Returns:
            (int str): frames
        """
        _frames = set()
        _LOGGER.debug('READ FRAMES %s', self)
        _LOGGER.debug(' - TOKENS %s %s %s', self.base, self.frame_expr,
                      self.extn)
        _head, _tail = self.filename.split(self.frame_expr)
        _LOGGER.debug(' - HEAD/TAIL "%s" // "%s"', _head, _tail)
        _dir = Dir(abs_path(self.dir))
        for _file in _dir.find(
                depth=1, extn=self.extn, type_='f', full_path=False,
                catch_missing=True, head=_head, tail=_tail):
            _LOGGER.debug(' - CHECKING %s', _file)
            if not _file.startswith(_head):
                _LOGGER.debug('   - BAD HEAD')
                continue
            if not _file.endswith(_tail):
                _LOGGER.debug('   - BAD TAIL')
                continue

            # Check frame str
            _fr_str = _file[len(_head):-len(_tail)]
            if self.frame_expr == '<U>_<V>':
                if (
                        len(_fr_str) != 5 or
                        _fr_str[2] != '_' or
                        not _fr_str[:2].isdigit() or
                        not _fr_str[-2:].isdigit()):
                    _LOGGER.debug(
                        '   - BAD U/V FR_STR %s %d %d %d %d', _fr_str,
                        len(_fr_str), _fr_str[2] != '_',
                        _fr_str[:2].isdigit(), _fr_str[-2:].isdigit())
                    continue
                _idx = int(_fr_str[:2] + _fr_str[-2:])
                _idxs = int(_fr_str[:2]), int(_fr_str[-2:])
            else:
                if not _fr_str.isdigit():
                    _LOGGER.debug('   - BAD FR_STR %s', _fr_str)
                    continue
                _idx = int(_fr_str)
                _idxs = (_idx, )

            # Check frame expr
            _expr = self.frame_expr
            if _expr == '<UDIM>':
                _expr = '%04d'
            elif _expr == '<U>_<V>':
                _expr = '%02d_%02d'
            if _expr % _idxs != _fr_str:
                _LOGGER.debug('   - BAD REMAP')
                continue

            _frames.add(_idx)

        return _frames

    def to_range(self, force=False):
        """Find start/end frames of this sequence.

        Args:
            force (bool): force reread from disk

        Returns:
            (tuple): start/end frames
        """
        _frames = self.to_frames(force=force)
        if not _frames:
            raise OSError('No frames found ' + self.path)
        return _frames[0], _frames[-1]

    def to_res(self):
        """Obtain resolution for this image sequence.

        Resolution is read from the middle frame.

        Returns:
            (tuple): width/height
        """
        from pini.utils import Image
        _start, _end = self.to_range()
        assert self.frames
        _frame = self.frames[int(len(self.frames) / 2)]
        _img = Image(self[_frame])
        _LOGGER.debug('TO RES %s', _img.path)
        return _img.to_res()

    def to_seq(self, extn=None):
        """Build a sequence object based on this sequence.

        Args:
            extn (str): override extension

        Returns:
            (Seq): new sequence object
        """
        _path = f'{self.dir}/{self.base}.{self.frame_expr}.{extn or self.extn}'
        return Seq(_path)

    def to_start(self):
        """Obtain start/first frame of this sequence.

        Returns:
            (int): first frame
        """
        return self.to_range()[0]

    def to_video(  # pylint: disable=unused-argument
            self, video, burnins=False, force=False, **kwargs):
        """Convert this image sequence to a video.

        NOTE: for docs see clip.seq_to_video

        Args:
            video (File): file to create
            burnins (bool): add burnins
            force (bool): overwrite existing without confirmation

        Returns:
            (Video): video file
        """
        from pini import dcc
        from .. import clip

        # Prepare output path
        _video = clip.Video(video)
        _video.delete(force=force, wording='replace')
        assert not _video.exists()
        if _video.extn.lower() not in ('mp4', 'mov'):
            raise RuntimeError(f'Bad extn {_video.path}')
        _video.test_dir()

        # Build video
        if dcc.NAME == 'nuke':
            # Catch nuke hanging bug
            return self._to_video_nuke(video=_video, burnins=burnins)
        return uc_ffmpeg.seq_to_video(
            seq=self, video=_video, burnins=burnins, **kwargs)

    def _to_video_nuke(self, video, clean_up=True, burnins=False, force=False):
        """Compile video using nuke.

        In nuke (on linux only maybe?) making an ffmpeg system call seems to
        cause a hang, so video conversion is done by simply creating a read
        and a write node, and writing out the video that way.

        NOTE:
         - read colspace: linear (exr), otherwise rec709
         - write colspace: rec709

        Args:
            video (Video): video file to write
            clean_up (bool): delete tmp nodes
            burnins (bool): apply burnins
            force (bool): overwrite existing without confirmation
                (for debugging)
        """
        _LOGGER.debug('TO VIDEO NUKE %s', self.path)
        import nuke
        from pini.utils import Video

        if burnins:
            raise NotImplementedError('Burnins in nuke')

        _video = Video(video)
        _start, _end = self.to_range()

        # Clean up
        for _name in ["TMP_READ", "TMP_WRITE", "TMP_REFORMAT"]:
            _node = nuke.toNode(_name)
            if _node:
                nuke.delete(_node)
        if _video.exists():
            _video.delete(force=force)

        # Build read
        _to_clean = []
        nuke.Root()['colorManagement'].setValue('OCIO')
        _colspace = "scene_linear" if self.extn == 'exr' else "color_picking"
        _read = nuke.createNode(
            'Read',
            f"name TMP_READ file {self.path} first {_start:d} last {_end:d} "
            f"colorspace {_colspace}")
        _to_clean.append(_read)

        # Reformat if width larger than 4096
        _width = _read.width()
        _LOGGER.debug(' - WIDTH %d', _width)
        if _width > 4096:
            _scale = 4096 / _width
            _LOGGER.debug(' - SCALE %f', _scale)
            _reformat = nuke.createNode(
                'Reformat',
                'name TMP_REFORMAT type scale')
            _reformat['scale'].setValue(_scale)
            _to_clean.append(_reformat)

        # Build write
        _write = nuke.createNode(
            'Write',
            f"name TMP_WRITE file {_video.path} file_type mov mov64_codec h264 "
            f"colorspace color_picking")
        _to_clean.append(_write)

        nuke.render(_write, start=_start, end=_end)

        if clean_up:
            for _node in _to_clean:
                nuke.delete(_node)

        return _video

    def __eq__(self, other):
        if not isinstance(other, Seq):
            return False
        return self.path == other.path

    def __getitem__(self, idx):
        assert isinstance(idx, int)
        if self.frame_expr == '<U>_<V>':
            _idx_s = f'{idx:04d}'
            assert len(_idx_s) == 4
            _uv_s = f'{_idx_s[:2]}_{_idx_s[-2:]}'
            return self.path.replace(self.frame_expr, _uv_s)
        if self.frame_expr == '<UDIM>':
            _idx_s = f'{idx:04d}'
            return self.path.replace(self.frame_expr, _idx_s)
        return self.path % idx

    def __hash__(self):
        return hash(self.path)

    def __lt__(self, other):
        if not isinstance(other, (Path, Seq)):
            return self.path < other
        return self.path < other.path

    def __repr__(self):
        _type = type(self).__name__.strip('_')
        return f'<{_type}|{self.path}>'

    def __str__(self):
        return self.path
