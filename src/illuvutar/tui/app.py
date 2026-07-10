"""GodChatApp: Textual TUI for interacting with the God Agent."""
import httpx
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.containers import Horizontal, Vertical
from textual import work
from illuvutar.agents.god import GodAgent
from illuvutar.world_state.writer import WorldStateWriter


class WorldStatePanel(Static):
    def __init__(self, writer: WorldStateWriter, **kwargs):
        super().__init__(**kwargs)
        self._writer = writer

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)

    def refresh_status(self) -> None:
        status = self._writer.status()
        lines = ["[b]WORLD STATE[/b]\n"]
        for name, done in status.items():
            icon = "✓" if done else "○"
            lines.append(f"  {icon} {name}")
        self.update("\n".join(lines))


class GodChatApp(App):
    CSS = """
    #left { width: 2fr; }
    #right { width: 1fr; border-left: solid $primary; padding: 1; }
    #chat-log { height: 1fr; }
    Input { dock: bottom; }
    """

    def __init__(self, god_agent: GodAgent, writer: WorldStateWriter, engine_url: str = ""):
        super().__init__()
        self.god_agent = god_agent
        self.writer = writer
        self.engine_url = engine_url.rstrip("/")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left"):
                yield RichLog(id="chat-log", highlight=True, markup=True)
                yield Input(placeholder="Speak to the god...", id="input")
            yield WorldStatePanel(self.writer, id="right")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        # Show memory status if resuming a prior session
        prior_count = len([m for m in self.god_agent.messages if m.get("role") != "system"])
        if prior_count > 0:
            log.write(f"[bold green]Resuming previous session ({prior_count} messages in memory).[/bold green]")
        log.write("[bold yellow]God:[/bold yellow] I am awakened. What palette have you prepared for me?")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        self.query_one("#input", Input).value = ""
        log = self.query_one("#chat-log", RichLog)

        # /whisper <name> <message>
        if message.startswith("/whisper "):
            parts = message[9:].split(" ", 1)
            if len(parts) == 2 and self.engine_url:
                name, text = parts
                log.write(f"[bold magenta]Whisper → {name}:[/bold magenta] {text}")
                self._whisper_to_entity(name, text)
            else:
                log.write("[red]Usage: /whisper <entity_id> <message>[/red]")
            return

        # /thoughts — fetch recent thoughts from engine
        if message == "/thoughts":
            if self.engine_url:
                self._fetch_thoughts()
            else:
                log.write("[red]No engine URL configured. Start with --engine-url.[/red]")
            return

        log.write(f"[bold cyan]You:[/bold cyan] {message}")
        self._send_to_god(message)

    @work(thread=True)
    def _whisper_to_entity(self, entity_id: str, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        try:
            r = httpx.post(
                f"{self.engine_url}/entity/{entity_id}/say",
                json={"text": text},
                timeout=5,
            )
            if r.status_code == 200:
                self.call_from_thread(
                    log.write,
                    f"[dim]Whisper delivered to {entity_id}. They will respond in their next thought.[/dim]",
                )
            else:
                self.call_from_thread(log.write, f"[red]Engine error: {r.text}[/red]")
        except Exception as e:
            self.call_from_thread(log.write, f"[red]Cannot reach engine: {e}[/red]")

    @work(thread=True)
    def _fetch_thoughts(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        try:
            r = httpx.get(f"{self.engine_url}/thoughts", timeout=5)
            thoughts = r.json()
            if thoughts:
                lines = "\n".join(
                    f"  [purple]{t['entity_id']}[/purple]: {t['text']}" for t in thoughts[-10:]
                )
                self.call_from_thread(
                    log.write,
                    "[bold purple]Recent entity thoughts:[/bold purple]\n" + lines,
                )
            else:
                self.call_from_thread(log.write, "[dim]No thoughts recorded yet.[/dim]")
        except Exception as e:
            self.call_from_thread(log.write, f"[red]Cannot reach engine: {e}[/red]")

    @work(thread=True)
    def _send_to_god(self, message: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        self.call_from_thread(log.write, "[dim]God is contemplating…[/dim]")
        try:
            response = self.god_agent.chat(message)
        except Exception as e:
            self.call_from_thread(
                log.write,
                f"[red]The god does not answer (is the model running?): {e}[/red]",
            )
            return
        self.call_from_thread(log.write, f"[bold yellow]God:[/bold yellow] {response}")
        if self.god_agent.is_done():
            self.call_from_thread(log.write, "[bold green]The world is complete.[/bold green]")
