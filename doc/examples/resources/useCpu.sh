#!/bin/env sh

set -e

# Just compute SQRT for $1 seconds on $2 threads
stress --vm 1 --vm-bytes $2 --timeout $1

# Output artefact for surveyor:
echo {\"bytes\": $2, \"timeout\": $1} > /artefact/results.json
