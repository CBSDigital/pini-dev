"""Tools for managing shotgrid integration."""

import copy
import logging
import os
import pprint
import time

import six

from pini import qt, pipe
from pini.tools import usage
from pini.utils import single, to_time_f, strftime, basic_repr

from . import sg_user, sg_version, sg_utils, sg_handler

_LOGGER = logging.getLogger(__name__)


class CPSubmitter(object):
    """Default shotgrid submitter."""

    def __init__(self, is_direct=True, supports_comment=False):
        """Constructor.

        Args:
            is_direct (bool): whether this submitter submist directly or
                whether it launches a separate interface
            supports_comment (bool): whether this submitter supports
                comments directly
        """
        self.is_direct = is_direct
        self.supports_comment = supports_comment

    def run(self, outputs):
        """Run this submitter with the given output.

        Args:
            outputs (CPOutput list): outputs to submit
        """
        self._submit(outputs)
        for _out in outputs:
            _update_work_metadata(_out)

    def _submit(self, outputs):
        """Submit this output to shotgrid.

        (Can be reimplemented in subclass)

        Args:
            outputs (CPOutput list): outputs to submit
        """
        submit(outputs)

    def __repr__(self):
        return basic_repr(self, label=None)


SUBMITTER = CPSubmitter()


class _VersionAlreadyExists(RuntimeError):
    """Raised when a version already exists on shotgrid."""

    def __init__(self, user, url, mtime):
        """Constructor.

        Args:
            user (str): name of version owner
            url (str): version url
            mtime (float): version mtime
        """
        super(_VersionAlreadyExists, self).__init__()
        self.user = user
        self.url = url
        self.mtime = mtime


def _check_video_disk_metadata(video, frames=None):
    """Check mov metadata on disk.

    If the mov is missing metadata the source is found and the metadata
    is copied from there.

    Args:
        video (CPOutputVideo): mov file
        frames (CPOutputSeq): original frames
    """
    _LOGGER.debug('CHECK VIDEO DISK METADATA %s', video.path)
    _work = sg_utils.output_to_work(video)

    # Account for missing metadata
    _LOGGER.debug(' - METADATA %s', video.metadata)
    if not video.metadata:
        _metadata = None
        _LOGGER.info('MISSING MOV METADATA %s', video)
        if video.type_ in ['render_mov', 'plate_mov', 'mov']:
            _src_type = video.type_.replace('_mov', '')
            _src = single(video.entity.find_outputs(
                _src_type, task=video.task, tag=video.tag, ver_n=video.ver_n,
                output_name=video.output_name))
            _LOGGER.info('SOURCE %s', _src)
            _LOGGER.info('COPYING METADATA %s', pprint.pformat(_src.metadata))
            _metadata = _src.metadata
        elif video.type_ == 'blast_mov':
            assert _work
            _metadata = copy.copy(_work.metadata)
            for _key in ['size']:
                _metadata.pop(_key, None)
            _metadata['src'] = _work.path
        else:
            raise ValueError(video.type_)
        if _metadata:
            video.set_metadata(_metadata)

    # Account for src missing from metadata
    if 'src' not in video.metadata and _work:
        video.add_metadata(src=_work.path, force=True)

    # Check frames
    _frames = frames
    if not frames and _work:
        if not video.type_.endswith('mov'):
            raise RuntimeError(video.type_)
        _seq_type = video.type_[:-4] or 'render'
        _LOGGER.debug(' - SEQ_TYPE %s -> %s', video.type_, _seq_type)
        _frames = _work.find_output(
            base=video.base, type_=_seq_type, catch=True)
        _LOGGER.debug(' - FRAMES %s', _frames)
        if _frames:
            video.add_metadata(frames=_frames.path)


