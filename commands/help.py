from importlib import import_module

description = (
    'List commands, browse a category, or show one command. ~admin lists gated commands.\n'
    '  ~help [page|archive|personas|analysis|translation|utility|ai|command]'
)

# Commands that work but are intentionally NOT listed by ~help (still reachable
# via ~help <command>).
HIDDEN = {"markov", "mimic", "pers", "modelqueue", "admin"}

# Admin / super-admin commands - listed only by ~admin (or ~help admin), never
# in the public ~help.
ADMIN_CATEGORIES = [
    ("super admin", [
        "botpersona", "botmode", "botcontext", "botchance",
        "banuser", "unbanuser", "warnings", "model", "axismerge",
        "announce", "gojomons", "emotes",
        "chan_autotl", "global_autotl", "notranslate",
    ]),
    ("admin", [
        "autotl", "setlang", "tloutput",
    ]),
]
ADMIN_NAMES = {name for _title, names in ADMIN_CATEGORIES for name in names}

# Public categories shown by ~help (admin + hidden commands excluded).
CATEGORIES = [
    ("translation", [
        "practice", "romanize", "speak",
    ]),
    ("archive", [
        "said", "saidnext", "saidmost", "regex", "userregex", "quote", "random",
        "firstseen", "chatstats", "regulars", "askchat",
    ]),
    ("personas", [
        "persona", "hyper", "generate",
    ]),
    ("analysis", [
        "whosaid", "markers", "like", "vibes", "twin", "traits", "style",
        "top", "bottom", "distinct", "why", "axis", "emote", "explain",
        "funny", "ragebait", "irony",
    ]),
    ("utility", [
        "help", "experimental", "ping", "artifacts",
    ]),
]

GROUPS_PER_PAGE = 2

# Rough/prototype commands get a * marker in the listing (legend appended
# when any are shown; full notes via ~experimental). Top-level names only
# subroutes like "explain emote" are covered by their parent.
EXPERIMENTAL_MARK = {"askchat", "emote", "irony"}

# These commands can make a live local-AI call in at least one mode. Some have
# a no-model fast path (cached axes, raw receipts, engine=markov); ~help ai
# spells out the distinction without bloating every command description.
MODEL_MARK = {
    "askchat", "persona", "hyper", "generate", "top", "bottom", "distinct",
    "why", "axis", "emote", "explain", "irony", "traits", "ragebait",
}


def _known_command_pages(command_names):
    grouped = []
    seen = set()
    # hidden + admin commands never appear in the public listing
    command_set = set(command_names) - HIDDEN - ADMIN_NAMES
    for title, names in CATEGORIES:
        present = [name for name in names if name in command_set]
        if present:
            grouped.append((title, present))
            seen.update(present)
    leftovers = sorted(command_set - seen)
    if leftovers:
        grouped.append(("other", leftovers))
    return [
        grouped[index:index + GROUPS_PER_PAGE]
        for index in range(0, len(grouped), GROUPS_PER_PAGE)
    ]


def _format_command_list(prefix: str, page: int, pages) -> str:
    total = max(1, len(pages))
    page = max(1, min(page, total))
    chunks = []
    marked = False
    model_marked = False
    for title, names in pages[page - 1]:
        rendered = " ".join(
            f"{prefix}{name}{'*' if name in EXPERIMENTAL_MARK else ''}"
            f"{'†' if name in MODEL_MARK else ''}"
            for name in names)
        marked = marked or any(name in EXPERIMENTAL_MARK for name in names)
        model_marked = model_marked or any(name in MODEL_MARK for name in names)
        chunks.append(f"{title}: {rendered}")
    legend = f" | *=experimental ({prefix}experimental)" if marked else ""
    if model_marked:
        legend += f" | †=may use local AI ({prefix}help ai)"
    return (
        f"Commands {page}/{total}: " + " | ".join(chunks) +
        f" | {prefix}help <command> for details{legend}"
    )


def format_admin_list(prefix: str, command_names) -> str:
    command_set = set(command_names)
    chunks = []
    for title, names in ADMIN_CATEGORIES:
        present = [n for n in names if n in command_set]
        if present:
            rendered = " ".join(f"{prefix}{n}" for n in present)
            chunks.append(f"{title}: {rendered}")
    if not chunks:
        return "No admin commands available."
    return (
        "Admin commands: " + " | ".join(chunks) +
        f" | {prefix}help <command> for details"
    )


def command_help_text(command: str, prefix: str = "~") -> str:
    """Return one command's normal help text for ~help x and ~x help."""
    from command_registry import command_handlers

    command = (command or "").lower()
    if command not in command_handlers:
        return f"Command not found. Use {prefix}help to list all commands."
    try:
        module = import_module(f"commands.{command}")
        detail = getattr(module, "description", "No description available for this command.")
    except ImportError as exc:
        detail = f"Failed to load command module: {exc}"
    return f"{command}: {detail}"


async def handle_help(bot, message, params):
    from command_registry import command_handlers

    if not params:
        pages = _known_command_pages(command_handlers.keys())
        await message.channel.send(_format_command_list(bot.prefix, 1, pages))
        return

    command = params[0].lower()
    if command == "admin":
        await message.channel.send(format_admin_list(bot.prefix, command_handlers.keys()))
        return
    if command in {"experimental", "experiments"}:
        module = import_module("commands.experimental")
        await message.channel.send(module.format_experimental_list(bot.prefix))
        return
    if command in {"ai", "gpu", "model", "models"}:
        await message.channel.send(
            f"Local AI required: {bot.prefix}persona {bot.prefix}hyper "
            f"{bot.prefix}ragebait {bot.prefix}irony | default AI, local mode available: "
            f"{bot.prefix}generate (engine=markov) | AI only for uncached/live analysis: "
            f"{bot.prefix}top {bot.prefix}bottom {bot.prefix}axis {bot.prefix}why "
            f"{bot.prefix}traits {bot.prefix}distinct | optional model-written answers with archive fallback: "
            f"{bot.prefix}askchat {bot.prefix}emote {bot.prefix}explain | no-AI persona: "
            f"{bot.prefix}mimic"
        )
        return
    category_aliases = {
        "language": "translation",
        "languages": "translation",
        "persona": "personas",
        "stats": "archive",
        "search": "archive",
        "tools": "utility",
    }
    wanted = category_aliases.get(command, command)
    for title, names in CATEGORIES:
        if wanted != title:
            continue
        present = [name for name in names if name in command_handlers]
        rendered = " ".join(
            f"{bot.prefix}{name}{'*' if name in EXPERIMENTAL_MARK else ''}"
            f"{'†' if name in MODEL_MARK else ''}"
            for name in present
        )
        legend = f" | *=experimental ({bot.prefix}experimental)" if any(
            name in EXPERIMENTAL_MARK for name in present
        ) else ""
        if any(name in MODEL_MARK for name in present):
            legend += f" | †=may use local AI ({bot.prefix}help ai)"
        await message.channel.send(
            f"{title}: {rendered} | {bot.prefix}help <command> for details{legend}"
        )
        return
    if command.isdigit():
        pages = _known_command_pages(command_handlers.keys())
        await message.channel.send(_format_command_list(bot.prefix, int(command), pages))
        return
    if command in command_handlers:
        await message.channel.send(command_help_text(command, bot.prefix))
    else:
        await message.channel.send(f"Command not found. Use {bot.prefix}help to list all commands.")
