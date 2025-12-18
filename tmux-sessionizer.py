#!/usr/bin/env python3
"""
Fuzzy find a directory and start/connect to a tmux session in it.

Requires:
  - tmux
  - fzf
  - eza (optional, for default preview)

Instructions:
  - Set up the config dictionary near the top of the file to your liking.
  - Add this script to your PATH.
"""

from collections import defaultdict
import subprocess
from pathlib import Path
import os
import argparse
import sys
from typing import Callable, TypedDict


class Config(TypedDict):
    parent_dir: Path
    depth: int
    fzf_options: list[str]
    fzf_preview: str
    tmux_session_factory: Callable[[str, Path], list[list[str]]]
    allowed_dotfiles: list[str]


def detect_env_activation(path: Path) -> None | list[str]:
    # eg: use poetry shell if there is a pyproject.toml
    if not path.is_dir():
        return None

    if (path / "shell.nix").is_file():
        # nix-shell
        return ["nix-shell", "--run", "$SHELL"]
    elif (path / "pyproject.toml").is_file():
        # poetry shell
        return ["poetry", "shell"]
    elif (path / ".venv").is_dir():
        # activate venv
        venv_path = path / ".venv" / "bin" / "activate"
        return ["/usr/bin/env", "bash", "-c", f"source {venv_path}"]
    return None


def standard_tmux_session(session_name: str, path: Path) -> list[list[str]]:
    apath = str(path.resolve())
    cmds: list[list[str]] = []
    env_cmd = detect_env_activation(path)

    # First window (neovim):
    cmds.append(["tmux", "rename-window", "-t", f"{session_name}:1", "neovim"])

    # Second window (two panes, dev shells):
    cmds.append(
        ["tmux", "new-window", "-t", f"{session_name}", "-n", "dev", "-c", apath]
    )
    cmds.append(["tmux", "split-window", "-v", "-t", f"{session_name}:2", "-c", apath])
    # Select the first pane, so it's not weird.
    cmds.append(
        [
            "tmux",
            "select-window",
            "-t",
            f"{session_name}:2.1",
        ]
    )

    # Third window (shell):
    cmds.append(
        ["tmux", "new-window", "-t", f"{session_name}", "-n", "shell", "-c", apath]
    )

    # send keys:
    keys: dict[str, list[str]] = defaultdict(list)

    if env_cmd:
        # Activate the env in all panes
        env_cmd_str = " ".join(env_cmd)

        keys["1.1"].append(env_cmd_str)
        keys["2.1"].append(env_cmd_str)
        keys["2.2"].append(env_cmd_str)
        keys["3.1"].append(env_cmd_str)

    keys["1.1"].append("nvim .")

    cmds.extend(
        [
            [
                "tmux",
                "send-keys",
                "-t",
                f"{session_name}:{pane}",
                " && ".join(pane_cmds),
                "C-m",
            ]
            for pane, pane_cmds in keys.items()
        ]
    )

    cmds.append(
        [
            "tmux",
            "select-window",
            "-t",
            f"{session_name}:1",
        ]
    )

    return cmds


CONFIG: Config = {
    "parent_dir": Path(
        os.getenv("TMUX_SESSIONIZER_PARENT_DIR", os.getenv("HOME", "."))
    ).resolve(),
    "depth": 2,
    "fzf_options": ["--cycle"],
    "fzf_preview": "eza --color=always --icons --group-directories-first --git-ignore -T -L 2",
    "tmux_session_factory": standard_tmux_session,
    "allowed_dotfiles": [".config", ".dotfiles"],
}


def find_project_dirs(
    path: Path, depth: int, acc: None | list[Path] = None
) -> list[Path]:
    if acc is None:
        acc = []
    if depth < 0:
        return acc

    if path.is_symlink():
        # Don't follow symlinks, or we can get weird recursions
        acc.append(path)
        return acc

    if path.is_dir():
        # print(f"Searching in {path}...")
        # Check if the path starts with .:
        if path.name.startswith("."):
            acc.append(path)
            # if path.name in CONFIG["allowed_dotfiles"]:
            #     find_project_dirs(path, 1, acc)  # don't go much deeper
            return acc

        # Path does not start with a dot. So we add it to the list and continue searching:
        acc.append(path)
        if path_is_git_repo(path):
            # Don't go any deeper
            return acc
        for child in path.iterdir():
            find_project_dirs(child, depth - 1, acc)
    return acc


