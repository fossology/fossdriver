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
        logging.debug("GET: " + url)
        exc = None
        for i in range(0,5):
            try:
                r = self.session.get(url)
                return r
            except requests.exceptions.ConnectionError as e:
                # try again after a brief pause
                time.sleep(1)
                exc = e
                logging.debug("attempt " + str(i+1) + " failed")
        # if we get here, we failed to connect
        raise exc

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
        endpoint = "/repo/?mod=upload_file"
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
        endpoint = "/repo/?mod=folder_create"
        values = {
            "parentid": str(parentFolderNum),
            "newname": folderName,
            "description": folderDesc,
        }
        self._post(endpoint, values)

    def UploadFile(self, filePath, folderNum):
        """
        Initiate an upload to the Fossology server. No scanning agents will be triggered.
        Arguments:
            - filePath: path to file being uploaded.
            - folderNum: ID number of folder to receive upload.
        """
        endpoint = "/repo/?mod=upload_file"
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

    def _getJobsForUpload(self, uploadNum):
        """Helper function: Retrieve job data for the given upload number."""
        # FIXME currently retrieves just first page
        endpoint = "/repo/?mod=ajaxShowJobs&do=showjb"
        values = {
            "upload": uploadNum,
            "allusers": 0,
            "page": 0,
        }
        results = self._post(endpoint, values)
        decodedContent = fossdriver.parser.decodeAjaxShowJobsData(results.content)
        jobData = fossdriver.parser.parseDecodedAjaxShowJobsData(decodedContent)
        return jobData

    def _getMostRecentAgentJobNum(self, uploadNum, agent):
        """
        Helper function: Retrieve job ID number for most recent agent of given type.
        Arguments:
            - uploadNum: ID number of upload.
            - agent: name of agent to check for.
        Returns job ID number or -1 if not found.
        """
        # FIXME given _getJobsForUpload, currently retrieves just first page
        jobs = self._getJobsForUpload(uploadNum)
        if jobs is None or jobs == []:
            return -1
        # will be returned in reverse chrono order, so we can just loop through
        # and stop on the first one we come to
        for job in jobs:
            if job.agent == agent:
                return job._id
        return -1

    def _getJobSingleData(self, jobNum):
        """Helper function: Retrieve job data for a single job."""
        endpoint = f"/repo/?mod=ajaxShowJobs&do=showSingleJob&jobId={jobNum}"
        results = self._get(endpoint)
        job = fossdriver.parser.parseSingleJobData(results.content)
        return job

    def _isJobDoneYet(self, jobNum):
        """Helper function: Return whether a specified job has completed yet."""
        job = self._getJobSingleData(jobNum)
        if job.status == "Completed":
            return True
        if "killed" in job.status:
            return True
        return False

    def StartReuserAgent(self, uploadNum, reusedUploadNum):
        """
        Start the reuser agent.
        Arguments:
            - uploadNum: ID number of upload to analyze.
            - reusedUploadNum: ID number of upload to be reused.
        """
        # FIXME determine why the magic number 3 is used below --
        # FIXME part of group ID? is it always 3?
        endpoint = "/repo/?mod=agent_add"
        values = {
            "agents[]": "agent_reuser",
            "upload": str(uploadNum),
            "uploadToReuse": f"{reusedUploadNum},3",
        }
        results = self._post(endpoint, values)

    def StartMonkAndNomosAgents(self, uploadNum):
        """
        Start the monk and nomos agents.
        Arguments:
            - uploadNum: ID number of upload to analyze.
        """
        endpoint = "/repo/?mod=agent_add"
        values = {
            "agents[]": ["agent_monk", "agent_nomos"],
            "upload": str(uploadNum),
        }
        results = self._post(endpoint, values)

    def StartSPDXTVReportGeneratorAgent(self, uploadNum):
        """
        Start the spdx2tv agent to generate an SPDX tag-value report.
        Arguments:
            - uploadNum: ID number of upload to export as tag-value.
        """
        endpoint = f"/repo/?mod=ui_spdx2&outputFormat=spdx2tv&upload={uploadNum}"
        self._get(endpoint)

    def GetSPDXTVReport(self, uploadNum, outFilePath):
        """
        Download and write to disk the SPDX tag-value report for the most recent
        spdx2tv agent.
        Arguments:
            - uploadNum: ID number of upload to retrieve report for.
            - outFilePath: path to write report to.
        Returns: True if succeeded, False if failed for any reason.
        """
        # first, get reportId so we can build the endpoint
        jobNum = self._getMostRecentAgentJobNum(uploadNum, "spdx2tv")
        job = self._getJobSingleData(jobNum)
        if job.agent != "spdx2tv" or job.status != "Completed":
            return False

        # now, go get the actual report
        endpoint = f"/repo/?mod=download&report={job.reportId}"
        results = self._get(endpoint)
        with open(outFilePath, "w") as f:
            f.write(results.content.decode("utf-8"))
        return True

    def IsAgentDone(self, uploadNum, agent):
        """
        Return whether the most recent agent for this upload has completed yet.
        Arguments:
            - uploadNum: ID number of upload.
            - agent: name of agent to check for.
        """
        jobNum = self._getMostRecentAgentJobNum(uploadNum, agent)
        return self._isJobDoneYet(jobNum)

    def WaitUntilAgentIsDone(self, uploadNum, agent, pollSeconds=10):
        """
        Poll every __ seconds until the most recent agent for this upload has
        completed.
        Arguments:
            - uploadNum: ID number of upload.
            - agent: name of agent to check for.
            - pollSeconds: number of seconds to wait between polling. Defaults to 10.
        """
        # FIXME consider adding a max # of tries before returning
        jobNum = self._getMostRecentAgentJobNum(uploadNum, agent)
        while not self._isJobDoneYet(jobNum):
            time.sleep(pollSeconds)
