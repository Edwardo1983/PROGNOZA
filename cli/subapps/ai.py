from __future__ import annotations

import json
from pathlib import Path

import typer

from ai.orchestrator import AIOrchestrator

from ..common import console, ensure_dir
from ..i18n import t

ai_app = typer.Typer(help='AI orchestrator helpers')


def _load_json(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


@ai_app.command('decide')
def decide(ctx: Path = typer.Argument(..., exists=True)) -> None:
    context = _load_json(ctx)
    orchestrator = AIOrchestrator()
    result = orchestrator.select_model(context)
    console().print(t('ai.decision', choice=result['choice'], confidence=result.get('confidence', 0.0)))
    console().print(json.dumps(result, indent=2))


@ai_app.command('explain')
def explain(ctx: Path = typer.Argument(..., exists=True), out: Path = typer.Option(Path('reports/explain.md'))) -> None:
    context = _load_json(ctx)
    orchestrator = AIOrchestrator()
    markdown = orchestrator.explain_forecast(context)
    out = ensure_dir(out)
    out.write_text(markdown, encoding='utf-8')
    console().print(t('ai.explain.saved', path=str(out)))


@ai_app.command('drift')
def drift(ref: Path = typer.Option(..., exists=True), cur: Path = typer.Option(..., exists=True), out: Path = typer.Option(Path('reports/drift.md'))) -> None:
    orchestrator = AIOrchestrator()
    context = {
        'reference_stats': _load_json(ref),
        'current_stats': _load_json(cur),
    }
    summary = orchestrator.summarize_drift(context)
    markdown = summary.get('narrative_md', '')
    out = ensure_dir(out)
    out.write_text(markdown, encoding='utf-8')
    console().print(t('ai.drift.saved', path=str(out)))

