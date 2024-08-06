import os
import time
import datetime
import sys
import re
import shutil
import hashlib
import subprocess
import requests
import logging

from git import Repo, GitCommandError

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(filename='./logs/updater.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get the sleep duration from environment variable
SLEEP_DURATION = int(os.getenv('SLEEP_DURATION', 3600))  # Default to 1 hours if not set

# get the directory of the current script
script_dir = os.path.dirname(os.path.realpath(__file__))

MAIN_REPO_DIR = os.path.join(script_dir, 'PKGBUILDs')
REPOS = [
    {
        'appimage_dir': os.path.join(MAIN_REPO_DIR, 'featherwallet-appimage'),
        'appimage_submodule_dir': os.path.join(MAIN_REPO_DIR, 'featherwallet-appimage', 'featherwallet-appimage'),
        'github_repo': 'feather-wallet/feather',
    },
    {
        'appimage_dir': os.path.join(MAIN_REPO_DIR, 'chatbox-appimage'),
        'appimage_submodule_dir': os.path.join(MAIN_REPO_DIR, 'chatbox-appimage', 'chatbox-appimage'),
        'github_repo': 'Bin-Huang/chatbox',
    },
]

# Read environment variables for GitHub authentication
TOKEN_GITHUB = os.getenv('TOKEN_GITHUB')
GITHUB_USER = os.getenv('GITHUB_USER')  # Your GitHub username

headers = {
    'Authorization': f'token {TOKEN_GITHUB}',
    'Accept': 'application/vnd.github.v3+json',
}

# Reset and clean a repository (removes new/untracked files)
def reset_and_clean(repo_dir):
    repo = Repo(repo_dir)
    print(f"Resetting and cleaning repository in {repo_dir}...")
    logging.info(f"Resetting and cleaning repository in {repo_dir}...")
    for submodule in repo.submodules:
        print(f"Submodule: {submodule}")
        logging.info(f"Submodule: {submodule}")
        submodule_repo = submodule.module()
        try:
            submodule_repo.git.checkout('main')
        except GitCommandError:
            try:
                submodule_repo.git.checkout('master')
            except GitCommandError:
                print("Both main and master branches do not exist, staying on current branch.", file=sys.stderr)
                logging.error("Both main and master branches do not exist, staying on current branch.")
        submodule_repo.git.pull()
        submodule_repo.git.reset('--hard')
        submodule_repo.git.clean('-fdx')
    try:
        repo.git.checkout('main')
    except GitCommandError:
        try:
            repo.git.checkout('master')
        except GitCommandError:
            print("Both main and master branches do not exist, staying on current branch.", file=sys.stderr)
            logging.error("Both main and master branches do not exist, staying on current branch.")
    repo.git.pull()
    repo.git.reset('--hard')
    repo.git.clean('-fdx')

# Test the PKGBUILD script using makepkg command
def test_pkgbuild(pkgbuild_dir):
    try:
        subprocess.check_call(['makepkg', '-f', '--clean'], cwd=pkgbuild_dir)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to build the package in {pkgbuild_dir}. Error: {e}")
        print(f"Failed to build the package in {pkgbuild_dir}. Aborting...")
        raise

# Retrieve the current version from the PKGBUILD script
def get_old_version(pkgbuild_file):
    with open(pkgbuild_file, 'r') as f:
        content = f.read()
        old_version_match = re.search(r'pkgver=(.+?)\n', content)
        if old_version_match:
            return old_version_match.group(1)
        else:
            raise ValueError("Couldn't find pkgver in the PKGBUILD file.")

# Retrieve the current package release number from the PKGBUILD script
def get_old_pkgrel(pkgbuild_file):
    with open(pkgbuild_file, 'r') as f:
        content = f.read()
        old_pkgrel_match = re.search(r'pkgrel=(.+?)\n', content)
        if old_pkgrel_match:
            return old_pkgrel_match.group(1)
        else:
            raise ValueError("Couldn't find pkgrel in the PKGBUILD file.")

# Get the latest stable version (tag) from the GitHub repository
def get_latest_tag(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/tags'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tags = response.json()
        if tags:
            for i in range(len(tags)):
                tag_name = tags[i]['name']
                if "beta" not in tag_name.lower() and "rc" not in tag_name.lower():
                    tag_name = tag_name.lstrip('vV')
                    return tag_name
    print(f"Failed to retrieve tags for {owner}/{repo}. Response code: {response.status_code}, response text: {response.text}", file=sys.stderr)
    logging.error(f"Failed to retrieve tags for {owner}/{repo}. Response code: {response.status_code}, response text: {response.text}")
    raise ValueError("Failed to retrieve the latest tag.")

# Compute the checksum of the given URL content
def get_checksum(url, algorithm='sha512'):
    response = requests.get(url, stream=True)

    if response.status_code != 200:
        print(f"Failed to download the file. URL: {url}, Status code: {response.status_code}", file=sys.stderr)
        logging.error(f"Failed to download the file. URL: {url}, Status code: {response.status_code}")
        raise ValueError(f"Failed to download the file. URL: {url}, Status code: {response.status_code}")

    print(f"Calculating {algorithm} checksum for {url}...")
    logging.info(f"Calculating {algorithm} checksum for {url}...")

    # Save the file to disk for comparison
    filename = url.split("/")[-1]
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)

    # Calculate checksum
    with open(filename, 'rb') as f:
        h = hashlib.new(algorithm)
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    checksum = h.hexdigest()

    print(f"Calculated {algorithm} checksum: {checksum}")
    logging.info(f"Calculated {algorithm} checksum: {checksum}")
    return checksum

# Update checksums in the PKGBUILD content
def update_checksums(content, url):
    algorithm = 'sha512'
    old_checksum_line = re.search(rf'{algorithm}sums=\((.*?)\)', content)
    if old_checksum_line:
        old_checksum = old_checksum_line.group(1).strip("'\"")
        if old_checksum != 'SKIP':
            new_checksum = get_checksum(url, algorithm)
            print(f"Replacing old {algorithm} checksum {old_checksum} with new checksum {new_checksum}...")
            logging.info(f"Replacing old {algorithm} checksum {old_checksum} with new checksum {new_checksum}...")
            content = content.replace(old_checksum, new_checksum)
    else:
        print(f"[IGNORE if you are using PGP for verification] Couldn't find {algorithm}sums in the PKGBUILD file. Make sure it exists and is not set to 'SKIP'.", file=sys.stderr)
        logging.error(f"[IGNORE if you are using PGP for verification] Couldn't find {algorithm}sums in the PKGBUILD file. Make sure it exists and is not set to 'SKIP'.")
    return content

# Update the PKGBUILD script
def update_pkgbuild(repo):
    appimage_dir = repo['appimage_dir']
    pkgbuild_file = os.path.join(appimage_dir, 'PKGBUILD')
    old_version = get_old_version(pkgbuild_file)
    old_pkgrel = get_old_pkgrel(pkgbuild_file)
    github_repo = repo['github_repo']
    owner, repo_name = github_repo.split('/')
    latest_tag = get_latest_tag(owner, repo_name)

    with open(pkgbuild_file, 'r') as f:
        content = f.read()

    if old_version != latest_tag:  # If a new version is found
        print(f"New version for {github_repo} found: {latest_tag}! Updating PKGBUILD...")
        logging.info(f"New version for {github_repo} found: {latest_tag}! Updating PKGBUILD...")
        content = content.replace(old_version, latest_tag)  # Update version

        content = content.replace(f"pkgrel={old_pkgrel}", "pkgrel=1")  # Reset pkgrel to 1
        logging.info(f"Updating pkgrel from {old_pkgrel} to 1...")

        # Extract url from PKGBUILD content and store in pkgbuild_url
        pkgbuild_url_match = re.search(r'url=(.+?)\n', content)

        # Extract _appimage from PKGBUILD content
        _appimage_match = re.search(r'_appimage=(.+?)\n', content)
        if _appimage_match:
            _appimage_value = _appimage_match.group(1).strip('"')
            _appimage_value = _appimage_value.replace('${pkgver}', latest_tag)
            _appimage_value = _appimage_value.replace('${_pkgname}', repo_name)
            _appimage_value = _appimage_value.replace('${arch}', 'x86_64')  # Assuming x86_64 as the default architecture
        else:
            print("Couldn't find _appimage in the PKGBUILD file.", file=sys.stderr)
            logging.error("Couldn't find _appimage in the PKGBUILD file.")
            raise ValueError("Couldn't find _appimage in the PKGBUILD file.")

        # Extract source URL and substitute the variables from the PKGBUILD file
        source_url_match = re.search(r'source=\("(.*?)"', content)
        if source_url_match:
            source_url = source_url_match.group(1).strip('"')
            source_url = source_url.replace('${pkgver}', latest_tag)
            source_url = source_url.replace('${_pkgname}', repo_name)
            source_url = source_url.replace('${url}', pkgbuild_url_match.group(1).strip('"'))
            source_url = source_url.replace('${_appimage}', _appimage_value)
        else:
            print("Couldn't find source URL in the PKGBUILD file.", file=sys.stderr)
            logging.error("Couldn't find source URL in the PKGBUILD file.")
            raise ValueError("Couldn't find source URL in the PKGBUILD file.")
        print(f"Source URL: {source_url}")
        logging.info(f"Source URL: {source_url}")

        content = update_checksums(content, source_url)

        with open(pkgbuild_file, 'w') as f:
            f.write(content)

        test_pkgbuild(appimage_dir)

    else:
        print(f"No new version found for {github_repo}. Skipping...")
        logging.info(f"No new version found for {github_repo}. Skipping...")
        logging.info(f"PKGREL is: {old_pkgrel}")

# Handle the commits
def commit_changes(repo_dir, message):
    repo = Repo(repo_dir)
    git = repo.git

    try:
        git.add('-A')
        git.commit('-m', message)
    except GitCommandError as e:
        if 'nothing to commit' in str(e):
            print(f"Nothing to commit in {repo_dir}...")
            logging.info(f"Nothing to commit in {repo_dir}...")
            return False
        else:
            print(f"Failed to commit changes in {repo_dir} with message '{message}'. Error: {e}", file=sys.stderr)
            logging.error(f"Failed to commit changes in {repo_dir} with message '{message}'. Error: {e}")
            raise e
    else:
        print(f"Committed changes in {repo_dir} with message '{message}'...")
        logging.info(f"Committed changes in {repo_dir} with message '{message}'...")
        return True

# Push changes
def push_changes(repo_dir):
    repo = Repo(repo_dir)
    git = repo.git
    git.push()
    print(f"Pushed changes in {repo_dir}...")
    logging.info(f"Pushed changes in {repo_dir}...")

# Apply the changes to the submodules
def apply_changes(repo):
    appimage_submodule_dir = repo['appimage_submodule_dir']

    # Copy the modified PKGBUILD file to the submodule directory
    shutil.copy2(os.path.join(repo['appimage_dir'], 'PKGBUILD'), appimage_submodule_dir)

    # Run makepkg --printsrcinfo and capture the output
    result = subprocess.run(['makepkg', '--printsrcinfo'], cwd=appimage_submodule_dir, capture_output=True, text=True)
    srcinfo_output = result.stdout

    # Save the output to the .SRCINFO file
    with open(os.path.join(appimage_submodule_dir, '.SRCINFO'), 'w') as f:
        f.write(srcinfo_output)

# Main loop
def main():
    while True:  # Infinite loop
        reset_and_clean(MAIN_REPO_DIR)
        for repo in REPOS:
            try:
                reset_and_clean(repo['appimage_submodule_dir'])
                update_pkgbuild(repo)
                apply_changes(repo)
                # Commit changes to the submodule
                commit_message = f"Bumped {repo['github_repo']} to version {get_latest_tag(*repo['github_repo'].split('/'))}"
                submodule_changes = commit_changes(repo['appimage_submodule_dir'], commit_message)

                # If there were changes in the submodule, commit the changes in the main repo
                if submodule_changes:
                    commit_changes(MAIN_REPO_DIR, commit_message)
                    push_changes(repo['appimage_submodule_dir'])
                    push_changes(MAIN_REPO_DIR)
            except Exception as e:
                print(f"Failed to update {repo['github_repo']}. Error: {str(e)}", file=sys.stderr)
                logging.error(f"Failed to update {repo['github_repo']}. Error: {str(e)}")

        # Print the time for the next run
        next_run = datetime.datetime.now() + datetime.timedelta(seconds=SLEEP_DURATION)
        print("--------------------------------------------------")
        print(f"Sleeping for {SLEEP_DURATION} seconds...")
        logging.info(f"Sleeping for {SLEEP_DURATION} seconds...")
        print(f"Next run will be at {next_run.isoformat()}")
        logging.info(f"Next run will be at {next_run.isoformat()}")

        # Sleep for SLEEP_DURATION seconds
        time.sleep(SLEEP_DURATION)

if __name__ == "__main__":
    main()
