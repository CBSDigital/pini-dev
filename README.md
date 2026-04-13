# README #

The pini tools are an open source set of tools for managing VFX workflow 
across multiple dccs. 

They are maintained by Henry van der Beek (ninhenzo64@gmail.com).

The pini-icons module is an API for emoji sets, and includes open source
icon sets from openmoji, joypixels and android.


Install pini python libraries:

 -  Clone the pini repo:
    git clone git@bitbucket.org:ninhenzo64/pini-release.git

 -  Add the following paths to $PYTHONPATH:
    $PINI/python/pini


Maya install:

 - Add $PINI/startup dir to $PYTHONPATH


Nuke install:

 - Add $PINI/startup dir to $NUKE_PATH


Hou install:

 - Add $PINI/startup/hou to $HOUDINI_PATH (eg. $PINI/startup/hou;&)



Environment Variables:
 
 - PINI_PIPE_AUTOGEN_ASS_GZ_TMPLS - Set to 0 to disable autogenerate ass.gz 
      templates. If this is disabled then ass.gz output templates must be
      declared specifically in the job.cfg file. Default is enabled.
 - PINI_DEFAULT_FONT_SIZE - Apply default text size for qt interfaces.
 - PINI_INSTALL_DISABLE - Disable install pini.
 - PINI_HOU_APPLY_SCALE_FIX - Set to 0 to disable 0.01 abc scaling in 
      houdini. Default is enabled.
 - PINI_PUB_JUNK_GRPS - List of groups which can be junked on publish
      (eg. "JUNK|WORKFLOW"). Default is just "JUNK".
 - PINI_UI_INSTALL_DISABLE - Disable building of interface elements.