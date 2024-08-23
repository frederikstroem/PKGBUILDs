# Define variables for the package directories
chatbox_dir := "chatbox-appimage"
featherwallet_dir := "featherwallet-appimage"
submodule_branch := "master"

full-flow:
    just init-and-reset-submodules
    just test-pkgbuilds
    just apply-pkgbuilds
    just commit-and-push-all

reset-submodule submodule-dir:
    git -C {{submodule-dir}} restore .
    git -C {{submodule-dir}} clean -fdx
    git -C {{submodule-dir}} pull
    git -C {{submodule-dir}} checkout {{submodule_branch}}
    git -C {{submodule-dir}} reset --hard origin/{{submodule_branch}}

init-and-reset-submodules:
    git submodule update --init --recursive
    just reset-submodule {{chatbox_dir}}/{{chatbox_dir}}
    just reset-submodule {{featherwallet_dir}}/{{featherwallet_dir}}

# Task to test the PKGBUILD script
test-pkgbuild pkgbuild-dir:
    cd {{pkgbuild-dir}} && makepkg -f --clean && git clean -fdx .

test-pkgbuilds:
    just test-pkgbuild {{chatbox_dir}}
    just test-pkgbuild {{featherwallet_dir}}

apply-pkgbuild pkgbuild-dir:
    just reset-submodule {{pkgbuild-dir}}/{{pkgbuild-dir}}
    cp {{pkgbuild-dir}}/PKGBUILD {{pkgbuild-dir}}/{{pkgbuild-dir}}
    cd {{pkgbuild-dir}}/{{pkgbuild-dir}} && makepkg --printsrcinfo > .SRCINFO

apply-pkgbuilds:
    just apply-pkgbuild {{chatbox_dir}}
    just apply-pkgbuild {{featherwallet_dir}}

commit-and-push pkgbuild-dir:
    git -C {{pkgbuild-dir}}/{{pkgbuild-dir}} add --all
    git -C {{pkgbuild-dir}}/{{pkgbuild-dir}} commit -m "Bumped version"
    git -C {{pkgbuild-dir}}/{{pkgbuild-dir}} push
    git add {{pkgbuild-dir}}
    git commit -m "Bumped version for {{pkgbuild-dir}}"
    git push

commit-and-push-all:
    just commit-and-push {{chatbox_dir}}
    just commit-and-push {{featherwallet_dir}}
