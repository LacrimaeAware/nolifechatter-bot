import logging
import urllib.error

from command_registry import command_handlers, load_command_handlers  # noqa: F401
from services import model_queue
from utils import cooldowns
from utils.command_bans import is_banned

# Commands that hit LM Studio hard enough to share one global lane across all
# channels. Optional model-written answers (~askchat/~emote) are queued by their
# handlers after local evidence retrieval.
MODEL_REQUIRED_COMMANDS = {
    "persona", "pers", "hyper", "generate", "ragebait",
    "irony",
}
GENERATE_LOCAL_SUBCOMMANDS = {"save", "list", "del", "delete"}

_OFFLINE_SIGNS = (
    "10061", "actively refused", "connection refused", "max retries",
    "connection aborted", "failed to establish", "[errno 111]",
    "1225", "refused the network connection", "clientconnectorerror",
)
_REJECTED_SIGNS = (
    "http error 400", "http error 500", "failed to load model",
    "has not started loading", "operation canceled", "timed out", "timeout",
    "server disconnected",
    # LM Studio embedder/chat error shapes (utils._embed / _chat_sync raise
    # "embedding HTTP 4xx: ..." / "chat HTTP 4xx: ..." - the model is up but
    # loading/unloading, not offline). Without these they fell through to a
    # useless "An error occurred".
    "embedding http 4", "embedding http 5", "chat http 4", "chat http 5",
    "was unloaded", "model unloaded", "no models loaded", "model not found",
)
_MODEL_MISSING_SIGNS = (
    "failed to load model", "has not started loading", "was unloaded",
    "model unloaded", "no models loaded", "model not found",
)
_MODEL_BUSY_SIGNS = (
    "http error 500", "operation canceled", "timed out", "timeout",
    "server disconnected", "embedding http 5", "chat http 5",
)


def _backend_offline(exc):
    """True only when the local model server looks unreachable."""
    if isinstance(exc, urllib.error.HTTPError):
        return False
    if isinstance(exc, urllib.error.URLError):
        return any(sign in str(getattr(exc, "reason", exc)).lower() for sign in _OFFLINE_SIGNS)
    if isinstance(exc, ConnectionError):
        return True
    return any(sign in str(exc).lower() for sign in _OFFLINE_SIGNS)


