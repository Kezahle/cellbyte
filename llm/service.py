from typing import List, Dict, Any, Optional

from config.config import settings
from llm.base import LLMProvider, Message
from llm.openai_provider import OpenAIProvider

class LLMService:
    """
    A high-level service for interacting with the LLM.
    It handles prompt engineering, intent detection, and orchestrates calls
    to the underlying LLM provider.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        if provider:
            self.provider = provider
        else:
            self.provider = OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL
            )

    def detect_query_intent(self, query: str) -> str:
        """Detects the user's intent using a fast, rule-based approach."""
        query_lower = query.lower().strip()
        
        meta_question_indicators = [
            'what can you', 'what could you', 'what kind of analysis', 'what is possible',
            'help me', 'what are my options', 'what should i ask', 'what can we analyze'
        ]
        question_indicators = [
            'what is', 'what are', 'tell me about', 'explain', 'describe',
            'can you explain', 'what does', 'what do', 'what data'
        ]
        analysis_indicators = [
            'calculate', 'compute', 'find the', 'show me the', 'plot', 'chart', 'graph',
            'analyze', 'compare', 'average', 'sum of', 'count the', 
            'group by', 'filter', 'list all', 'display the', 'visualize'
        ]
        
        if any(indicator in query_lower for indicator in meta_question_indicators):
            return 'question'
        if any(indicator in query_lower for indicator in analysis_indicators):
            return 'analysis'
        if any(indicator in query_lower for indicator in question_indicators):
            return 'question'
        return 'analysis'

    def answer_question(self, query: str, available_datasets: Dict[str, Any]) -> str:
        """Answers a direct question about the data's schema or capabilities without generating code."""
        dataset_context = "\n\n## Available Datasets:\n"
        for name, schema in available_datasets.items():
            dataset_context += f"\n### Dataset: `{name}`\n"
            dataset_context += f"- Shape: {schema['shape']['rows']} rows × {schema['shape']['columns']} columns\n"
            dataset_context += f"- Columns: {', '.join(schema['columns'])}\n"

        system_prompt = """
You are a helpful data assistant. Your job is to answer questions about the available datasets.
- Describe the dataset's structure (columns, rows).
- Explain what kind of information the data likely contains based on the schema.
- Suggest 3-5 specific, actionable analysis examples that are possible with the data, referencing real column names.
- Be conversational, clear, and concise.
"""
        
        user_prompt = f"Question: {query}\n{dataset_context}"
        messages = [Message(role="system", content=system_prompt), Message(role="user", content=user_prompt)]
        response = self.provider.generate(messages, temperature=0.2)
        return response.content

    def generate_plan(self, query: str, available_datasets: Dict[str, Any], conversation_history: List[Dict]) -> str:
        """Generates a step-by-step execution plan for an analysis query."""
        history_context = ""
        if conversation_history:
            history_context = "\n\n## Recent Conversation History:\n"
            for interaction in conversation_history[-settings.HISTORY_LIMIT:]:
                history_context += f"- User asked: \"{interaction['query']}\"\n"

        dataset_context = "\n\n## Available Datasets:\n"
        for name, schema in available_datasets.items():
            dataset_context += f"\n### Dataset: `{name}`\n"
            dataset_context += f"- Columns: {', '.join(schema['columns'])}\n"
        
        system_prompt = """
You are a data analysis planning assistant. Create a clear, step-by-step plan to answer the user's query based *only* on the provided schemas.
1.  Identify the necessary dataset(s) and the real columns needed.
2.  Describe the main analysis steps (e.g., filter, group, aggregate, join).
3.  Specify the final output (e.g., a table, a bar chart, a single number).
4.  If a column is not in the schema, you cannot use it.
5.  Keep the plan concise and grounded in the provided data.
Return ONLY the plan as a numbered list.
"""
        
        user_prompt = f"Query: {query}\n{dataset_context}\n{history_context}"
        messages = [Message(role="system", content=system_prompt), Message(role="user", content=user_prompt)]
        response = self.provider.generate(messages, temperature=0.0)
        return response.content

    def generate_code(self, query: str, plan: str, available_datasets: Dict[str, Any], conversation_history: List[Dict] = None) -> str:
        """Generates code that respects user-defined output formats."""
        
        # Add history context
        history_context = ""
        if conversation_history:
            history_context = "\n\n## Recent Conversation Context:\n"
            for interaction in conversation_history[-3:]:  # Last 3 interactions
                history_context += f"- Previous query: \"{interaction['query']}\"\n"
                history_context += f"- Generated artifacts: {', '.join(interaction.get('artifacts', []))}\n"
        

        dataset_info = "\n\n## Data Loading Instructions:\n"
        dataset_info += "The datasets are available in the `/data` directory inside the execution environment.\n"
        dataset_info += "Load them using the following commands:\n\n"
        for name in available_datasets.keys():
            var_name = f"df_{name.replace('-', '_').replace(' ', '_')}"
            dataset_info += f"# Load the '{name}' dataset\n"
            dataset_info += f"{var_name} = pd.read_csv('/data/{name}.csv')\n\n"

        system_prompt = """
You are an expert Python data analyst. Write a single, executable Python script.

**Requirements:**
1.  Start with necessary imports (`pandas`, `matplotlib.pyplot`, `seaborn`, `openpyxl`).
2.  Load data as specified in the Data Loading Instructions.
3.  Implement the logic from the plan. Use only real column names from the schemas.
4.  **Output Handling (CRITICAL):**
    - The user may specify a format in their query (e.g., "as an excel file", "in a csv").
    - If the user asks for **Excel**, save the final DataFrame to `/output/table.xlsx` using `df.to_excel(..., index=False)`.
    - If the user asks for **CSV** or doesn't specify, save to `/output/table.csv` using `df.to_csv(..., index=False)`.
    - For **charts/plots**, always save them to `/output/chart.png` using `plt.savefig()`.
    - Print any key metrics or text summaries to the console using `print()`.
5.  Return ONLY the raw Python code, with no explanations or markdown.
"""
        
        user_prompt = f"Query: {query}\n\nPlan:\n{plan}\n{dataset_info}\n{history_context}"
        messages = [Message(role="system", content=system_prompt), Message(role="user", content=user_prompt)]
        response = self.provider.generate(messages, temperature=0.0, max_tokens=2500)
        
        code = response.content.strip()
        if code.startswith("```python"): code = code.split("```python\n", 1)[1]
        if code.endswith("```"): code = code.rsplit("\n```", 1)[0]
        return code.strip()

    def get_model_info(self) -> str:
        return f"{self.provider.__class__.__name__} - {self.provider.get_model_name()}"