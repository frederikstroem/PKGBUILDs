FROM archlinux

#
# ROOT
#

# Remove snapper to increase speed
# RUN pacman -Rns --noconfirm snap-pac snapper

# Update the system and install necessary packages
RUN pacman -Syu --noconfirm
RUN pacman -S --noconfirm base-devel git openssh python python-pip gnupg
# Feather dependencies
RUN pacman -Syu --noconfirm tor fuse2fs

# Install pip dependencies
# RUN pip install requests gitpython
RUN pacman -S --noconfirm python-requests python-gitpython

# Create a non-root user
RUN useradd -m builduser && \
    passwd -d builduser && \
    echo 'builduser ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# # Copy the updater.py file to the container
# COPY updater.py /home/builduser/

# Copy trusted GPG key
COPY featherwallet.asc /home/builduser/featherwallet.asc

# Create ssh dir
RUN mkdir -p /home/builduser/.ssh
COPY ssh_key /home/builduser/.ssh/id_ed25519

# Skip SSH key verification
RUN echo -e "Host *\n\tStrictHostKeyChecking no\n\tUserKnownHostsFile=/dev/null\n\n" > /home/builduser/.ssh/config

# Fix perms
RUN chmod 600 /home/builduser/.ssh/id_ed25519
RUN chown -R builduser:builduser /home/builduser

#
# USER
#

# Switch to the non-root user
USER builduser
WORKDIR /home/builduser

# Set Git name and email
ARG GIT_NAME
ARG GIT_EMAIL
RUN git config --global user.name "${GIT_NAME}"
RUN git config --global user.email "${GIT_EMAIL}"

# Import the trusted GPG key
RUN gpg --import /home/builduser/featherwallet.asc

# Clone the repository and its submodules
ARG GIT_REPO
RUN git clone --recurse-submodules "${GIT_REPO}"

CMD tail -f /dev/null