def _backend_rejected(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return True
    text = str(exc).lower()
    return any(sign in text for sign in _REJECTED_SIGNS)


def _backend_model_missing(exc):
    text = str(exc).lower()
    return any(sign in text for sign in _MODEL_MISSING_SIGNS)


def _backend_busy(exc):
    text = str(exc).lower()
    return any(sign in text for sign in _MODEL_BUSY_SIGNS)


def _axis_term(params) -> str:
    """The trait phrase for ~top/~bottom - every bare word joined (traits can be
    multi-word, e.g. 'anal lover'), skipping flags (burst, user=<name>, @user)
    and a numeric n. Matches how the command parses the trait, so the cache
    check (fast-path vs model queue) is made against the real axis name."""
    words = []
    for p in params:
        low = (p or "").lower()
        if (low == "burst" or low.startswith("user=")
                or (p or "").startswith("@") or low.isdigit()):
            continue
        words.append(low)
    return " ".join(words).strip()


def _why_trait(params) -> tuple[str, str, bool] | None:
    """Return (user, trait, words_mode) for ordinary ~why user trait [words] - via
    the same arg normalization the command itself uses (handles the swapped
    trait-first slip), so the queue/fast-path decision matches what will run."""
    if len(params) < 2 or params[0].lower() in {"emote", "emotes"}:
        return None
    from commands.why import normalize_why_args
    return normalize_why_args(params)


def _persona_target(params) -> str:
    """Match ~persona's leading-only flag parsing and return its target."""
    for param in params or []:
        low = param.lower()
        if low.startswith(("model=", "anon=")):
            continue
        return param.lstrip("@")
    return ""


def _irony_has_text(params) -> bool:
    for param in params or []:
        if not param.lower().startswith(("context=", "user=", "author=", "chat=")):
            return True
    return False


def _model_command_kind(command, params, user="") -> str | None:
    """Return 'required' only when this exact invocation needs live model work."""
    command = (command or "").lower()
    if not params:
        if command == "distinct":
            from utils import persona_traits
            return None if persona_traits.axes_ready() else "required"
        return None
    first = params[0].lower()
    if command == "generate" and first in GENERATE_LOCAL_SUBCOMMANDS:
        return None
    if command == "generate":
        from utils import persona_generate
        return None if persona_generate.recipe_engine(params, user) == "markov" else "required"
    if command == "ragebait":
        # ~ragebait ref is a local lookup of what the last bait riffed on
        if first.lstrip("@").startswith("ref"):
            return None
        from utils import chat_archive
        return "required" if chat_archive.message_count_for(first.lstrip("@")) else None
    if command in {"persona", "pers", "hyper"}:
        target = _persona_target(params)
        if not target:
            return None
        from utils import chat_archive
        return "required" if chat_archive.message_count_for(target) else None
    if command == "irony" and not _irony_has_text(params):
        return None
    if command == "why" and first in {"emote", "emotes"}:
        return None
    if command == "why":
        parsed = _why_trait(params)
        if parsed:
            target, trait, words_mode = parsed
            from commands.why import has_msg_index
            if not has_msg_index(target):
                return None
            if words_mode:
                return "required"
            from utils import persona_axes
            if persona_axes.axis_cached(trait):
                from utils import persona_traits
                if trait in persona_traits.pole_map() and not persona_traits.axes_ready():
                    return "required"
                return None
        return "required"
    if command in {"top", "bottom"}:
        # Only a genuinely NEW axis is model work. Built-in poles and
        # already-built dynamic axes (incl. their opposite pole / aliases)
        # resolve with no LLM call - run them fast so they don't stall behind
        # a live axis build in the global queue.
        term = _axis_term(params)
        if len(term.split()) > 3:
            return None
        if term:
            from utils import persona_axes
            if persona_axes.axis_cached(term):
                from utils import persona_traits
                if term in persona_traits.pole_map() and not persona_traits.axes_ready():
                    return "required"
                return None
        return "required"
    if command == "axis":
        term = first
        from utils import persona_axes
        if persona_axes.axis_cached(term):
            from utils import persona_traits
            # ~axis compares against every built-in axis, even when the queried
            # term itself is a saved custom axis.
            if not persona_traits.axes_ready():
                return "required"
            return None
        return "required"
    if command in {"traits", "distinct"}:
        if command == "traits":
            from utils import chat_archive, persona_embeddings
            target = chat_archive.normalize_author(first.lstrip("@"))
            if (not persona_embeddings.available()
                    or target not in persona_embeddings._centered()):
                return None
        from utils import persona_traits
        return None if persona_traits.axes_ready() else "required"
    if command in MODEL_REQUIRED_COMMANDS:
        return "required"
    return None


def _model_command_capability(command, params) -> str:
    """The live model type an invocation needs: chat, embedding, or both."""
    command = (command or "").lower()
    if command in {"irony", "traits", "distinct"}:
        return "embedding"
    if command in {"top", "bottom"}:
        term = _axis_term(params)
        from utils import persona_axes
        return "embedding" if persona_axes.axis_cached(term) else "both"
    if command == "axis":
        from utils import persona_axes
        term = params[0].lower() if params else ""
        return "embedding" if persona_axes.axis_cached(term) else "both"
    if command == "why":
        parsed = _why_trait(params)
        if parsed:
            from utils import persona_axes
            return "embedding" if persona_axes.axis_cached(parsed[1]) else "both"
    return "chat"


class CommandProcessor:
    def __init__(self, bot):
        self.bot = bot

    async def process_command(self, message):
        # command-banned users are silently ignored (~banuser/~unbanuser)
        if message.author and is_banned(message.author.name):
            logging.info(f"Ignored command from banned user {message.author.name}")
            return
        parts = message.content.lstrip(self.bot.prefix).split()
        if not parts:
            return
        command = parts[0].lower()
        params = parts[1:]

        handler = command_handlers.get(command)
        if not handler:
            logging.warning(f"Command not recognized: {command}")
            await message.channel.send(f"Command not recognized. Try {self.bot.prefix}help for command list.")
            return

        # Every command supports the same discoverable help form. Restrict the
        # interception to one lone argument so phrases such as
        # "~said anyone help" remain valid archive searches.
        if len(params) == 1 and params[0].lower() == "help":
            from commands.help import command_help_text
            await message.channel.send(command_help_text(command, self.bot.prefix))
            return

        user = message.author.name if message.author else ""
        # Anti-spam gate (utils/cooldowns.py): stacking more commands while
        # your previous one is still running earns a warning, then an
        # escalating per-user cooldown. Waiting for each reply never costs
        # anything. The pending slot is released in _finish_command.
        if user and not await self._admit(message, user):
            return
        try:
            model_kind = _model_command_kind(command, params, user)
            if model_kind and message.channel:
                capability = _model_command_capability(command, params)
                await self._run_model_queued(
                    message, command, params, handler, user, model_kind, capability)
            else:
                await self._run(message, command, params, handler)
        finally:
            self._finish_command(user)

    async def _admit(self, message, user) -> bool:
        """Apply the stacking cooldown. False means the command must not run."""
        verdict, secs = cooldowns.before(user)
        if verdict == "ok":
            return True
        notice = None
        if verdict == "warn":
            notice = (f"@{user} slow down: wait for the bot to reply before sending "
                      "another command. Keep stacking and a short cooldown applies.")
        elif verdict == "cooldown":
            notice = (f"@{user} command cooldown {secs // 60}m {secs % 60}s: you kept "
                      "stacking commands after the warning.")
        # "drop": already told about the active cooldown; stay silent.
        if notice and message.channel:
            await message.channel.send(notice)
        return False

    @staticmethod
    def _finish_command(user) -> None:
        if user:
            cooldowns.after(user)

    async def _report_error(self, message, command, exc):
        if _backend_offline(exc):
            await message.channel.send(
                model_queue.availability_message("offline", command))
        elif _backend_rejected(exc):
            logging.warning(f"Local model rejected command {command}: {exc}")
            if _backend_model_missing(exc):
                state = "model_missing"
            else:
                state = "busy" if _backend_busy(exc) else "rejected"
            await message.channel.send(
                model_queue.availability_message(state, command, "both"))
        else:
            logging.error(
                "Error handling command %s", command,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            await message.channel.send(f"~{command} failed: internal error logged.")

    async def _run(self, message, command, params, handler):
        """Fast commands: run immediately."""
        try:
            await handler(self.bot, message, params)
        except Exception as e:
            await self._report_error(message, command, e)

    def model_queue_status(self) -> str:
        return model_queue.status()

    def clear_model_queue(self) -> int:
        return model_queue.clear_pending()

    async def _run_model_queued(
        self, message, command, params, handler, user, model_kind, capability
    ):
        """One shared lane for command invocations that use LM Studio."""
        sig = command + " " + " ".join(params).strip().lower()
        label = command + (" " + " ".join(params[:2]) if params else "")

        async def work():
            await handler(self.bot, message, params)

        try:
            await model_queue.submit(
                label=label,
                user=user,
                user_key=user,
                sig=sig,
                model_kind=model_kind,
                capability=capability,
                command=command,
                send=message.channel.send,
                work=work,
            )
        except Exception as e:
            await self._report_error(message, command, e)
