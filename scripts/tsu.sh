#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${HOME}/.tailscale-userspace"
RUN_DIR="${BASE_DIR}/run"
LOG_DIR="${BASE_DIR}/log"
STATE_DIR="${BASE_DIR}/state"

SOCK="${RUN_DIR}/tailscaled.sock"
STATE="${STATE_DIR}/tailscaled.state"
LOG="${LOG_DIR}/tailscaled.log"
PIDFILE="${RUN_DIR}/tailscaled.pid"
WATCHDOG_PIDFILE="${RUN_DIR}/watchdog.pid"
TMUX_SESSION="tailscale-u"

TAILSCALED_BIN="$(command -v tailscaled || true)"
TAILSCALE_BIN="$(command -v tailscale || true)"
TMUX_BIN="$(command -v tmux || true)"

mkdir -p "${RUN_DIR}" "${LOG_DIR}" "${STATE_DIR}"
chmod 700 "${BASE_DIR}" "${RUN_DIR}" "${LOG_DIR}" "${STATE_DIR}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_bins() {
  [[ -n "${TAILSCALED_BIN}" ]] || die "tailscaled not found in PATH"
  [[ -n "${TAILSCALE_BIN}" ]] || die "tailscale not found in PATH"
}

pid_alive() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

pid_cmd_contains() {
  local pid="${1:-}"
  local needle="${2:-}"
  [[ -n "${pid}" && -n "${needle}" ]] || return 1
  ps -p "${pid}" -o command= 2>/dev/null | grep -Fq "${needle}"
}

stop_pid_gracefully() {
  local pid="${1:-}"
  local wait_steps="${2:-20}"
  local i

  [[ -n "${pid}" ]] || return 1

  kill "${pid}" 2>/dev/null || true

  for ((i = 0; i < wait_steps; i++)); do
    if pid_alive "${pid}"; then
      sleep 0.5
    else
      return 0
    fi
  done

  if pid_alive "${pid}"; then
    kill -9 "${pid}" 2>/dev/null || true
    sleep 0.1
  fi

  ! pid_alive "${pid}"
}

list_tailscaled_pids() {
  pgrep -x tailscaled 2>/dev/null || true
}

