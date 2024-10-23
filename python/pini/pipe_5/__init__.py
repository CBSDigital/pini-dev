"""Tools for managing the pipeline (disk structure)."""

# pylint: disable=wrong-import-position

import os

from pini.utils import HOME_PATH, Dir

MASTER = os.environ.get('PINI_PIPE_MASTER', 'disk')
NAME = os.environ.get('PINI_PIPE_NAME', 'pini')
GLOBAL_CACHE_ROOT = Dir(
    os.environ.get('PINI_GLOBAL_CACHE_ROOT', HOME_PATH+'/.pini'))

SHOTGRID_AVAILABLE = bool(
    os.environ.get('PINI_SG_KEY') and
    os.environ.get('PINI_SG_URL'))
SUBMIT_AVAILABLE = os.environ.get('PINI_PIPE_ENABLE_SUBMIT', False)

from .elem import (
    CPJob, ROOT, find_jobs, find_job, cur_job, CPRoot, obt_job,
    to_job, CPSequence, cur_sequence, CPAsset,
    cur_asset, CPShot, cur_shot, to_shot, CPEntity, to_entity,
    cur_entity, find_entity, recent_entities, CPWorkDir, cur_work_dir,
    to_work_dir, cur_task, map_task, CPWork, cur_work, add_recent_work,
    install_set_work_callback, recent_work, load_recent, to_work,
    CPOutputFile, CPOutputSeq, OUTPUT_FILE_TYPES, OUTPUT_SEQ_TYPES,
    to_output, ver_sort, CPOutputVideo, OUTPUT_VIDEO_TYPES,
    CPOutputBase, cur_output, CPOutputSeqDir)

from .cp_template import CPTemplate, glob_templates, glob_template
from .cp_utils import (
    validate_token, admin_mode, is_valid_token, task_sort, cur_user,
    EXTN_TO_DCC, validate_tokens, map_path, tag_sort, output_clip_sort,
    passes_filters, DEFAULT_TAG, ASSET_PROFILE, SHOT_PROFILE,
    expand_pattern_variations)

from .cp_tools import version_up

from . import cache

ENTITY_TYPES = CPAsset, CPShot

CACHE = cache.CCPRoot(ROOT.path)
