"""Tools for managing maya deadline submissions."""

import ast
import logging
import os

from maya import cmds

from pini import pipe, dcc
from pini.utils import File, Dir, abs_path, to_str

from maya_pini import open_maya as pom, ref
from maya_pini.utils import to_render_extn

from . import ds_job, ds_utils

_DIR = File(__file__).to_dir()
_LOGGER = logging.getLogger(__name__)
_EMPTY_SCENE = File(
    os.environ.get('PINI_DEADLINE_EMPTY_MB', _DIR.to_file('empty.mb')))


class _CDMayaJob(ds_job.CDJob):
    """Base class for all deadline maya jobs."""

    def __init__(
            self, output, name=None, camera=None, ignore_error_211=False,
            strict_error_checking=False, **kwargs):
        """Constructor.

        Args:
            output (CPOutput): output file
            name (str): job name
            camera (CCamera): job camera
            ignore_error_211 (bool): ignore render errors
            strict_error_checking (bool): apply strict error checking
        """
        self.camera = camera
        self.ignore_error_211 = ignore_error_211
        self.strict_error_checking = strict_error_checking

        _name = name or output.output_name
        super().__init__(name=_name, output=output, **kwargs)

    def _build_info_data(self, output_filename=None):
        """Build info data for this job.

        Args:
            output_filename (str): override output filename

        Returns:
            (dict): submission info data
        """
        from pini import farm

        if not self.group:
            raise RuntimeError(
                f'No group specified - {farm.find_groups()}')

        _data = super()._build_info_data()

        _data.update({
            'ChunkSize': str(self.chunk_size),
            'Comment': self.comment,
            'ConcurrentTasks': '1',
            'Department': '',
            'EnableAutoTimeout': '0',
            'ExtraInfoKeyValue0': 'DraftFrameRate=24',
            'ExtraInfoKeyValue1': 'DraftType=movie',
            'ExtraInfoKeyValue2': 'DraftExtension=mov',
            'ExtraInfoKeyValue3': 'DraftCodec=h264',
            'ExtraInfoKeyValue4': 'DraftQuality=100',
            'ExtraInfoKeyValue5': 'DraftColorSpaceIn=Draft sRGB',
            'ExtraInfoKeyValue6': 'DraftColorSpaceOut=Draft sRGB',
            'ExtraInfoKeyValue7': 'DraftResolution=1',
            'ExtraInfoKeyValue8': f'SubmitQuickDraft={self.draft}',
            'Frames': str(self.frames).strip('[]').replace(' ', ''),
            'Group': self.group,
            'MinRenderTimeMinutes': '0',
            'Name': self.name,
            'OnJobComplete': 'Nothing',
            'Pool': 'none',
            'Priority': str(self.priority),
            'SecondaryPool': '',
            'TaskTimeoutMinutes': '0',
            'Whitelist': '',
            'Plugin': 'MayaBatch',
        })
        if output_filename:
            _data['OutputFilename0'] = output_filename

        # Gather asset paths
        _paths = set()
        for _ref in ref.find_path_refs():
            _file = File(_ref.path)
            _paths.add(_file.path)
            if _file.extn in ('jpg', ):
                _tx = File(_ref.path).to_file(extn='tx')
                _paths.add(_tx.path)
        for _idx, _path in enumerate(sorted(_paths)):
            _data[f'AWSAssetFile{_idx:d}'] = _path

        return _data

    def _build_job_data(self, output_file_path=None):
        """Build job data for this submission.

        Args:
            output_file_path (str): override output filepath

        Returns:
            (dict): submission job data
        """
        _width, _height = dcc.get_res()
        _output_file_path = output_file_path or self.output.dir
        _col_policy = cmds.colorManagementPrefs(query=True, policyFileName=True)
        _col_cfg = cmds.colorManagementPrefs(query=True, configFilePath=True)

        _data = super()._build_job_data()
        _data.update({
            'Animation': '1',
            'Build': '64bit',
            'CountRenderableCameras': '1',
            'EnableOpenColorIO': '1',
            'IgnoreError211': self.ignore_error_211,
            'ImageHeight': str(_height),
            'ImageWidth': str(_width),
            'OCIOConfigFile': _col_cfg,
            'OCIOPolicyFile': _col_policy,
            "OutputFilePath": _output_file_path,
            'OutputFilePrefix': _determine_img_prefix(),
            'ProjectPath': cmds.workspace(query=True, openWorkspace=True),
            'RenderSetupIncludeLights': '1',
            'StrictErrorChecking': self.strict_error_checking,
            'StartupScript': '',
            'UseLegacyRenderLayers': '0',
            'UseLocalAssetCaching': '0',
        })
        _data['Camera'] = str(self.camera or '')
        _data['Camera0'] = ''
        for _idx, _cam in enumerate(
                pom.find_cams(default=None), start=1):
            _data[f'Camera{_idx:d}'] = str(_cam)

        return _data

    def submit(self, submit=True, name=None):
        """Submit this job to deadline.

        Args:
            submit (bool): execute submission
            name (str): override submission name (for .sub file)

        Returns:
            (str): job id
        """
        self.output.test_dir()
        return super().submit(submit=submit, name=name)


