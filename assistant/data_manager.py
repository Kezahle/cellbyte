import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import warnings

from config.config import settings

class DataManager:
    """Manages CSV data loading, schema inference, and artifact tracking."""

    def __init__(self):
        self.datasets: Dict[str, pd.DataFrame] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.artifacts: List[str] = []

    def load_csv(self, filepath: Path, dataset_name: Optional[str] = None) -> Dict[str, Any]:
        """Loads a CSV file with robust delimiter/encoding detection and infers its schema."""
        if not filepath.exists():
            raise FileNotFoundError(f"CSV file not found: {filepath}")

        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        if file_size_mb > settings.MAX_CSV_SIZE_MB:
            raise ValueError(f"CSV file is too large: {file_size_mb:.2f}MB (max: {settings.MAX_CSV_SIZE_MB}MB)")

        if dataset_name is None:
            dataset_name = filepath.stem

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.readline()
                delimiter = ';' if header.count(';') > header.count(',') else ','
            df = pd.read_csv(filepath, sep=delimiter, on_bad_lines='warn', engine='python')
        except Exception:
            try:
                df = pd.read_csv(filepath, sep=None, on_bad_lines='warn', engine='python')
            except Exception as e:
                raise IOError(f"Could not parse CSV file '{filepath.name}'. Error: {e}")

        self.datasets[dataset_name] = df
        schema = self._infer_schema(df, dataset_name, filepath)
        self.schemas[dataset_name] = schema
        return schema

    def _infer_schema(self, df: pd.DataFrame, dataset_name: str, filepath: Path) -> Dict[str, Any]:
        """Infers a detailed schema from a DataFrame."""
        schema = {
            "name": dataset_name, "filepath": str(filepath),
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": list(df.columns), "dtypes": {}, "sample_values": {},
            "date_columns": [], "numeric_columns": [], "categorical_columns": [],
            "date_range": None
        }

        for col in df.columns:
            schema["dtypes"][col] = str(df[col].dtype)
            non_null_values = df[col].dropna()
            if not non_null_values.empty:
                schema["sample_values"][col] = [str(v)[:50] for v in non_null_values.head(3).tolist()]

            if pd.api.types.is_numeric_dtype(df[col]):
                schema["numeric_columns"].append(col)
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                schema["date_columns"].append(col)
            elif self._is_likely_date_column(df[col]):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        parsed_dates = pd.to_datetime(df[col], errors='coerce', dayfirst=True, yearfirst=False)
                    if parsed_dates.notna().sum() / len(df.index) > 0.7:
                        schema["date_columns"].append(col)
                        min_date, max_date = parsed_dates.min(), parsed_dates.max()
                        if pd.notna(min_date) and pd.notna(max_date) and schema["date_range"] is None:
                            schema["date_range"] = {"min": str(min_date.date()), "max": str(max_date.date())}
                    else:
                        schema["categorical_columns"].append(col)
                except Exception:
                    schema["categorical_columns"].append(col)
            else:
                schema["categorical_columns"].append(col)
        return schema

    def _is_likely_date_column(self, series: pd.Series) -> bool:
        if series.dtype != 'object': return False
        sample = series.dropna().head(10)
        if sample.empty: return False
        return sample.str.match(r'(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})|(\d{4})', na=False).sum() > 5

    def format_schema_summary(self, dataset_name: str) -> str:
        """Formats schema as a rich, detailed string for display."""
        schema = self.get_schema(dataset_name)
        lines = [
            f"Shape: {schema['shape']['rows']} rows × {schema['shape']['columns']} columns",
        ]
        if schema['date_range']:
            lines.append(f"Date Coverage: [cyan]{schema['date_range']['min']}[/cyan] to [cyan]{schema['date_range']['max']}[/cyan]")
        
        lines.append("\n[bold]Columns:[/bold]")
        for col in schema['columns']:
            dtype = schema['dtypes'][col]
            samples = schema.get('sample_values', {}).get(col, ['N/A'])
            sample_str = ", ".join(map(str, samples))
            lines.append(f"  - [bold]{col}[/bold] (type: {dtype}) | Samples: [dim]'{sample_str}'[/dim]")
        return "\n".join(lines)

    def get_schema_summary_for_llm(self) -> str:
        """Generates a concise string summary of all schemas for the LLM prompt."""
        if not self.schemas: return "No datasets loaded."
        summary = ""
        for name, schema in self.schemas.items():
            summary += f"Dataset: `{name}`\n"
            summary += f"  - Shape: {schema['shape']['rows']} rows, {schema['shape']['columns']} columns\n"
            summary += f"  - Columns: {', '.join(schema['columns'])}\n"
            samples = []
            for col in schema['columns'][:3]:
                sample_vals = schema.get('sample_values', {}).get(col, [])
                if sample_vals:
                    samples.append(f"{col}: {', '.join(sample_vals)}")
            if samples:
                summary += f"  - Sample Values: {'; '.join(samples)}\n\n"
        return summary.strip()

    def get_dataset(self, dataset_name: str) -> pd.DataFrame: return self.datasets[dataset_name]
    def get_schema(self, dataset_name: str) -> Dict[str, Any]: return self.schemas[dataset_name]
    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]: return self.schemas.copy()
    def list_datasets(self) -> List[str]: return list(self.datasets.keys())
    def save_dataset_for_execution(self, dataset_name: str, output_dir: Path) -> Path:
        df = self.get_dataset(dataset_name)
        output_path = output_dir / f"{dataset_name}.csv"
        df.to_csv(output_path, index=False, sep=',')  # Change to comma
        return output_path