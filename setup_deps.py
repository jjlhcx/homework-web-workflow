from pathlib import Path
import subprocess
import sys


def dependencies_ready(vendor):
    try:
        subprocess.run(
            [sys.executable, '-c',
             'import sys; sys.path.insert(0,sys.argv[1]); import playwright.sync_api,greenlet',
             str(vendor)],
            check=True, timeout=8, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return True


def pip(args, timeout):
    try:
        subprocess.run([sys.executable, '-m', 'pip', '--disable-pip-version-check',
                        '--no-input', *args], check=True, timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return False
    return True


def prepare(project):
    vendor = project / 'vendor'
    if dependencies_ready(vendor):
        return 'DEPENDENCIES_READY'
    cache = project / 'wheelhouse'
    cache.mkdir(exist_ok=True)
    requirements = ['-r', str(project / 'requirements.txt')]
    install = ['install', '--no-index', '--find-links', str(cache), '--target', str(vendor),
               '--upgrade', '--no-warn-script-location', *requirements]
    if any(cache.glob('*.whl')) and pip(install, 20) and dependencies_ready(vendor):
        return 'DEPENDENCIES_INSTALLED'
    download = ['download', '--only-binary=:all:', '--timeout', '8', '--retries', '1',
                '--dest', str(cache), *requirements]
    if not pip(download, 50):
        return 'DEPENDENCY_DOWNLOAD_FAILED: put compatible wheels in wheelhouse and run setup again.'
    if not pip(install, 20) or not dependencies_ready(vendor):
        return 'DEPENDENCY_INSTALL_FAILED: check the Python version and wheelhouse contents.'
    return 'DEPENDENCIES_INSTALLED'


if __name__ == '__main__':
    project = Path(__file__).resolve().parent
    if sys.argv[1:] == ['--check']:
        sys.exit(0 if dependencies_ready(project / 'vendor') else 1)
    status = prepare(project)
    ready = status in ('DEPENDENCIES_READY', 'DEPENDENCIES_INSTALLED')
    if ready:
        (project / '.python-runtime').write_text(sys.executable + '\n', encoding='utf-8')
    print(status)
    sys.exit(0 if ready else 1)
