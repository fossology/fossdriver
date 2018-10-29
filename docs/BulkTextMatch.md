SPDX-License-Identifier: BSD-3-Clause OR MIT

# Bulk Text Matches

The `BulkTextMatch` Task in fossdriver can run bulk text matches for arbitrary
text (using the Monk scanning agent).

`BulkTextMatch` is more configurable than some of the other Task types in
fossdriver. This document provides details on how to configure it.

## Creating a BulkTextMatch Task

First, create a BulkTextMatch task object by providing the following arguments:

- the server object (with an earlier call to `server.Login()`; see README.md for details)
- the name of the upload to scan
- the name of the folder containing that upload.
- the text contents to use for the search

Example:

```
refText = "SPDX-License-Identifier: Apache-2.0"

t = BulkTextMatch(server, "myUpload", "myUploadFolder", refText)
```

## Setting actions

Next, set actions for the Monk agent on the server to take when it finds a match
to the searched text.

An action is one of the following:

- `add`: add a license finding for the matched file
- `remove`: remove a license finding for the matched file

Actions are set for the task by calling `.add(licenseName)` or
`.remove(licenseName)`, as applicable. Internally, calling these creates a tuple
of the license name and the action type, and appends it to the BulkTextMatch's
`actionTuples` list.

A BulkTextMatch can perform multiple actions upon matching the searched text.

Note that for each action, a license with the given name must already exist on
the FOSSology server.

Example:

```
t.add("Apache-2.0")
t.remove("Apache-possibility")
```

## Run the BulkTextMatch Task

Finally, like other Tasks, the BulkTextMatch should be run by calling `.run()`.
This will start the Monk scanner agent for the upload, and will wait until it
completes before returning.

Example:

```
t.run()
```