def _check_video_sg_metadata(video, sg_data=None, force=False):
    """Check the given mov has the required metadata on shotgrid.

    Args:
        video (CPOutputVideo): source video
        sg_data (dict): current shotgrid metadeata
        force (bool): update video without confirmation
    """
    _LOGGER.debug('CHECK VIDEO METADATA %s', video)
    _LOGGER.debug(' - DISK METADATA %s', video.metadata)

    _sg_data = sg_data or sg_version.to_version_data(video)

    # Check path to movie
    _LOGGER.debug(' - PATH TO MOVIE %s', _sg_data['sg_path_to_movie'])
    if _sg_data['sg_path_to_movie'] != video.path:
        _LOGGER.info(' - NEED TO UPDATE MOV PATH')
        sg_handler.update(
            entity_type='Version',
            entity_id=_sg_data['id'],
            data={'sg_path_to_movie': video.path})

    # Check path to frames
    _frames = video.metadata.get('frames')
    _LOGGER.debug(' - PATH TO FRAMES %s', _frames)
    if _frames and _frames != _sg_data['sg_path_to_frames']:
        _LOGGER.info(' - NEED TO UPDATE FRAMES PATH')
        _out = pipe.to_output(_frames)
        _start, _end = _out.to_range(force=True)
        _data = {
            'sg_path_to_frames': _out.path.replace('.%04d.', '.####.'),
            'sg_first_frame': _start,
            'sg_last_frame': _end}
        sg_handler.update(
            entity_type='Version',
            entity_id=_sg_data['id'],
            data=_data)

    # Check user (may not be set)
    _user = video.metadata.get('owner')
    _LOGGER.info(' - USER %s %s', _sg_data['user'], _user)
    if _user:
        _user_data = sg_user.to_user_data(_user)
        _LOGGER.info(' - USER %s %s', _user, _user_data)
        if not _user_data:
            _LOGGER.info('USER MISSING FROM SG')
        else:
            _email = _user_data['email'].lower()
            assert _email.startswith(_user.lower())
            if not _sg_data['user']['id'] == _user_data['id']:
                if not force:
                    qt.ok_cancel(
                        'Update user {} -> {}?\n\n{}'.format(
                            _sg_data['user']['name'], _user_data['name'],
                            video.path),
                        icon=sg_utils.ICON)
                sg_handler.update(
                    entity_type='Version',
                    entity_id=_sg_data['id'],
                    data={'user': _user_data})
    elif _sg_data['user'] and _sg_data['user']['name'] == 'PiniAccess 1.0':
        sg_handler.update(
            entity_type='Version',
            entity_id=_sg_data['id'],
            data={'user': None})

    # Check movie uploaded
    if not _sg_data['sg_uploaded_movie']:
        _LOGGER.info(' - NEED TO UPLOAD MOVIE')
        sg_handler.to_handler().upload(
            entity_type="Version",
            entity_id=_sg_data['id'],
            path=video.path,
            field_name='sg_uploaded_movie',
        )
        _LOGGER.info(' - UPLOADED MOVIE')

    # Check description
    _work = sg_utils.output_to_work(video)
    _LOGGER.info(' - WORK %s', _work)
    if (
            _work and
            _work.notes and
            _sg_data.get('description') != _work.notes):
        _LOGGER.info('NOTES %s', _work.notes)
        sg_handler.update(
            entity_type='Version',
            entity_id=_sg_data['id'],
            data={'description': _work.notes})
        _LOGGER.info('UPDATED NOTES')


def _update_work_metadata(out):
    """Update work file metadata - add submitted marker.

    Args:
        out (CPOutput): output which was submitted
    """
    _work = sg_utils.output_to_work(out)
    if not _work:
        return
    _metadata = copy.copy(_work.metadata)
    _metadata['submitted'] = True
    _work.set_metadata(_metadata)


def _render_video(seq, video, burnins=False, force=False):
    """Render video of the given image sequence.

    Args:
        seq (CPOutputSeq): images
        video (CPOutputVideo): video
        burnins (bool): apply burnins to video
        force (bool): overwrite existing without confirmation
    """

    # Render mov
    _start = time.time()
    _LOGGER.info(' - GENERATING MP4 %s', video.path)
    seq.to_video(video, burnins=burnins, force=force)
    _dur = time.time() - _start
    _LOGGER.info(
        ' - MADE MOV IN %.01fs %s -> %s',
        _dur, seq.nice_size(), video.nice_size())

    # Update metadata
    _data = copy.copy(seq.metadata)
    _data['frames'] = seq.path
    _data['submitted'] = True
    video.set_metadata(_data)


