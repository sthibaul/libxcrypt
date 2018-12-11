#!/bin/bash
set -e

if [[ "$TRAVIS_OS_NAME" = "windows" ]]; then
  choco install -y cygwin --params "/InstallDir:C:\cygwin /NoStartMenu"
  choco install -y cyg-get
  cyg-get install -y libtool
else
  pip install --user codecov
fi
