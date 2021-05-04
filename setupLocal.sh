## Check if sourced - has to be called outside function
# Took from https://stackoverflow.com/questions/2683279/how-to-detect-if-a-script-is-being-sourced
([[ -n $ZSH_EVAL_CONTEXT && $ZSH_EVAL_CONTEXT =~ :file$ ]] ||
[[ -n $KSH_VERSION && $(cd "$(dirname -- "$0")" &&
    printf '%s' "${PWD%/}/")$(basename -- "$0") != "${.sh.file}" ]] ||
[[ -n $BASH_VERSION ]] && (return 0 2>/dev/null)) && sourced=1

if [ -z "$sourced" ]; then
    echo "Invalid usage; do not invoke directly, use 'source setupDevel.sh' instead"
    exit 1
fi

if [ ! -e ".venv" ]; then
    echo "No virtual environment, installing it"
    python3 -m venv .venv
fi

source .venv/bin/activate

export SURVEYOR_CFG=configuration/local.py
export FLASK_APP=surveyor
export FLASK_ENV=development