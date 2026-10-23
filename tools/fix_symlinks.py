"""Replace git symlink placeholders with real copies, in a repo and all its submodules.

On Windows without symlink support git checks out a symlink as a small text file
holding the target path. Builds then fail on files like `../../x/y.c`.

Usage: py -I tools/fix_symlinks.py <repo>
"""
import os
import shutil
import subprocess
import sys


def repos(root):
    yield root
    out = subprocess.run(["git", "-C", root, "submodule", "foreach", "--recursive", "--quiet", "pwd"],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        path = line.strip()
        if path.startswith("/") and len(path) > 2 and path[2] == "/":  # /c/... from Git Bash
            path = path[1] + ":" + path[2:]
        yield path


def symlinks(repo):
    out = subprocess.run(["git", "-C", repo, "ls-files", "-s"], capture_output=True, text=True,
                         check=True).stdout
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        if meta.startswith("120000 "):
            yield os.path.join(repo, path)


def main(root):
    fixed = skipped = 0
    pending = [p for r in repos(root) for p in symlinks(r)]
    # Links can point at other links: retry until nothing changes.
    while pending:
        progress, left = False, []
        for link in pending:
            if not os.path.isfile(link) or os.path.getsize(link) > 1024:
                continue  # already a real file
            target = open(link, encoding="utf-8", errors="replace").read().strip()
            src = os.path.normpath(os.path.join(os.path.dirname(link), target))
            if src in pending and src not in left and os.path.getsize(src) <= 1024 and src != link:
                left.append(link)
                continue
            if os.path.isdir(src):
                os.remove(link)
                shutil.copytree(src, link)
            elif os.path.isfile(src):
                shutil.copyfile(src, link)
            else:
                print(f"missing target: {link} -> {target}")
                skipped += 1
                continue
            fixed += 1
            progress = True
        if not progress:
            break
        pending = left
    print(f"replaced {fixed} symlink placeholders, {skipped} with missing targets")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(os.path.abspath(sys.argv[1]))
