# fossdriver

fossdriver is intended to enable control of a [FOSSology server](https://www.fossology.org) from Python programs.

This package is significantly based on, and inspired by, the excellent [fossup](https://gitlab.com/toganlabs/fossup) FOSSology Uploader package from Togán Labs.

## Requirements

fossdriver requires a [FOSSology server](https://www.fossology.org) to talk to. (fossdriver doesn't contain a FOSSology server; you'll have to go set one up yourself.)

The current version of fossdriver is designed for use with a FOSSology server version 3.3.0, which is the now-current release of FOSSology. It has not been tested on other versions.

fossdriver requires Python 3.6+ or later.

fossdriver makes use of, and installs if not present, the following dependencies (and their subdependencies, of course):

- **requests** and **requests_toolbox** - for communicating with the server
- **bs4 (BeautifulSoup)** and **lxml** - for parsing server responses

## Installation

fossdriver is not yet released on PyPI, so a standard `pip install` doesn't work yet.

To install in development mode, first download the source and unpack it at `/WHEREVER/fossdriver/`, then run in a virtualenv:

```
pip install -e /WHEREVER/fossdriver
```

Also create a config file in your home directory, at e.g. `.fossdriverrc`, with the following details for your FOSSology server:

```
{
    "serverUrl": "SERVER URL",
    "username": "USERNAME",
    "password": "PASSWORD"
}
```

Note that the URL **should NOT** include the `/repo/` portion of the URL that FOSSology typically appends.

## Usage

1) In your Python project, import the fossdriver objects:

```
from fossdriver.config import FossConfig
from fossdriver.server import FossServer
from fossdriver.tasks import (CreateFolder, Upload, Scanners, Copyright,
    Reuse, BulkTextMatch, SPDXTV)
```

2) Create a config object:

```
config = FossConfig()
configPath = os.path.join(str(Path.home()), ".fossdriver", "fossdriverrc.json")
config.configure(configPath)
```

3) Create and connect to the server:

```
server = FossServer(config)
server.Login()
```

4) Run some tasks on the server:

```
# create a new folder on the server
CreateFolder(server, "Test Folder", "Parent Folder").run()

# upload archive.zip to the new folder
Upload(server, "archive.zip", "Test Folder").run()

# start the Monk and Nomos scanners
Scanners(server, "archive.zip", "Test Folder").run()

# also run the Copyright statement scanner
Copyright(server, "archive.zip", "Test Folder").run()

# also reuse prior results from an earlier scan
Reuse(server, "archive.zip", "Test Folder", "earlier-scan-1", "Earlier Scan Folder").run()

# see docs/BulkTextMatch.md for details on how to use BulkTextMatch

# and export an SPDX tag-value file
SPDXTV(server, "archive.zip", "Test Folder", "/tmp/archive.spdx").run()
```

## Contributing

Contributions to fossdriver are welcome. Please see the CONTRIBUTING.md file for details on contributing.

## License

fossdriver is provided under a choice of either the [MIT](https://spdx.org/licenses/MIT.html) license or the [BSD-3-Clause](https://spdx.org/licenses/BSD-3-Clause.html) license, at the licensee's option. Copies of these licenses are included in the LICENSE file.

```
SPDX-License-Identifier: BSD-3-Clause OR MIT
```
