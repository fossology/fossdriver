# Copyright The Linux Foundation
# SPDX-License-Identifier: BSD-3-Clause
#
# Based in significant part on fossup from Togán Labs,
# https://gitlab.com/toganlabs/fossup, with the following notice:
#
# Copyright (C) 2016-2018, Togan Labs Ltd. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import json
import logging
from mimetypes import MimeTypes
import os
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import time
import urllib

import fossdriver.parser

class FossServer(object):

    def __init__(self, config):
        # connection data
        self.config = config
        self.session = requests.Session()

    def _get(self, endpoint):
        """Helper function: Make a GET call to the Fossology server."""
        url = self.config.serverUrl + endpoint
        r = self.session.get(url)
        logging.debug("GET: " + url + " " + str(r))
        return r

    def _post(self, endpoint, values):
        """Helper function: Make a POST call to the Fossology server."""
        url = self.config.serverUrl + endpoint
        data = values
        r = self.session.post(url, data=data)
        logging.debug("POST: " + url + " " + str(r))
        return r

    def _postFile(self, endpoint, values):
        """Helper function: Make a POST call to the Fossology server with multipart data."""
        url = self.config.serverUrl + endpoint
        data = MultipartEncoder(fields=values)
        headers = {
            'Content-Type': data.content_type,
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'Referer': url,
        }
        # FIXME is this next line necessary?
        # cookies = self.session.cookies.get_dict()

        r = self.session.post(url, data=data, headers=headers)
        logging.debug("POST (file): " + url + " " + str(r))
        return r

    def Login(self):
        """Log in to Fossology server. Should be the first call made."""
        endpoint = "/repo/?mod=auth"
        values = {
            "username": self.config.username,
            "password": self.config.password,
        }
        self._post(endpoint, values)
        # FIXME check for success?

    def GetFolderNum(self, folderName):
        """Find folder ID number for the given folder name from Fossology server."""
        # retrieve from upload_file, since that provides the list of all folders
        endpoint = "/repo/?mod=upload_file"
        results = self._get(endpoint)
        return fossdriver.parser.parseFolderNumber(results.content, folderName)

    def _getUploadData(self, folderNum, uploadName, exact=True):
        """
        Helper to retrieve upload data for the given name from Fossology server.
        Arguments:
            - folderNum: ID number for folder to search, likely obtained from GetFolderNum.
            - uploadName: name of upload to search for.
            - exact: if True, will return the first upload to have exactly this name.
                     if False, will return the first upload to contain this name.
        """
        # FIXME note that using browse-processPost means we may only get
        # FIXME the first 100 uploads in the folder. may be able to check
        # FIXME iTotalDisplayRecords and loop to get more if needed
        endpoint = f"/repo/?mod=browse-processPost&folder={folderNum}&iDisplayStart=0&iDisplayLength=100"
        results = self._get(endpoint)
        rj = json.loads(results.content)
        uploadData = rj.get("aaData", None)
        if uploadData is None:
            return None

        parsedUploads = fossdriver.parser.parseAllUploadDataForFolder(uploadData)
        if parsedUploads == []:
            return None
        for u in parsedUploads:
            if exact == True and uploadName == u.name:
                return u
            if exact == False and uploadName in u.name:
                return u
        return None

    def GetUploadNum(self, folderNum, uploadName, exact=True):
        """
        Find upload ID number for the given name from Fossology server.
        Arguments:
            - folderNum: ID number for folder to search, likely obtained from GetFolderNum.
            - uploadName: name of upload to search for.
            - exact: if True, will return the first upload to have exactly this name.
                     if False, will return the first upload to contain this name.
        """
        u = self._getUploadData(folderNum, uploadName, exact)
        if u is None:
            return -1
        return u._id

    def _getUploadFormBuildToken(self):
        """Helper function: Obtain a hidden one-time form token to upload a file for scanning."""
        endpoint = f"/repo/?mod=upload_file"
        results = self._get(endpoint)
        return fossdriver.parser.parseUploadFormBuildToken(results.content)

    def CreateFolder(self, parentFolderNum, folderName, folderDesc=""):
        """
        Create a new folder for scans.
        Arguments:
            - parentFolderNum: ID number of parent folder.
            - folderName: new name for folder.
            - folderDesc: new description for folder. Defaults to empty string.
        """
        endpoint = f"/repo/?mod=folder_create"
        values = {
            "parentid": str(parentFolderNum),
            "newname": folderName,
            "description": folderDesc,
        }
        self._post(endpoint, values)

    def StartUpload(self, filePath, folderNum):
        """
        Initiate an upload to the Fossology server. No scanning agents will be triggered.
        Arguments:
            - filePath: path to file being uploaded.
            - folderNum: ID number of folder to receive upload.
        """
        endpoint = f"/repo/?mod=upload_file"
        basename = os.path.basename(os.path.expanduser(filePath))
        print(f"Uploading {basename} to folder {folderNum}...")

        # determine mime type
        mime = MimeTypes()
        murl = urllib.request.pathname2url(filePath)
        mime_type = mime.guess_type(murl)

        # retrieve custom token for upload
        buildtoken = self._getUploadFormBuildToken()

        values = (
            ("uploadformbuild", buildtoken),
            ("folder", str(folderNum)),
            ("fileInput", (basename, open(filePath, "rb"), mime_type[0])),
            ("descriptionInputName", basename),
            ("public", "private"),
            ("Check_agent_bucket", "0"),
            ("Check_agent_copyright", "0"),
            ("Check_agent_ecc", "0"),
            ("Check_agent_mimetype", "0"),
            ("Check_agent_nomos", "0"),
            ("Check_agent_monk", "0"),
            ("Check_agent_pkgagent", "0"),
            ("deciderRules[]", ""),
        )

        results = self._postFile(endpoint, values)
        print("done")
        return fossdriver.parser.parseAnchorTagsForNewUploadNumber(results.content)
