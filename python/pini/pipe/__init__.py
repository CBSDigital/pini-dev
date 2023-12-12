"""Tools for managing the pipeline (disk structure)."""

import os

from .cp_job import (
    CPJob, JOBS_ROOT, find_jobs, find_job, obtain_job, cur_job,
    apply_create_asset_type_callback, set_jobs_root, to_job)

from .cp_sequence import (
    CPSequence, apply_create_sequence_callback, cur_sequence)

from .cp_asset import CPAsset, apply_create_asset_callback, cur_asset
from .cp_shot import CPShot, apply_create_shot_callback, cur_shot, to_shot
from .cp_entity import to_entity, cur_entity, find_entity

from .cp_work_dir import (
    CPWorkDir, cur_work_dir, to_work_dir, cur_task, map_task)
from .cp_work import (
    CPWork, cur_work, apply_set_work_callback, add_recent_work,
    recent_work, version_up, load_recent, to_work)
from .cp_output import (
    CPOutput, CPOutputSeq, OUTPUT_TEMPLATE_TYPES, OUTPUT_SEQ_TEMPLATE_TYPES,
    to_output, ver_sort, CPOutputVideo, OUTPUT_VIDEO_TEMPLATE_TYPES,
    CPOutputBase, cur_output, CPOutputSeqDir)

from .cp_template import CPTemplate, glob_templates, glob_template
from .cp_utils import (
    validate_token, admin_mode, is_valid_token, task_sort, cur_user,
    EXTN_TO_DCC, validate_tokens, map_path, tag_sort)

from . import cache

NAME = os.environ.get('PINI_PIPE_NAME', 'pini')
MASTER = os.environ.get('PINI_PIPE_MASTER', 'disk')
SHOTGRID_AVAILABLE = bool(
    os.environ.get('PINI_SG_KEY') and
    os.environ.get('PINI_SG_URL'))

CACHE = cache.CPCache()
