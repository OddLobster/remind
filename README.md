# remind

Forgot the syntax of `chown` again? `--help` is too long, `man` is worse.
`remind` shows a few short examples you can run right away, filled with real
values from where you are: your files, your user, your git branch, ...

```
~/project $ remind chown
  chown lobster notes.txt                  # change owner
  chown lobster:lobster notes.txt          # change owner and group
  chown :lobster notes.txt                 # change only the group
  chown -R lobster:lobster src             # recursive, whole directory
  chown --reference=README.md notes.txt    # copy owner from another file
```

## Install

```bash
pipx install git+https://github.com/OddLobster/remind.git
```

No dependencies, just Python 3.9+. To update:
`pipx install --force git+https://github.com/OddLobster/remind.git`

## Usage

```bash
remind tar                      # examples for a command
remind git remote               # ... or a subcommand
remind                          # list all known commands
remind "find big files"         # ask a question (needs an API key, see below)
remind --add dig                # generate examples for a new command
remind --keep '<command line>'  # save a command you ran (see `keep` below)
```

About 60 commands are built in: files and permissions, find/grep, text
processing (sed, awk, cut, sort, ...), archives, disk, processes, network,
systemd, ssh, git, docker, jq.

Examples that delete or kill something never use your real file names or
process IDs, they always show `<placeholders>`, so copy-paste is safe.

## Your own reminders

### `keep`: save what worked

Add this to your `~/.bashrc`:

```bash
keep() { remind --keep "$(fc -ln -1)"; }
```

Then run `keep` right after a command worked:

```
$ rsync -avP src/ nas:/backup/
$ keep
comment: sync to nas
added to [rsync]
```

From now on `remind rsync` shows it below the built-in examples, marked with ★.

### The reminders file

Everything you add with `keep` or `--add` lives in
`~/.config/remind/reminders.txt`. It's plain text, so edit it as you like:

```
[rsync]
rsync -avP src/ nas:/backup/  # sync to nas

[git remote]
git remote get-url origin  # show origin url
```

`{file}`, `{dir}`, `{user}`, `{branch}`, ... work there too and get filled in
like the built-in examples.

## Questions and `--add` (optional)

These use a model on [OpenRouter](https://openrouter.ai). Set your key:

```bash
export OPENROUTER_API_KEY=sk-or-...
export REMIND_MODEL=deepseek/deepseek-v4.1-flash   # optional, this is the default
```

Only your question (or the command name) is sent. The model answers with
placeholders like `{file}` that are filled in locally, so your file names
never leave your machine.
