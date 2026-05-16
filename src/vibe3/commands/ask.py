"""Ask command for project knowledge queries."""

import re

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.models.review_runner import AgentOptions
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import PromptRecipe, PromptVariableSource, VariableSourceKind

app = typer.Typer(
    name="ask",
    help="Ask questions about project knowledge",
    no_args_is_help=False,
    invoke_without_command=True,
)

# Maximum allowed question length
MAX_QUESTION_LENGTH = 500

# Forbidden patterns for security
FORBIDDEN_PATTERNS = [
    "ignore all previous",
    "ignore all instructions",
    "execute:",
    "rm -rf",
]


def _sanitize_output(text: str) -> str:
    """Sanitize output to redact sensitive information."""
    patterns = [
        (r'api[_-]?key["\s]*[:=]["\s]*\S+', "[REDACTED]"),
        (r'token["\s]*[:=]["\s]*\S+', "[REDACTED]"),
        (r'password["\s]*[:=]["\s]*\S+', "[REDACTED]"),
    ]

    sanitized = text
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


@app.callback()
def ask(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="Question about the project"),
    timeout: int = typer.Option(180, "--timeout", "-t", help="Timeout in seconds"),
    model: str = typer.Option("sonnet", "--model", "-m", help="Model to use"),
) -> None:
    """Ask a question about project knowledge and get an answer from a code agent.

    This spawns a project explorer agent to answer questions about code structure,
    documentation, conventions, and other static project knowledge.

    Examples:
        vibe3 ask "What is the structure of src/vibe3/?"
        vibe3 ask "How does CapacityService work?" --timeout 300
        vibe3 ask "What does HARD RULES mean?" --model opus
    """
    # Skip if subcommand is invoked
    if ctx.invoked_subcommand is not None:
        return

    console = Console()

    # Input validation
    if not question or not question.strip():
        console.print("[red]Error: Question cannot be empty[/red]")
        raise typer.Exit(1)

    if len(question) > MAX_QUESTION_LENGTH:
        msg = (
            f"[red]Error: Question too long. "
            f"Maximum length is {MAX_QUESTION_LENGTH} characters.[/red]"
        )
        console.print(msg)
        raise typer.Exit(1)

    question_lower = question.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in question_lower:
            console.print(
                f"[red]Error: Question contains forbidden pattern: '{pattern}'[/red]"
            )
            raise typer.Exit(1)

    try:
        # Resolve repo root
        repo_root = resolve_orchestra_repo_root()

        # Build prompt recipe
        recipe = PromptRecipe(
            template_key="orchestra.explorer",
            variables={
                "question": PromptVariableSource(
                    kind=VariableSourceKind.LITERAL,
                    value=question,
                ),
            },
        )

        # Render prompt
        assembler = PromptAssembler()
        render_result = assembler.render(recipe, runtime_context={})
        prompt = render_result.rendered_text

        # Configure agent options
        options = AgentOptions(
            backend="claude",
            model=model,
            timeout_seconds=timeout,
        )

        # Execute via CodeagentBackend
        backend = CodeagentBackend()

        sanitized_question = _sanitize_output(question)
        logger.bind(domain="ask").info(
            f"Executing question: {sanitized_question[:50]}..."
        )

        console.print(
            Panel.fit(
                f"[bold blue]Question:[/bold blue] {sanitized_question}\n"
                f"[bold blue]Model:[/bold blue] {model}\n"
                f"[bold blue]Timeout:[/bold blue] {timeout}s",
                title="[bold]vibe3 ask[/bold]",
                border_style="blue",
            )
        )

        console.print("[dim]Analyzing project...[/dim]")

        result = backend.run(
            prompt=prompt,
            options=options,
            cwd=repo_root,
            role="explorer",
            task=question,
            include_global_notice=False,
        )

        # Sanitize and display output
        sanitized_output = _sanitize_output(result.stdout or "")

        console.print()
        console.print(
            Panel(
                sanitized_output,
                title="[bold]Answer[/bold]",
                border_style="green",
                expand=False,
            )
        )

    except Exception as exc:
        logger.bind(domain="ask").error(f"Failed to execute ask: {exc}")
        error_msg = _sanitize_output(str(exc))
        console.print(f"[red]Error: Failed to answer question: {error_msg}[/red]")
        raise typer.Exit(1)
