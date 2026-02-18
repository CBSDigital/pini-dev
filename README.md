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
 
 - PINI_DEFAULT_FONT_SIZE - apply default text size for qt interfaces
 - PINI_PUB_JUNK_GRPS - list of groups which can be junked on publish
      eg. JUNK|WORKFLOW
      default - JUNK
 - PINI_HOU_APPLY_SCALE_FIX - set to 0 to disable 0.01 abc scaling in houdini