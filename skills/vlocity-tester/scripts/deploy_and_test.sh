#!/usr/bin/env bash
# ==============================================================================
# deploy_and_test.sh
# Deploys a Vlocity/OmniStudio component to a Salesforce org and immediately
# runs an integration/REST API test using the matching invoke scripts.
# ==============================================================================

set -eo pipefail

# Highlight colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERROR]${NC} $1"; }

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <component_dir> <ip_key_or_dr_name> [org_alias]"
  echo "Example: $0 ./vlocity/IntegrationProcedure/MyAccount_UpdateAddress MyAccount_UpdateAddress my-scratch-org"
  exit 1
fi

COMPONENT_DIR="$1"
TEST_KEY="$2"
ORG_ALIAS="${3:-}"

# Check directories
if [ ! -d "$COMPONENT_DIR" ]; then
  log_err "Component directory '$COMPONENT_DIR' does not exist."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: Deploy using vlocity packDeploy
if ! command -v vlocity &> /dev/null; then
  log_err "The 'vlocity' CLI command is not available in the PATH."
  log_err "Please install the Vlocity Build Tool CLI: npm install -g vlocity"
  exit 1
fi

log_info "Fetching target Salesforce username..."
SF_CMD="sf org display --json"
if [ -n "$ORG_ALIAS" ]; then
  SF_CMD="$SF_CMD --target-org \"$ORG_ALIAS\""
fi

ORG_JSON=$(eval "$SF_CMD" 2>/dev/null || true)
if [ -z "$ORG_JSON" ]; then
  log_err "Failed to query target Salesforce org info. Please authenticate using 'sf org login web'."
  exit 1
fi

USERNAME=$(echo "$ORG_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('result', {}).get('username', ''))" 2>/dev/null || true)
if [ -z "$USERNAME" ]; then
  log_err "Could not retrieve the username from 'sf org display' output nyan! (｡•́︿•̀｡)"
  exit 1
fi

log_info "Extracted username: $USERNAME"

# Parse PROJECT_PATH and MANIFEST_ENTRY
COMPONENT_DIR_NORM="${COMPONENT_DIR%/}"
CATEGORIES=("IntegrationProcedure" "DataRaptor" "OmniScript" "FlexCard" "VlocityCard" "Product2" "CalculationProcedure" "CalculationMatrix" "System" "StoryObject" "UIFormula" "VlocityAction" "VlocityAttachment" "VlocityStateModel" "VlocityUITemplate" "ManualQueue")

PROJECT_PATH=""
MANIFEST_ENTRY=""

for cat in "${CATEGORIES[@]}"; do
  if [[ "$COMPONENT_DIR_NORM" =~ (.*)/($cat/.*) ]]; then
    PROJECT_PATH="${BASH_REMATCH[1]}"
    MANIFEST_ENTRY="${BASH_REMATCH[2]}"
    break
  elif [[ "$COMPONENT_DIR_NORM" =~ ^($cat/.*) ]]; then
    PROJECT_PATH="."
    MANIFEST_ENTRY="${BASH_REMATCH[1]}"
    break
  fi
done

if [ -z "$PROJECT_PATH" ]; then
  PROJECT_PATH=$(dirname "$(dirname "$COMPONENT_DIR_NORM")")
  MANIFEST_ENTRY=$(basename "$(dirname "$COMPONENT_DIR_NORM")")/$(basename "$COMPONENT_DIR_NORM")
fi

log_info "Parsed Vlocity structure:"
log_info "  - Project Path: $PROJECT_PATH"
log_info "  - Manifest Entry: $MANIFEST_ENTRY"

# Write dynamic Vlocity job file
TEMP_JOB_FILE="./vlocity-temp-job-$$.yaml"

cleanup() {
  if [ -f "$TEMP_JOB_FILE" ]; then
    log_info "Cleaning up temporary job configuration..."
    rm -f "$TEMP_JOB_FILE"
  fi
}
trap cleanup EXIT INT TERM

cat <<EOF > "$TEMP_JOB_FILE"
projectPath: $PROJECT_PATH
queries:
  - VlocityDataPackType: Product2
    query: Select Id, Name, %vlocity_namespace%__GlobalKey__c from Product2
manifestOnly: true
separateProducts: true
oauthConnection: true
activate: true
manifest:
  - $MANIFEST_ENTRY
