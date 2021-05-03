#!/bin/env sh

set -e

# Just wait for number of seconds specified, do nothing interesting
for i in $(seq 1 $1); do
    sleep 1;
    echo $i;
done

# Output artefact for surveyor:
echo {\"waitedFor\": $1} > /artefact/results.json
