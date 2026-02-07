#!/usr/bin/env zsh
#
# Email validation functions using regex
#

# Function to validate email address using regex
# Returns 0 if valid, 1 if invalid
validate_email() {
    local email="$1"
    
    # Basic length check
    if [[ ${#email} -gt 254 ]]; then
        return 1
    fi
    
    # Regex pattern for email validation
    # This pattern checks for:
    # - Valid local part (before @)
    # - @ symbol
    # - Valid domain part (after @)
    # - At least one dot in the domain part
    local email_pattern='^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if [[ $email =~ $email_pattern ]]; then
        return 0
    else
        return 1
    fi
}

# Alternative more strict email validation function
validate_email_strict() {
    local email="$1"
    
    # Length check
    if [[ ${#email} -gt 254 ]] || [[ ${#email} -lt 5 ]]; then  # Minimum length check
        return 1
    fi
    
    # More strict pattern that also ensures the email doesn't start or end with special characters
    local strict_pattern='^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
    
    if [[ $email =~ $strict_pattern ]]; then
        # Additional check to ensure no consecutive dots in local part
        if [[ $email =~ \.\. ]]; then
            return 1
        fi
        # Ensure there's only one @
        local at_count=$(echo "$email" | tr -cd '@' | wc -c)
        if [[ $at_count -ne 1 ]]; then
            return 1
        fi
        
        return 0
    else
        return 1
    fi
}

# Function to demonstrate usage
test_email_validation() {
    local emails=(
        "valid@example.com"
        "user.name@example.com"
        "user+tag@example.co.uk"
        "invalid.email"
        "@invalid.com"
        "invalid@"
        "invalid..double.dot@example.com"
        "too.long.string.here.to.test.length.validation.purpose@example.com"
        "a@b.co"
    )
    
    echo "Testing email validation:"
    for email in "${emails[@]}"; do
        if validate_email "$email"; then
            echo "✓ '$email' is valid"
        else
            echo "✗ '$email' is invalid"
        fi
    done
}

# Uncomment the line below to run tests when this script is executed directly
# test_email_validation
