import typer
from typing import Optional
import importlib
import sys

app = typer.Typer(help="Edeon Data Curation Pipeline CLI", no_args_is_help=True)

SUPPORTED_ENDPOINTS = [
    "bee_acute_oral_ld50",
    "bee_acute_contact_ld50",
    "rat_acute_oral_ld50",
    "fish_acute_lc50",
    "daphnia_acute_ec50",
    "algae_growth_ec50",
    "earthworm_acute_lc50",
    "bird_acute_oral_ld50",
    "soil_koc",
    "soil_dt50",
    "bcf",
    "skin_sensitization"
]

@app.command(help="Run a pipeline stage for a specific endpoint.")
def run(
    endpoint: str = typer.Argument(..., help="Canonical endpoint name"),
    stage: str = typer.Argument(..., help="Pipeline stage to run (acquire, curate, split, card, all)")
):
    if endpoint == "release":
        from edeon_data.shared.release import run_release_pipeline
        typer.echo(">>> Running Edeon Release Pipeline (C & D)...")
        try:
            run_release_pipeline()
            typer.echo(">>> Release pipeline completed successfully.\n")
        except Exception as e:
            typer.echo(f"Error running release pipeline: {e}", err=True)
            import traceback
            traceback.print_exc()
            raise typer.Exit(code=1)
        return

    if endpoint not in SUPPORTED_ENDPOINTS:
        typer.echo(f"Error: Endpoint '{endpoint}' is not supported.", err=True)
        typer.echo(f"Supported endpoints: {', '.join(SUPPORTED_ENDPOINTS)}", err=True)
        raise typer.Exit(code=1)
        
    valid_stages = {"acquire", "curate", "split", "card", "all"}
    if stage not in valid_stages:
        typer.echo(f"Error: Stage '{stage}' is invalid.", err=True)
        typer.echo("Must be one of: acquire, curate, split, card, all", err=True)
        raise typer.Exit(code=1)

    # Convert endpoint name to package module name
    # e.g., bee_acute_oral_ld50 or bee_acute_contact_ld50 might share the 'bee' package
    module_mapping = {
        "bee_acute_oral_ld50": "bee",
        "bee_acute_contact_ld50": "bee",
        "rat_acute_oral_ld50": "rat_ld50",
        "fish_acute_lc50": "fish",
        "daphnia_acute_ec50": "daphnia",
        "algae_growth_ec50": "algae",
        "earthworm_acute_lc50": "earthworm",
        "bird_acute_oral_ld50": "bird",
        "soil_koc": "koc",
        "soil_dt50": "dt50",
        "bcf": "bcf",
        "skin_sensitization": "skin_sens"
    }
    
    module_name = module_mapping.get(endpoint, endpoint)
    
    try:
        # Dynamically import endpoints.<module_name>
        module_path = f"edeon_data.endpoints.{module_name}"
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        typer.echo(f"Pipeline module for '{endpoint}' not implemented or found at '{module_path}'.", err=True)
        raise typer.Exit(code=1)
        
    # Execute stage(s)
    stages_to_run = [stage] if stage != "all" else ["acquire", "curate", "split", "card"]
    
    for stg in stages_to_run:
        func_name = f"run_{stg}" if hasattr(mod, f"run_{stg}") else stg
        if not hasattr(mod, func_name):
            typer.echo(f"Error: Module '{module_path}' has no function '{func_name}' for stage '{stg}'.", err=True)
            raise typer.Exit(code=1)
            
        typer.echo(f">>> Running stage '{stg}' for endpoint '{endpoint}'...")
        try:
            func = getattr(mod, func_name)
            # Invoke the function (passing endpoint if the module handles multiple endpoints)
            if endpoint in ["bee_acute_oral_ld50", "bee_acute_contact_ld50"]:
                func(endpoint=endpoint)
            else:
                func()
            typer.echo(f">>> Stage '{stg}' completed successfully.\n")
        except Exception as e:
            typer.echo(f"Error running stage '{stg}' for '{endpoint}': {e}", err=True)
            import traceback
            traceback.print_exc()
            raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    list_endpoints: bool = typer.Option(False, "--list", help="List all available endpoints"),
    version: Optional[str] = typer.Option(None, "--version", help="Show pipeline version for the given endpoint")
):
    if list_endpoints:
        typer.echo("Available Endpoints:")
        for ep in SUPPORTED_ENDPOINTS:
            typer.echo(f" - {ep}")
        raise typer.Exit()
        
    if version:
        if version not in SUPPORTED_ENDPOINTS:
            typer.echo(f"Error: Unknown endpoint '{version}'.", err=True)
            raise typer.Exit(code=1)
        # For now, default version is 1.0.0
        typer.echo(f"Endpoint '{version}' pipeline version: 1.0.0")
        raise typer.Exit()
        
    if ctx.invoked_subcommand is None:
        # Show help if no subcommand is invoked
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
