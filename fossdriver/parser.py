# Copyright Contributors to the fossdriver project.
# SPDX-License-Identifier: BSD-3-Clause OR MIT

import bs4
import json
import logging

class ParsedUpload(object):
    def __init__(self):
        self.name = ""
        self._id = -1
        self.folderId = -1
        self.topTreeItemId = -1
        self.spdxTvUrl = ""
        self.spdxXmlUrl = ""

class ParsedLicense(object):
    def __init__(self):
        self.name = ""
        self._id = -1

    def __repr__(self):
        return f"ParsedLicense: {self.name} ({self._id})"

class ParsedJob(object):
    def __init__(self):
        self._id = -1
        self.status = ""
        self.agent = ""
        self.reportId = -1

    def __repr__(self):
        return f"Job {self._id}: {self.agent}, {self.status}"

def parseUploadDataForFolderLineItem(lineItem):
    """
    Parses one line item for parsing the uploads in a folder.
    Returns a ParsedUpload object with the fields filled in.
    """
    u = ParsedUpload()
    # the first item in the list has the data we care about
    soup = bs4.BeautifulSoup(lineItem[0], "lxml")
    # the name is stored in the bold tag
    boldTag = soup.b
    u.name = boldTag.string
    # the top tree item ID is stored in the a tag's href
    aTag = soup.a
    href = aTag.get("href", None)
    if href is not None and "item=" in href:
        p1 = href.partition("item=")
        p2 = p1[2].partition("&show=")
        u.topTreeItemId = int(p2[0])
    # search through option strings to get SPDX URLs
    opt = soup.find("option", {"title": "Generate SPDX report"})
    if opt is not None:
        u.spdxXmlUrl = opt.attrs.get("value")
    opt = soup.find("option", {"title": "Generate SPDX report in tag:value format"})
    if opt is not None:
        u.spdxTvUrl = opt.attrs.get("value")
    # and the upload ID is in lineItem[2][0]
    u._id = lineItem[2][0]
    return u

def parseAllUploadDataForFolder(uploadData):
    """
    Parses all line items from a call to browse-processPost.
    Returns a list of all found ParsedUpload objects.
    """
    parsedUploads = []
    for lineItem in uploadData:
        u = parseUploadDataForFolderLineItem(lineItem)
        if u is not None:
            parsedUploads.append(u)
    return parsedUploads

def parseLicenseDataForOneLicense(lineItem):
    """
    Parses one line item for parsing the available licenses.
    Returns a ParsedLicense object with the fields filled in.
    """
    lic = ParsedLicense()
    # the license ID is stored in the option tag's value attribute
    value = lineItem.get("value", -1)
    lic._id = int(value)
    # the license name is stored in the option tag's contents
    lic.name = lineItem.string
    return lic

def parseAllLicenseData(content):
    """
    Parses all line items from a call to view-license.
    Returns a list of all found ParsedLicense objects.
    """
    parsedLicenses = []
    soup = bs4.BeautifulSoup(content, "lxml")
    sel = soup.find("select", id="bulkLicense")
    if sel is None:
        return []
    options = sel.find_all("option")
    for lineItem in options:
        lic = parseLicenseDataForOneLicense(lineItem)
        if lic is not None:
            parsedLicenses.append(lic)
    return parsedLicenses

def parseUploadFormBuildToken(content):
    """Extract and return the uploadformbuild token from previously-retrieved HTML."""
    soup = bs4.BeautifulSoup(content, "lxml")
    try:
        return soup.find("input", {"name": "uploadformbuild"}).get("value", None)
    except Exception as e:
        logging.warn(f"Couldn't extract uploadformbuild token: {str(e)}")
        return None

def parseFolderNumber(content, folderName):
    """Extract and return the folder ID number for the given folder name."""
    soup = bs4.BeautifulSoup(content, "lxml")
    folders = soup.find_all("select", {"name":"folder"})
    if folders is None:
        return None
    for folder in folders:
        for option in folder.findAll("option"):
            if option.text.strip() == folderName:
                return option["value"]
    return None

def parseAnchorTagsForNewUploadNumber(content):
    """Extract the new upload number from the response in a call to UploadFile."""
    soup = bs4.BeautifulSoup(content, "lxml")
    anchors = soup.find_all("a")
    for anchor in anchors:
        href = anchor.get("href", None)
        if href is None:
            continue
        if "upload=" in href:
            p = href.partition("upload=")
            return int(p[2])
    return -1

def decodeAjaxShowJobsData(content):
    """Extract and decode the raw ajaxShowJobs data."""
    rj = json.loads(content)
    s1 = rj["showJobsData"]
    # this is current a string that has unicode-escaped data.
    # we want to convert it to a bytes object, then re-convert it back
    # to a string and decode the escapes when doing so.
    b1 = s1.encode("utf-8")
    s2 = b1.decode("unicode-escape")
    return s2

def parseDecodedAjaxShowJobsData(content):
    """Parse the ajaxShowJobs data that has already been decoded."""
    soup = bs4.BeautifulSoup(content, "lxml")
    rows = soup.find_all("tr")
    jobData = []
    for row in rows:
        cl = row.get("class", None)
        if cl is None:
            # header or other row; ignore
            continue
        job = ParsedJob()
        cols = row.find_all("td")
        if cols is None or len(cols) < 8:
            continue
        # first column: job ID
        job._id = int(cols[0].a.contents[0])
        # second column: status
        if cols[1].contents == []:
            job.status = "Not started"
        else:
            job.status = cols[1].contents[0]
        # third column: agent name
        job.agent = cols[2].contents[0]
        # fourth column: # of items; may be empty or in process
        # fifth column: date range
        # sixth column: rate
        # seventh column: ETA
        # eighth column: job action
        if job.status == "Completed":
            aLink = cols[7].a
            if aLink is not None:
                href = aLink.get("href", None)
                p = href.partition("report=")
                job.reportId = int(p[2])
        jobData.append(job)
    return jobData

def parseSingleJobData(content):
    """Parse the JSON data returned from status call for a single job."""
    rj = json.loads(content)
    jobArr = rj.get("aaData", None)
    if jobArr is None:
        return None
    job = ParsedJob()
    # first row: job ID
    jobIdRow = jobArr[0]
    jobIdString = jobIdRow.get("1", None)
    if jobIdRow is not None:
        soup = bs4.BeautifulSoup(jobIdString, "lxml")
        aLink = soup.a
        if aLink.contents != []:
            job._id = int(aLink.contents[0])
    # third row: agent name
    jobAgentRow = jobArr[3]
    job.agent = jobAgentRow.get("1", "")
    # twelfth row: job status
    jobStatusRow = jobArr[11]
    statusLines = jobStatusRow.get("1", "")
    if statusLines is not None:
        p = statusLines.partition("<br>")
        job.status = p[0]
    # second row: report ID, if this is an SPDX reporter job
    jobReportIdRow = jobArr[1]
    jobReportIdString = jobReportIdRow.get("1", None)
    if ((job.agent == "spdx2tv" or job.agent == "spdx2") and
        job.status == "Completed"):
        job.reportId = int(jobReportIdString)
    return job
