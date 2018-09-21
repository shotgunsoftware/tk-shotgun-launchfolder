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
from sgtk.util.errors import PublishPathNotDefinedError, PublishPathNotSupported
import sys
import os
import subprocess

class LaunchFolder(sgtk.platform.Application):
    
    def init_app(self):
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
        Given a path this method will choose the appropriate way to open that as a folder in the OS's default
        file manager. If the path to the file is invalid then nothing will happen.
        :param path: A path to a file or folder.
        """

        if os.path.isfile(path):
            self._launch_filemanager_for_file(path)
        elif os.path.isdir(path):
            self._launch_filemanager_for_folder(path)
        else:
            # possibly we have an image sequence and therefore its a symbolic path, instead check to see if
            # the parent folder of the path is valid and try opening that.
            # todo: The issue with this logic is that possibly it was a directory that just didn't exist,
            # so we would just be gathering the next directory up,
            # ideally need a better way to handle sequences.
            parent_dir = os.path.dirname(path)
            self._launch_filemanager_for_folder(parent_dir)

            
    def _launch_filemanager_for_folder(self, path):
        """
        This method will take a path to a folder and open it in the OS's default file manager.
        :param path: A folder path
        :raises: Exception: if the Platform is not supported
        :raises: ValueError: if the path is not a valid directory.
        """
        self.log_debug("Launching file system viewer for folder %s" % path)

        # Check that we don't have a file path.
        if not os.path.isdir(path):
            raise ValueError(
                "The path \"%s\" is not a valid directory." % path)

        # get the setting
        system = sys.platform
        self.log_debug("Detected system: %s" % system)

        # build the commands for opening the folder on the various OS's
        if system.startswith("linux"):
            cmd_args = ["xdg-open", path]
        elif system == "darwin":
            cmd_args = ["open", path]
        elif system == "win32":
            cmd_args= ["cmd.exe", "/C", "start", path ]
        else:
            raise Exception("Platform '%s' is not supported." % system)

        self.log_debug("Executing command '%s'" % cmd_args)
        exit_code = subprocess.call(cmd_args)
        if exit_code != 0:
            self.log_error("Failed to launch '%s'!" % cmd_args)

    def _launch_filemanager_for_file(self, path):
        """
        This method will take a path to a file and open it in the OS's default file manager.
        This is only used for files, for folders use _launch_filemanager_for_folder.
        :param path: A file path
        :raises: Exception: if the Platform is not supported
        :raises: ValueError: if the path is not a valid file.
        """
        self.log_debug("Launching file system viewer for file %s" % path)

        if not os.path.isfile(path):
            raise ValueError(
                "The path \"%s\" is not a valid file path." % path)

        # get the setting
        system = sys.platform
        self.log_debug("Detected system: %s" % system)

        if system.startswith("linux"):
            cmd_args = ["xdg-open", os.path.dirname(path)]
        elif system == "darwin":
            cmd_args = ["open", "-R", path]
        elif system == "win32":
            # /select makes windows select the file within the explorer window
            # The problem with this approach is that it always returns back an error code of 1 even if it
            # does behave correctly.ß
            cmd_args = ["explorer", "/select,", path]
        else:
            raise Exception("Platform '%s' is not supported." % system)

        self.log_debug("Executing command '%s'" % cmd_args)
        exit_code = subprocess.call(cmd_args)

        if system == "win32":
            # As mentioned above the Windows command will always return error code 1 regardless of success
            # So all we can do is check if path exists and hope that it ran.
            if not os.path.exists(path):
                self.log_error("Failed to launch '%s'!" % cmd_args)
        elif exit_code != 0:
            self.log_error("Failed to launch '%s'!" % cmd_args)

    def _get_published_file_path(self, entity_id):
        """
        Will attempt to return back a resolved path for a PublishedFile entity
        :param entity_id: int for the PublishedFile ID.
        :return: str path or None depending on whether it successfully resolves the path.
        """

        # Find the publish so that we can get the path back.
        # Note there is a bug with the resolve_publish_path method requiring the `code` to be present, even though we
        # don't really need it. If this bug (SG-8 is fixed in the future we can remove the need to gather the code.
        published_file = self.sgtk.shotgun.find_one("PublishedFile", [["id", "is", entity_id]], ["code", "path"])
        # Resolve the path for the local OS
        try:
            local_path = sgtk.util.resolve_publish_path(self.sgtk, published_file)
            self.log_debug("Gathered path for PublishedFile entity %s path: %s " % (entity_id, local_path))
        except (PublishPathNotDefinedError, PublishPathNotSupported) as e:
            # It might fail to resolve the path to the publish if the published file is an uploaded file
            # or URL, in which case we revert to the default context based method.
            self.log_warning("Publish path couldn't be resolved "
                             "falling back to context based path; reason: %s" % e)
            local_path = None

        return local_path

    def show_in_filesystem(self, entity_type, entity_ids):
        """
        Pop up a filesystem finder window for each folder associated
        with the given entity ids.
        """
        paths = []

        # As the this method relies on the path_cache to find the folders,
        # we must check we are in sync before continuing.
        self.sgtk.synchronize_filesystem_structure()

        for eid in entity_ids:

            pub_file_path = None

            if entity_type == "PublishedFile":
                # If the entity type is a PublishedFile, we should try at first to extract the path of the publish
                # and open the folder for that. If we can't we will fall back on the context driven path.
                self.log_debug("Getting path for PublishedFile entity %s " % eid)
                pub_file_path = self._get_published_file_path(eid)

            if pub_file_path:
                paths.append(pub_file_path)

            else:
                # We've not found a path to a specific file for the entity, so we should try to resolve the path
                # using the path cache instead.

                # Use the path cache to look up all paths linked to the task's entity
                context = self.sgtk.context_from_entity(entity_type, eid)

                # todo: Add support for step folders, when a step is present in the context, open the step folder

                # We don't have a PublishedFile path, so we should just use the standard context paths
                # associated with this entity in the path cache.
                paths.extend(context.filesystem_locations)
                            
        if len(paths) == 0:
            self.log_info("No location exists on disk yet for any of the selected entities. "
                          "Please use shotgun to create folders and then try again!")
        else:
            self.log_info("Paths to open: %s" % paths)
            # launch folder windows
            for x in paths:
                self.launch(x)