cleanup_conflicting_tailscaled() {
  local managed_pid
  local pid
  local conflicts=()

  managed_pid="$(read_pidfile "${PIDFILE}" 2>/dev/null || true)"

  while IFS= read -r pid; do
    [[ -n "${pid}" ]] || continue
    [[ "${pid}" == "${managed_pid}" ]] && continue
    conflicts+=("${pid}")
  done < <(list_tailscaled_pids)

  if (( ${#conflicts[@]} == 0 )); then
    return 0
  fi

  echo "found existing tailscaled process(es): ${conflicts[*]}"
  echo "stopping existing tailscaled process(es) before start..."
  for pid in "${conflicts[@]}"; do
    if stop_pid_gracefully "${pid}" 20; then
      echo "stopped tailscaled pid=${pid}"
    else
      die "failed to stop existing tailscaled pid=${pid}; stop it manually and retry"
    fi
  done
}

read_pidfile() {
  local f="$1"
  [[ -f "${f}" ]] || return 1
  cat "${f}"
}

is_running() {
  local pid
  pid="$(read_pidfile "${PIDFILE}" 2>/dev/null || true)"
  pid_alive "${pid}" && pid_cmd_contains "${pid}" "tailscaled"
}

is_watchdog_running() {
  local pid
  pid="$(read_pidfile "${WATCHDOG_PIDFILE}" 2>/dev/null || true)"
  pid_alive "${pid}" && pid_cmd_contains "${pid}" "watchdog-loop"
}

wait_socket() {
  local n=0
  while (( n < 40 )); do
    [[ -S "${SOCK}" ]] && return 0
    sleep 0.25
    n=$((n + 1))
  done
  return 1
}

cli() {
  "${TAILSCALE_BIN}" --socket="${SOCK}" "$@"
}

start_plain() {
  need_bins

  if is_running; then
    echo "tailscaled already running: pid=$(cat "${PIDFILE}")"
    return 0
  fi

  cleanup_conflicting_tailscaled

  rm -f "${SOCK}"

  nohup "${TAILSCALED_BIN}" \
    --tun=userspace-networking \
    --socks5-server=127.0.0.1:1055 \
    --statedir="${STATE_DIR}" \
    --state="${STATE}" \
    --socket="${SOCK}" \
    --port=41641 \
    >> "${LOG}" 2>&1 &

  local pid=$!
  echo "${pid}" > "${PIDFILE}"

  if wait_socket && pid_alive "${pid}"; then
    echo "started tailscaled (plain): pid=${pid}"
    echo "SOCKS5 proxy: 127.0.0.1:1055"
    return 0
  fi

  echo "failed to start tailscaled; tail log below:"
  tail -n 50 "${LOG}" || true
  exit 1
}

start_tmux() {
  need_bins
  [[ -n "${TMUX_BIN}" ]] || die "tmux not found in PATH"

  if is_running; then
    echo "tailscaled already running: pid=$(cat "${PIDFILE}")"
    return 0
  fi

  cleanup_conflicting_tailscaled

  rm -f "${SOCK}"

  if ! tmux has-session -t "${TMUX_SESSION}" 2>/dev/null; then
    tmux new-session -d -s "${TMUX_SESSION}" \
      "bash -lc '
        mkdir -p \"${RUN_DIR}\" \"${LOG_DIR}\" \"${STATE_DIR}\";
        echo \$\$ > \"${PIDFILE}\";
        exec \"${TAILSCALED_BIN}\" \
          --tun=userspace-networking \
          --socks5-server=127.0.0.1:1055 \
          --statedir=\"${STATE_DIR}\" \
          --state=\"${STATE}\" \
          --socket=\"${SOCK}\" \
          --port=41641 >> \"${LOG}\" 2>&1
      '"
  else
    die "tmux session ${TMUX_SESSION} already exists but pidfile/socket state is inconsistent"
  fi

  if wait_socket && is_running; then
    echo "started tailscaled in tmux session: ${TMUX_SESSION}"
    echo "SOCKS5 proxy: 127.0.0.1:1055"
    return 0
  fi

  echo "failed to start tailscaled in tmux; tail log below:"
  tail -n 50 "${LOG}" || true
  exit 1
}

stop() {
  if [[ "${TSU_SKIP_WATCHDOG_STOP:-0}" != "1" ]] && is_watchdog_running; then
    stop_watchdog
  fi

  if is_running; then
    local pid
    pid="$(cat "${PIDFILE}")"
    stop_pid_gracefully "${pid}" 20 || true
  fi

  if [[ -n "${TMUX_BIN}" ]] && tmux has-session -t "${TMUX_SESSION}" 2>/dev/null; then
    tmux kill-session -t "${TMUX_SESSION}" || true
  fi

  rm -f "${PIDFILE}" "${SOCK}"
  echo "stopped tailscaled"
}

restart() {
  stop || true
  start
}

status() {
  if is_running; then
    echo "tailscaled: running pid=$(cat "${PIDFILE}")"
  else
    echo "tailscaled: not running"
  fi

  if [[ -n "${TMUX_BIN}" ]] && tmux has-session -t "${TMUX_SESSION}" 2>/dev/null; then
    echo "tmux: session ${TMUX_SESSION} exists"
  else
    echo "tmux: no session"
  fi

  if is_watchdog_running; then
    echo "watchdog: running pid=$(cat "${WATCHDOG_PIDFILE}")"
  else
    echo "watchdog: not running"
  fi

  echo
  cli status || true

  echo
  echo "SOCKS5 proxy: 127.0.0.1:1055 (if running)"
  echo "To use with SSH: add ProxyCommand to ~/.ssh/config"
  echo "To use with curl/git: export ALL_PROXY=socks5://127.0.0.1:1055"
}

up() {
  # Check for duplicate device names
  local self_name
  self_name="$(hostname -s 2>/dev/null || echo "")"

  if [[ -n "${self_name}" ]]; then
    local existing
    existing="$(cli status 2>/dev/null | awk -v name="$self_name" '$2 == name && !/^-/ {print $1}')"
    if [[ -n "${existing}" ]]; then
      echo "WARNING: Device name '${self_name}' already exists in tailnet:"
      echo "  ${existing} (${self_name})"
      echo ""
      echo "This may cause confusion. Consider using --hostname to set a unique name:"
      echo "  tsu up --hostname=${self_name}-2"
      echo ""
    fi
  fi

  cli up "$@"
}

down() {
  cli down
}

doctor() {
  echo "==== process ===="
  ps aux | grep '[t]ailscaled' || true

  echo
  echo "==== pidfile ===="
  cat "${PIDFILE}" 2>/dev/null || true

  echo
  echo "==== socket ===="
  ls -l "${SOCK}" 2>/dev/null || true

  echo
  echo "==== status ===="
  cli status || true

  echo
  echo "==== netcheck ===="
  cli netcheck || true

  echo
  echo "==== SOCKS5 proxy ===="
  if is_running; then
    echo "SOCKS5 proxy should be running on: 127.0.0.1:1055"
    lsof -i :1055 2>/dev/null || echo "Port 1055 not listening"
  else
    echo "tailscaled not running"
  fi

  echo
  echo "==== SSH config ===="
  if grep -q "ProxyCommand.*1055" ~/.ssh/config 2>/dev/null; then
    echo "✓ SSH ProxyCommand configured for SOCKS5"
    grep -A 2 "Host 100\.\*" ~/.ssh/config 2>/dev/null || true
  else
    echo "✗ SSH ProxyCommand not configured"
    echo "Run: tsu configure-ssh"
  fi

  echo
  echo "==== last log ===="
  tail -n 80 "${LOG}" || true
}

logs() {
  tail -f "${LOG}"
}

attach() {
  [[ -n "${TMUX_BIN}" ]] || die "tmux not found in PATH"
  tmux attach -t "${TMUX_SESSION}"
}

pingcheck() {
  local target="${1:-}"
  [[ -n "${target}" ]] || die "usage: tsu pingcheck <tailnet-ip-or-name>"
  cli ping -c 1 "${target}"
}

watchdog_loop() {
  local target="${1:-}"
  local interval="${2:-60}"
  local fail_max="${3:-3}"

  [[ -n "${target}" ]] || die "usage: tsu watchdog-loop <target> [interval] [fail_max]"

  local fails=0
  while true; do
    # Check if target is online before pinging
    if ! is_peer_online "${target}"; then
      echo "$(date '+%F %T') target ${target} offline, skipping ping" >> "${LOG_DIR}/watchdog.log"
      sleep "${interval}"
      continue
    fi

    if pingcheck "${target}" >/dev/null 2>&1; then
      fails=0
    else
      fails=$((fails + 1))
      echo "$(date '+%F %T') ping failed ${fails}/${fail_max}" >> "${LOG_DIR}/watchdog.log"

      if (( fails >= fail_max )); then
        echo "$(date '+%F %T') restarting tailscaled" >> "${LOG_DIR}/watchdog.log"
        TSU_SKIP_WATCHDOG_STOP=1 restart >> "${LOG_DIR}/watchdog.log" 2>&1 || true
        sleep 5
        fails=0
      fi
    fi
    sleep "${interval}"
  done
}

start_watchdog() {
  local target="${1:-}"
  local interval="${2:-60}"
  local fail_max="${3:-3}"

  [[ -n "${target}" ]] || die "usage: tsu watchdog-start <target> [interval] [fail_max]"

  if is_watchdog_running; then
    echo "watchdog already running: pid=$(cat "${WATCHDOG_PIDFILE}")"
    return 0
  fi

  nohup "$0" watchdog-loop "${target}" "${interval}" "${fail_max}" \
    >> "${LOG_DIR}/watchdog.log" 2>&1 &
  echo $! > "${WATCHDOG_PIDFILE}"

  echo "watchdog started: pid=$(cat "${WATCHDOG_PIDFILE}") target=${target}"
}

start_watchdog_auto() {
  local interval="${1:-60}"
  local fail_max="${2:-3}"

  local target
  target="$(get_first_online_peer)"

  if [[ -z "${target}" ]]; then
    echo "ERROR: No online peers found"
    echo "Available peers:"
    cli status | awk 'NR>1 && !/^-/ {print "  " $2 " (" $1 ") " ($0 ~ /offline/ ? "[offline]" : "")}'
    return 1
  fi

  echo "Auto-selected target: ${target}"
  start_watchdog "${target}" "${interval}" "${fail_max}"
}

stop_watchdog() {
  if ! is_watchdog_running; then
    rm -f "${WATCHDOG_PIDFILE}"
    echo "watchdog not running"
    return 0
  fi

  local pid
  pid="$(cat "${WATCHDOG_PIDFILE}")"
  stop_pid_gracefully "${pid}" 10 || true

  rm -f "${WATCHDOG_PIDFILE}"
  echo "watchdog stopped"
}

configure_ssh() {
  local ssh_config="${HOME}/.ssh/config"
  local proxy_config="Host 100.* *.ts.net
    ProxyCommand ncat --proxy 127.0.0.1:1055 --proxy-type socks5 %h %p"

  # Check if ncat is installed
  if ! command -v ncat >/dev/null 2>&1; then
    echo "ERROR: ncat not found. Install with: brew install nmap"
    return 1
  fi

  # Create .ssh directory if it doesn't exist
  mkdir -p "${HOME}/.ssh"
  chmod 700 "${HOME}/.ssh"

  # Check if already configured
  if grep -q "ProxyCommand.*127.0.0.1:1055" "${ssh_config}" 2>/dev/null; then
    echo "SSH ProxyCommand already configured in ${ssh_config}"
    return 0
  fi

  # Append configuration
  echo "" >> "${ssh_config}"
  echo "# Tailscale userspace SOCKS5 proxy" >> "${ssh_config}"
  echo "${proxy_config}" >> "${ssh_config}"

  echo "✓ SSH ProxyCommand configured"
  echo "Added to ${ssh_config}:"
  echo ""
  echo "${proxy_config}"
  echo ""
  echo "Now you can use:"
  echo "  ssh user@100.112.203.89"
  echo "  ssh macmini"
}

# ========================================
# Helper functions
# ========================================

# Extract first https URL from text
extract_https_url() {
  local text="${1:-}"
  printf '%s\n' "${text}" \
    | grep -Eo 'https://[^[:space:]]+' \
    | head -1 \
    | sed 's/[),.;]*$//'
}

# Best-effort DNSName (from tailscale status --json)
get_dns_name() {
  cli status --json 2>/dev/null \
    | sed -n 's/.*"DNSName":"\([^"]*\)".*/\1/p' \
    | head -1 \
    | sed 's/\.$//'
}

# Get self hostname from tailscale status
get_self_name() {
  cli status | awk '/^-/ {print $2}'
}

# Get online peer names (exclude self and offline)
get_online_peers() {
  cli status | awk 'NR>1 && !/offline/ && !/^-/ {print $2}'
}

# Get first online peer IP
get_first_online_peer() {
  cli status | awk 'NR>1 && !/offline/ && !/^-/ {print $1; exit}'
}

# Check if a peer is online
is_peer_online() {
  local target="${1:-}"
  [[ -z "${target}" ]] && return 1
  cli status | awk -v t="$target" '($1 == t || $2 == t) && !/offline/ {found=1; exit} END {exit !found}'
}

# Get Docker exposed ports
get_docker_ports() {
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi
  docker ps --format '{{.Ports}}' 2>/dev/null | grep -oE '0\.0\.0\.0:[0-9]+' | cut -d: -f2 | sort -nu
}

# ========================================
# Serve commands
# ========================================

serve_list() {
  if ! is_running; then
    echo "ERROR: tailscaled not running"
    return 1
  fi
  echo "Current serve configuration:"
  echo
  cli serve status 2>&1 || echo "No serve config"
}

serve_clear() {
  if ! is_running; then
    echo "ERROR: tailscaled not running"
    return 1
  fi
  cli serve reset
  cli funnel reset >/dev/null 2>&1 || true
  echo "✓ All serve/funnel configurations cleared"
}

serve_add() {
  local port="${1:-}"
  [[ -n "${port}" ]] || die "usage: tsu serve add <port>"

  if ! is_running; then
    echo "ERROR: tailscaled not running"
    echo "Run: tsu start"
    return 1
  fi

  echo "Adding TCP forward for port ${port}..."
  cli serve --tcp:"${port}" tcp://localhost:"${port}" --bg 2>&1

  local my_ip
  my_ip="$(cli status | grep -o '100\.[0-9.]*' | head -1)"
  echo ""
  echo "✓ Port ${port} exposed via tailscale serve"
  echo "Access: tcp://${my_ip}:${port}"
}

serve_public() {
  local port="${1:-}"
  local suffix="${2:-}"
  [[ -n "${port}" ]] || die "usage: tsu serve public <port> [path]"

  if ! is_running; then
    echo "ERROR: tailscaled not running"
    echo "Run: tsu start"
    return 1
  fi

  echo "Enabling public funnel for localhost:${port} ..."
  local out
  if ! out="$(cli funnel --yes --bg "${port}" 2>&1)"; then
    echo "${out}" >&2
    return 1
  fi

  local url
  url="$(extract_https_url "${out}")"
  if [[ -z "${url}" ]]; then
    local status_out
    status_out="$(cli funnel status 2>&1 || true)"
    url="$(extract_https_url "${status_out}")"
  fi
  if [[ -z "${url}" ]]; then
    local dns_name
    dns_name="$(get_dns_name)"
    if [[ -n "${dns_name}" ]]; then
      url="https://${dns_name}"
    fi
  fi

  if [[ -n "${suffix}" ]]; then
    suffix="/${suffix#/}"
    url="${url%/}${suffix}"
  fi

  echo "✓ Public funnel enabled for port ${port}"
  if [[ -n "${url}" ]]; then
    echo "Public URL: ${url}"
    echo "Tip: use 'tsu serve list' or 'tsu funnel status' in userspace mode."
    echo "Tip: plain 'tailscale funnel status' may hit /var/run/tailscaled.socket."
  else
    echo "Public URL: <unable to auto-detect>"
    echo "Run: tsu serve list"
    return 2
  fi
}

serve_webhook() {
  local port="${1:-}"
  [[ -n "${port}" ]] || die "usage: tsu serve webhook <port>"
  serve_public "${port}" "/webhook/github"
}

serve_rm() {
  local port="${1:-}"
  [[ -n "${port}" ]] || die "usage: tsu serve rm <port>"

  if ! is_running; then
    echo "ERROR: tailscaled not running"
    return 1
  fi

  cli serve --tcp:"${port}" clear 2>&1 || true
  echo "✓ Port ${port} removed from serve config"
}

serve_ssh() {
  if ! is_running; then
    echo "ERROR: tailscaled not running"
    echo "Run: tsu start"
    return 1
  fi

  echo "Exposing SSH (port 22) via tailscale serve..."
  cli serve --tcp:22 tcp://localhost:22 --bg 2>&1

  local my_ip
  my_ip="$(cli status | grep -o '100\.[0-9.]*' | head -1)"
  echo ""
  echo "✓ SSH exposed via tailscale serve"
  echo "Access: ssh user@${my_ip}"
}

serve_docker() {
  if ! is_running; then
    echo "ERROR: tailscaled not running"
    echo "Run: tsu start"
    return 1
  fi

  local ports
  ports="$(get_docker_ports)"

  if [[ -z "${ports}" ]]; then
    echo "No Docker ports found (or Docker not running)"
    return 0
  fi

  echo "Detected Docker ports: ${ports}"
  echo ""

  local my_ip count=0
  my_ip="$(cli status | grep -o '100\.[0-9.]*' | head -1)"

  for port in ${ports}; do
    echo "Exposing port ${port}..."
    if cli serve --tcp:"${port}" tcp://localhost:"${port}" --bg 2>&1; then
      echo "  → tcp://${my_ip}:${port}"
      ((count++))
    fi
  done

  echo ""
  echo "✓ Exposed ${count} Docker port(s)"
}

serve_cmd() {
  local subcmd="${1:-}"
  shift || true

  case "${subcmd}" in
    list)   serve_list ;;
    clear)  serve_clear ;;
    add)    serve_add "$@" ;;
    public) serve_public "$@" ;;
    webhook) serve_webhook "$@" ;;
    rm)     serve_rm "$@" ;;
    ssh)    serve_ssh ;;
    docker) serve_docker ;;
    *)      echo "usage: tsu serve {list|clear|add|public|webhook|rm|ssh|docker}" ;;
  esac
}

