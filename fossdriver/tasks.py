# Copyright The Linux Foundation
# SPDX-License-Identifier: BSD-3-Clause

import logging

class Task(object):
    def __init__(self, server, _type="unspecified"):
        self.server = server
        self._type = _type

    def __repr__(self):
        return f"Task: {self._type}"

    def run(self):
        """Run the specified Task and return success or failure."""
        return False

class CreateFolder(Task):
    def __init__(self, server, newFolderName, parentFolderName):
        super(CreateFolder, self).__init__(server, "CreateFolder")
        self.newFolderName = newFolderName
        self.parentFolderName = parentFolderName

    def __repr__(self):
        return f"Task: {self._type} (new folder {self.newFolderName}, parent folder {self.parentFolderName})"

    def run(self):
        logging.info(f"Running task: {self._type}")
        """Create the folder and return success or failure."""
        # FIXME check whether the folder already exists
        # first, get the parent folder ID
        parentFolderNum = self.server.GetFolderNum(self.parentFolderName)
        if parentFolderNum is None or parentFolderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for parent folder {self.parentFolderName}")
            return False

        # now, create the folder
        logging.info(f"Creating folder {self.newFolderName} in parent folder {self.parentFolderName} ({parentFolderNum})")
        self.server.CreateFolder(parentFolderNum, self.newFolderName, self.newFolderName)
        # FIXME check to see whether it was successfully created?

        # note that no waiting is necessary because this is an instant action
        return True

class Upload(Task):
    def __init__(self, server, filePath, folderName):
        super(Upload, self).__init__(server, "Upload")
        self.filePath = filePath
        self.folderName = folderName

    def __repr__(self):
        return f"Task: {self._type} (filePath {self.filePath}, folder {self.folderName})"

    def run(self):
        logging.info(f"Running task: {self._type}")
        """Start the upload, wait until it completes and return success or failure."""
        # first, get the destination folder ID
        folderNum = self.server.GetFolderNum(self.folderName)
        if folderNum is None or folderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for folder {self.folderName}")
            return False

        # now, start the upload
        logging.info(f"Uploading {self.filePath} to folder {self.folderName} ({folderNum})")
        newUploadNum = self.server.UploadFile(self.filePath, folderNum)
        if newUploadNum is None or newUploadNum < 1:
            logging.error(f"Failed: could not receive ID number for upload {self.filePath}")
            return False
        logging.info(f"Upload complete, {self.filePath} upload ID number is {newUploadNum}")

        # and wait until upload finishes unpacking
        logging.info(f"Waiting for upload {newUploadNum} to unpack")
        self.server.WaitUntilAgentIsDone(newUploadNum, "ununpack", pollSeconds=5)
        self.server.WaitUntilAgentIsDone(newUploadNum, "adj2nest", pollSeconds=5)

        return True

class Scanners(Task):
    def __init__(self, server, uploadName, folderName):
        super(Scanners, self).__init__(server, "Scanners")
        self.uploadName = uploadName
        self.folderName = folderName

    def __repr__(self):
        return f"Task: {self._type} (uploadName {self.uploadName}, folder {self.folderName})"

    def run(self):
        """Start the monk and nomos agents, wait until they complete and return success or failure."""
        logging.info(f"Running task: {self._type}")
        # first, get the folder and then upload ID
        folderNum = self.server.GetFolderNum(self.folderName)
        if folderNum is None or folderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for folder {self.folderName}")
            return False
        uploadNum = self.server.GetUploadNum(folderNum, self.uploadName)
        if uploadNum is None or uploadNum == -1:
            logging.error(f"Failed: could not retrieve upload number for upload {self.uploadName} in folder {self.folderName} ({folderNum})")
            return False

        # now, start the scanners
        logging.info(f"Running monk and nomos scanners on upload {self.uploadName} ({uploadNum})")
        self.server.StartMonkAndNomosAgents(uploadNum)

        # and wait until both scanners finish
        logging.info(f"Waiting for monk and nomos to finish for upload {self.uploadName} ({uploadNum})")
        self.server.WaitUntilAgentIsDone(uploadNum, "monk", pollSeconds=5)
        self.server.WaitUntilAgentIsDone(uploadNum, "nomos", pollSeconds=5)

        return True

