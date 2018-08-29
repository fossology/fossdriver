# Copyright Contributors to the fossdriver project.
# SPDX-License-Identifier: BSD-3-Clause OR MIT

import json
import logging

class FossConfig(object):

    def __init__(self):
        self.serverUrl = ""
        self.username = ""
        self.password = ""

    def configure(self, configFilename):
        try:
            with open(configFilename, "r") as f:
                js = json.load(f)

                # pull out the expected parameters
                self.serverUrl = js.get("serverUrl", "")
                self.username = js.get("username", "")
                self.password = js.get("password", "")

                # check whether we got everything we expected
                isValid = True
                if self.serverUrl == "":
                    logging.error(f"serverUrl not found in config file")
                    isValid = False
                if self.username == "":
                    logging.error(f"username not found in config file")
                    isValid = False
                if self.password == "":
                    logging.error(f"password not found in config file")
                    isValid = False

                return isValid

        except json.decoder.JSONDecodeError as e:
            logging.error(f"Error loading or parsing {configFilename}: {str(e)}")
            return False
