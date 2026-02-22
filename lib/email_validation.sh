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

    # Check for consecutive dots
    if [[ "$email" == *..* ]]; then
        return 1
    fi

    # Check for starting or ending dots in the email
    if [[ "$email" == .* ]] || [[ "$email" == *. ]]; then
        return 1
    fi

    # Check for starting hyphen in domain part (after @)
    if [[ "$email" =~ @- ]]; then
        return 1
    fi

    # Check for hyphen at the end of domain label (right before the TLD dot)
    # e.g., domain-.com is invalid, but example-one.com is valid
    local domain="${email##*@}"
    local domain_label=$(echo "$domain" | rev | cut -d'.' -f2 | rev)
    if [[ "$domain_label" == *- ]]; then
        return 1
    fi

    # Check for trailing dot in local part (before @)
    if [[ "$email" == *.@* ]]; then
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
