from pathlib import Path

import typer

from sarmesh.diagnostics import configure_logging, report_fatal_error
from sarmesh.storage.database import Database
from sarmesh.storage.paths import default_database_path

app = typer.Typer(help="SARMesh command line interface")


@app.callback()
def _setup() -> None:
    # Runs ahead of every subcommand, so a source checkout gets the same log
    # file as a packaged build without each command wiring it up itself.
    configure_logging()


incident_app = typer.Typer(help="Manage incidents")
team_app = typer.Typer(help="Manage teams")
tracker_app = typer.Typer(help="Manage trackers")

app.add_typer(incident_app, name="incident")
app.add_typer(team_app, name="team")
app.add_typer(tracker_app, name="tracker")


def get_database() -> Database:
    database = Database(default_database_path())
    database.migrate()
    return database


@incident_app.command("create")
def create_incident(
    name: str,
) -> None:
    database = get_database()

    incident = database.incidents.create(name=name)

    typer.echo(f"Created incident {incident.id}: {incident.name}")


@team_app.command("create")
def create_team(
    name: str,
    personnel: int = typer.Option(
        1,
        "--personnel",
        "-p",
        help="Number of personnel in the team",
    ),
) -> None:
    database = get_database()

    team = database.teams.create(
        name=name,
        personnel_count=personnel,
    )

    typer.echo(f"Created team {team.id}: {team.name}")


@tracker_app.command("add")
def add_tracker(
    node_id: str,
    label: str,
) -> None:
    database = get_database()

    tracker = database.trackers.create(
        node_id=node_id,
        label=label,
    )

    typer.echo(f"Added tracker {tracker.label} ({tracker.node_id})")


@tracker_app.command("assign")
def assign_tracker(
    node_id: str,
    team_id: str,
    incident_id: str,
) -> None:
    database = get_database()

    database.assignments.create(
        incident_id=incident_id,
        tracker_node_id=node_id,
        team_id=team_id,
    )

    typer.echo(f"Assigned {node_id} to team {team_id} for incident {incident_id}")


@app.command("app")
def desktop_app(
    basemap: Path | None = typer.Option(
        None,
        "--basemap",
        "-m",
        help="MBTiles file to serve as the offline basemap",
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Reach the radio over TCP instead of USB serial",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="TCP port for --host (default 4403)",
    ),
    http_port: int | None = typer.Option(
        None,
        "--http-port",
        help="Port for the local UI server (default 8000, or any free port)",
    ),
    browser: bool = typer.Option(
        False,
        "--browser",
        help="Serve only and print the URL; do not open a native window",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Do not connect to a radio (view and edit stored data only)",
    ),
) -> None:
    """Launch the SARMesh desktop app."""
    from sarmesh.app import DesktopApp

    if basemap is not None and not basemap.is_file():
        report_fatal_error(f"Basemap not found: {basemap}")
        raise typer.Exit(1)

    desktop = DesktopApp(
        database_path=default_database_path(),
        port=http_port,
        basemap=basemap,
        radio_host=host,
        radio_port=port,
        offline=offline,
    )

    try:
        desktop.run(window=not browser)
    except ConnectionError as error:
        report_fatal_error(str(error))
        raise typer.Exit(1) from error


@app.command("run")
def run(
    host: str | None = typer.Option(
        None,
        "--host",
        "-H",
        help="Reach the node over TCP instead of USB serial",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="TCP port for --host (default 4403)",
    ),
) -> None:
    from sarmesh.services.tracking import TrackingService
    from sarmesh.transports.meshtastic import MeshtasticTransport

    database = get_database()
    tracking_service = TrackingService(
        database=database,
    )

    transport = MeshtasticTransport(
        on_position=tracking_service.handle_position,
        host=host,
        port=port,
    )

    try:
        transport.run()
    except ConnectionError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    finally:
        database.close()
