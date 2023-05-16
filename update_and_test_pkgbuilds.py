import os
import subprocess
import requests
import re
import hashlib
import json

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
        old_version_match = re.search(r'pkgver=(.+?)', content)
        if old_version_match:
            return old_version_match.group(1)
        else:
            raise ValueError("Couldn't find pkgver in the PKGBUILD file.")

def get_latest_tag(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/tags'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tags = response.json()
        if tags:
            latest_tag = tags[0]['name']
            return latest_tag
    print(f"Failed to retrieve tags for {owner}/{repo}. Response code: {response.status_code}, response text: {response.text}")
    raise ValueError("Failed to retrieve the latest tag.")

def get_checksum(url, algorithm='sha256'):
    response = requests.get(url, stream=True)
    if algorithm == 'sha256':
        h = hashlib.sha256()
    elif algorithm == 'blake2b':
        h = hashlib.blake2b()
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    for chunk in response.iter_content(chunk_size=8192):
        h.update(chunk)
    return h.hexdigest()

def replace_checksums(content, checksum_name, new_checksums):
    checksum_line = re.search(f'{checksum_name}=\((.*?)\)', content)
    if checksum_line:
        checksums = checksum_line.group(1).split()
        for i, checksum in enumerate(checksums):
            if checksum != 'SKIP':
                content = content.replace(checksum, new_checksums[i])
    return content

def main():
    if not TOKEN_GITHUB:
        raise ValueError("Invalid or missing TOKEN_GITHUB environment variable. Please set a valid GitHub personal access token.")

    g = Github(TOKEN_GITHUB)
    for repo_info in REPOS:
        appimage_dir = repo_info['appimage_dir']
        github_repo = repo_info['github_repo']
        owner = github_repo.split('/')[0]  # Extract the owner from the repo string
        repo = github_repo.split('/')[1]  # Extract the repo from the repo string

        version = get_latest_tag(owner, repo)

        pkgbuild_path = os.path.join(appimage_dir, 'PKGBUILD')
        with open(pkgbuild_path, 'r') as f:
            content = f.read()

        old_version = get_old_version(pkgbuild_path)

        content = content.replace(f"pkgver={old_version}", f"pkgver={version}")

        url_match = re.search(r'source=\[(.*?)\]', content)
        if url_match:
            urls = url_match.group(1).split()
            new_sha256_checksums = [get_checksum(url.replace('${pkgver}', version), 'sha256') for url in urls if url != 'SKIP']
            new_b2_checksums = [get_checksum(url.replace('${pkgver}', version), 'blake2b') for url in urls if url != 'SKIP']

            content = replace_checksums(content, 'sha256sums', new_sha256_checksums)
            content = replace_checksums(content, 'b2sums', new_b2_checksums)


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