funnel_cmd() {
  local subcmd="${1:-status}"
  shift || true

  case "${subcmd}" in
    status) cli funnel status "$@" ;;
    reset)  cli funnel reset "$@" ;;
    *)      echo "usage: tsu funnel {status|reset}" ;;
  esac
}

show_env() {
  echo "========================================="
  echo "  Environment Variables for SOCKS5"
  echo "========================================="
  echo ""
  echo "To access tailnet with curl/git/pip:"
  echo ""
  echo "  export ALL_PROXY=socks5://127.0.0.1:1055"
  echo ""
  echo "Or for specific commands:"
  echo ""
  echo "  ALL_PROXY=socks5://127.0.0.1:1055 curl http://100.x.x.x:8080"
  echo "  ALL_PROXY=socks5://127.0.0.1:1055 git clone ..."
  echo ""
  echo "For proxychains (optional):"
  echo "  brew install proxychains-ng"
  echo "  echo 'socks5 127.0.0.1 1055' >> ~/.proxychains/proxychains.conf"
  echo "  proxychains4 ssh 100.112.203.89"
  echo ""
}

start() {
  if [[ "${1:-}" == "--plain" ]]; then
    shift
    start_plain "$@"
  else
    start_tmux "$@"
  fi
}

show_server_guide() {
  cat <<EOF
========================================
  服务器端快速启动指南
========================================

【场景】你想从其他机器 SSH 到这台机器

【步骤】
1. 启动 tailscaled
   tsu start

2. 登录 tailscale
   tsu up

3. 查看状态
   tsu status

4. 可选：暴露本地服务
   tsu serve ssh       # 暴露 SSH
   tsu serve docker    # 暴露 Docker 端口
   tsu serve add 4000  # 暴露指定端口
   tsu serve public 8080           # 直接得到公网 URL
   tsu serve webhook 8080          # 直接得到 webhook 公网 URL

5. 可选：启用 watchdog（自动选择目标）
   tsu watchdog-auto 60 3

【说明】
- ✅ 不需要配置 SSH ProxyCommand
- ✅ 确保 SSH server 已启动
- ✅ SOCKS5 proxy 自动启用 (127.0.0.1:1055)

【诊断】
tsu doctor

========================================
EOF
}

