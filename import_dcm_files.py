#!/usr/bin/python

import base64
import os.path
import sys
import time

import httplib2

if len(sys.argv) != 4 and len(sys.argv) != 6:
    print("""
Sample script to recursively import in Orthanc all the DICOM files
that are stored in some path. Please make sure that Orthanc is running
before starting this script. The files are uploaded through the REST
API.

Usage: %s [hostname] [HTTP port] [path]
Usage: %s [hostname] [HTTP port] [path] [username] [password]
For instance: %s localhost 8042 .
""" % (sys.argv[0], sys.argv[0], sys.argv[0]))
    exit(-1)

URL = 'http://%s:%d/instances' % (sys.argv[1], int(sys.argv[2]))

success = 0

# This function will upload a single file to Orthanc through the REST API
def UploadFile(path):
    global success

    f = open(path, "rb")
    content = f.read()
    f.close()

    try:
        sys.stdout.write("Importing %s" % path)

        h = httplib2.Http()

        headers = {'content-type': 'application/dicom'}

        if len(sys.argv) == 6:
            username = sys.argv[4]
            password = sys.argv[5]

            # h.add_credentials(username, password)

            # This is a custom reimplementation of the
            # "Http.add_credentials()" method for Basic HTTP Access
            # Authentication (for some weird reason, this method does
            # not always work)
            # http://en.wikipedia.org/wiki/Basic_access_authentication
            headers['authorization'] = 'Basic ' + base64.b64encode(username + ':' + password)

        resp, content = h.request(URL, 'POST',
                                  body=content,
                                  headers=headers)

        if resp.status == 200:
            sys.stdout.write(" => success\n")
            success += 1
        else:
            sys.stdout.write(" => failure (Is it a DICOM file?)\n")

    except:
        sys.stdout.write(" => unable to connect (Is Orthanc running? Is there a password?)\n")

root_folder = sys.argv[3]
#SLEEP_TIME_S = 60 #3 * 60

if os.path.isfile(root_folder):
    # Upload a single file
    UploadFile(sys.argv[3])
    pass
else:
    # Recursively upload a directory
    # by a single folder (study) at a time
    study_level_dirs = [folder for folder in os.listdir(root_folder) if
                        os.path.isdir(os.path.join(root_folder, folder))]

    for study_dir in study_level_dirs:
        # we collect each study's files recursively and send them in one batch
        for root, dirs, files in os.walk(os.path.join(root_folder, study_dir)):
            for f in files:
                UploadFile(os.path.join(root, f))

        # then we sleep
        #time.sleep(SLEEP_TIME_S)

print("\nSummary: %d DICOM file(s) have been imported" % success)
