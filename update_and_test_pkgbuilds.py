import os
import subprocess
import requests
import re
from git import Repo
from github import Github

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

TOKEN_GITHUB = os.getenv('TOKEN_GITHUB')
GITHUB_USER = os.getenv('GITHUB_USER')  # Your GitHub username

headers = {
    'Authorization': f'token {TOKEN_GITHUB}',
    'Accept': 'application/vnd.github.v3+json',
}

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
    response = requests.get(url, headers=headers)
    return response.json()

def main():
    g = Github(TOKEN_GITHUB)
    for repo_info in REPOS:
        appimage_dir = repo_info['appimage_dir']
        github_repo = repo_info['github_repo']

        release_info = get_latest_release(github_repo)
        version = release_info['tag_name']

        pkgbuild_path = os.path.join(appimage_dir, 'PKGBUILD')
        with open(pkgbuild_path, 'r') as f:
            content = f.read()

        old_version = get_old_version(pkgbuild_path)

        content = content.replace(f"OLD_VERSION={old_version}", f"OLD_VERSION={version}")

        with open(pkgbuild_path, 'w') as f:
            f.write(content)

        test_script_path = os.path.join(appimage_dir, 'test')
        subprocess.check_call(['bash', test_script_path])

        apply_script_path = os.path.join(appimage_dir, 'apply')
        subprocess.check_call(['bash', apply_script_path])

        # Use gitpython to create a new branch and commit the changes
        repo = Repo(os.getcwd())
        new_branch = repo.create_head(f"update-{appimage_dir}-to-{version}")
        new_branch.checkout()
        repo.index.add([pkgbuild_path])
        repo.index.commit(f"Update {appimage_dir} to version {version}")

        # Push the new branch to GitHub
        origin = repo.remote("origin")
        origin.push(f"{new_branch}:{new_branch}")

        # Use PyGithub to create a new pull request
        gh_repo = g.get_repo(f"{GITHUB_USER}/{github_repo}")
        pr = gh_repo.create_pull(
            title=f"Update {appimage_dir} to version {version}",
            body="",
            head=f"{GITHUB_USER}:{new_branch}",
            base="main",
        )

if __name__ == "__main__":
    main()
