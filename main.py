# Copyright The Linux Foundation
# SPDX-License-Identifier: BSD-3-Clause

import json
import os
from pathlib import Path
import sys

from fossdriver.config import FossConfig
from fossdriver.server import FossServer

if __name__ == "__main__":
    # load and parse config file
    config = FossConfig()
    configPath = os.path.join(str(Path.home()), ".fossdriver", "fossdriverrc.json")
    retval = config.configure(configPath)
    if not retval:
        print("Could not load config file; exiting")
        sys.exit(1)

    server = FossServer(config)
    server.Login()

    folder = "Burrow"
    upload = "burrow"

    folderNum = server.GetFolderNum(folder)
    print(f"Folder {folder} is ID {folderNum}")

    uploadNum = server.GetUploadNum(folderNum, upload, False)
    print(f"Upload {upload} is ID {uploadNum}")
