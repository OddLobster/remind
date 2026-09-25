#!/usr/bin/env python3
"""remind - short, runnable examples for common Linux commands.

Examples are filled with real values from where you are: files in the
current directory, your user and group, listening ports, git branch, ...
Destructive examples always use <placeholders> so copy-paste is safe.
"""
import getpass
import grp
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from functools import cache
from pathlib import Path

MODEL = os.environ.get("REMIND_MODEL", "deepseek/deepseek-v4.1-flash")
USER_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "remind" / "templates.json"

# Each line: "command  # comment". {name} is filled from CONTEXT below.
TEMPLATES = {
    # --- files & permissions ---
    "chown": r"""
chown {user} {file}  # change owner
chown {user}:{group} {file}  # change owner and group
chown :{group} {file}  # change only the group
chown -R {user}:{group} {dir}  # recursive, whole directory
chown --reference={file2} {file}  # copy owner from another file
""",
    "chmod": r"""
chmod +x {script}  # make executable
chmod 644 {file}  # rw-r--r--  normal file
chmod 755 {dir}  # rwxr-xr-x  directories, scripts
chmod 600 ~/.ssh/id_ed25519  # rw-------  private, owner only
chmod u+w,g-w,o-rwx {file}  # symbolic: u=user g=group o=others
chmod -R g+rX {dir}  # recursive, X = execute only on dirs
""",
    "ln": r"""
ln -s {file} link-name  # symlink: ln -s TARGET LINK_NAME
ln -s "$PWD"/{file} ~/.local/bin/  # link into another dir (use absolute target)
ln -sf {file2} link-name  # replace an existing link
ln {file} hardlink-name  # hard link
readlink -f link-name  # show where a link points
""",
    "cp": r"""
cp {file} {file}.bak  # quick backup
cp -r {dir} {dir}-copy  # copy a directory
cp {file} {file2} {dir}/  # copy several files into a dir
cp -a {dir} /tmp/  # keep permissions, times, links
cp -i {file} {dir}/  # ask before overwriting
""",
    "mv": r"""
mv {file} new-name  # rename
mv {file} {file2} {dir}/  # move several files into a dir
mv -i {file} {dir}/  # ask before overwriting
mv -n {file} {dir}/  # never overwrite
mv {dir} ../  # move a directory one level up
""",
    "rm": r"""
rm <file>  # delete a file
rm -i <file>  # ask first
rm -r <dir>  # delete a directory and its contents
rm -rf <dir>  # no questions asked - careful!
rmdir <dir>  # delete only if empty
""",
    "mkdir": r"""
mkdir newdir  # create a directory
mkdir -p a/b/c  # create parents as needed
mkdir -p project/{src,tests,docs}  # several at once
mkdir -m 700 private  # with permissions
mkdir -p newdir && cd newdir  # create and enter
""",
    "touch": r"""
touch newfile.txt  # create an empty file
touch {file}  # set modified time to now
touch -d '2 days ago' {file}  # set a specific time
touch -r {file2} {file}  # copy timestamp from another file
""",
    "stat": r"""
stat {file}  # everything: size, perms, owner, times
stat -c '%U:%G %a %n' {file}  # owner:group, octal perms, name
stat -c %s {file}  # size in bytes
stat -c %y {file}  # last modified time
""",
    # --- finding & searching ---
    "find": r"""
find . -name '*.{ext}'  # by name pattern
find . -iname '*readme*'  # case-insensitive
find . -type d -name {dir}  # directories only
find . -type f -mtime -1  # modified in the last 24h
find . -type f -size +100M  # bigger than 100MB
find . -name '*.{ext}' -exec grep -l TODO {} +  # run a command on the results
find . -name '*.tmp' -delete  # delete matches (run without -delete first!)
""",
    "grep": r"""
grep -rn 'TODO' .  # recursive, with line numbers
grep -i 'error' {file}  # case-insensitive
grep -v '^#' {file}  # lines NOT matching
grep -rl 'pattern' --include='*.{ext}' .  # only file names, only .{ext} files
grep -E 'foo|bar' {file}  # extended regex, OR
grep -C 3 'pattern' {file}  # 3 lines of context around matches
""",
    "locate": r"""
locate {file}  # find by name (fast, uses a database)
locate -i readme  # case-insensitive
locate -l 10 '*.{ext}'  # limit to 10 results
sudo updatedb  # refresh the database
""",
    "which": r"""
which python3  # path of a command
which -a python3  # all matches in PATH
type ls  # also shows aliases, functions, builtins
command -v docker  # script-friendly: fails if missing
readlink -f "$(which python3)"  # real file behind symlinks
""",
    # --- text processing ---
    "sed": r"""
sed 's/old/new/' {file}  # replace first match per line (prints result)
sed 's/old/new/g' {file}  # replace all matches
sed -i.bak 's/old/new/g' {file}  # edit in place, keep a .bak backup
sed -n '10,20p' {file}  # print lines 10-20
sed '/^$/d' {file}  # drop empty lines
sed 's|/usr/local|/opt|g' {file}  # other delimiter for paths
""",
    "awk": r"""
awk '{print $1}' {file}  # first column (whitespace separated)
awk '{print $NF}' {file}  # last column
awk -F: '{print $1}' /etc/passwd  # custom separator
awk '$3 > 100' {file}  # rows where column 3 > 100
awk '{sum += $2} END {print sum}' {file}  # sum a column
awk 'NR==5' {file}  # only line 5
""",
    "cut": r"""
cut -d: -f1 /etc/passwd  # field 1, ':' separated
cut -d, -f1,3 {file}  # fields 1 and 3 of a CSV
cut -f2- {file}  # field 2 onwards (tab separated)
cut -c1-10 {file}  # first 10 characters of each line
""",
    "sort": r"""
sort {file}  # alphabetical
sort -n {file}  # numeric
sort -rn {file}  # numeric, largest first
sort -t, -k2,2 {file}  # by 2nd column, comma separated
sort -u {file}  # sort and remove duplicates
du -sh * | sort -h  # human sizes (1K, 2M, 3G)
""",
    "uniq": r"""
sort {file} | uniq  # uniq only works on sorted input
sort {file} | uniq -c | sort -rn  # count occurrences, most common first
sort {file} | uniq -d  # only duplicated lines
sort {file} | uniq -u  # only lines that appear once
""",
    "wc": r"""
wc -l {file}  # lines
wc -w {file}  # words
wc -c {file}  # bytes
ls | wc -l  # number of files here
find . -name '*.{ext}' -exec wc -l {} +  # lines per file + total
""",
    "head": r"""
head {file}  # first 10 lines
head -n 20 {file}  # first 20 lines
head -n -5 {file}  # all but the last 5 lines
head -c 100 {file}  # first 100 bytes
""",
    "tail": r"""
tail {file}  # last 10 lines
tail -n 50 {file}  # last 50 lines
tail -f {file}  # follow as it grows (logs)
tail -n +2 {file}  # from line 2 on (skip a header)
""",
    "xargs": r"""
find . -name '*.{ext}' | xargs grep -l TODO  # pass results as arguments
find . -name '*.{ext}' -print0 | xargs -0 wc -l  # safe with spaces in names
find . -maxdepth 1 -name '*.{ext}' | xargs -I{} cp {} {dir}/  # {} = each item
cat urls.txt | xargs -n1 curl -O  # one command per line
cat urls.txt | xargs -P4 -n1 curl -O  # 4 in parallel
""",
    "tr": r"""
tr 'a-z' 'A-Z' < {file}  # uppercase
tr -d '\r' < {file} > fixed.txt  # remove Windows line endings
tr -s ' ' < {file}  # squeeze repeated spaces
echo "$PATH" | tr ':' '\n'  # one PATH entry per line
""",
    "diff": r"""
diff {file} {file2}  # compare two files
diff -u {file} {file2}  # unified format (like git)
diff -y {file} {file2}  # side by side
diff -r {dir} other-dir  # compare directories
diff -rq {dir} other-dir  # only which files differ
""",
    # --- archives ---
    "tar": r"""
tar -czf backup.tar.gz {dir}  # create: c=create z=gzip f=file
tar -xzf {archive}  # extract: x=extract
tar -xzf {archive} -C {dir}  # extract into a directory
tar -tzf {archive}  # list contents: t=list
tar -cJf backup.tar.xz {dir}  # create with xz (smaller)
tar -xf {archive}  # extract, auto-detect compression
""",
    "zip": r"""
zip archive.zip {file} {file2}  # zip some files
zip -r archive.zip {dir}  # zip a directory
zip -r archive.zip {dir} -x '*.git*'  # exclude a pattern
zip -e secret.zip {file}  # password protected
""",
    "unzip": r"""
unzip {zip}  # extract here
unzip {zip} -d {dir}  # extract into a directory
unzip -l {zip}  # list contents
unzip -q {zip}  # quiet
""",
    "gzip": r"""
gzip -k {file}  # compress to .gz, keep the original
gzip -9 -k {file}  # maximum compression
gunzip data.gz  # decompress
zcat app.log.gz | grep error  # read without extracting
gzip -l data.gz  # show compression ratio
""",
    # --- disk ---
    "du": r"""
du -sh {dir}  # total size of a directory
du -sh *  # size of everything here
du -sh * | sort -h  # ... sorted by size
du -h -d 1 .  # one level deep
du -ah {dir} | sort -rh | head -n 10  # 10 biggest items
""",
    "df": r"""
df -h  # free space on all disks
df -h .  # disk that holds the current dir
df -hT  # with filesystem type
df -i  # inodes (can run out before space does)
""",
    "mount": r"""
findmnt  # mounts as a tree
mount | column -t  # mounts as a table
sudo mount /dev/sdb1 /mnt  # mount a partition
sudo mount -o loop image.iso /mnt  # mount an ISO file
sudo umount /mnt  # unmount
""",
    "lsblk": r"""
lsblk  # disks and partitions
lsblk -f  # with filesystems, labels, UUIDs
lsblk -d  # only whole disks
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT  # pick columns
""",
    # --- processes ---
    "ps": r"""
ps aux  # all processes
ps -ef --forest  # as a tree
ps -u {user}  # processes of a user
ps -p {pid} -o pid,ppid,%cpu,%mem,cmd  # details of one process
ps aux --sort=-%mem | head  # top memory users
pgrep -a {proc}  # find by name (better than ps | grep)
""",
    "kill": r"""
kill <pid>  # ask to stop (SIGTERM)
kill -9 <pid>  # force kill (SIGKILL)
kill -HUP <pid>  # reload config (many daemons)
kill %1  # kill background job 1
kill -l  # list signals
""",
    "pkill": r"""
pgrep -a {proc}  # preview what would match
pkill <name>  # kill by name
pkill -f '<pattern>'  # match the full command line
pkill -9 <name>  # force
""",
    "top": r"""
top  # interactive: P=cpu, M=mem, k=kill, q=quit
top -u {user}  # only one user's processes
top -p {pid}  # watch one process
top -o %MEM  # sort by memory
htop  # nicer version, if installed
""",
    "nohup": r"""
nohup ./{script} &  # keep running after logout, output -> nohup.out
nohup ./{script} > out.log 2>&1 &  # own log file
nohup ./{script} > /dev/null 2>&1 &  # discard output
disown %1  # detach an already running job
""",
    "jobs": r"""
./{script} &  # start in background
jobs  # list background jobs
fg %1  # bring job 1 to the foreground
bg %1  # resume a Ctrl+Z-paused job in background
kill %1  # kill job 1
""",
    # --- network ---
    "ss": r"""
ss -tlnp  # listening TCP ports + process
ss -ulnp  # listening UDP ports
ss -tnp  # established connections
ss -tlnp 'sport = :{port}'  # who listens on a port
sudo lsof -i :{port}  # same, with lsof
ss -s  # summary
""",
    "curl": r"""
curl http://localhost:{port}  # test a local server
curl -O https://example.com/file.zip  # save with the remote name
curl -o page.html https://example.com  # save under a name
curl -L https://example.com  # follow redirects
curl -I https://example.com  # headers only
curl -X POST -H 'Content-Type: application/json' -d '{"name":"x"}' https://example.com/api  # POST JSON
""",
    "wget": r"""
wget https://example.com/file.zip  # download
wget -O out.zip https://example.com/file.zip  # save under a name
wget -c https://example.com/big.iso  # resume a broken download
wget -qO- https://example.com  # print to stdout
wget -r -np -k https://example.com/docs/  # mirror a section of a site
""",
    "ping": r"""
ping -c 4 8.8.8.8  # 4 pings, is the internet up?
ping -c 4 google.com  # also tests DNS
ping -c 1 -W 1 192.168.1.1  # one try, 1s timeout
""",
    "ip": r"""
ip -br a  # interfaces and IPs, short
ip a show {iface}  # one interface
ip r  # routes, default gateway
ip neigh  # devices on the local network (ARP)
sudo ip link set {iface} up  # bring an interface up
curl ifconfig.me  # your public IP
""",
    "scp": r"""
scp {file} {host}:~/  # upload
scp {host}:~/remote.txt .  # download
scp -r {dir} {host}:~/  # upload a directory
scp -P 2222 {file} {host}:/tmp/  # custom port (capital P!)
""",
    "rsync": r"""
rsync -av {dir}/ backup/  # copy the CONTENTS of dir (trailing slash!)
rsync -av {dir} backup/  # copy the dir itself into backup/
rsync -avz {dir}/ {host}:~/backup/  # to a server, compressed
rsync -avn --delete {dir}/ backup/  # dry run of a mirror (-n)
rsync -av --delete {dir}/ backup/  # mirror: deletes extras in backup/
rsync -av --exclude='.git' {dir}/ backup/  # exclude a pattern
rsync -avP big.iso {host}:~/  # progress + resumable
""",
    "ssh": r"""
ssh {host}  # connect
ssh -p 2222 user@server  # custom port
ssh -i ~/.ssh/id_ed25519 user@server  # specific key
ssh {host} 'df -h'  # run one command remotely
ssh -L 8080:localhost:80 {host}  # remote port 80 -> localhost:8080
ssh-copy-id {host}  # install your key on the server
""",
    "ssh-keygen": r"""
ssh-keygen -t ed25519 -C 'you@example.com'  # new key pair
ssh-keygen -t ed25519 -f ~/.ssh/id_work  # with a custom file name
ssh-keygen -p -f ~/.ssh/id_ed25519  # change passphrase
ssh-keygen -lf ~/.ssh/id_ed25519.pub  # fingerprint
ssh-keygen -R hostname  # remove from known_hosts (host key changed)
cat ~/.ssh/id_ed25519.pub  # public key to copy somewhere
""",
    # --- system ---
    "systemctl": r"""
systemctl status {service}  # status + last log lines
sudo systemctl restart {service}  # restart (also: start, stop)
sudo systemctl enable --now {service}  # start now and on boot
systemctl list-units --type=service --state=running  # running services
systemctl --failed  # failed units
sudo systemctl daemon-reload  # after editing unit files
""",
    "journalctl": r"""
journalctl -u {service}  # logs of a service
journalctl -u {service} -f  # follow
journalctl -u {service} --since '1 hour ago'  # recent only
journalctl -b -p err  # errors since boot
journalctl -n 50 --no-pager  # last 50 lines
journalctl --disk-usage  # how much space logs use
""",
    "crontab": r"""
crontab -l  # list your jobs
crontab -e  # edit; line format: min hour day month weekday command
0 3 * * * {cwd}/{script}  # (in crontab -e) daily at 03:00
*/15 * * * * {cwd}/{script}  # every 15 minutes
0 9 * * 1-5 {cwd}/{script}  # weekdays at 09:00
@reboot {cwd}/{script}  # at every boot
""",
    "sudo": r"""
sudo !!  # rerun the last command as root
sudo -i  # root shell
sudo -u www-data whoami  # run as another user
sudo -l  # what am I allowed to run?
sudo -e /etc/hosts  # edit a file as root with your editor
echo 'text' | sudo tee -a /etc/hosts  # append to a root-owned file
""",
    "useradd": r"""
sudo useradd -m -s /bin/bash alice  # with home dir and bash
sudo useradd -m -G sudo alice  # ... and in the sudo group
sudo passwd alice  # set password
sudo adduser alice  # Debian/Ubuntu: interactive, friendlier
sudo userdel -r alice  # delete user and home dir
""",
    "usermod": r"""
sudo usermod -aG docker {user}  # add to a group (-a! or you lose the others)
groups {user}  # check groups (log out/in to apply)
sudo usermod -s /bin/zsh {user}  # change login shell
sudo usermod -l newname oldname  # rename a user
sudo usermod -L alice  # lock an account
""",
    "history": r"""
history | tail -n 20  # last 20 (tip: Ctrl+R to search)
history | grep ssh  # search
!123  # rerun command number 123
!!  # rerun the last command
!$  # last argument of the previous command
HISTTIMEFORMAT='%F %T ' history  # with timestamps
""",
    # --- tools ---
    "git": r"""
git status -sb  # short status
git log --oneline --graph -20  # compact history
git diff --staged  # what will be committed
git restore --staged {file}  # unstage a file
git restore <file>  # discard changes in a file
git commit --amend --no-edit  # add staged changes to the last commit
git reset --soft HEAD~1  # undo last commit, keep the changes
git stash && git stash pop  # park changes and bring them back
git switch -c new-branch  # create and switch to a branch
git push -u origin {branch}  # push and set upstream
git log --follow -p -- {file}  # full history of one file
""",
    "docker": r"""
docker ps -a  # all containers (drop -a for running only)
docker images  # local images
docker run -it --rm ubuntu bash  # throwaway interactive container
docker run -d -p 8080:80 --name web nginx  # background, host:container port
docker run --rm -it -v "$PWD":/app -w /app {image} sh  # mount current dir
docker exec -it {container} sh  # shell inside a running container
docker logs -f {container}  # follow logs
docker build -t myapp .  # build image from ./Dockerfile
docker compose up -d  # start compose stack (down to stop)
docker system prune  # remove stopped containers, unused data
""",
    "docker compose": r"""
docker compose up -d  # start in background
docker compose up -d --build  # rebuild images and restart
docker compose ps  # status of services
docker compose logs -f  # follow logs of all services
docker compose exec web sh  # shell inside service 'web'
docker compose down  # stop and remove containers
docker compose down -v  # ... and delete volumes (data!)
""",
    "git remote": r"""
git remote -v  # list remotes with URLs
git remote add upstream https://github.com/user/repo.git  # add a remote
git remote set-url {remote} git@github.com:user/repo.git  # change URL (e.g. https -> ssh)
git remote show {remote}  # details: branches, tracking
git remote rename {remote} new-name  # rename a remote
git remote remove <name>  # remove a remote
git fetch {remote}  # download without merging
""",
    "git stash": r"""
git stash  # park uncommitted changes
git stash -u  # ... including untracked files
git stash push -m 'wip: message'  # with a description
git stash list  # all stashes
git stash show -p stash@{0}  # what's inside a stash
git stash pop  # re-apply the latest and remove it
git stash apply stash@{1}  # re-apply a specific one, keep it
git stash drop <stash@{n}>  # delete a stash
""",
    "git branch": r"""
git branch -a  # all branches, incl. remote
git branch -vv  # with upstream and last commit
git switch -c new-branch  # create and switch
git branch -m new-name  # rename the current branch
git branch --merged  # branches already merged into this one
git branch -d <branch>  # delete a merged branch (-D to force)
git push {remote} --delete <branch>  # delete a remote branch
""",
    "git log": r"""
git log --oneline --graph --all -20  # compact graph of all branches
git log -p -- {file}  # changes to one file
git log --since='2 weeks ago'  # recent commits
git log -S 'text'  # commits that added/removed some text
git log {remote}/{branch}..HEAD  # commits not pushed yet
git shortlog -sn  # number of commits per author
""",
    "jq": r"""
jq . {json}  # pretty print
jq 'keys' {json}  # top-level keys
jq '.name' {json}  # one field
jq -r '.[].name' {json}  # field of every array item, raw strings
jq '.[] | select(.age > 30)' {json}  # filter
jq 'length' {json}  # number of items
jq -c . {json}  # compact, one line
curl -s https://api.github.com/repos/jqlang/jq | jq '.stargazers_count'  # from a pipe
""",
}

