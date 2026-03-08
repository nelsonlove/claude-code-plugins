#!/usr/bin/env python3
"""Generate or regenerate ~/Desktop/BREWFILE-AUDIT.org from Homebrew state.

On regeneration, preserves existing TODO states from a prior org file.
Babel action blocks are injected from a static template, never regenerated.

Usage:
    python3 generate-audit.py [--existing PATH] [--output PATH] [--template-dir DIR]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


# ── Section grouping rules ──────────────────────────────────────────────
# Maps package names to section headings (order matters — first match wins).
# Packages not matching any rule go into "Misc / uncategorized".

SECTION_RULES = [
    # Section name, type filter (None=any), package name patterns
    ("TAPS", "tap", [r".*"]),
    ("Core shell / file tools", "brew", [
        r"bash$", r"zsh$", r"fish$", r"coreutils", r"findutils", r"gnu-.*",
        r"grep$", r"sed$", r"gawk$", r"moreutils", r"diffutils",
        r"tree$", r"eza$", r"lsd$", r"bat$", r"fd$", r"ripgrep",
        r"fzf$", r"zoxide", r"trash", r"rename", r"watch$",
        r"entr$", r"pv$", r"jq$", r"yq$", r"gron$",
        r"curl$", r"wget$", r"httpie", r"xh$",
        r"htop$", r"btop$", r"procs$", r"dust$", r"duf$", r"ncdu$",
        r"progress$", r"viddy$", r"gum$", r"glow$", r"charm.*",
        r"starship", r"atuin", r"sheldon", r"direnv",
        r"stow$", r"chezmoi", r"mackup",
        r"readline", r"gettext", r"libevent", r"ncurses", r"pcre",
        r"pkg-config", r"autoconf", r"automake", r"cmake", r"ninja",
        r"make$", r"bison$", r"flex$",
    ]),
    ("tmux stack", "brew", [r"tmux$", r"tpm$", r"reattach.*"]),
    ("git tools", "brew", [
        r"git$", r"git-.*", r"gh$", r"hub$", r"lazygit", r"tig$",
        r"delta$", r"diff-so-fancy", r"bfg$", r"pre-commit",
        r"act$",  # GitHub Actions local runner
    ]),
    ("Python ecosystem", "brew", [
        r"python", r"pyenv", r"pipx", r"uv$", r"ruff$",
        r"black$", r"mypy$", r"poetry$", r"pdm$",
        r"ipython", r"jupyter", r"numpy", r"scipy",
    ]),
    ("Node / JS ecosystem", "brew", [
        r"node$", r"nvm$", r"fnm$", r"yarn$", r"pnpm$", r"bun$",
        r"deno$", r"typescript", r"eslint", r"prettier",
    ]),
    ("Cloud / infra / devops", "brew", [
        r"aws.*", r"azure.*", r"gcloud", r"terraform", r"pulumi",
        r"docker", r"podman", r"colima", r"lima", r"qemu",
        r"kubectl", r"helm", r"k9s", r"kind$", r"minikube",
        r"ansible", r"vagrant", r"packer", r"consul", r"vault",
        r"fly$", r"flyctl", r"heroku", r"railway",
        r"cloudflare", r"wrangler", r"minio", r"caddy", r"nginx",
        r"traefik", r"wireguard", r"tailscale",
        r"supabase", r"firebase", r"vercel",
        r"backblaze", r"rclone", r"restic",
    ]),
    ("Security", "brew", [
        r"gnupg", r"gpg.*", r"pinentry", r"openssl", r"libsodium",
        r"age$", r"sops$", r"vault$", r"pass$", r"gopass",
        r"nmap$", r"masscan", r"wireshark", r"tcpdump",
        r"trivy", r"grype", r"syft", r"cosign",
        r"yubikey", r"ykman",
    ]),
    ("Media / audio / video", "brew", [
        r"ffmpeg", r"imagemagick", r"graphicsmagick",
        r"sox$", r"lame$", r"flac$", r"opus.*", r"vorbis",
        r"mpv$", r"vlc$", r"yt-dlp", r"youtube-dl",
        r"gifsicle", r"optipng", r"pngquant", r"webp$",
        r"exiftool", r"libheif", r"jpeg.*", r"libpng",
        r"switchaudio", r"blackhole",
        r"shairport", r"libao", r"portaudio",
    ]),
    ("AI / ML", "brew", [
        r"ollama", r"llama.*", r"whisper", r"mlx$",
        r"sentencepiece", r"protobuf",
        r"runpod.*",
    ]),
    ("Documents / text / writing", "brew", [
        r"pandoc", r"latex", r"tex.*", r"groff",
        r"aspell", r"hunspell", r"languagetool",
        r"poppler", r"ghostscript", r"qpdf", r"ocrmypdf",
        r"djvu", r"calibre", r"markdown",
        r"vale$", r"proselint",
    ]),
    ("Languages / runtimes", "brew", [
        r"go$", r"rust.*", r"cargo.*", r"lua.*", r"luajit",
        r"ruby$", r"rbenv", r"perl$", r"php$",
        r"java$", r"openjdk", r"gradle", r"maven",
        r"zig$", r"nim$", r"crystal$", r"elixir", r"erlang",
        r"ghc$", r"cabal", r"stack$", r"haskell",
        r"swift$", r"swiftformat", r"swiftlint",
        r"r$", r"julia$", r"octave$",
        r"racket", r"guile", r"chicken",
        r"sbcl$", r"ecl$",  # Common Lisp
        r"clojure", r"leiningen",
        r"dotnet", r"mono$",
        r"v$", r"vlang",
    ]),
    ("Games / interactive fiction", "brew", [
        r"frotz", r"inform.*", r"z-machine",
        r"glulx", r"gargoyle",
    ]),
    ("Window management", "brew", [
        r"yabai", r"skhd", r"aerospace", r"borders$",
    ]),
    ("macOS tools", "brew", [
        r"dark-mode", r"duti$", r"ical-buddy", r"mas$",
        r"terminal-notifier", r"osxutils", r"osx-cpu-temp",
        r"blueutil", r"brightness", r"switchaudio",
        r"plist.*", r"trash$",
    ]),
    ("Shell niceties / novelty", "brew", [
        r"cowsay", r"fortune", r"lolcat", r"figlet", r"toilet",
        r"cmatrix", r"nyancat", r"sl$", r"pipes-sh",
        r"neofetch", r"fastfetch", r"onefetch",
        r"asciinema", r"ttyrec", r"carbonyl",
    ]),
    ("Fonts", "cask", [r"font-.*"]),
]


def get_brew_info():
    """Get all installed package info from brew."""
    result = subprocess.run(
        ["brew", "info", "--json=v2", "--installed"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error running brew info: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def get_installed_on_request():
    """Get set of packages installed on request (not auto-deps)."""
    result = subprocess.run(
        ["brew", "list", "--installed-on-request"],
        capture_output=True, text=True
    )
    return set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()


def get_taps():
    """Get list of taps."""
    result = subprocess.run(["brew", "tap"], capture_output=True, text=True)
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def get_mas_apps():
    """Get list of Mac App Store apps."""
    result = subprocess.run(["mas", "list"], capture_output=True, text=True)
    apps = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        # Format: "497799835 Xcode (16.2)"
        m = re.match(r"(\d+)\s+(.+?)\s+\(", line)
        if m:
            apps.append({"id": m.group(1), "name": m.group(2)})
    return apps


def get_install_date(pkg_name):
    """Get install date for a formula/cask from Cellar/Caskroom."""
    for prefix in ["/opt/homebrew/Cellar", "/usr/local/Cellar",
                   "/opt/homebrew/Caskroom", "/usr/local/Caskroom"]:
        p = Path(prefix) / pkg_name
        if p.exists():
            # Get earliest version dir creation time
            versions = sorted(p.iterdir(), key=lambda x: x.stat().st_ctime)
            if versions:
                from datetime import datetime
                ts = versions[0].stat().st_ctime
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return "n/a"


def classify_package(name, pkg_type):
    """Determine which section a package belongs to."""
    for section_name, type_filter, patterns in SECTION_RULES:
        if type_filter and type_filter != pkg_type:
            continue
        for pat in patterns:
            if re.search(pat, name, re.IGNORECASE):
                return section_name
    return "Misc / uncategorized"


def parse_existing_org(path):
    """Parse an existing org file to extract TODO states and notes per package.

    Returns dict: package_name -> {"state": "KEEP"/"DROP"/etc, "note": "..."}
    """
    if not path or not Path(path).exists():
        return {}

    existing = {}
    current_state = None
    current_pkg = None

    with open(path) as f:
        for line in f:
            # Match heading: ** KEEP package-name  :brew:
            m = re.match(r"\*\*\s+(KEEP|DROP|MAYBE|DEP)\s+(\S+)", line)
            if m:
                current_state = m.group(1)
                current_pkg = m.group(2)
                existing[current_pkg] = {"state": current_state, "note": ""}
                continue

            # Match PACKAGE property (more reliable than heading)
            m = re.match(r"\s*:PACKAGE:\s+(.+)", line)
            if m and current_state:
                pkg = m.group(1).strip()
                existing[pkg] = existing.get(current_pkg, {"state": current_state, "note": ""})
                if pkg != current_pkg:
                    existing[pkg] = {"state": current_state, "note": ""}
                current_pkg = pkg
                continue

            # Match note line (italic in org): /some note/
            m = re.match(r"/(.+)/\s*$", line)
            if m and current_pkg and current_pkg in existing:
                existing[current_pkg]["note"] = m.group(1)

    return existing


def heuristic_verdict(name, pkg_type, desc, on_request):
    """Apply heuristic annotation rules. Returns (state, note)."""
    if not on_request and pkg_type == "brew":
        return ("DEP", "auto-installed dependency")

    name_lower = name.lower()

    # Strong KEEP signals
    keep_patterns = [
        (r"^(git|python|node|tmux|ripgrep|fd|fzf|bat|eza|jq|gh|starship|atuin|uv)$",
         "core tool"),
        (r"^(emacs|vim|neovim)$", "editor"),
        (r"^mas$", "App Store CLI"),
    ]
    for pat, note in keep_patterns:
        if re.match(pat, name_lower):
            return ("KEEP", note)

    # Default for on-request packages
    return ("MAYBE", f"review — {desc[:60] if desc else 'no description'}")


def build_entries(brew_info, on_request, taps, mas_apps, existing):
    """Build list of entry dicts from brew data."""
    entries = []

    # Taps
    for tap_name in sorted(taps):
        prev = existing.get(tap_name, {})
        state = prev.get("state", "MAYBE")
        note = prev.get("note", f"review this tap")
        entries.append({
            "name": tap_name,
            "type": "tap",
            "installed": "n/a",
            "desc": "",
            "state": state,
            "note": note,
            "section": "TAPS",
        })

    # Formulae
    for f in brew_info.get("formulae", []):
        name = f["name"]
        desc = f.get("desc", "") or ""
        installed = get_install_date(name)
        is_on_request = name in on_request

        prev = existing.get(name, {})
        if prev:
            state = prev["state"]
            note = prev["note"] or desc
        else:
            state, note = heuristic_verdict(name, "brew", desc, is_on_request)

        entries.append({
            "name": name,
            "type": "brew",
            "installed": installed,
            "desc": desc,
            "state": state,
            "note": note,
            "section": classify_package(name, "brew"),
        })

    # Casks
    for c in brew_info.get("casks", []):
        name = c["token"]
        desc = c.get("desc", "") or c.get("name", [name])[0]
        installed = get_install_date(name)

        prev = existing.get(name, {})
        if prev:
            state = prev["state"]
            note = prev["note"] or desc
        else:
            state, note = heuristic_verdict(name, "cask", desc, True)

        entries.append({
            "name": name,
            "type": "cask",
            "installed": installed,
            "desc": desc,
            "state": state,
            "note": note,
            "section": "Fonts" if name.startswith("font-") else classify_package(name, "cask"),
        })

    # MAS apps
    for app in mas_apps:
        prev = existing.get(app["name"], {})
        state = prev.get("state", "MAYBE")
        note = prev.get("note", "App Store app")
        entries.append({
            "name": app["name"],
            "type": "mas",
            "installed": "n/a",
            "desc": "",
            "state": state,
            "note": note,
            "section": "MAS — App Store",
            "mas_id": app["id"],
        })

    return entries


def emit_org(entries, template_dir, output_path):
    """Write the org file from entries + static templates."""
    template_dir = Path(template_dir)

    # Read header template
    header = (template_dir / "header.org").read_text()
    header = header.replace("%DATE%", date.today().isoformat())

    # Read actions template
    actions = (template_dir / "actions-block.org").read_text()

    # Group entries by section (preserve order of first appearance via SECTION_RULES)
    section_order = [s[0] for s in SECTION_RULES] + ["CASKS", "MAS — App Store", "Misc / uncategorized"]
    seen_sections = []
    sections = {}
    for e in entries:
        s = e["section"]
        if s not in sections:
            sections[s] = []
            seen_sections.append(s)
        sections[s].append(e)

    # Order sections: known order first, then any extras
    ordered = []
    for s in section_order:
        if s in sections:
            ordered.append(s)
    for s in seen_sections:
        if s not in ordered:
            ordered.append(s)

    with open(output_path, "w") as f:
        f.write(header)
        f.write("\n")

        for section in ordered:
            f.write(f"* {section}\n")
            for e in sorted(sections[section], key=lambda x: x["installed"]):
                tag = f":{e['type']}:"
                # Pad heading to align tags at column 56
                heading = f"{e['state']} {e['name']}"
                padded = f"** {heading:<52s} {tag}\n"
                f.write(padded)
                f.write(":PROPERTIES:\n")
                f.write(f":INSTALLED: {e['installed']}\n")
                f.write(f":TYPE:      {e['type']}\n")
                f.write(f":PACKAGE:   {e['name']}\n")
                if e.get("mas_id"):
                    f.write(f":MAS_ID:    {e['mas_id']}\n")
                f.write(":END:\n")
                if e["desc"]:
                    f.write(f"{e['desc']}\n")
                if e["note"]:
                    f.write(f"/{e['note']}/\n")
                f.write("\n")

        f.write(actions)

    print(f"Wrote {output_path} with {len(entries)} entries across {len(ordered)} sections")


def main():
    parser = argparse.ArgumentParser(description="Generate Brewfile audit org file")
    parser.add_argument("--existing", help="Path to existing org file (preserves states)")
    parser.add_argument("--output", default=str(Path.home() / "Desktop" / "BREWFILE-AUDIT.org"))
    parser.add_argument("--template-dir", required=True, help="Path to templates/ directory")
    args = parser.parse_args()

    print("Fetching brew info (this may take a moment)...")
    brew_info = get_brew_info()
    on_request = get_installed_on_request()
    taps = get_taps()

    print("Fetching Mac App Store apps...")
    try:
        mas_apps = get_mas_apps()
    except FileNotFoundError:
        print("  mas not found, skipping App Store apps")
        mas_apps = []

    existing = parse_existing_org(args.existing)
    if existing:
        print(f"Loaded {len(existing)} existing triage decisions")

    entries = build_entries(brew_info, on_request, taps, mas_apps, existing)
    emit_org(entries, args.template_dir, args.output)


if __name__ == "__main__":
    main()
