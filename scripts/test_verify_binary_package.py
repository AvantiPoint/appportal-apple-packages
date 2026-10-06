import importlib.util
import copy
import io
from contextlib import redirect_stderr
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('proof', Path(__file__).with_name('verify_binary_package.py'))
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)
MANIFEST = (Path(__file__).resolve().parent.parent / 'Package.swift').read_text()
PRIVACY = dict(NSPrivacyTracking=False, NSPrivacyTrackingDomains=[], NSPrivacyCollectedDataTypes=[], NSPrivacyAccessedAPITypes=[])

class PublicConsumerTests(unittest.TestCase):
    def test_current_manifest_has_only_four_pinned_binary_products(self):
        version, targets = proof.parse_manifest(MANIFEST)
        self.assertEqual(set(targets), set(proof.MODULES))
        self.assertRegex(version, r'^[0-9]+\.[0-9]+\.[0-9]+(?:-|$)')

    def test_manifest_rejects_source_dependencies_and_targets(self):
        for added in ('.package(url: "https://example.com/source", from: "1.0.0")', '.target(name: "Source")',
                      '.executableTarget(name: "Source")', '.testTarget(name: "Source")',
                      '.systemLibrary(name: "Source")', '.macro(name: "Source")'):
            with self.subTest(added=added), self.assertRaises(ValueError):
                proof.parse_manifest(MANIFEST + added)

    def test_manifest_rejects_unpinned_urls_and_checksums(self):
        version, _ = proof.parse_manifest(MANIFEST)
        for invalid in (MANIFEST.replace('/releases/download/', '/archive/'),
                        MANIFEST.replace('https://github.com/', 'https://secret@github.com/'),
                        MANIFEST.replace('checksum: "', 'checksum: "x', 1),
                        MANIFEST.replace('/v' + version + '/', '/v0.0.0/', 1)):
            with self.subTest(invalid=invalid[:30]), self.assertRaises(ValueError):
                proof.parse_manifest(invalid)

    def test_optional_products_require_shared_runtime(self):
        with self.assertRaises(ValueError):
            proof.parse_manifest(MANIFEST.replace('["AppPortalTelemetry", "AppPortalMessaging"]', '["AppPortalMessaging"]'))

    def test_manifest_rejects_changed_missing_or_extra_platforms(self):
        for platform in proof.MANIFEST_PLATFORMS:
            with self.subTest(platform=platform), self.assertRaises(ValueError):
                proof.parse_manifest(MANIFEST.replace(platform, platform.replace('.v', '.v99')))
        for invalid in (MANIFEST.replace('.watchOS(.v6), ', ''),
                        MANIFEST.replace('.watchOS(.v6)', '.watchOS(.v6), .visionOS(.v1)'),
                        MANIFEST.replace('.watchOS(.v6)', '.watchOS(.v6), .watchOS(.v6)')):
            with self.subTest(invalid=invalid[:30]), self.assertRaises(ValueError):
                proof.parse_manifest(invalid)

    def test_manifest_accepts_same_platforms_in_different_order(self):
        changed = MANIFEST.replace('.iOS(.v13), .macOS(.v11)', '.macOS(.v11), .iOS(.v13)')
        self.assertEqual(proof.parse_manifest(changed), proof.parse_manifest(MANIFEST))

    def fixture(self, root, change=None):
        module = proof.MODULES[0]
        prefix = module + '.xcframework/'
        files = {}
        libraries = []
        for index, (platform, variant) in enumerate(proof.SDK_TARGETS):
            identifier = 'slice-' + str(index)
            item = dict(LibraryIdentifier=identifier, LibraryPath=module + '.framework',
                        SupportedPlatform=platform, SupportedArchitectures=['arm64'])
            if variant:
                item['SupportedPlatformVariant'] = variant
            libraries.append(item)
            framework = prefix + identifier + '/' + module + '.framework/'
            files[framework + module] = b'test-only-binary'
            files[framework + 'Modules/' + module + '.swiftmodule/arm64-apple-test.swiftinterface'] = b'// -enable-library-evolution'
            files[framework + 'PrivacyInfo.xcprivacy'] = plistlib.dumps(PRIVACY)
        files[prefix + 'Info.plist'] = plistlib.dumps({'AvailableLibraries': libraries})
        if change:
            change(files)
        archive = root / 'fixture.zip'
        with zipfile.ZipFile(archive, 'w') as target:
            for name, data in files.items():
                target.writestr(name, data)
        return archive

    def check_fixture(self, change=None):
        with tempfile.TemporaryDirectory() as temporary:
            return proof.validate_archive(self.fixture(Path(temporary), change), proof.MODULES[0])

    def test_archive_requires_all_platforms_and_public_metadata(self):
        self.assertEqual(len(self.check_fixture()), 8)

    def test_archive_rejects_implementation_and_private_metadata(self):
        for suffix in ('.swift', '.SWIFT', '.m', '.cpp', '.private.swiftinterface', '.abi.json', '.swiftmodule', '.swiftsourceinfo', '.SWIFTSOURCEINFO'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                self.check_fixture(lambda files: files.update({'AppPortalTelemetry.xcframework/secret' + suffix: b'private'}))

    def test_archive_rejects_source_directory(self):
        with self.assertRaises(ValueError):
            self.check_fixture(lambda files: files.update({'AppPortalTelemetry.xcframework/Sources/implementation.txt': b'private'}))

    def test_archive_rejects_traversal(self):
        with self.assertRaises(ValueError):
            self.check_fixture(lambda files: files.update({'AppPortalTelemetry.xcframework/../escape': b'bad'}))

    def test_archive_rejects_missing_architecture_interface(self):
        with self.assertRaises(ValueError):
            self.check_fixture(lambda files: files.pop(next(n for n in files if n.endswith('.swiftinterface'))))

    def test_archive_rejects_missing_privacy_manifest(self):
        with self.assertRaises(ValueError):
            self.check_fixture(lambda files: files.pop(next(n for n in files if n.endswith('.xcprivacy'))))

    def test_archive_rejects_library_without_evolution(self):
        with self.assertRaises(ValueError):
            self.check_fixture(lambda files: files.update({next(n for n in files if n.endswith('.swiftinterface')): b'no evolution'}))

    def test_archive_rejects_non_dictionary_privacy_plists(self):
        for value in ([], 'invalid', 1, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check_fixture(lambda files: files.update({next(n for n in files if n.endswith('.xcprivacy')): plistlib.dumps(value)}))

    def test_privacy_requires_known_keys_and_correct_nested_types(self):
        valid = copy.deepcopy(PRIVACY)
        valid['NSPrivacyCollectedDataTypes'] = [{
            'NSPrivacyCollectedDataType': 'NSPrivacyCollectedDataTypeDeviceID',
            'NSPrivacyCollectedDataTypeLinked': True, 'NSPrivacyCollectedDataTypeTracking': False,
            'NSPrivacyCollectedDataTypePurposes': ['NSPrivacyCollectedDataTypePurposeAppFunctionality']}]
        valid['NSPrivacyAccessedAPITypes'] = [{
            'NSPrivacyAccessedAPIType': 'NSPrivacyAccessedAPICategoryUserDefaults',
            'NSPrivacyAccessedAPITypeReasons': ['CA92.1']}]
        proof.validate_privacy_manifest(valid)
        for key, value in (('NSPrivacyTracking', 1), ('NSPrivacyTrackingDomains', 'example.com'),
                           ('NSPrivacyTrackingDomains', [1]), ('NSPrivacyCollectedDataTypes', {}),
                           ('NSPrivacyCollectedDataTypes', ['invalid']),
                           ('NSPrivacyAccessedAPITypes', [{'NSPrivacyAccessedAPIType': 'category'}])):
            invalid = copy.deepcopy(valid)
            invalid[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                proof.validate_privacy_manifest(invalid)
        for field, value in (('NSPrivacyCollectedDataTypeLinked', 1),
                             ('NSPrivacyCollectedDataTypePurposes', ['']),
                             ('NSPrivacyCollectedDataTypePurposes', [])):
            invalid = copy.deepcopy(valid)
            invalid['NSPrivacyCollectedDataTypes'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                proof.validate_privacy_manifest(invalid)
        for invalid in ({}, dict(valid, MisspelledPrivacyKey=[])):
            with self.assertRaises(ValueError):
                proof.validate_privacy_manifest(invalid)

    def test_optional_slices_require_same_architectures_as_telemetry(self):
        slices = {module: [{'SupportedPlatform': 'ios', 'SupportedArchitectures': ['arm64']}]
                  for module in proof.MODULES}
        proof.validate_architecture_sets(slices)
        for architectures in ([], ['arm64', 'x86_64'], ['x86_64']):
            changed = copy.deepcopy(slices)
            changed['AppPortalMessaging'][0]['SupportedArchitectures'] = architectures
            with self.subTest(architectures=architectures), self.assertRaises(ValueError):
                proof.validate_architecture_sets(changed)

    def test_optional_products_cannot_link_sibling_frameworks(self):
        telemetry = '@rpath/AppPortalTelemetry.framework/AppPortalTelemetry (compatibility version 1.0.0)'
        for module in proof.MODULES:
            valid = '@rpath/' + module + '.framework/' + module + '\n' + telemetry
            proof.validate_linked_dependencies(module, valid)
            for sibling in set(proof.MODULES) - {module, proof.MODULES[0]}:
                with self.subTest(module=module, sibling=sibling), self.assertRaises(ValueError):
                    proof.validate_linked_dependencies(module, valid + '\n@rpath/' + sibling + '.framework/' + sibling)
        with self.assertRaises(ValueError):
            proof.validate_linked_dependencies('AppPortalMessaging', '@rpath/AppPortalMessaging.framework/AppPortalMessaging')
        with self.assertRaises(ValueError):
            proof.validate_linked_dependencies('AppPortalTelemetry', telemetry + '\n@rpath/AppPortalTelemetryXC.framework/AppPortalTelemetryXC')

    def test_clean_environment_does_not_inherit_credentials(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            'GITHUB_TOKEN': 'not-a-real-token', 'GH_TOKEN': 'not-a-real-token',
            'SWIFTPM_SOURCE_CONTROL_TOKEN': 'not-a-real-token', 'SWIFTPM_NETRC_DATA': 'private',
            'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'credential.helper', 'GIT_CONFIG_VALUE_0': 'helper',
        }):
            env = proof.clean_environment(Path(temporary))
            for key in ('GITHUB_TOKEN', 'GH_TOKEN', 'SWIFTPM_SOURCE_CONTROL_TOKEN', 'SWIFTPM_NETRC_DATA', 'GIT_CONFIG_COUNT'):
                self.assertNotIn(key, env)
            self.assertEqual(env['GIT_CONFIG_GLOBAL'], '/dev/null')
            self.assertEqual(env['GIT_CONFIG_NOSYSTEM'], '1')
            self.assertEqual(env['GIT_TERMINAL_PROMPT'], '0')
            self.assertTrue(env['HOME'].startswith(temporary))

    def test_swift_isolates_every_cache_and_disables_credential_readers(self):
        root = Path('/job/proof/product')
        command = proof.swift_command(root, root / 'consumer')
        for name in ('--scratch-path', '--cache-path', '--config-path', '--security-path'):
            self.assertTrue(command[command.index(name) + 1].startswith(str(root) + '/'))
        for name in ('--disable-dependency-cache', '--disable-netrc', '--disable-keychain'):
            self.assertIn(name, command)

    def test_workspace_cleanup_removes_only_its_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            outside = parent / 'outside'
            outside.mkdir()
            (outside / 'keep').write_text('keep')
            with proof.public_workspace(parent) as root:
                (root / 'owned').write_text('owned')
                (root / 'outside-link').symlink_to(outside, target_is_directory=True)
            self.assertFalse(root.exists())
            self.assertEqual((outside / 'keep').read_text(), 'keep')

    def test_workspace_cleanup_never_enters_mounted_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / 'owned-workspace'
            mount = root / 'sdk-mount'
            mount.mkdir(parents=True)
            (mount / 'RestoreVersion.plist').write_text('managed by Xcode')
            (root / 'ordinary-file').write_text('remove')
            with patch.object(proof.os.path, 'ismount', side_effect=lambda path: Path(path) == mount), redirect_stderr(io.StringIO()) as warnings:
                proof.cleanup_workspace(root)
            self.assertEqual((mount / 'RestoreVersion.plist').read_text(), 'managed by Xcode')
            self.assertFalse((root / 'ordinary-file').exists())
            self.assertIn('retained mounted', warnings.getvalue())

    def test_cleanup_failure_does_not_hide_a_proof_failure(self):
        with tempfile.TemporaryDirectory() as temporary, redirect_stderr(io.StringIO()):
            with patch.object(proof.os, 'scandir', side_effect=OSError('read-only')):
                with self.assertRaisesRegex(ValueError, 'proof failed'):
                    with proof.public_workspace(Path(temporary)):
                        raise ValueError('proof failed')

    def test_workflow_checks_out_only_public_repository_without_credentials(self):
        workflow = (Path(__file__).resolve().parent.parent / '.github/workflows/consumer.yml').read_text()
        self.assertEqual(workflow.count('uses: actions/checkout@v7'), 2)
        self.assertEqual(workflow.count('persist-credentials: false'), 2)
        self.assertNotIn('repository:', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertIn('github.event.pull_request.head.repo.full_name == github.repository', workflow)
        self.assertIn('runs-on: macos-26', workflow)
        self.assertIn('DEVELOPER_DIR: /Applications/Xcode_26.6.app/Contents/Developer', workflow)
        self.assertNotIn('MIC_GITHUB', workflow)
        self.assertNotIn('macos-26-large', workflow)

if __name__ == '__main__':
    unittest.main()