def _submit_seq(seq, progress, comment=None, burnins=False, force=False):
    """Submit an image sequence to shotgrid.

    Args:
        seq (CPOutputSeq): images
        progress (ProgressBar): progress bar
        comment (str): submission comment
        burnins (bool): apply burnins to video
        force (bool): submit without confirmation
    """
    _LOGGER.info('SUBMIT SEQ %s', seq.path)
    assert isinstance(seq, pipe.CPOutputSeq)

    # Obtain video
    _vid_type = seq.template.name+'_mov'
    _out_vid = seq.to_output(_vid_type, extn='mp4')
    assert _out_vid.tag == seq.tag
    progress.set_pc(5)
    if not _out_vid.exists() or not _out_vid.size():
        progress.set_pc(6)
        _render_video(seq=seq, video=_out_vid, burnins=burnins, force=True)
        progress.set_pc(35)
    assert _out_vid.exists()
    if not _out_vid.metadata.get('frames'):
        progress.set_pc(38)
        _out_vid.add_metadata(frames=seq.path)

    _submit_video(
        _out_vid, progress=progress, comment=comment, force=force, frames=seq)


def _submit_video(video, progress, frames=None, comment=None, force=False):
    """Submit the given mov to shotgrid.

    Args:
        video (CPOutputVideo): mov to submit
        progress (ProgressBar): progress bar
        frames (CPOutputSeq): source frames
        comment (str): submission comment
        force (bool): create entries without confirmation
    """
    _LOGGER.info('SUBMIT VIDEO %s', video.path)

    _check_video_disk_metadata(video)
    progress.set_pc(40)

    # Check for existing
    _data = sg_version.to_version_data(
        video, fields=['user', 'sg_uploaded_movie', 'created_at'])
    _frames = frames or video.metadata.get('frames')
    if _data:
        _user = _data.get('user', {}).get('name', '<Unknown>')
        _url = _data.get('sg_uploaded_movie', {}).get('url')
        _mtime = to_time_f(_data.get('created_at'))
        raise _VersionAlreadyExists(user=_user, url=_url, mtime=_mtime)
    _data = sg_version.create_version(
        video=video, frames=frames, comment=comment)
    progress.set_pc(45)
    _LOGGER.debug('VER %s', pprint.pformat(_data))
    assert _data

    _check_video_sg_metadata(video, sg_data=_data, force=force)
    _update_work_metadata(video)


@usage.get_tracker('SubmitToShotgrid', args=['output'])
def submit(output, comment=None, burnins=False, force=False):
    """Submit the given output to shotgrid.

    Args:
        output (any): output to submit
        comment (str): submission comment
        burnins (bool): apply burnins to video
        force (bool): create entities without confirmation
    """
    _progress = qt.progress_dialog('Shotgrid Submit')

    # Check output
    _out = output
    if isinstance(_out, six.string_types):
        _out = pipe.to_output(_out)

    # Execute submit
    try:
        if isinstance(_out, pipe.CPOutputVideo):
            _submit_video(
                _out, comment=comment, force=force, progress=_progress)
        elif isinstance(_out, pipe.CPOutputSeq):
            _submit_seq(
                _out, comment=comment, force=force, progress=_progress,
                burnins=burnins)
        else:
            raise ValueError(_out)
    except _VersionAlreadyExists as _exc:
        _progress.close()
        qt.notify(
            "This version has already been submitted:"
            "\n\n{path}\n\n"
            "Submission was made by {user} at {time}, and cannot be "
            "overwritten in case it has already been reviewed. Please "
            "create a new version to submit to shotgrid.".format(
                user=_exc.user, path=output.path,
                time=strftime('%H:%M%P on %a %m/%d/%y')),
            icon=sg_utils.ICON, title='Version Exists')
        return
    _progress.set_pc(50)

    # Update metadata/cache
    _obj_c = pipe.CACHE.obt_output(_out)
    _obj_c.add_metadata(submitted=True, force=True)
    _work = sg_utils.output_to_work(_out)
    _progress.set_pc(75)
    if _work:
        _work_c = pipe.CACHE.obt_work(_work)
        _work_c.update_outputs()
    _progress.close()

    # Notify
    if not force:
        qt.notify(
            'Submitted version to shotgrid:\n\n'+_out.path,
            icon=sg_utils.ICON,
            title='Version Submitted')


def set_submitter(submitter):
    """Set shotgrid submitter.

    Args:
        submitter (CPSubmitter): submitter to apply
    """
    from pini.pipe import shotgrid
    shotgrid.SUBMITTER = submitter
    os.environ['PINI_SHOTGRID_ENABLE_SUBMIT'] = '1'
    pipe.SUBMIT_AVAILABLE = True
