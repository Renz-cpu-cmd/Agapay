"""Synthetic archives and public configuration; never builds/signs with real keys."""
import unittest,zipfile,tempfile
from pathlib import Path
import release

def config():return dict(environment='production',version='1.0.0',build_number=1,revision='a'*40,release_id='synthetic-v1',api_origin='https://api.agapay.org',map_mode='list_only',map_origin='',map_restriction_evidence_sha256='')
class ReleasePolicyTest(unittest.TestCase):
    def test_bad_environment_provenance_and_network_configuration_fail(self):
        release.configuration(config())
        for key,value in [('environment','development'),('revision','fake'),('build_number',0),('api_origin','http://api.agapay.org'),('api_origin','https://127.0.0.1'),('api_origin','https://[::ffff:127.0.0.1]'),('map_mode','demo'),('map_mode','hosted')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):release.configuration(dict(config(),**{key:value}))
    def test_release_archive_cannot_bundle_development_keys_or_private_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive=Path(temporary)/'synthetic.apk'
            with zipfile.ZipFile(archive,'w') as output:output.writestr('assets/flutter_assets/assets/config/google_maps_demo_key.txt','SYNTHETIC-NOT-A-KEY')
            with self.assertRaises(ValueError):release.inspect_archive(archive)
            with zipfile.ZipFile(archive,'w') as output:output.writestr('assets/flutter_assets/assets/images/logo.png',b'fixture')
            release.inspect_archive(archive)
if __name__=='__main__':unittest.main()
