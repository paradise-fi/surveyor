# We will use an Ubuntu base image from a repository
FROM ubuntu:20.04

# Let's install our dependencies - in our case, it will be the program stress
# and git. We also install apt-transport-https and ca-certificates so we can use
# SSL to do `git pull`
RUN export DEBIAN_FRONTEND="noninteractive" && apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates apt-transport-https \
      stress git && \
      rm -rf /var/lib/apt/lists/*

# Create a directory where we store our scripts
RUN mkdir -p /scripts

# Fetch the scripts from Surveyor and place them under /scripts. Surveoyr
# provides several simple testing scripts in its repository.
#
# Note that if you use a compiled program, you would probably fetch the sources,
# compile it and install it.
RUN cd /tmp; \
    git clone https://github.com/paradise-fi/surveyor; \
    cp surveyor/doc/examples/resources/* /scripts

# Update PATH so we can call our scripts as installed programs
ENV PATH="/scripts:${PATH}"

