#!/bin/bash

TESTDIR=$(realpath $(dirname "$0"))
ROOTDIR=$(realpath "$TESTDIR/..")
BINDIR="$ROOTDIR/bin"
DATADIR="$ROOTDIR/data"
CONFFILE="$DATADIR/tvfamily.conf"
APIDIR="/home/toni/projectes/tvfamily-api/src"

# Enter to the test directory
pushd "$TESTDIR"

# Cleanup previous coverage information
echo 'cleaning up coverage information'
rm .coverage
rm -r htmlcov

# Remove the profiles information
rm -rf ~/.tvfamily/profiles

# Launch the server and recover its pid
echo 'executing the server in background'
PYTHONPATH="$PYTHONPATH:$ROOTDIR" coverage run $BINDIR/tvfamily -c "$CONFFILE" &
serverpid=$!
sleep 1

# Launch the client
echo 'executing the client'
PYTHONPATH="$PYTHONPATY:$APIDIR" $TESTDIR/clientcov.py

# Stop the server
echo 'client finished, stopping the server'
kill -SIGINT $serverpid

# Generate the coverage report
echo 'generating coverage report'
coverage html

# Go back to the original directory
popd

# Exit
echo 'exiting'
exit 0

