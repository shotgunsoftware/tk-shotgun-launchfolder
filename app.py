"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

App that launches a folder browser from inside of Shotgun
"""

import tank
import sys
import os
import platform

class LaunchFolder(tank.platform.Application):
    
    def init_app(self):
        entity_types = self.get_setting("entity_types")
        deny_permissions = self.get_setting("deny_permissions")
        deny_platforms = self.get_setting("deny_platforms")
        
        p = {
            "title": "Show in File System",
            "entity_types": entity_types,
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": True
        }
        
        self.engine.register_command("show_in_filesystem", self.show_in_filesystem, p)
            
    def launch(self, path):

        self.engine.log_debug("Launching file system viewer for folder %s" % path)        
        
        # get the setting        
        system = platform.system()
        
        # run the app
        if system == "Linux":
            cmd = 'xdg-open "%s"' % path
        elif system == "Darwin":
            cmd = 'open "%s"' % path
        elif system == "Windows":
            cmd = 'cmd.exe /C start "Folder" "%s"' % path
        else:
            raise Exception("Platform '%s' is not supported." % system)
        
        self.engine.log_debug("Executing command '%s'" % cmd)
        exit_code = os.system(cmd)
        if exit_code != 0:
            self.engine.log_error("Failed to launch '%s'!" % cmd)

    
    def show_in_filesystem(self, entity_type, entity_ids):
        paths = []
        
        for eid in entity_ids:

            entity = {"id": eid, "type": entity_type}
            
            # Use the path cache to look up all paths linked to the task's entity
            entity_paths = tank.get_paths_for_entity(self.engine.context.project_root, entity)
            
            if len(entity_paths) == 0:
                self.engine.log_info("No location exists on disk yet for one of the entities. "
                                     "Please use shotgun to create folders and then try again!") 
                return       
            paths.extend(entity_paths)
            
        # launch folder windows
        for x in paths:
            self.launch(x)
    
