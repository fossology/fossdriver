# Copyright Contributors to the fossdriver project.
# SPDX-License-Identifier: BSD-3-Clause OR MIT

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="fossdriver",
    version="0.0.3",
    author="Steve Winslow",
    author_email="swinslow@gmail.com",
    description="Python interface to control a FOSSology server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fossology/fossdriver",
    packages=setuptools.find_packages(),
    classifiers=(
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        # non-standard classifiers to designate specific license choices
        "License :: OSI Approved :: BSD-3-Clause License",
        "SPDX-License-Identifier: BSD-3-Clause OR MIT",
    ),
    install_requires=[
        "requests == 2.20.0",
        "requests-toolbelt == 0.8.0",
        "bs4 == 0.0.1",
        "lxml == 4.6.2",
        "version-parser == 1.0.0",
    ]
)
