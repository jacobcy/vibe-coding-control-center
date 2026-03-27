#!/usr/bin/env zsh
# lib/alias.sh - Alias inspector for Vibe 2.0

_vibe_alias_list() {
    local show_all=0
    local filter_target=""
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -a|--all) show_all=1 ;;
            *) filter_target="$1" ;;
        esac
        shift
    done

    local src_dir="${VIBE_ROOT}/alias"
    echo "${BOLD}Vibe Alias Gallery${NC}"
    if [[ $show_all -eq 0 && -z "$filter_target" ]]; then
        echo "💡 Showing ${CYAN}featured${NC} aliases. Use ${YELLOW}vibe alias -a${NC} for all."
        echo "🚀 To load into current shell: ${BOLD}source \$(vibe alias --load)${NC}"
    else
        echo "🚀 To load into current shell: ${BOLD}source \$(vibe alias --load)${NC}"
    fi
    echo ""

    if [[ ! -d "$src_dir" ]]; then
        log_error "No alias directory found: $src_dir"
        return 1
    fi

    local f_base f category tu=""
    [[ -n "$filter_target" ]] && tu=${filter_target:u}

    for f_base in git.sh vibe.sh openspec.sh agent.sh worktree.sh tmux.sh; do
        f="$src_dir/$f_base"
        [[ -f "$f" ]] || continue
        
        category=$(basename "$f" .sh | tr '[:lower:]' '[:upper:]')
        if [[ -n "$tu" ]]; then
            [[ "$category" == "$tu"* ]] || continue
        fi

        local d="" header_printed=0 is_featured=0
        while IFS= read -r line; do
            if [[ "$line" == "# @desc "* ]]; then
                d="${line#\# @desc }"
            elif [[ "$line" == "# @featured"* ]]; then
                is_featured=1
            elif [[ "$line" == "alias "* ]]; then
                local n="${line%%=*}"; n="${n#alias }"
                local c="${line#*=}"; c="${c//\'/}"; c="${c//\"/}"
                
                if [[ $show_all -eq 1 || $is_featured -eq 1 || ( $header_printed -eq 1 && $show_all -eq 1 ) || -n "$filter_target" ]]; then
                    if [[ $header_printed -eq 0 ]]; then
                        echo "${BLUE}● $category${NC}"
                        header_printed=1
                    fi
                    printf "  - \033[1;36m%-12s\033[0m # %-35s \033[2m[%s]\033[0m\n" "$n" "$d" "$c"
                fi
                d=""
                is_featured=0
            elif [[ "$line" == *'()'* ]]; then
                local n="${line%%\(\)*}"
                if [[ "$n" =~ ^[a-z0-9_]+$ ]]; then
                    if [[ $show_all -eq 1 || $is_featured -eq 1 || ( $header_printed -eq 1 && $show_all -eq 1 ) || -n "$filter_target" ]]; then
                        if [[ $header_printed -eq 0 ]]; then
                            echo "${BLUE}● $category${NC}"
                            header_printed=1
                        fi
                        printf "  - \033[1;36m%-12s\033[0m # %-35s \033[2m(function)\033[0m\n" "$n" "$d"
                    fi
                    d=""
                    is_featured=0
                fi
            elif [[ -n "$line" && "$line" != "#"* ]]; then
                d=""
                is_featured=0
            fi
        done < "$f"
        (( header_printed )) && echo ""
    done
}

vibe_alias() {
    case "${1:-}" in
        --load)
            echo "${VIBE_ROOT}/lib/alias/loader.sh"
            ;;
        -h|--help)
            echo "${BOLD}Vibe Alias Manager${NC}"
            echo ""
            echo "Usage: ${CYAN}vibe alias${NC} [group] [-a|--all]"
            echo "       ${CYAN}vibe alias --load${NC}"
            echo ""
            echo "Subcommands/Flags:"
            echo "  ${GREEN}<group>${NC}     过滤显示指定分组的别名 (git, vibe, openspec, opencode, claude, worktree, tmux)"
            echo "  ${GREEN}-a, --all${NC}   显示该分组或所有分组下的全部别名"
            echo "  ${GREEN}--load${NC}      输出 source 命令所需的路径配置"
            echo ""
            echo "🚀 ${BOLD}How to Load Aliases into current shell:${NC}"
            echo "  由于 Alias 无法在子进程中直接加载，请执行以下命令："
            echo "  ${CYAN}source \$(vibe alias --load)${NC}"
            echo ""
            echo "Examples:"
            echo "  vibe alias              # 显示重点常用别名 (Featured)"
            echo "  vibe alias -a           # 显示所有分组的全部别名"
            echo "  vibe alias worktree     # 显示 worktree 分组的所有别名"
            echo ""
            ;;
        *)
            _vibe_alias_list "$@"
            ;;
    esac
}