class Copyright(Task):
    def __init__(self, server, uploadName, folderName):
        super(Copyright, self).__init__(server, "Copyright")
        self.uploadName = uploadName
        self.folderName = folderName

    def __repr__(self):
        return f"Task: {self._type} (uploadName {self.uploadName}, folder {self.folderName})"

    def run(self):
        """Start the copyright agent, wait until it completes and return success or failure."""
        logging.info(f"Running task: {self._type}")
        # first, get the folder and then upload ID
        folderNum = self.server.GetFolderNum(self.folderName)
        if folderNum is None or folderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for folder {self.folderName}")
            return False
        uploadNum = self.server.GetUploadNum(folderNum, self.uploadName)
        if uploadNum is None or uploadNum == -1:
            logging.error(f"Failed: could not retrieve upload number for upload {self.uploadName} in folder {self.folderName} ({folderNum})")
            return False

        # now, start the scanners
        logging.info(f"Running copyright agent on upload {self.uploadName} ({uploadNum})")
        self.server.StartCopyrightAgent(uploadNum)

        # and wait until both scanners finish
        logging.info(f"Waiting for copyright agent to finish for upload {self.uploadName} ({uploadNum})")
        self.server.WaitUntilAgentIsDone(uploadNum, "copyright", pollSeconds=5)

        return True

class Reuse(Task):
    def __init__(self, server, newUploadName, newFolderName, oldUploadName, oldFolderName):
        super(Reuse, self).__init__(server, "Reuse")
        self.oldUploadName = oldUploadName
        self.oldFolderName = oldFolderName
        self.newUploadName = newUploadName
        self.newFolderName = newFolderName

    def __repr__(self):
        return f"Task: {self._type} (old: uploadName {self.oldUploadName}, folder {self.oldFolderName}; new: uploadName {self.newUploadName}, folder {self.newFolderName})"

    def run(self):
        """Start the reuser agents, wait until it completes and return success or failure."""
        logging.info(f"Running task: {self._type}")
        # first, get the old scan's folder and upload ID
        oldFolderNum = self.server.GetFolderNum(self.oldFolderName)
        if oldFolderNum is None or oldFolderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for old folder {self.oldFolderName}")
            return False
        oldUploadNum = self.server.GetUploadNum(oldFolderNum, self.oldUploadName)
        if oldUploadNum is None or oldUploadNum == -1:
            logging.error(f"Failed: could not retrieve upload number for old upload {self.oldUploadName} in folder {self.oldFolderName} ({oldFolderNum})")
            return False

        # next, get the new scan's folder and upload ID
        newFolderNum = self.server.GetFolderNum(self.newFolderName)
        if newFolderNum is None or newFolderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for new folder {self.newFolderName}")
            return False
        newUploadNum = self.server.GetUploadNum(newFolderNum, self.newUploadName)
        if newUploadNum is None or newUploadNum == -1:
            logging.error(f"Failed: could not retrieve upload number for new upload {self.newUploadName} in folder {self.newFolderName} ({newFolderNum})")
            return False

        # now, start the reuser agent
        logging.info(f"Running reuser agent on upload {self.newUploadName} ({newUploadNum}) reusing old upload {self.oldUploadName} ({oldUploadNum})")
        self.server.StartReuserAgent(newUploadNum, oldUploadNum)

        # and wait until reuser finishes
        logging.info(f"Waiting for reuser to finish for upload {self.newUploadName} ({newUploadNum}) reusing old upload {self.oldUploadName} ({oldUploadNum})")
        self.server.WaitUntilAgentIsDone(newUploadNum, "reuser", pollSeconds=5)

        return True

