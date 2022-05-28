# Copyright Contributors to the fossdriver project.
# SPDX-License-Identifier: BSD-3-Clause OR MIT

import json
import logging
from mimetypes import MimeTypes
import os
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import time
import urllib
import io
import sys
from version_parser import Version

import fossdriver.parser

NOT_LOGGED_IN_RESPONSE = 'session timed out'
USER_PASSWORD_NOT_FOUND = 'The combination of user name and password was not found'
MAX_LOGIN_ATTEMPTS = 5

class FossServerException(Exception):
    pass

class BulkTextMatchAction(object):
    def __init__(self):
        self.licenseId = -1
        self.licenseName = ""
        # action should be either "add" or "remove"
        self.action = ""

    def __repr__(self):
        return "BulkTextMatchAction: [{}], [{}], [{}]".format(self.action, self.licenseName, self.licenseId)

class FossServer(object):

    def __init__(self, config):
        # connection data
        self.config = config
        self.session = requests.Session()
        self.serverVersion = ""
        self.loginAttempts = 0
        
    def _checkLoggedIn(self, response):
        """ Returns true if the user is logged in """
        return not (response.ok and response.text != None and NOT_LOGGED_IN_RESPONSE in response.text)

    def _retryRequest(self, fn, *args, **kwargs):
        """ Retries a Request function checking for being logged in.  
        fn is function to call that returns a request object """
        exc = None
        connectionRetries = 0
        while connectionRetries < 5 and self.loginAttempts <= MAX_LOGIN_ATTEMPTS:
            try:
                r = fn(*args, **kwargs);
                if self._checkLoggedIn(r):
                    self.loginAttempts = 0
                    return r
                else:
                    self.loginAttempts += 1
                    self.Login()
            except requests.exceptions.ConnectionError as e:
                # try again after a brief pause
                time.sleep(1)
                exc = e
                logging.debug("attempt " + str(connectionRetries+1) + " failed")
            except Exception as e:
                logging.error("Unexpected exception in request - retrying...")
                exc = e
                time.sleep(1)
        # If we got here, we're in some sort of trouble...
        if  self.loginAttempts >= MAX_LOGIN_ATTEMPTS:
            logging.error("Unable to relogin - max login attempts exceeded")
            raise FossServerException('Maximum Login Attempts Exceeded')
        else:
            raise exc
            

    def _get(self, endpoint):
        """Helper function: Make a GET call to the Fossology server."""
        url = self.config.serverUrl + endpoint
        logging.debug("GET: " + url)
        return self._retryRequest(self.session.get, url);
        

    def _post(self, endpoint, values):
        """Helper function: Make a POST call to the Fossology server."""
        url = self.config.serverUrl + endpoint
        data = values
        exc = None
        logging.debug("POST: " + url)
        return self._retryRequest(self.session.post, url, data=data);

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
        return self._retryRequest(self.session.post, url, data=data, headers=headers);

    def Version(self):
        """Get the version number of the Fossology server."""
        endpoint = "/repo/"
        results = self._get(endpoint)
        return fossdriver.parser.parseVersionNumber(results.content)

    def IsAtLeastVersion(self, compareVersionStr):
        """
        Returns True if the Fossology server's version is _at least_
        as high as the specified compareVersionStr argument.
        The check uses the version-parser PyPI package, so it may need
        further testing on whether it correctly handles e.g. RC- and
        interim commit versions.
        """
        if self.serverVersion == 'unknown':
            # Assume git clones are a recent version, we can't really do
            # anything better than this...
            return True

        serverVer = Version(self.serverVersion)
        compareVer = Version(compareVersionStr)
        return serverVer >= compareVer

    def Login(self):
        """
        Log in to Fossology server. Should be the first call made,
        other than Version calls which can occur without logging in.
        """
        endpoint = "/repo/?mod=auth"
        values = {
            "username": self.config.username,
            "password": self.config.password,
        }
        r = self._post(endpoint, values)
        if USER_PASSWORD_NOT_FOUND in r.text:
            raise FossServerException('Unsuccessful Login')
        self.serverVersion = self.Version()

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
        endpoint = "/repo/?mod=browse-processPost&folder={}&iDisplayStart=0&iDisplayLength=100".format(folderNum)
        results = self._get(endpoint)
        rj = json.loads(results.content.decode('utf-8'))
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

        # determine mime type
        mime = MimeTypes()
        if sys.version_info > (3, 4):
            murl = urllib.request.pathname2url(filePath)
        else:
            murl = urllib.pathname2url(filePath)
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
        return fossdriver.parser.parseAnchorTagsForNewUploadNumber(results.content)

    def GetLicenses(self, uploadNum, itemNum):
        """
        Obtain a dict of all licenses available in the Fossology server.
        Requires upload and item numbers due to Fossology server interface.
        Arguments:
            - uploadNum: valid ID number for an existing upload.
            - topTreeItemNum: valid ID number for an item in that upload.
        """
        endpoint = "/repo/?mod=view-license&upload={}&item={}".format(uploadNum, itemNum)
        results = self._get(endpoint)
        licenses = fossdriver.parser.parseAllLicenseData(results.content)
        return licenses

    def GetUploadStatistics(self, uploadNum, itemNum):
        """
        Obtain a list of tuples in (str, int) format, where each str is one
        of the "Summary" values from the left side of the License view, and
        the int is the corresponding count.
        Requires upload and item numbers due to Fossology server interface.
        Arguments:
            - uploadNum: valid ID number for an existing upload.
            - topTreeItemNum: valid ID number for an item in that upload.
        """
        endpoint = "/repo/?mod=license&upload={}&item={}".format(uploadNum, itemNum)
        results = self._get(endpoint)
        stats = fossdriver.parser.parseStatisticsFromLicenseBrowser(results.content)
        return stats

    def FindLicenseInParsedList(self, parsedLicenses, licName):
        """
        Find the ParsedLicense object with the given license name.
        Assumes that the list of licenses is from a prior call to GetLicenses.
        Arguments:
            - parsedLicenses: a list of ParsedLicenses, likely obtained from GetLicenses.
            - licName: license name to search for
        Returns: ParsedLicense object with given name or None if not found.
        """
        for lic in parsedLicenses:
            if lic.name == licName:
                return lic
        return None

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
        # response format changed from XML to JSON on or around 3.5.0
        # see https://github.com/fossology/fossdriver/issues/17
        if self.IsAtLeastVersion("3.5.0"):
            # parse json
            jobData = fossdriver.parser.parseJSONShowJobsData(results.content)
            return jobData
        else:
            # decode and parse XML
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
        endpoint = "/repo/?mod=ajaxShowJobs&do=showSingleJob&jobId={}".format(jobNum)
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
            "uploadToReuse": "{}, 3".format(reusedUploadNum),
        }
        self._post(endpoint, values)

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
        self._post(endpoint, values)

    def StartCopyrightAgent(self, uploadNum):
        """
        Start the copyright agent.
        Arguments:
            - uploadNum: ID number of upload to analyze.
        """
        endpoint = "/repo/?mod=agent_add"
        values = {
            "agents[]": "agent_copyright",
            "upload": str(uploadNum),
        }
        self._post(endpoint, values)

    def StartSPDXTVReportGeneratorAgent(self, uploadNum):
        """
        Start the spdx2tv agent to generate an SPDX tag-value report.
        Arguments:
            - uploadNum: ID number of upload to export as tag-value.
        """
        endpoint = "/repo/?mod=ui_spdx2&outputFormat=spdx2tv&upload={}".format(uploadNum)
        self._get(endpoint)

    def StartSPDXRDFReportGeneratorAgent(self, uploadNum):
        """
        Start the spdx2 agent to generate an SPDX RDF report.
        Arguments:
            - uploadNum: ID number of upload to export as RDF.
        """
        endpoint = "/repo/?mod=ui_spdx2&outputFormat=spdx2&upload={}".format(uploadNum)
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
        endpoint = "/repo/?mod=download&report={}".format(job.reportId)
        results = self._get(endpoint)
        if sys.version_info > (3, 4):
            with open(outFilePath, "w") as f:
                f.write(results.content.decode("utf-8"))
        else:
            with io.open(outFilePath, "w", encoding="utf-8") as f:
                f.write(results.content.decode("utf-8"))
        return True

    def GetSPDXRDFReport(self, uploadNum, outFilePath):
        """
        Download and write to disk the SPDX RDF report for the most recent
        spdx2 agent.
        Arguments:
            - uploadNum: ID number of upload to retrieve report for.
            - outFilePath: path to write report to.
        Returns: True if succeeded, False if failed for any reason.
        """
        # first, get reportId so we can build the endpoint
        jobNum = self._getMostRecentAgentJobNum(uploadNum, "spdx2")
        job = self._getJobSingleData(jobNum)
        if job.agent != "spdx2" or job.status != "Completed":
            return False

        # now, go get the actual report
        endpoint = "/repo/?mod=download&report={}".format(job.reportId)
        results = self._get(endpoint)
        if sys.version_info > (3, 4):
            with open(outFilePath, "w") as f:
                f.write(results.content.decode("utf-8"))
        else:
            with io.open(outFilePath, "w", encoding="utf-8") as f:
                f.write(results.content.decode("utf-8"))
        return True

    def MakeBulkTextMatchAction(self, licenseId, licenseName, action):
        """Create and return a BulkTextMatchAction object with the given data."""
        # FIXME should this validate that the requested actions / lics are valid?
        btma = BulkTextMatchAction()
        btma.licenseId = licenseId
        btma.licenseName = licenseName
        btma.action = action
        return btma

    def StartBulkTextMatch(self, refText, itemNum, actions):
        """
        Start the monkbulk agent to run a bulk text match.
        Arguments:
            - refText: text to match on.
            - itemNum: ID number for tree item within upload (NOT the upload number).
            - actions: list of BulkTextMatchActions to perform.
        """
        endpoint = "/repo/?mod=change-license-bulk"
        # start building values
        values = {
            "refText": refText,
            "bulkScope": "u",
            "uploadTreeId": str(itemNum),
            "forceDecision": "0",
        }
        # now, build and add bulkAction data rows
        row = 0
        for action in actions:
            # FIXME should this validate that the requested actions / lics are valid?
            rowPrefix = "bulkAction[{}]".format(row)
            values["{}[licenseId]".format(rowPrefix)] = str(action.licenseId)
            values["{}[licenseName]".format(rowPrefix)] = action.licenseName
            values["{}[action]".format(rowPrefix)] = action.action
            row += 1
        self._post(endpoint, values)

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

    def StartRDFImport(self, rdfPath, folderNum, uploadNum):
        """
        Initiate an import of an RDF file to the Fossology server. The RDF file will
        be uploaded and then the reportImport agent will be triggered.

        NOTE that currently this makes the following assumptions, which are not
        currently configurable (but could be):
            - import licenses as new rather than candidate
            - import concluded license findings (and overwrite)
            - do not import licenseInfoInFile license findings
            - do not set file as TBD
            - do not import copyright findings (appears to cause problems with
              duplicates, based on my preliminary tests)

        Arguments:
            - rdfPath: path to RDF file being uploaded for import.
            - folderNum: ID number of folder where upload is located.
            - uploadNum: ID number of existing upload to be analyzed.
        """
        endpoint = "/repo/?mod=ui_reportImport"
        basename = os.path.basename(os.path.expanduser(rdfPath))

        # determine mime type
        # FIXME consider whether this should check and/or force to application/rdf+xml
        mime = MimeTypes()
        if sys.version_info > (3, 4):
            murl = urllib.request.pathname2url(rdfPath)
        else:
            murl = urllib.pathname2url(rdfPath)
        mime_type = mime.guess_type(murl)

        values = (
            ("oldfolderid", str(folderNum)),
            ("uploadselect", str(uploadNum)),
            ("report", (basename, open(rdfPath, "rb"), mime_type[0])),
            ("addNewLicensesAs", "license"),
            ("addConcludedAsDecisions", "true"),
            ("addConcludedAsDecisionsOverwrite", "true"),
        )

        results = self._postFile(endpoint, values)
        # FIXME should anything be returned?
