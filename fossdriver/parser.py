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

import bs4

class ParsedUpload(object):
    def __init__(self):
        self.name = ""
        self._id = -1
        self.folderId = -1
        self.spdxTvUrl = ""
        self.spdxXmlUrl = ""


def extractUploadDataForFolderLineItem(lineItem):
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

def extractAllUploadDataForFolder(uploadData):
    """
    Parses all line items from a call to browse-processPost.
    Returns a list of all found ParsedUpload objects.
    """
    parsedUploads = []
    for lineItem in uploadData:
        u = extractUploadDataForFolderLineItem(lineItem)
        if u is not None:
            parsedUploads.append(u)
    return parsedUploads