def find_tmux_session_by_path(path: Path) -> str | None:
    result = subprocess.run(
        ["tmux", "ls", "-F", "#{session_name}:#{session_path}"],
        stdout=subprocess.PIPE,
        # stderr=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode == 1 and result.stderr.startswith("no server running"):
        return None

    if result.returncode != 0:
        print("Some unknown error has occurred while looking for tmux sessions.")
        return None

    for line in result.stdout.strip().splitlines():
        str_line = str(line)
        if ":" not in str(line):
            continue
        name, session_path = str_line.split(":", 1)
        if Path(session_path).resolve() == path.resolve():
            return name


def path_is_git_repo(path: Path) -> bool:
    return path.is_dir() and (path / ".git").is_dir()


def start_standard_tmux_session(session_name: str, path: Path) -> None:
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session_name,
            "-c",
            str(path),
        ],
        check=True,
    )

    for cmd in CONFIG["tmux_session_factory"](session_name, path):
        subprocess.run(cmd, check=True)


def send_list_of_paths_to_fzf(paths: list[Path], parent_dir: Path) -> Path | None:
    # Remove duplicates:
    paths = sorted(list(set(paths)), key=lambda x: str(x))
    # Trim the parent directory from the paths
    paths = [path.relative_to(parent_dir) for path in paths]
    fzf_cmd = ["fzf"]
    if CONFIG["fzf_options"]:
        fzf_cmd.extend(CONFIG["fzf_options"])
    if CONFIG["fzf_preview"]:
        fzf_cmd.extend(
            [
                "--preview",
                f"{CONFIG['fzf_preview']} {parent_dir}/{{}}",
            ]
        )

    result = subprocess.run(
        fzf_cmd,
        input="\n".join(map(str, paths)).encode(),
        capture_output=True,
    )

    if result.returncode == 0:
        selected_path = parent_dir / Path(result.stdout.decode().strip())
        if selected_path.is_dir():
            return selected_path.resolve()
    elif result.returncode == 130:
        # User cancelled out of fzf:
        print("fzf selection cancelled.")
        return None
    else:
        print(
            "Some unknown error occurrsed during the fzf selection. fzf exited with code: ",
            result.returncode,
        )
        print(" === Output: ===\n", result.stdout.decode(), "\n === End of output ===")
        print(" === Error: ===\n", result.stderr.decode(), "\n === End of error ===")

    raise ValueError(
        "No valid directory selected. Do you have fzf installed and in your PATH?"
    )


def attach_to_tmux_session(session_name: str) -> None:
    if os.getenv("TMUX"):
        subprocess.run(["tmux", "switch-client", "-t", session_name])
    else:
        subprocess.run(["tmux", "attach-session", "-t", session_name])


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--parent-dir",
        type=Path,
        default=CONFIG["parent_dir"],
        help="Parent directory to search for subdirectories.",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=CONFIG["depth"],
        help="Depth of the subdirectories to search.",
    )

    # optionally just specify a positional directory to start the tmux session in
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=None,
        help="Directory to start the tmux session in, if you want to skip the fzf selection.",
    )

    parser.add_argument(
        "--sessions",
        action="store_true",
        default=False,
        help="Lists and swaps to active tmux sessions.",
    )

    return parser


def find_session_or_start_then_attach(selected_path: Path) -> int:
    if not selected_path.is_dir():
        raise ValueError(f"{selected_path} is not a valid directory.")
    # Check if there is an existing tmux session for this path:
    if session_name := find_tmux_session_by_path(selected_path):
        attach_to_tmux_session(session_name)
        return 0
    else:
        session_name = selected_path.name
        start_standard_tmux_session(session_name, selected_path)
        attach_to_tmux_session(session_name)
        return 0


def select_and_swap_to_active_session() -> None:
    sessions = subprocess.Popen(
        ["tmux", "ls", "-F", "#S"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    selected_session = subprocess.run(
        ["fzf", "--cycle", "--select-1"],
        stdin=sessions.stdout,
        text=True,
        capture_output=True,
    )

    if selected_session.returncode != 0:
        print("fzf selection cancelled.")
        return None

    selected_session = selected_session.stdout.strip()
    attach_to_tmux_session(selected_session)


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    if args.sessions:
        select_and_swap_to_active_session()
        return 0

    # Validation:
    if args.directory is not None:
        path = args.directory.resolve()
        if not path.is_dir():
            raise ValueError(f"{path} is not a valid directory.")
        else:
            # Start a tmux session in the specified directory:
            return find_session_or_start_then_attach(path)

    parent_dir = args.parent_dir.resolve()
    if not parent_dir.is_dir():
        raise ValueError(f"{parent_dir} is not a valid directory.")

    # Find all subdirectories and fuzzy find:
    project_dirs = find_project_dirs(parent_dir, args.depth)
    if not project_dirs:
        raise ValueError(f"No subdirectories found in {parent_dir}.")
    selected_path = send_list_of_paths_to_fzf(project_dirs, parent_dir)
    if selected_path is None:
        print("No directory selected. Exiting.")
        return 1

    return find_session_or_start_then_attach(selected_path)


if __name__ == "__main__":
    sys.exit(main())