class BulkTextMatch(Task):
    def __init__(self, server, uploadName, folderName, refText):
        super(BulkTextMatch, self).__init__(server, "BulkTextMatch")
        self.uploadName = uploadName
        self.folderName = folderName
        self.refText = refText
        # actionTuples will be list of (str: licenseName, str: "add" or "remove")
        self.actionTuples = []
        self.parsedLicenses = None

    def add(self, licenseName):
        """Create an "add" action and include it in the bulk actions."""
        actionTuple = (licenseName, "add")
        self.actionTuples.append(actionTuple)

    def remove(self, licenseName):
        """Create a "remove" action and include it in the bulk actions."""
        actionTuple = (licenseName, "remove")
        self.actionTuples.append(actionTuple)

    def _findLicenseID(self, licenseName):
        """Helper function: retrieve license ID for given license name."""
        # FIXME will only get licenses from server once, and will then cache
        # FIXME the result. this will be faster than retrieving the full list
        # FIXME every time an action is added / removed, but means that some
        # FIXME license changes on the server may not be reflected here.

        if self.parsedLicenses is None:
            # need to get upload ID + upload item ID so we can get licenses
            folderNum = self.server.GetFolderNum(self.folderName)
            if folderNum is None or folderNum == -1:
                logging.error(f"Failed: could not retrieve folder number for folder {self.folderName} when getting licenses")
                return -1
            u = self.server._getUploadData(folderNum, self.uploadName, False)
            if u is None:
                logging.error(f"Failed: could not retrieve upload data for upload {self.uploadName} when getting licenses")
                return -1
            self.parsedLicenses = self.server.GetLicenses(u._id, u.topTreeItemId)
            if self.parsedLicenses is None or self.parsedLicenses == []:
                logging.error(f"Failed: could not retrieve licenses for upload {self.uploadName}")
                return -1

        lic = self.server.FindLicenseInParsedList(self.parsedLicenses, licenseName)
        return lic._id

    def _makeRealAction(self, licenseName, actionType):
        """Helper function: make an action entry at the time the Task is being run."""
        licenseId = self._findLicenseID(licenseName)
        if licenseId == -1:
            logging.error(f"Failed: could not get license ID for license {licenseName}")
            return None
        return self.server.MakeBulkTextMatchAction(licenseId, licenseName, actionType)

    def run(self):
        """Start the monkbulk agent, wait until it completes and return success or failure."""
        logging.info(f"Running task: {self._type}")
        # first, get the folder and then upload ID, and full upload data
        folderNum = self.server.GetFolderNum(self.folderName)
        if folderNum is None or folderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for folder {self.folderName}")
            return False
        uploadNum = self.server.GetUploadNum(folderNum, self.uploadName)
        if uploadNum is None or uploadNum == -1:
            logging.error(f"Failed: could not retrieve upload number for upload {self.uploadName} in folder {self.folderName} ({folderNum})")
            return False
        u = self.server._getUploadData(folderNum, self.uploadName, False)
        if u is None:
            logging.error(f"Failed: could not retrieve upload data for upload {self.uploadName} when getting licenses")
            return -1

        # next, create the real actions list from the action tuples
        logging.info(f"=====> actionTuples: {self.actionTuples}")
        actionList = []
        for (licenseName, actionType) in self.actionTuples:
            a = self._makeRealAction(licenseName, actionType)
            if a is None:
                logging.error(f"Failed: could not create action for ({licenseName}, {actionType}) for upload {self.uploadName}")
                return False
            actionList.append(a)
        logging.info(f"=====> actionList: {actionList}")

        # now, start the bulk text match agent
        logging.info(f"Running monkbulk agent on upload {self.uploadName} ({uploadNum})")
        self.server.StartBulkTextMatch(self.refText, u.topTreeItemId, actionList)

        # and wait until agent finishes
        logging.info(f"Waiting for monkbulk to finish for upload {self.uploadName} ({uploadNum})")
        self.server.WaitUntilAgentIsDone(uploadNum, "monkbulk", pollSeconds=5)

        return True

class SPDXTV(Task):
    def __init__(self, server, uploadName, folderName, outFilePath):
        super(SPDXTV, self).__init__(server, "SPDXTV")
        self.uploadName = uploadName
        self.folderName = folderName
        self.outFilePath = outFilePath

    def __repr__(self):
        return f"Task: {self._type} (uploadName {self.uploadName}, folder {self.folderName}) to file {self.outFileName}"

    def run(self):
        """Start the spdx2tv agents, wait until it completes and return success or failure."""
        logging.info(f"Running task: {self._type}")
        # first, get the folder and then upload ID
        folderNum = self.server.GetFolderNum(self.folderName)
        if folderNum is None or folderNum == -1:
            logging.error(f"Failed: could not retrieve folder number for folder {self.folderName}")
            return False
        uploadNum = self.server.GetUploadNum(folderNum, self.uploadName)
        if uploadNum is None or uploadNum == -1:
            logging.error(f"Failed: could not retrieve upload number for upload {self.uploadName} in folder {self.folderName} ({folderNum})")
            return False

        # now, start the export agent
        logging.info(f"Running spdx2tv agent on upload {self.uploadName} ({uploadNum})")
        self.server.StartSPDXTVReportGeneratorAgent(uploadNum)

        # wait until the export agent finishes
        logging.info(f"Waiting for spdx2tv to finish for upload {self.uploadName} ({uploadNum})")
        self.server.WaitUntilAgentIsDone(uploadNum, "spdx2tv", pollSeconds=5)

        # finally, get and save the SPDX file
        retval = self.server.GetSPDXTVReport(uploadNum, self.outFilePath)
        return retval

# to add:
# Copyright
