#!/usr/bin/env python

import hashlib
import json
import os
import PIL.Image
import requests
import sys
import tvfamilyapi
import unittest

SERVER_ADDRESS = 'http://localhost:8888'
TESTDIR = os.path.dirname(sys.argv[0])
TESTPIC = os.path.join(TESTDIR, 'profile.png')
PROFILES_PATH = os.path.join(os.path.expanduser('~'), '.tvfamily', 'profiles')
PROFILES_FILE = os.path.join(PROFILES_PATH, 'profiles.json')

class ProfilesTestCase(unittest.TestCase):
    '''Test the Core object.'''

    def test_profiles(self):
        # Get the current list of profiles
        profiles = server.get_profiles()
        self.assertEqual(profiles, [])

        # Create a profile
        server.create_profile('fistro')
        profiles_new = server.get_profiles()
        for x in profiles + ['fistro']:
            self.assertIn(x, profiles_new)
        self.assertEqual(len(profiles) + 1, len(profiles_new))

        # Create a profile with an existing name
        self.assertRaises(
            tvfamilyapi.ServiceError, server.create_profile, 'fistro')

        # Try a raw request without the name argument
        r = requests.post('{}/api/createprofile'.format(SERVER_ADDRESS))
        resp = r.json()
        self.assertEqual(resp['code'], 1)
        self.assertEqual(resp['error'], "missing 'name' argument")

        # Get the picture of the newly created profile
        pic = server.get_profile_picture('fistro')
        self.assertEqual(pic, b'')

        # Test obtaining the picture from a non existing profile
        self.assertRaises(
            tvfamilyapi.ServiceError, server.get_profile_picture, 'john doe')

        # Try a raw request without the name argument
        r = requests.get('{}/api/getprofilepicture'.format(SERVER_ADDRESS))
        resp = r.json()
        self.assertEqual(resp['code'], 1)
        self.assertEqual(resp['error'], "missing 'name' argument")

        # Set the default picture
        server.set_profile_picture('fistro')
        new_pic = server.get_profile_picture('fistro')
        self.assertEqual(pic, new_pic)

        # Set a new profile picture, must be resized
        server.set_profile_picture('fistro', TESTPIC)

        # Get the new picture
        new_pic_hash = self._checksum(server.get_profile_picture('fistro'))

        # Resize the sent picture and calculate the hash
        pic = PIL.Image.open(TESTPIC)
        pic = pic.resize((256, 256))
        pic.save('temppic.png')
        calculated_pic_hash = self._checksum_file('temppic.png')
        os.unlink('temppic.png')
        self.assertEqual(new_pic_hash, calculated_pic_hash)

        # Set an image for non existing profile
        self.assertRaises(tvfamilyapi.ServiceError, server.set_profile_picture,
            'john doe', TESTPIC)

        # Try a raw request without the name parameter
        r = requests.post('{}/api/setprofilepicture'.format(SERVER_ADDRESS))
        resp = r.json()
        self.assertEqual(resp['code'], 1)
        self.assertEqual(resp['error'], "missing 'name' argument")

        # Try a raw request without the file
        r = requests.post('{}/api/setprofilepicture'.format(SERVER_ADDRESS),
            params={'name': 'fistro'}, files={})
        resp = r.json()
        self.assertEqual(resp['code'], 1)
        self.assertEqual(resp['error'], "malformed request")

        # Set the default picture
        server.set_profile_picture('fistro')
        new_pic = server.get_profile_picture('fistro')
        self.assertEqual(b'', new_pic)

        # Send a file that is not a valid picture
        self.assertRaises(tvfamilyapi.ServiceError, server.set_profile_picture, 
            'fistro', sys.argv[0])

        # Modify the permissions of the profiles directory and try to change
        # the profile picture
        os.chmod(PROFILES_PATH, 0o555)
        self.assertRaises(tvfamilyapi.ServiceError, server.set_profile_picture,
            'fistro', TESTPIC)
        os.chmod(PROFILES_PATH, 0o755)

        # Create a profile that won't be saved
        os.chmod(PROFILES_FILE, 0o444)
        server.create_profile('pecador')
        with open(PROFILES_FILE, 'r') as f:
            profiles_in_file = json.loads(f.read())
        self.assertNotIn('pecador', profiles_in_file)
        # The profile has been created nevertheless
        profiles = server.get_profiles()
        self.assertIn('pecador', profiles)
        os.chmod(PROFILES_FILE, 0o644)
        server.delete_profile('pecador')

        # Delete the profile
        server.delete_profile('fistro')
        profiles_third = server.get_profiles()
        self.assertEqual(profiles_third, [])

        # Create a profile with an image
        server.create_profile('fistro', TESTPIC)
        new_pic_hash = self._checksum(server.get_profile_picture('fistro'))
        self.assertEqual(new_pic_hash, calculated_pic_hash)
        server.delete_profile('fistro')

        # Create a profile with a wrong image
        self.assertRaises(tvfamilyapi.ServiceError, server.create_profile,
            'fistro', sys.argv[0])

        # Try a raw request without the file
        r = requests.post('{}/api/createprofile'.format(SERVER_ADDRESS),
            params={'name': 'fistro'}, files={})
        resp = r.json()
        self.assertEqual(resp['code'], 1)
        self.assertEqual(resp['error'], "malformed request")

        # Try a raw request without the name argument
        r = requests.get('{}/api/deleteprofile'.format(SERVER_ADDRESS))
        resp = r.json()
        self.assertEqual(resp['code'], 1)
        self.assertEqual(resp['error'], "missing 'name' argument")

        # Delete a non existing profile
        self.assertRaises(
            tvfamilyapi.ServiceError, server.delete_profile, 'fistro')

    def _checksum_file(self, filename):
        with open(filename, 'rb') as f:
            return self._checksum(f.read())

    def _checksum(self, img):
        m = hashlib.md5()
        m.update(img)
        return m.hexdigest()

if __name__ == '__main__':
    global server
    server = tvfamilyapi.Server(SERVER_ADDRESS)
    unittest.main()

