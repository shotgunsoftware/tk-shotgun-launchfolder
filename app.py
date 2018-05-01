# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
App that launches a folder browser from inside of Shotgun
"""

import sgtk
import sys
import os

class LaunchFolder(sgtk.platform.Application):
    
    def init_app(self):
        entity_types = self.get_setting("entity_types")
        deny_permissions = self.get_setting("deny_permissions")
        deny_platforms = self.get_setting("deny_platforms")
        
        p = {
            "title": "Show in File System",
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": True
        }
        
        self.engine.register_command("show_in_filesystem", self.show_in_filesystem, p)
            
    def launch(self, path):
        """
        This method will take a path to a folder and open it in the OS's default file manager.

        :param path: A folder path
        :return: None
        """
        self.log_debug("Launching file system viewer for folder %s" % path)

        # get the setting
        system = sys.platform

        # run the app
        if system == "linux2":
            cmd = 'xdg-open "%s"' % path
        elif system == "darwin":
            cmd = 'open "%s"' % path
        elif system == "win32":
            cmd = 'cmd.exe /C start "Folder" "%s"' % path
        else:
            raise Exception("Platform '%s' is not supported." % system)

        self.log_debug("Executing command '%s'" % cmd)
        exit_code = os.system(cmd)
        if exit_code != 0:
            self.log_error("Failed to launch '%s'!" % cmd)

    def launch_file_folder(self, path):
        """
        This method will take a path to a file and open it in the OS's default file manager.

        :param path: A file path
        :return: None
        """
        self.log_debug("Launching file system viewer for file %s" % path)

        # get the setting
        system = sys.platform

        # build a command that will open and ideally select the file in the OS's default file manager
        if system == "linux2":
            # Can't find a reliable way to open a file browser and select a file on linux
            # So if we get passed a file path, only open up the folder
            cmd = 'xdg-open "%s"' % os.path.dirname(path)
        elif system == "darwin":
            cmd = 'open -R "%s"' % path
        elif system == "win32":
            cmd = 'explorer /select,"%s"' % path
        else:
            raise Exception("Platform '%s' is not supported." % system)

        self.log_debug("Executing command '%s'" % cmd)
        exit_code = os.system(cmd)
        if exit_code != 0:
            self.log_error("Failed to launch '%s'!" % cmd)

    
    def show_in_filesystem(self, entity_type, entity_ids):
        """
        Pop up a filesystem finder window for each folder associated
        with the given entity ids.
        """
        paths = []

        # As the this method relies on the path_cache to find the folders,
        # we must check we are in sync before continuing
        self.sgtk.synchronize_filesystem_structure()

        for eid in entity_ids:

            if entity_type == "PublishedFile":
                # Find the publish so that we can get the path back.
                published_file = self.sgtk.shotgun.find_one("PublishedFile", [["id", "is", eid]], ['code', 'path'])
                # Resolve the path for the local OS
                try:
                    local_path = sgtk.util.resolve_publish_path(self.sgtk, published_file)
                except Exception as e:
                    self.log_debug("Publish path couldn't be resolved falling back to context based path; reason: %s" % e)
                    local_path = None

                if local_path:
                    if (os.path.isdir(local_path) or os.path.isfile(local_path)):
                        # If the path is pointing to a valid file or folder then its good to use as is.
                        paths.append(local_path)
                        continue

                    # possibly we have an image sequence and therefore its a symbolic path, instead check to see if
                    # the parent folder of the path is valid and try opening that.
                    # The issue with this logic is that possibly it was a directory that just didn't exist, as so
                    # we would just be gathering the next directory up, ideally need a better way to handle sequences
                    parent_dir = os.path.dirname(local_path)
                    if parent_dir and os.path.isdir(parent_dir):
                        paths.append(parent_dir)
                        continue

            # Use the path cache to look up all paths linked to the task's entity
            context = self.sgtk.context_from_entity(entity_type, eid)
            context_paths = context.filesystem_locations

            if context.step:
                # As steps are non project entities and not linked from the step to the other entities you won't get step
                # paths back from the context.filesystem_locations
                # If we have a step in the context, we should check to see if we can resolve the path more deeply using that.
                step_paths = self.sgtk.paths_from_entity("Step", context.step['id'])

                for context_path in context_paths:
                    # Loop over the context paths, and check to see if any of them can be extended with a step path.
                    # We take the first match we come across.
                    # If it can't fall back to the standard context path
                    step_path = next((step_path for step_path in step_paths if step_path.startswith(context_path)),
                                     None)
                    if step_path:
                        paths.append(step_path)
                    else:
                        paths.append(context_path)
            else:
                # We don't have a PublishedFile path, or a step path, so we should just use the standard context paths
                # associated with this entity in the path cache.
                paths.extend(context_paths)
                            
        if len(paths) == 0:
            self.log_info("No location exists on disk yet for any of the selected entities. "
                          "Please use shotgun to create folders and then try again!")
        else:
            # launch folder windows
            for x in paths:
                if os.path.isfile(str(x)):
                    self.launch_file_folder(x)
                else:
                    self.launch(x)