show_client_guide() {
  cat <<EOF
========================================
  客户端快速启动指南
========================================

【场景】你想 SSH 到其他机器

【步骤】
1. 安装依赖
   brew install nmap

2. 启动 tailscaled
   tsu start

3. 登录 tailscale
   tsu up

4. 配置 SSH（只需一次）
   tsu configure-ssh

5. 测试连接
   ssh user@100.112.203.89

6. 可选：启用 watchdog（自动选择目标）
   tsu watchdog-auto 60 3

【说明】
- ✅ 必须配置 SSH ProxyCommand
- ✅ 必须安装 nmap/ncat
- ✅ SOCKS5 proxy 自动启用 (127.0.0.1:1055)

【访问 tailnet 服务】
export ALL_PROXY=socks5://127.0.0.1:1055
curl http://100.112.203.89:4000

【诊断】
tsu doctor

========================================
EOF
}

usage() {
  cat <<EOF
usage:
  tsu start [--plain]          [server, client] 启动 tailscaled (默认 tmux 模式)
  tsu stop                     [server, client] 停止 tailscaled 和 watchdog
  tsu restart                  [server, client] 重启 tailscaled
  tsu status                   [server, client] 查看状态
  tsu up [args...]             [server, client] 登录 tailscale
  tsu down                     [server, client] 登出 tailscale
  tsu logs                     [server, client] 查看日志
  tsu doctor                   [server, client] 诊断问题

  tsu configure-ssh            [client] 配置 SSH ProxyCommand
  tsu env                      [client] 显示 SOCKS5 环境变量用法

  tsu serve list               [server] 列出当前转发
  tsu serve clear              [server] 清除所有转发（含 funnel）
  tsu serve ssh                [server] 转发 SSH (22)
  tsu serve docker             [server] 自动检测并转发 Docker 端口
  tsu serve add <port>         [server] 添加端口转发
  tsu serve public <port> [path] [server] 打开公网 funnel 并回显 URL
  tsu serve webhook <port>     [server] 输出 webhook 公网地址（.../webhook/github）
  tsu serve rm <port>          [server] 移除端口转发
  tsu funnel status            [server, client] 查看 funnel 状态（userspace socket）
  tsu funnel reset             [server, client] 清空 funnel 配置（userspace socket）

  tsu attach                   [server, client] 进入 tmux 会话
  tsu pingcheck <target>       [server, client] 测试连接
  tsu watchdog-start <target> [interval] [fail_max]  [server, client] 启用自愈
  tsu watchdog-auto [interval] [fail_max]            [server, client] 自动选择目标并启用自愈
  tsu watchdog-stop            [server, client] 停止 watchdog

  tsu server                   显示服务器端快速启动指南
  tsu client                   显示客户端快速启动指南

SOCKS5 proxy: 127.0.0.1:1055 (自动启用)
EOF
}

cmd="${1:-}"
shift || true

case "${cmd}" in
  start) start "$@" ;;
  stop) stop ;;
  restart) restart ;;
  status) status ;;
  up) up "$@" ;;
  down) down ;;
  doctor) doctor ;;
  logs) logs ;;
  attach) attach ;;
  pingcheck) pingcheck "$@" ;;
  watchdog-start) start_watchdog "$@" ;;
  watchdog-auto) start_watchdog_auto "$@" ;;
  watchdog-stop) stop_watchdog ;;
  watchdog-loop) watchdog_loop "$@" ;;
  configure-ssh) configure_ssh ;;
  env) show_env ;;
  serve) serve_cmd "$@" ;;
  funnel) funnel_cmd "$@" ;;
  serve-setup) serve_add "$@" ;;  # backward compatibility
  server) show_server_guide ;;
  client) show_client_guide ;;
  *) usage; exit 1 ;;
esac
