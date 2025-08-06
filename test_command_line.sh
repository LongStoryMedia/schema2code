#!/usr/bin/env bash
# test_command_line.sh
# This script calls the schema2code command line tool for each schema file in each language
# to test the actual command line functionality

# Setup colors for better output readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Base directories
SCHEMA_DIR="sample_schemas"
OUTPUT_DIR="sample_code"

# Clear out the output directory before running tests
echo -e "${YELLOW}Clearing output directory: $OUTPUT_DIR${NC}"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Language settings
declare -A LANGUAGES
LANGUAGES=(
    ["dotnet"]="csharp"
    ["go"]="go"
    ["protos"]="proto"
    ["python"]="python"
    ["typescript"]="typescript"
)

# Language-specific options
declare -A LANGUAGE_OPTIONS
LANGUAGE_OPTIONS=(
    ["dotnet"]="--namespace SchemaTypes"
    ["go"]="--package schema"
    ["protos"]="--package schema"
    ["python"]=""
    ["typescript"]=""
)

# Make sure output directories exist
for lang_dir in "${!LANGUAGES[@]}"; do
    mkdir -p "$OUTPUT_DIR/$lang_dir"
done

# Counter for statistics
TOTAL_SCHEMAS=0
TOTAL_SUCCESSFUL=0
TOTAL_FAILED=0

# Print header
echo -e "${BLUE}===================================================${NC}"
echo -e "${BLUE}Testing schema2code command line for multiple schemas${NC}"
echo -e "${BLUE}===================================================${NC}"

# Get list of schema files
mapfile -t SCHEMA_FILES < <(find "$SCHEMA_DIR" -type f -name "*.yaml" -o -name "*.json" | sort)
TOTAL_SCHEMAS=${#SCHEMA_FILES[@]}

echo -e "${YELLOW}Found ${TOTAL_SCHEMAS} schema files to process${NC}"
echo ""

# Process each language
for lang_dir in "${!LANGUAGES[@]}"; do
    lang_name=${LANGUAGES[$lang_dir]}
    options=${LANGUAGE_OPTIONS[$lang_dir]}
    
    echo -e "${BLUE}=== Processing $lang_name files (output to $OUTPUT_DIR/$lang_dir/) ===${NC}"
    successful=0
    failed=0
    
    # Process each schema file for this language
    for schema_file in "${SCHEMA_FILES[@]}"; do
        # Get base filename without extension
        base_name=$(basename "$schema_file")
        file_name="${base_name%.*}"
        
        # Set output extension based on language
        case "$lang_name" in
            "csharp")
                # For C#, use PascalCase filenames - proper snake_case to PascalCase conversion
                # First lowercase everything, then capitalize first letter and letters after underscores, then remove underscores
                pascal_name=$(echo "$file_name" | awk 'BEGIN{FS="_";OFS=""} {for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)} 1')
                output_file="$OUTPUT_DIR/$lang_dir/${pascal_name}.cs"
            ;;
            "typescript")
                # For TypeScript, use PascalCase filenames - proper snake_case to PascalCase conversion
                # First lowercase everything, then capitalize first letter and letters after underscores, then remove underscores
                pascal_name=$(echo "$file_name" | awk 'BEGIN{FS="_";OFS=""} {for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) substr($i,2)} 1')
                output_file="$OUTPUT_DIR/$lang_dir/${pascal_name}.ts"
            ;;
            "python")
                output_file="$OUTPUT_DIR/$lang_dir/${file_name}.py"
            ;;
            "go")
                output_file="$OUTPUT_DIR/$lang_dir/${file_name}.go"
            ;;
            "proto")
                output_file="$OUTPUT_DIR/$lang_dir/${file_name}.proto"
            ;;
            *)
                output_file="$OUTPUT_DIR/$lang_dir/${file_name}.txt"
            ;;
        esac
        
        echo -e -n "Processing ${YELLOW}$(basename "$schema_file")${NC}... "
        
        # Run the command
        cmd="python -m src.main \"$schema_file\" --language $lang_name --output \"$output_file\" $options"
        output=$(eval "$cmd" 2>&1)
        exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            echo -e "${GREEN}SUCCESS${NC}"
            
            # Validate Python files for syntax errors
            if [ "$lang_name" == "python" ]; then
                echo -e -n "    Validating Python syntax... "
                python -m py_compile "$output_file" 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}OK${NC}"
                else
                    echo -e "${RED}SYNTAX ERROR${NC}"
                    echo -e "${RED}File has syntax errors: $output_file${NC}"
                    failed=$((failed + 1))
                    continue
                fi
                
                # Check for missing imports using Python's ast module
                echo -e -n "    Checking imports... "
                import_check=$(python -c "
import ast, sys
try:
    with open('$output_file', 'r') as f:
        tree = ast.parse(f.read())

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for name in node.names:
                imports.add(name.name)
        elif isinstance(node, ast.Import):
            for name in node.names:
                imports.add(name.name.split('.')[0])

    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used_names.add(node.value.id)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            used_names.add(node.value.id)

    missing = []
    for name in used_names:
        if name not in imports and name not in ['str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'None', 'True', 'False']:
            if not any(imp.endswith(name) for imp in imports):
                missing.append(name)

    if missing:
        print('ERROR: Potentially undefined references: ' + ', '.join(missing))
        sys.exit(1)
    sys.exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
                " 2>&1)
                
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}OK${NC}"
                else
                    echo -e "${RED}IMPORT ISSUE${NC}"
                    echo -e "${RED}$import_check${NC}"
                    failed=$((failed + 1))
                    continue
                fi
            fi
            
            successful=$((successful + 1))
        else
            echo -e "${RED}FAILED${NC}"
            echo -e "${RED}$output${NC}"
            failed=$((failed + 1))
        fi
    done
    
    echo -e "${YELLOW}$lang_name summary: $successful successful, $failed failed${NC}"
    echo ""
    
    TOTAL_SUCCESSFUL=$((TOTAL_SUCCESSFUL + successful))
    TOTAL_FAILED=$((TOTAL_FAILED + failed))
done

# Print summary
echo -e "${BLUE}===================================================${NC}"
echo -e "${BLUE}Summary:${NC}"
echo -e "${BLUE}Total schemas processed: ${TOTAL_SCHEMAS}${NC}"
echo -e "${GREEN}Total successful generations: ${TOTAL_SUCCESSFUL}${NC}"
echo -e "${RED}Total failed generations: ${TOTAL_FAILED}${NC}"
echo -e "${BLUE}===================================================${NC}"