ALIASES = {
    "rmdir": "rm", "pgrep": "pkill", "htop": "top", "fg": "jobs", "bg": "jobs",
    "gunzip": "gzip", "zcat": "gzip", "umount": "mount", "lsof": "ss",
    "adduser": "useradd", "userdel": "useradd", "chgrp": "chown",
}


def sh(*cmd):
    """Run a command, return stdout or "" if anything goes wrong."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


@cache
def listing():
    """Non-hidden entries in the current dir, newest first."""
    try:
        paths = [p for p in Path.cwd().iterdir() if not p.name.startswith(".")]
        return sorted(paths, key=lambda p: p.lstat().st_mtime, reverse=True)
    except OSError:
        return []


def files():
    return [p for p in listing() if p.is_file()]


def nth(items, i, default):
    return items[i] if len(items) > i else default


def file_with(suffixes, default):
    return next((p.name for p in files() if p.name.endswith(suffixes)), default)


def ext():
    exts = Counter(p.suffix[1:] for p in files() if p.suffix[1:].isalnum())
    return exts.most_common(1)[0][0] if exts else "txt"


def process():
    for line in sh("ps", "-u", getpass.getuser(), "-o", "pid=,comm=", "--sort=-start_time").splitlines():
        pid, _, name = line.strip().partition(" ")
        if name.strip() != "ps" and int(pid) != os.getpid():
            return pid, name.strip()
    return "1234", "myapp"


def port():
    for line in sh("ss", "-tlnH").splitlines():
        cols = line.split()
        if len(cols) >= 4:
            return cols[3].rsplit(":", 1)[1]
    return "8080"


def service():
    out = sh("systemctl", "list-units", "--type=service", "--state=running", "--no-legend", "--plain")
    names = [line.split()[0].removesuffix(".service") for line in out.splitlines() if line.strip()]
    return next((n for n in ("ssh", "cron", "docker") if n in names), nth(names, 0, "ssh"))


def iface():
    for line in sh("ip", "-br", "link").splitlines():
        name = line.split()[0].split("@")[0]
        if name != "lo":
            return name
    return "eth0"


def ssh_host():
    try:
        for line in (Path.home() / ".ssh" / "config").read_text().splitlines():
            parts = line.split()
            if len(parts) > 1 and parts[0].lower() == "host":
                host = next((h for h in parts[1:] if "*" not in h and "?" not in h), None)
                if host:
                    return host
    except OSError:
        pass
    return "user@server"


def git_branch():
    branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD").strip()
    return branch if branch and branch != "HEAD" else "main"


def git_remote():
    remotes = sh("git", "remote").split()
    return "origin" if "origin" in remotes else nth(remotes, 0, "origin")


def docker_first(what, fmt, default):
    names = [n for n in sh("docker", what, "--format", fmt).split() if "<none>" not in n]
    return nth(names, 0, default)


# Placeholder -> function returning a value. Only called when a template needs it.
CONTEXT = {
    "file": lambda: nth(files(), 0, Path("file.txt")).name,
    "file2": lambda: nth(files(), 1, Path("other.txt")).name,
    "dir": lambda: nth([p for p in listing() if p.is_dir()], 0, Path("somedir")).name,
    "script": lambda: file_with((".sh", ".py"), "script.sh"),
    "archive": lambda: file_with((".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar"), "archive.tar.gz"),
    "zip": lambda: file_with((".zip",), "archive.zip"),
    "json": lambda: file_with((".json",), "data.json"),
    "ext": ext,
    "cwd": os.getcwd,
    "user": getpass.getuser,
    "group": lambda: grp.getgrgid(os.getgid()).gr_name,
    "pid": lambda: process()[0],
    "proc": lambda: process()[1],
    "port": port,
    "service": service,
    "iface": iface,
    "host": ssh_host,
    "branch": git_branch,
    "remote": git_remote,
    "container": lambda: docker_first("ps", "{{.Names}}", "mycontainer"),
    "image": lambda: docker_first("images", "{{.Repository}}:{{.Tag}}", "ubuntu"),
}

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def examples(command):
    lines = [line.partition(" # ") for line in TEMPLATES[command].strip().splitlines()]
    needed = {m for cmd, _, _ in lines for m in PLACEHOLDER.findall(cmd) if m in CONTEXT}
    values = {name: shlex.quote(CONTEXT[name]()) for name in needed}

    def fill(cmd):
        return PLACEHOLDER.sub(lambda m: values.get(m[1], m[0]), cmd.strip())

    return [(fill(cmd), note.strip()) for cmd, _, note in lines]


def show(command):
    rows = examples(command)
    width = min(max(len(cmd) for cmd, _ in rows), 55)
    dim, reset = ("\033[2m", "\033[0m") if sys.stdout.isatty() else ("", "")
    for cmd, note in rows:
        print(f"  {cmd.ljust(width)}  {dim}# {note}{reset}")


def load_user_templates():
    """Your own reminders (added with --add), stored as {"cmd": ["line", ...]}."""
    try:
        return json.loads(USER_FILE.read_text())
    except FileNotFoundError:
        return {}


def ask_llm(command):
    """Ask the model on OpenRouter for template lines for a command."""
    placeholders = ", ".join("{" + name + "}" for name in CONTEXT)
    prompt = f"""Write 4-6 short, practical examples for the Linux command `{command}`.
