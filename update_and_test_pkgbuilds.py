import os
import subprocess
import requests
import re

REPOS = [
    {
        'appimage_dir': 'featherwallet-appimage',
        'github_repo': 'feather-wallet/feather',
    },
    {
        'appimage_dir': 'chatbox-appimage',
        'github_repo': 'Bin-Huang/chatbox',
    },
]

# Function to get the old version from PKGBUILD
def get_old_version(pkgbuild_file):
    with open(pkgbuild_file, 'r') as f:
        content = f.read()
        old_version_match = re.search(r'OLD_VERSION="(.+?)"', content)
        if old_version_match:
            return old_version_match.group(1)
        else:
            raise ValueError("Couldn't find OLD_VERSION in the PKGBUILD file.")

def get_latest_release(repo):
    url = f'https://api.github.com/repos/{repo}/releases/latest'
    response = requests.get(url)
    return response.json()

def main():
    for repo_info in REPOS:
        appimage_dir = repo_info['appimage_dir']
        github_repo = repo_info['github_repo']

        release_info = get_latest_release(github_repo)
        version = release_info['tag_name']

        # Update PKGBUILD with the new version
        pkgbuild_path = os.path.join(appimage_dir, 'PKGBUILD')
        with open(pkgbuild_path, 'r') as f:
            content = f.read()
        # Find the old version
        old_version = get_old_version(pkgbuild_path)

        content = content.replace(f"OLD_VERSION={old_version}", f"OLD_VERSION={version}")

        with open(pkgbuild_path, 'w') as f:
            f.write(content)

        # Test the PKGBUILD
        test_script_path = os.path.join(appimage_dir, 'test')
        subprocess.check_call(['bash', test_script_path])

        # Apply the changes
        apply_script_path = os.path.join(appimage_dir, 'apply')
        subprocess.check_call(['bash', apply_script_path])

        # # Commit and push the changes
        # commit_message = f"Update {appimage_dir} to version {version}"
        # subprocess.check_call(['git', 'add', pkgbuild_path])
        # subprocess.check_call(['git', 'commit', '-m', commit_message])
        # subprocess.check_call(['git', 'push'])

if __name__ == "__main__":
    main()
