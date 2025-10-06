import sys
from pathlib import Path
import tempfile
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table
from datetime import datetime
import pandas as pd
# --- NEW IMPORT for UI File Picker ---
import tkinter as tk
from tkinter import filedialog

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.config import settings
from assistant.data_manager import DataManager
from llm.service import LLMService
from assistant.code_executor import CodeExecutor
from assistant.session_manager import SessionManager
from export.exporter import Exporter

class ChatWithDataApp:
    """The main application class for the Chat with Your Data assistant."""

    def __init__(self):
        self.console = Console()
        self.session_id = f"session_{datetime.now():%Y%m%d_%H%M%S}"
        self.session_output_dir = settings.OUTPUT_DIR / self.session_id
        self.session_output_dir.mkdir(parents=True, exist_ok=True)
        
        self.data_manager = DataManager()
        self.llm_service = LLMService()
        self.code_executor = CodeExecutor()
        self.session_manager = SessionManager()
        self.exporter = Exporter()
        
        self.console.print(f"[dim]Session started. Outputs will be saved in: {self.session_output_dir}[/dim]")

    def run(self):
        """The main application loop."""
        self.display_welcome()
        
        while True:
            try:
                action = Prompt.ask(
                    "\n[bold cyan]Choose an action[/bold cyan]",
                    choices=["load", "chat", "list", "export", "save", "load_session", "quit"],
                    default="chat"
                )
                
                if action == "load": self.load_dataset()
                elif action == "chat": self.chat()
                elif action == "list": self.list_session_info()
                elif action == "export": self.export_artifact()
                elif action == "save": self.save_session()
                elif action == "load_session": self.load_session()
                elif action == "quit":
                    if Confirm.ask("Are you sure you want to quit?"):
                        self.console.print("[green]Goodbye![/green]")
                        break
            
            except KeyboardInterrupt:
                if Confirm.ask("\n[yellow]Execution interrupted. Quit application?[/yellow]"): break
            except Exception as e:
                self.console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")

    def display_welcome(self):
        welcome_text = "# 🤖 Chat with Your Data\nAsk questions, generate analyses, and export results."
        self.console.print(Panel(Markdown(welcome_text), title="Welcome", border_style="cyan"))
        self.console.print(f"[dim]Using LLM: {self.llm_service.get_model_info()}[/dim]")
        exec_mode = 'Docker' if self.code_executor.use_docker else 'Subprocess'
        self.console.print(f"[dim]Execution Mode: {exec_mode}[/dim]")

    # --- THIS METHOD IS UPDATED ---
    def load_dataset(self):
        """Guides the user to load a CSV dataset from samples or a file picker."""
        self.console.print("\n[bold]Load Dataset[/bold]")
        csv_files = sorted(list(settings.DATA_DIR.glob("*.csv")))
        
        table = Table(title="Select a Data Source")
        table.add_column("Index", style="cyan")
        table.add_column("Source")
        
        for i, f in enumerate(csv_files, 1):
            table.add_row(str(i), f"Sample file: {f.name}")
        
        browse_index = len(csv_files) + 1
        table.add_row(str(browse_index), "Browse for a local CSV file...")
        
        self.console.print(table)
        
        choice = Prompt.ask("Select an option", default="1")
        filepath = None
        
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(csv_files):
                filepath = csv_files[choice_num - 1]
            elif choice_num == browse_index:
                filepath_str = self._open_file_dialog()
                if filepath_str:
                    filepath = Path(filepath_str)
            else:
                self.console.print("[red]Invalid selection.[/red]")
                return
        except ValueError:
            self.console.print("[red]Invalid selection. Please enter a number.[/red]")
            return

        if not filepath:
            self.console.print("[yellow]No file selected.[/yellow]")
            return

        try:
            with self.console.status("[bold green]Loading and analyzing CSV..."):
                schema = self.data_manager.load_csv(filepath)
            
            self.console.print(Panel(
                self.data_manager.format_schema_summary(schema['name']),
                title=f"✓ Dataset '{schema['name']}' Loaded Successfully",
                border_style="green"
            ))
        except Exception as e:
            self.console.print(f"[red]Error loading dataset: {e}[/red]")

    def _open_file_dialog(self) -> str:
        """Opens a native file dialog to select a CSV file."""
        self.console.print("[dim]Opening file browser...[/dim]")
        root = tk.Tk()
        root.withdraw()  # Hide the main tkinter window
        filepath = filedialog.askopenfilename(
            title="Select a CSV file",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        root.destroy()
        return filepath

    # ... (The rest of the file is unchanged from the last working version) ...
    def chat(self):
        if not self.data_manager.list_datasets():
            self.console.print("[yellow]No datasets loaded. Please use 'load' first.[/yellow]")
            return
        
        self.console.print("\n[bold]Chat with Your Data[/bold] ([dim]type 'back' to return[/dim])")
        while True:
            query = Prompt.ask("\n[bold green]You[/bold green]")
            if query.lower() in ['back', 'exit', 'quit']: break
            if not query.strip(): continue
            self.process_query(query)

    def process_query(self, query: str):
        try:
            intent = self.llm_service.detect_query_intent(query)
            
            if intent == 'question':
                with self.console.status("[bold]Answering..."):
                    answer = self.llm_service.answer_question(query, self.data_manager.get_all_schemas())
                self.console.print(Panel(Markdown(answer), title="Answer", border_style="blue"))
                return

            with self.console.status("[bold]1. Generating plan..."):
                plan = self.llm_service.generate_plan(query, self.data_manager.get_all_schemas(), self.session_manager.get_conversation_history())
            self.console.print(Panel(plan, title="Execution Plan", border_style="cyan"))
            if not Confirm.ask("Proceed?", default=True): return

            with self.console.status("[bold]2. Generating code..."):
                code = self.llm_service.generate_code(query, plan, self.data_manager.get_all_schemas(), self.session_manager.get_conversation_history())
            self.console.print(Panel(f"```python\n{code}\n```", title="Generated Code", border_style="magenta"))
            if not Confirm.ask("Execute?", default=True): return

            with self.console.status("[bold]3. Executing..."):
                temp_data_files = {}
                with tempfile.TemporaryDirectory() as temp_dir:
                    for name in self.data_manager.list_datasets():
                        temp_data_files[name] = self.data_manager.save_dataset_for_execution(name, Path(temp_dir))
                    result = self.code_executor.execute(code, temp_data_files, self.session_output_dir)

            if result.success:
                self.console.print("\n[bold green]✓ Execution Successful![/bold green]")
                if result.stdout: self.console.print(Panel(result.stdout, title="Text Output", border_style="green"))
                
                artifact_ids = []
                if result.output_files:
                    self.console.print("[bold]Generated Artifacts:[/bold]")
                    for file_type, file_path in result.output_files.items():
                        artifact = self.session_manager.create_artifact(file_type, file_path.suffix.lstrip('.'), file_path, query)
                        new_path = self.session_output_dir / f"{artifact.id}{file_path.suffix}"
                        file_path.rename(new_path)
                        artifact.path = new_path
                        artifact_ids.append(artifact.id)
                        self.console.print(f"  - `[{artifact.id}]` {file_type}: {new_path.name}")
                        if file_type == 'table' and file_path.suffix in ['.csv', '.xlsx']: self.preview_artifact(new_path)
                        elif file_type == 'chart': self.console.print(f"  [dim]Chart saved to {new_path}[/dim]")
                
                self.session_manager.add_interaction(query, plan, code, result.stdout, artifact_ids)
            else:
                self.console.print(Panel(f"{result.error}\n\n{result.stderr}", title="✗ Execution Failed", border_style="red"))
                self.session_manager.add_interaction(query, plan, code, f"ERROR: {result.error}", [])
        except Exception as e:
            self.console.print(f"[bold red]An unexpected error during processing: {e}[/bold red]")

    def preview_artifact(self, file_path: Path):
        try:
            if file_path.suffix == '.csv': df = pd.read_csv(file_path)
            elif file_path.suffix == '.xlsx': df = pd.read_excel(file_path)
            else: return
            table = Table(title=f"Preview of {file_path.name}", show_header=True, header_style="bold magenta")
            for col in df.columns: table.add_column(col)
            for _, row in df.head(5).iterrows(): table.add_row(*[str(item) for item in row])
            self.console.print(table)
        except Exception as e:
            self.console.print(f"[yellow]Could not generate preview for {file_path.name}: {e}[/yellow]")

    def list_session_info(self):
        self.console.print("\n[bold]Current Session Info[/bold]")
        datasets = self.data_manager.list_datasets()
        if datasets:
            dataset_table = Table(title="Loaded Datasets")
            dataset_table.add_column("Name", style="cyan"); dataset_table.add_column("Rows"); dataset_table.add_column("Columns")
            for name in datasets:
                schema = self.data_manager.get_schema(name)
                dataset_table.add_row(name, str(schema['shape']['rows']), str(schema['shape']['columns']))
            self.console.print(dataset_table)
        else: self.console.print("\n[dim]No datasets loaded.[/dim]")
        artifacts = self.session_manager.list_artifacts()
        if artifacts:
            artifact_table = Table(title="Generated Artifacts")
            artifact_table.add_column("Index", style="cyan"); artifact_table.add_column("ID"); artifact_table.add_column("Filename"); artifact_table.add_column("Status"); artifact_table.add_column("Generated By (Query)")
            for i, artifact in enumerate(artifacts, 1):
                status = "[green]Available[/green]" if artifact.path.exists() else "[bold red]Missing[/bold red]"
                query_preview = (artifact.query[:40] + '...') if len(artifact.query) > 40 else artifact.query
                artifact_table.add_row(str(i), artifact.id, artifact.path.name, status, query_preview)
            self.console.print(artifact_table)
        else: self.console.print("\n[dim]No artifacts generated yet.[/dim]")

    def export_artifact(self):
        artifacts = self.session_manager.list_artifacts()
        if not artifacts: self.console.print("[yellow]No artifacts to export.[/yellow]"); return
        self.list_session_info()
        choice = Prompt.ask("\nEnter the Index number of the artifact to convert")
        try:
            artifact = artifacts[int(choice) - 1]
            if not artifact.path.exists(): self.console.print(f"[bold red]Error: File '{artifact.path.name}' is missing.[/bold red]"); return
            target_format = Prompt.ask("Enter target format (e.g., 'xlsx')")
            with self.console.status(f"[bold]Converting..."):
                output_path = self.exporter.convert_format(artifact.path, target_format)
            self.console.print(f"[green]✓ Converted successfully to: {output_path}[/green]")
            self.session_manager.create_artifact('file', output_path.suffix.lstrip('.'), output_path, f"Converted from {artifact.id}")
        except (ValueError, IndexError): self.console.print("[red]Invalid selection.[/red]")
        except Exception as e: self.console.print(f"[red]Action failed: {e}[/red]")

    def save_session(self):
        if not self.session_manager.interactions: self.console.print("[yellow]No activity to save.[/yellow]"); return
        filename = Prompt.ask("Enter session filename", default=f"session_{datetime.now():%Y%m%d_%H%M}.json")
        filepath = self.session_output_dir / filename
        try:
            self.session_manager.save_session(filepath)
            self.console.print(f"[green]✓ Session saved to: {filepath}[/green]")
        except Exception as e: self.console.print(f"[red]Save failed: {e}[/red]")

    def load_session(self):
        session_files = sorted(list(settings.OUTPUT_DIR.glob("**/session_*.json")))
        if not session_files: self.console.print("[yellow]No saved sessions found.[/yellow]"); return
        table = Table(title="Available Sessions")
        table.add_column("Index", style="cyan"); table.add_column("File Path")
        for i, f in enumerate(session_files, 1): table.add_row(str(i), str(f))
        self.console.print(table)
        choice = Prompt.ask("Select session number to load")
        try:
            filepath = session_files[int(choice) - 1]
            self.session_manager.load_session(filepath)
            self.console.print(f"[green]✓ Session loaded from: {filepath}[/green]")
            self.list_session_info()
        except (ValueError, IndexError): self.console.print("[red]Invalid selection.[/red]")
        except Exception as e: self.console.print(f"[red]Load failed: {e}[/red]")

if __name__ == "__main__":
    app = ChatWithDataApp()
    app.run()