EOF

log_info "Starting Vlocity deployment using vlocity packDeploy..."
vlocity -sfdx.username "$USERNAME" -job "$TEMP_JOB_FILE" packDeploy

log_info "Deployment completed successfully!"

# Step 2: Detect component type from folder path or filename
TYPE="unknown"
if [[ "$COMPONENT_DIR" == *"IntegrationProcedure"* ]]; then
  TYPE="ip"
elif [[ "$COMPONENT_DIR" == *"DataRaptor"* ]]; then
  TYPE="dr"
else
  # Auto-detect from folder contents
  if glob_match=$(find "$COMPONENT_DIR" -name "*_DataPack.json" | head -n 1); then
    if grep -q "IntegrationProcedure" "$glob_match" 2>/dev/null; then
      TYPE="ip"
    elif grep -q "DataRaptor" "$glob_match" 2>/dev/null; then
      TYPE="dr"
    fi
  fi
fi

if [ "$TYPE" == "unknown" ]; then
  log_warn "Could not auto-detect if component is IP or DR. Defaulting to Integration Procedure."
  TYPE="ip"
fi

# Step 3: Find inputs and outputs
INPUT_FILE=""
EXPECTED_OUTPUT_FILE=""

# Check in parent directory or subfolders for SampleInput/SampleOutput
if [ -f "$COMPONENT_DIR/SampleInput.json" ]; then
  INPUT_FILE="$COMPONENT_DIR/SampleInput.json"
elif [ -f "$COMPONENT_DIR/sampleInput.json" ]; then
  INPUT_FILE="$COMPONENT_DIR/sampleInput.json"
fi

if [ -f "$COMPONENT_DIR/SampleOutput.json" ]; then
  EXPECTED_OUTPUT_FILE="$COMPONENT_DIR/SampleOutput.json"
elif [ -f "$COMPONENT_DIR/sampleOutput.json" ]; then
  EXPECTED_OUTPUT_FILE="$COMPONENT_DIR/sampleOutput.json"
fi

# Generate temp file to hold actual response
ACTUAL_OUTPUT_FILE=$(mktemp)

# Step 4: Invoke REST API
log_info "Invoking deployed Vlocity element..."
INVOKE_ARGS=""
if [ -n "$ORG_ALIAS" ]; then
  INVOKE_ARGS="--org $ORG_ALIAS"
fi

if [ -n "$INPUT_FILE" ]; then
  log_info "Found input fixture at '$INPUT_FILE'"
  INVOKE_ARGS="$INVOKE_ARGS --input \"$INPUT_FILE\""
fi

INVOKE_ARGS="$INVOKE_ARGS --output \"$ACTUAL_OUTPUT_FILE\""

if [ "$TYPE" == "ip" ]; then
  log_info "Invoking IP '$TEST_KEY'..."
  python3 "$SCRIPT_DIR/invoke_ip.py" --ip-key "$TEST_KEY" $INVOKE_ARGS
else
  log_info "Invoking DR '$TEST_KEY'..."
  python3 "$SCRIPT_DIR/invoke_dr.py" --dr-name "$TEST_KEY" --schema auto $INVOKE_ARGS
fi

log_info "Invocation completed. Output stored in: $ACTUAL_OUTPUT_FILE"

# Step 5: Compare outputs if expected fixture is found
if [ -n "$EXPECTED_OUTPUT_FILE" ]; then
  log_info "Comparing actual response with expected fixture '$EXPECTED_OUTPUT_FILE'..."
  
  if python3 "$SCRIPT_DIR/compare_output.py" --actual "$ACTUAL_OUTPUT_FILE" --expected "$EXPECTED_OUTPUT_FILE" --fuzzy-ids; then
    log_info "✅ TEST PASSED: Output matches the expected test fixture perfectly!"
    rm -f "$ACTUAL_OUTPUT_FILE"
    exit 0
  else
    log_err "❌ TEST FAILED: Differences found in output."
    rm -f "$ACTUAL_OUTPUT_FILE"
    exit 1
  fi
else
  log_warn "No expected output file (SampleOutput.json) found in '$COMPONENT_DIR'. Showing actual output:"
  cat "$ACTUAL_OUTPUT_FILE"
  echo ""
  rm -f "$ACTUAL_OUTPUT_FILE"
  exit 0
fi