class CDMayaRenderJob(_CDMayaJob):
    """Maya render job on deadline."""

    stype = 'MayaRender'
    plugin = 'MayaRender'

    def __init__(self, layer, work, camera, frames=None, **kwargs):
        """Constructor.

        Args:
            layer (str): name of layer being rendered
            work (CPWork): work file
            camera (CCamera): job camera
            frames (int list): job frame list
        """
        self.layer = layer
        assert camera

        _fmt = to_render_extn()
        _output = pipe.CACHE.cur_work.to_output(
            'render', output_name=self.layer, extn=_fmt, work=work)
        _name = f'{work.base} - {layer} - {camera}'
        _frames = frames or dcc.t_frames()

        super().__init__(
            camera=camera, output=_output, work=work, frames=_frames,
            name=_name, **kwargs)

        assert self.output
        assert self.batch_name

    def _build_info_data(self, output_filename=None):
        """Build info data for this job.

        Args:
            output_filename (str): override output filename

        Returns:
            (dict): submission info data
        """
        assert self.work
        assert self.output
        _cam = str(self.camera).strip('|')
        _name = f'{self.work} - {self.output.output_name} - {_cam}'
        _output_filename = output_filename or self.output.path.replace(
            '.%04d.', '.####.')
        _data = super()._build_info_data(output_filename=_output_filename)
        return _data

    def _build_job_data(self, output_file_path=None):
        """Build job data for this submission.

        Args:
            output_file_path (str): override output filepath

        Returns:
            (dict): submission job data
        """
        _imgs = cmds.workspace(fileRuleEntry='images')
        _imgs_dir = Dir(abs_path(cmds.workspace(expandName=_imgs)))
        _output_file_path = output_file_path or _imgs_dir.path + '/'
        _ren = cmds.getAttr("defaultRenderGlobals.currentRenderer")

        _data = super()._build_job_data(
            output_file_path=_output_file_path)

        _shared_data = {
            'FrameNumberOffset': '0',
            'LocalRendering': '0',
            'MaxProcessors': '0',
            'RenderHalfFrames': '0',
            'RenderLayer': self.output.output_name,
            'Renderer': _ren,
            'UsingRenderLayers': '1'}
        _data.update(_shared_data)

        # Add renderer specific data
        _ren_data = {}
        if _ren == 'Arnold':
            _ren_data = {
                'ArnoldVerbose': '2',
                'MayaToArnoldVersion': '5'}
        elif _ren == 'VRay':
            pass
        if _ren_data:
            _data.update(_ren_data)

        return _data


class CDMayaPyJob(ds_job.CDPyJob):
    """Represents a mayapy submission on deadline."""

    stype = 'MayaPy'
    plugin = 'MayaBatch'

    def __init__(
            self, name, py, stime=None, priority=50, machine_limit=0,
            comment=None, error_limit=1, work=None, batch_name=None,
            tmp_py=None, edit_py=False):
        """Constructor.

        Args:
            name (str): job name
            py (str): python to execute
            stime (float): job submission time
            priority (int): job priority (0-100)
            machine_limit (int): job machine limit
            comment (str): job comment
            error_limit (int): job error limit
            work (File): maya work file to load
            batch_name (str): batch/group name
            tmp_py (File): override path to tmp py file
            edit_py (bool): edit py file on save to disk
        """
        _work = work or _EMPTY_SCENE
        assert isinstance(_work, File)
        ast.parse(py)
        _py = ds_utils.wrap_py(
            py=py, name=name, work=_work, py_file=tmp_py, maya=True)
        super().__init__(
            name=name, py=_py, stime=stime, priority=priority, tmp_py=tmp_py,
            machine_limit=machine_limit, batch_name=batch_name,
            comment=comment, error_limit=error_limit, wrap_py=False,
            edit_py=edit_py)
        self.work = _work
        assert self.work

    def _build_job_data(self):
        """Build job data for this submission.

        Returns:
            (dict): submission job data
        """
        _ver, _ = dcc.to_version()

        _data = super()._build_job_data()
        _data['Build'] = 'None'
        _data['ProjectPath'] = 'None'
        _data['RenderSetupIncludeLights'] = '1'
        _data['SceneFile'] = to_str(self.work)
        _data['ScriptFilename'] = self.py_file.path
        _data['ScriptJob'] = 'True'
        _data['StrictErrorChecking'] = 'False'
        _data['Version'] = str(_ver)
        _data['UseLegacyRenderLayers'] = '0'

        return _data


def _determine_img_prefix(work=None):
    """Determine image prefix for render globals.

    Args:
        work (CPWork): work file being rendered

    Returns:
        (str): render image prefix
    """
    from pini.tools import error
    _LOGGER.debug('DETERMINE IMAGE PREFIX')

    _work = work or pipe.cur_work()
    _LOGGER.debug(' - WORK %s', _work.path)
    _imgs = cmds.workspace(fileRuleEntry='images')
    _imgs_dir = Dir(abs_path(cmds.workspace(expandName=_imgs)))
    _LOGGER.debug(' - IMGS %s %s', _imgs, _imgs_dir.path)

    _ren = cmds.getAttr('defaultRenderGlobals.currentRenderer')
    if _ren == 'arnold':
        _token = '<RenderLayer>'
    elif _ren == 'vray':
        _token = '<layer>'
    elif _ren == 'redshift':
        _token = '<Layer>'
    else:
        raise error.HandledError(
            f'No submitter has be implmented for {_ren} renderer')

    _out = _work.to_output('render', output_name='TOKEN')
    _out_path = _out.path.replace('TOKEN', _token)

    _img_prefix, _ = _imgs_dir.rel_path(_out_path).split('.%04d.', 1)

    return _img_prefix
