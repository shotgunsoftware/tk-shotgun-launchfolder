# Copyright (c) 2020 Shotgun Software Inc.
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
from sgtk.util import filesystem


class LaunchFolder(sgtk.platform.Application):
    def init_app(self):
        deny_permissions = self.get_setting("deny_permissions")
        deny_platforms = self.get_setting("deny_platforms")

        p = {
            "title": "Show in File System",
            "deny_permissions": deny_permissions,
            "deny_platforms": deny_platforms,
            "supports_multiple_selection": True,
        }

        self.engine.register_command("show_in_filesystem", self.show_in_filesystem, p)

    def _get_published_file_path(self, entity_id):
        """
        Will attempt to return back a resolved path for a PublishedFile entity
        :param entity_id: int for the PublishedFile ID.
        :return: str path or None depending on whether it successfully resolves the path.
        """

        # Find the publish so that we can get the path back.
        # Note there is a bug with the resolve_publish_path method requiring the `code` to be present, even though we
        # don't really need it. If this bug (SG-8561) is fixed in the future we can remove the need to gather the code.
        published_file = self.sgtk.shotgun.find_one(
            "PublishedFile", [["id", "is", entity_id]], ["code", "path"]
        )
        # Resolve the path for the local OS
        try:
            local_path = sgtk.util.resolve_publish_path(self.sgtk, published_file)
            self.log_debug(
                "Gathered path for PublishedFile entity %s path: %s "
                % (entity_id, local_path)
            )
        except (PublishPathNotDefinedError, PublishPathNotSupported) as e:
            # It might fail to resolve the path to the publish if the published file is an uploaded file
            # or URL, in which case we revert to the default context based method.
            self.log_warning(
                "Publish path couldn't be resolved "
                "falling back to context based path; reason: %s" % e
            )
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
            self.log_info(
                "No location exists on disk yet for any of the selected entities. "
                "Please use SG to create folders and then try again!"
            )
        else:
            self.log_debug("Paths to open: %s" % paths)
            # launch folder windows
            for x in paths:
                try:
                    filesystem.open_file_browser(x)
                except ValueError as e:
                    self.log_error(
                        "Failed to open the following path as it is not valid!: '%s' Error: %s"
                        % (x, e)
                    )
                except RuntimeError as e:
                    # Catch the exception and just re raise it through log_error
                    self.log_error("%s" % (e))
