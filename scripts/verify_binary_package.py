#!/usr/bin/env python3
"""Verify the public release, then compile consumers without private source or credentials."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPOSITORY = 'https://github.com/AvantiPoint/appportal-apple-packages'
MODULES = ('AppPortalTelemetry', 'AppPortalMessaging', 'AppPortalLocation', 'AppPortalSmartLinks')
MANIFEST_PLATFORMS = {'.iOS(.v13)', '.macOS(.v11)', '.tvOS(.v13)', '.watchOS(.v6)', '.macCatalyst(.v13)'}
SDK_TARGETS = {
    ('ios', ''): ('iphoneos', 'ios13.0'),
    ('ios', 'simulator'): ('iphonesimulator', 'ios13.0-simulator'),
    ('ios', 'maccatalyst'): ('macosx', 'ios13.1-macabi'),
    ('macos', ''): ('macosx', 'macos11.0'),
    ('tvos', ''): ('appletvos', 'tvos13.0'),
    ('tvos', 'simulator'): ('appletvsimulator', 'tvos13.0-simulator'),
    ('watchos', ''): ('watchos', 'watchos6.0'),
    ('watchos', 'simulator'): ('watchsimulator', 'watchos6.0-simulator'),
}
SMOKE = {
    'AppPortalTelemetry': 'let client: AppPortalClient = AppPortal.current\nprint(type(of: client))',
    'AppPortalMessaging': 'print(AppPortalMessages.handlePushPayload(["title": "Hello"]) as Any)',
    'AppPortalLocation': 'print(String(describing: LiveAppPortalLocation.self))',
    'AppPortalSmartLinks': 'print(AppPortalSmartLinkHandlingResult.rejected(.invalidAssociatedURL))',
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def parse_manifest(text):
    require(not re.search(r'\.(?:target|executableTarget|testTarget|systemLibrary|macro|plugin|package)\s*\(', text),
            'Public package must contain only binary targets and no source dependencies')
    platforms = re.findall(r'platforms\s*:\s*\[([^\]]*)\]', text)
    require(len(platforms) == 1, 'Expected one advertised platform declaration')
    declared = re.sub(r'\s+', '', platforms[0]).rstrip(',').split(',')
    require(len(declared) == len(MANIFEST_PLATFORMS) and set(declared) == MANIFEST_PLATFORMS,
            'Manifest platform minimums differ from the advertised support matrix')
    matches = re.findall(r'\.binaryTarget\(name: "([^"]+)", url: "([^"]+)", checksum: "([0-9a-f]{64})"\)', text)
    require(len(matches) == 4 and text.count('.binaryTarget(') == 4, 'Expected four pinned binary targets')
    require({m[0] for m in matches} == set(MODULES), 'Unexpected binary modules')
    versions = set()
    targets = {}
    for module, url, checksum in matches:
        match = re.fullmatch(re.escape(REPOSITORY) + r'/releases/download/v([0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?)/' + re.escape(module) + r'-\1\.xcframework\.zip', url)
        require(match is not None, 'Expected immutable, credential-free public release URL')
        versions.add(match.group(1))
        targets[module] = (url, checksum)
    require(len(versions) == 1, 'All modules must use the same release')
    for module in MODULES:
        dependencies = [module] if module == MODULES[0] else [MODULES[0], module]
        require(f'.library(name: "{module}", targets: {json.dumps(dependencies)})' in text,
                f'{module}: product must include its shared runtime dependency')
    return versions.pop(), targets

def validate_archive(path, module):
    root = module + '.xcframework/'
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive entries')
        for entry in archive.infolist():
            name = entry.filename
            parts = PurePosixPath(name).parts
            require(name.startswith(root) and '..' not in parts and '\\' not in name,
                    'Unsafe archive path or unexpected root')
            lower = name.lower()
            require(not lower.endswith(('.swift', '.m', '.mm', '.c', '.cc', '.cpp', '.private.swiftinterface', '.abi.json', '.swiftsourceinfo'))
                    and not (lower.endswith('.swiftmodule') and not entry.is_dir())
                    and 'sources' not in [part.lower() for part in parts],
                    'Implementation source or private compiler metadata in binary archive')
            if stat.S_ISLNK(entry.external_attr >> 16):
                target = archive.read(entry).decode('utf-8')
                require(target and not target.startswith('/') and '..' not in PurePosixPath(target).parts
                        and '\\' not in target, 'Unsafe framework symlink')
        info = plistlib.loads(archive.read(root + 'Info.plist'))
        libraries = info['AvailableLibraries']
        require(len(libraries) == len(SDK_TARGETS) and
                {(i['SupportedPlatform'], i.get('SupportedPlatformVariant', '')) for i in libraries} == set(SDK_TARGETS),
                'Expected all eight platform/variant slices')
        for item in libraries:
            identifier = item['LibraryIdentifier']
            require(re.fullmatch(r'[A-Za-z0-9_\-]+', identifier) is not None, 'Invalid slice identifier')
            require(item['LibraryPath'] == module + '.framework', 'Framework/module name mismatch')
            framework = root + identifier + '/' + item['LibraryPath'] + '/'
            require(framework + module in names, 'Missing framework binary')
            interfaces = [n for n in names if n.startswith(framework) and n.endswith('.swiftinterface')]
            for arch in item['SupportedArchitectures']:
                require(any(PurePosixPath(n).name.startswith(arch + '-apple-') for n in interfaces),
                        'Missing architecture public interface')
            for name in interfaces:
                require('-enable-library-evolution' in archive.read(name).decode(), 'Library evolution is disabled')
            privacy = [n for n in names if n.startswith(framework) and n.endswith('/PrivacyInfo.xcprivacy')]
            require(len(privacy) == 1, 'Missing or ambiguous framework privacy manifest')
            validate_privacy_manifest(plistlib.loads(archive.read(privacy[0])))
        return libraries

def validate_privacy_manifest(privacy):
    # Validate the packaging schema, not the accuracy or legal sufficiency of disclosures.
    keys = {'NSPrivacyTracking', 'NSPrivacyTrackingDomains', 'NSPrivacyCollectedDataTypes', 'NSPrivacyAccessedAPITypes'}
    require(isinstance(privacy, dict) and set(privacy) == keys, 'Expected privacy manifest dictionary and known keys')
    require(type(privacy['NSPrivacyTracking']) is bool, 'Privacy tracking must be a Boolean')
    def strings(value):
        return isinstance(value, list) and all(isinstance(item, str) and item for item in value)
    require(strings(privacy['NSPrivacyTrackingDomains']), 'Privacy tracking domains must be an array of strings')
    schemas = (
        ('NSPrivacyCollectedDataTypes', {
            'NSPrivacyCollectedDataType': str, 'NSPrivacyCollectedDataTypeLinked': bool,
            'NSPrivacyCollectedDataTypeTracking': bool, 'NSPrivacyCollectedDataTypePurposes': list}),
        ('NSPrivacyAccessedAPITypes', {'NSPrivacyAccessedAPIType': str, 'NSPrivacyAccessedAPITypeReasons': list}),
    )
    for key, schema in schemas:
        require(isinstance(privacy[key], list), key + ' must be an array of dictionaries')
        for entry in privacy[key]:
            require(isinstance(entry, dict) and set(entry) == set(schema), 'Invalid privacy declaration keys')
            for field, kind in schema.items():
                value = entry[field]
                require(type(value) is kind, field + ' has an invalid property-list type')
                if kind is list:
                    require(bool(value) and strings(value), field + ' must be a nonempty array of strings')
                elif kind is str:
                    require(bool(value), field + ' must be nonempty')

def validate_architecture_sets(slices):
    # A product cannot support an architecture absent from its shared Telemetry runtime.
    expected = {(i['SupportedPlatform'], i.get('SupportedPlatformVariant', '')): set(i['SupportedArchitectures'])
                for i in slices[MODULES[0]]}
    for module in MODULES:
        actual = {(i['SupportedPlatform'], i.get('SupportedPlatformVariant', '')): set(i['SupportedArchitectures'])
                  for i in slices[module]}
        require(actual == expected and all(actual.values()), module + ': architecture sets must match Telemetry')

def validate_linked_dependencies(module, links):
    # otool -L includes the framework's own install name as well as linked dependencies.
    declared = set(re.findall(r'(AppPortal[A-Za-z0-9_]+)\.framework/', links))
    allowed = {module, MODULES[0]}
    require(declared <= allowed, module + ': undeclared AppPortal framework dependency')
    if module != MODULES[0]:
        require('@rpath/AppPortalTelemetry.framework/' in links, 'Shared runtime dependency missing')

def clean_environment(root):
    home = root / 'home'
    home.mkdir()
    temp = root / 'tmp'
    temp.mkdir()
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(home), 'TMPDIR': str(temp) + '/',
           'CFFIXED_USER_HOME': str(home), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '/usr/bin/false', 'SSH_ASKPASS': '/usr/bin/false',
           'CLANG_MODULE_CACHE_PATH': str(root / 'clang-cache'),
           'SWIFTPM_MODULECACHE_OVERRIDE': str(root / 'swift-module-cache')}
    if os.environ.get('DEVELOPER_DIR'):
        env['DEVELOPER_DIR'] = os.environ['DEVELOPER_DIR']
    return env

def swift_command(root, consumer):
    return ['swift', 'run', '--package-path', str(consumer), '--configuration', 'release',
            '--scratch-path', str(root / 'build'), '--cache-path', str(root / 'cache'),
            '--config-path', str(root / 'config'), '--security-path', str(root / 'security'),
            '--disable-dependency-cache', '--disable-netrc', '--disable-keychain', 'Smoke']

def download(url, path):
    # urllib has no automatic netrc/keychain authentication. No credential headers are supplied.
    with urllib.request.urlopen(url, timeout=90) as response:
        path.write_bytes(response.read())

def cleanup_workspace(root):
    # Xcode can mount read-only SDK images below TMPDIR. Never traverse a mount,
    # another filesystem, or a directory symlink while cleaning our own workspace.
    device = root.lstat().st_dev
    def remove(directory):
        complete = True
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                try:
                    if entry.is_symlink():
                        path.unlink()
                    elif entry.stat(follow_symlinks=False).st_dev != device or os.path.ismount(path):
                        complete = False
                    elif entry.is_dir(follow_symlinks=False):
                        complete = remove(path) and complete
                    else:
                        path.unlink()
                except OSError:
                    complete = False
        if complete:
            directory.rmdir()
        return complete
    try:
        complete = remove(root)
    except OSError:
        complete = False
    if not complete:
        print('WARNING: retained mounted or unavailable temporary entries for runner teardown: ' + str(root), file=sys.stderr)

@contextmanager
def public_workspace(parent):
    root = Path(tempfile.mkdtemp(prefix='appportal-public-consumer-', dir=parent))
    try:
        yield root
    finally:
        cleanup_workspace(root)

def verify(manifest_path, temporary_parent):
    manifest = manifest_path.read_text()
    version, targets = parse_manifest(manifest)
    with public_workspace(temporary_parent) as root:
        env = clean_environment(root)
        def run(*args):
            print('+', ' '.join(map(str, args)), flush=True)
            return subprocess.check_output(args, env=env, cwd=root, text=True)
        print(run('xcodebuild', '-version'), run('swift', '--version'), flush=True)
        tagged_manifest = root / 'TaggedPackage.swift'
        download(f'https://raw.githubusercontent.com/AvantiPoint/appportal-apple-packages/v{version}/Package.swift', tagged_manifest)
        require(tagged_manifest.read_text() == manifest, 'Checkout manifest differs from the exact public tag')
        release_path = root / 'release.json'
        download(f'{REPOSITORY}/releases/download/v{version}/release.json', release_path)
        release = json.loads(release_path.read_text())
        require(release['version'] == version, 'Release provenance version mismatch')
        print('Release provenance:', json.dumps(release, sort_keys=True), flush=True)
        slices = {}
        frameworks = root / 'frameworks'
        frameworks.mkdir()
        for module, (url, checksum) in targets.items():
            archive = root / (module + '.zip')
            download(url, archive)
            require(hashlib.sha256(archive.read_bytes()).hexdigest() == checksum, 'Archive checksum mismatch')
            require(release['checksums'][url.rsplit('/', 1)[-1]] == checksum, 'Release checksum mismatch')
            slices[module] = validate_archive(archive, module)
            run('ditto', '-x', '-k', str(archive), str(frameworks))
        validate_architecture_sets(slices)
        for item in slices[MODULES[0]]:
            platform = (item['SupportedPlatform'], item.get('SupportedPlatformVariant', ''))
            sdk, suffix = SDK_TARGETS[platform]
            sdk_path = run('xcrun', '--sdk', sdk, '--show-sdk-path').strip()
            search = []
            if platform == ('ios', 'maccatalyst'):
                search += ['-F', sdk_path + '/System/iOSSupport/System/Library/Frameworks',
                           '-L', sdk_path + '/System/iOSSupport/usr/lib']
            for module in MODULES:
                match = next(i for i in slices[module] if (i['SupportedPlatform'], i.get('SupportedPlatformVariant', '')) == platform)
                framework_parent = frameworks / (module + '.xcframework') / match['LibraryIdentifier']
                binary = framework_parent / (module + '.framework') / module
                require(set(run('lipo', '-archs', str(binary)).split()) == set(match['SupportedArchitectures']), 'Binary architecture mismatch')
                links = run('otool', '-L', str(binary))
                validate_linked_dependencies(module, links)
                search += ['-F', str(framework_parent)]
            source = root / 'SliceConsumer.swift'
            source.write_text('\n'.join('import ' + m for m in MODULES) + '\npublic func smoke() {\n' + '\n'.join(SMOKE.values()) + '\n}\n')
            for architecture in item['SupportedArchitectures']:
                print('Link public binary slice:', platform, architecture, flush=True)
                run('xcrun', '--sdk', sdk, 'swiftc', '-emit-library', '-sdk', sdk_path,
                    '-target', f'{architecture}-apple-{suffix}', *search,
                    *[arg for module in MODULES for arg in ('-framework', module)],
                    str(source), '-o', str(root / 'SliceConsumer.dylib'))
        for module in MODULES:
            product_root = root / module
            consumer = product_root / 'consumer'
            source = consumer / 'Sources/Smoke'
            source.mkdir(parents=True)
            (consumer / 'Package.swift').write_text('''// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "Smoke", platforms: [.macOS(.v11)],
    dependencies: [.package(url: "%s", exact: "%s")],
    targets: [.executableTarget(name: "Smoke", dependencies: [
        .product(name: "%s", package: "appportal-apple-packages")
    ])])
''' % (REPOSITORY, version, module))
            (source / 'main.swift').write_text('import ' + module + '\n' + SMOKE[module] + '\n')
            env['CLANG_MODULE_CACHE_PATH'] = str(product_root / 'clang-cache')
            env['SWIFTPM_MODULECACHE_OVERRIDE'] = str(product_root / 'swift-module-cache')
            print('Cold remote product consumer:', module, flush=True)
            print(run(*swift_command(product_root, consumer)), flush=True)
            resolved = json.loads((consumer / 'Package.resolved').read_text())
            require(len(resolved['pins']) == 1 and resolved['pins'][0]['location'] == REPOSITORY
                    and resolved['pins'][0]['state']['version'] == version, 'Unexpected resolved dependency')
        print('PASS: every public binary slice linked; four independently cold remote products built and ran.', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parent.parent / 'Package.swift')
    parser.add_argument('--temporary-parent', type=Path, required=True)
    args = parser.parse_args()
    verify(args.manifest, args.temporary_parent)