Focus on the most common uses and the syntax people usually forget.

Output ONLY lines in this exact format, nothing else, no markdown:
command  # short comment

You may use these placeholders, they get replaced with real values from the user's machine:
{placeholders}
(file/file2 = files in current dir, dir = subdirectory, script = .sh/.py file, ext = common file
extension, proc/pid = a running process, host = ssh host, cwd = current directory)
Destructive examples (deleting, killing, overwriting) must NOT use placeholders;
use <angle-bracket> names like <file> instead.

Example for `tar`:
{TEMPLATES["tar"].strip()}"""

    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        text = json.load(response)["choices"][0]["message"]["content"]
    lines = [line.strip().strip("`") for line in text.splitlines()]
    return [line for line in lines if " # " in line and not line.startswith("#")]


def add(command):
    if command in TEMPLATES:
        print(f"'{command}' already has a reminder", file=sys.stderr)
        return 1
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("set OPENROUTER_API_KEY first", file=sys.stderr)
        return 1

    print(f"asking {MODEL} ...", file=sys.stderr)
    try:
        lines = ask_llm(command)
    except urllib.error.HTTPError as e:
        print(f"OpenRouter error {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
        print(f"request failed: {e}", file=sys.stderr)
        return 1
    if not lines:
        print("the model returned no usable examples, try again", file=sys.stderr)
        return 1

    TEMPLATES[command] = "\n".join(lines)
    show(command)
    if input("\nsave? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        return 0
    user = load_user_templates()
    user[command] = lines
    USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_FILE.write_text(json.dumps(user, indent=2) + "\n")
    print(f"saved to {USER_FILE}")
    return 0


def main():
    TEMPLATES.update({cmd: "\n".join(lines) for cmd, lines in load_user_templates().items()})
    args = sys.argv[1:]
    if len(args) > 1 and args[0] == "--add":
        return add(" ".join(args[1:]))
    if not args or args[0].startswith("-"):
        print("usage: remind <command> [subcommand]\n       remind --add <command> [subcommand]   (generate with an LLM)\n\nknown commands:")
        line = " "
        for name in sorted(TEMPLATES):
            if len(line) + len(name) > 76:
                print(line)
                line = " "
            line += " " + (f"[{name}]" if " " in name else name)
        print(line)
        return 0

    name = " ".join(args)
    command = ALIASES.get(name, name)
    if command not in TEMPLATES:
        print(f"no reminder for '{name}' yet, add one with: remind --add {name}", file=sys.stderr)
        return 1

    show(command)
    subcommands = [n.split(" ", 1)[1] for n in sorted(TEMPLATES) if n.startswith(command + " ")]
    if subcommands:
        print(f"\n  more: remind {command} {'|'.join(subcommands)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
