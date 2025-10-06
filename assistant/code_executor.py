import subprocess
import tempfile
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from config.config import settings

@dataclass
class ExecutionResult:
    """Result from code execution."""
    success: bool
    stdout: str
    stderr: str
    output_files: Dict[str, Path]
    error: Optional[str] = None

class CodeExecutor:
    """Executes Python code in a sandboxed environment, preferring Docker if available."""

    def __init__(self):
        self.use_docker = settings.USE_DOCKER_EXECUTION
        if self.use_docker and not self.check_docker_available():
            print("[yellow]Warning: Docker execution is enabled, but Docker is not available. Falling back to subprocess.[/yellow]")
            self.use_docker = False

    # --- THIS IS THE CORRECTED METHOD SIGNATURE ---
    def execute(self, code: str, data_files: Dict[str, Path], session_output_dir: Path) -> ExecutionResult:
        """
        Executes Python code, routing to Docker or subprocess based on configuration.
        """
        if self.use_docker:
            return self._execute_docker(code, data_files, session_output_dir)
        else:
            return self._execute_subprocess(code, data_files, session_output_dir)

    def _execute_subprocess(self, code: str, data_files: Dict[str, Path], session_output_dir: Path) -> ExecutionResult:
        """Executes code in a local subprocess (less secure)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            # The sandbox output dir is now the session-specific one
            output_dir = temp_path / "output"
            data_dir.mkdir()
            output_dir.mkdir()

            code = self._prepare_code_for_local_execution(code, data_dir, output_dir)
            
            for name, filepath in data_files.items():
                shutil.copy(filepath, data_dir / f"{name}.csv")

            code_file = temp_path / "execute.py"
            code_file.write_text(code, encoding='utf-8')

            try:
                result = subprocess.run(
                    [sys.executable, str(code_file)],
                    capture_output=True, text=True, encoding='utf-8',
                    timeout=settings.CODE_EXECUTION_TIMEOUT,
                    env={"MPLBACKEND": "Agg"}
                )
                # Pass the final session directory to the collector
                output_files = self._collect_output_files(output_dir, session_output_dir)
                return ExecutionResult(
                    success=result.returncode == 0,
                    stdout=result.stdout, stderr=result.stderr,
                    output_files=output_files
                )
            except subprocess.TimeoutExpired:
                return ExecutionResult(False, "", "", {}, f"Execution timed out after {settings.CODE_EXECUTION_TIMEOUT}s")
            except Exception as e:
                return ExecutionResult(False, "", "", {}, f"Subprocess execution error: {e}")

    def _execute_docker(self, code: str, data_files: Dict[str, Path], session_output_dir: Path) -> ExecutionResult:
        """Executes code in a secure Docker container."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            # The sandbox output dir is now the session-specific one
            output_dir = temp_path / "output"
            data_dir.mkdir()
            output_dir.mkdir()

            for name, filepath in data_files.items():
                shutil.copy(filepath, data_dir / f"{name}.csv")

            (temp_path / "execute.py").write_text(code, encoding='utf-8')
            (temp_path / "requirements.txt").write_text("pandas\nmatplotlib\nseaborn\nopenpyxl")

            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "1.0",
                "-v", f"{temp_path}:/workspace",
                "-w", "/workspace",
                settings.DOCKER_IMAGE,
                "sh", "-c", "pip install -r requirements.txt > /dev/null && python execute.py"
            ]

            try:
                result = subprocess.run(
                    docker_cmd, capture_output=True, text=True, encoding='utf-8',
                    timeout=settings.CODE_EXECUTION_TIMEOUT + 30
                )
                # Pass the final session directory to the collector
                output_files = self._collect_output_files(output_dir, session_output_dir)
                return ExecutionResult(
                    success=result.returncode == 0,
                    stdout=result.stdout, stderr=result.stderr,
                    output_files=output_files
                )
            except subprocess.TimeoutExpired:
                return ExecutionResult(False, "", "", {}, f"Docker execution timed out after {settings.CODE_EXECUTION_TIMEOUT}s")
            except Exception as e:
                return ExecutionResult(False, "", "", {}, f"Docker execution error: {e}")

    def _prepare_code_for_local_execution(self, code: str, data_dir: Path, output_dir: Path) -> str:
        """Replaces placeholder paths for local execution."""
        code = code.replace("'/data/", f"r'{str(data_dir)}/")
        code = code.replace('"/data/', f'r"{str(data_dir)}/')
        code = code.replace("'/output/", f"r'{str(output_dir)}/")
        code = code.replace('"/output/', f'r"{str(output_dir)}/')
        return code

    def _collect_output_files(self, source_dir: Path, dest_dir: Path) -> Dict[str, Path]:
        """Moves files from the sandbox output to the final session output directory."""
        output_files = {}
        type_map = {'.png': 'chart', '.jpg': 'chart', '.csv': 'table', '.xlsx': 'table'}
        
        for file_path in source_dir.iterdir():
            if file_path.is_file():
                file_type = type_map.get(file_path.suffix.lower(), 'file')
                dest_path = dest_dir / file_path.name
                shutil.move(file_path, dest_path)
                output_files[file_type] = dest_path
        return output_files

    def check_docker_available(self) -> bool:
        """Checks if the Docker command is available on the system."""
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False