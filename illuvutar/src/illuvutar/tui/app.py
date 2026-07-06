"""GodChatApp: Textual TUI for interacting with the God Agent."""
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

    def __init__(self, god_agent: GodAgent, writer: WorldStateWriter):
        super().__init__()
        self.god_agent = god_agent
        self.writer = writer

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
        log.write("[bold yellow]God:[/bold yellow] I am awakened. What palette have you prepared for me?")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        self.query_one("#input", Input).value = ""
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {message}")
        self._send_to_god(message)

    @work(thread=True)
    def _send_to_god(self, message: str) -> None:
        response = self.god_agent.chat(message)
        log = self.query_one("#chat-log", RichLog)
        self.call_from_thread(log.write, f"[bold yellow]God:[/bold yellow] {response}")
        if self.god_agent.is_done():
            self.call_from_thread(log.write, "[bold green]The world is complete.[/bold green]")
