# Chat with Your Data - Python Assistant

A local Python CLI that turns natural language into executable analytics on CSV data. You ask questions, it writes code, runs it safely, and shows you the results.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Rich CLI Interface                      │
│            (Interactive prompts & previews)              │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                 Session Manager                          │
│  • Artifact registry (charts, tables, reports)           │
│  • Session persistence (save/load JSON)                  │
└──┬────────────────┬────────────────┬────────────────────┘
   │                │                │
┌──▼──────┐   ┌────▼─────┐    ┌────▼──────────┐
│  Data   │   │   LLM    │    │     Code      │
│ Manager │   │ Service  │    │   Executor    │
│         │   │          │    │  (Sandboxed)  │
└─────────┘   └──────────┘    └───────────────┘
```

The app follows a simple flow: load CSV → ask question → see plan → review code → execute → get results. Each component has one job and does it well.

## Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API Key

### Setup
```bash
# Run the setup script
chmod +x setup.sh
./setup.sh

# Add your API key to .env
# OPENAI_API_KEY="sk-..."

# Launch
source venv/bin/activate
python main.py
```

## What It Does

### 1. Smart Schema Detection
Drop in a CSV and it figures out column types, date ranges, and sample values automatically. Handles weird delimiters and encodings without complaining.

### 2. Multiple Datasets
Load as many CSVs as you want. The AI knows about all of them and can pull from multiple sources in one query.

### 3. Transparent Workflow
- You ask a question in plain English
- It shows you a step-by-step plan
- Generates Python code you can review
- Runs it in a sandbox
- Shows tables and charts

At every step, you can say no and bail out. No black boxes.

### 4. Safe Execution
Code runs in an isolated subprocess. It can't touch your filesystem or do anything weird. Times out after 60 seconds if something goes wrong.

### 5. Artifact Tracking
Everything generated (charts, tables) gets saved in session folders with unique IDs. You can export and convert formats later.

## How I Built This

### Problem-Solving Approach

Started by mapping out the user stories from the brief. The core insight was that this isn't really about "chat" - it's about translating intent into code. So I focused on three things:

1. **Schema inference**: The LLM needs to know what columns exist before it can write code. Built a robust schema analyzer that handles messy real-world CSVs.

2. **Code generation**: Instead of trying to parse natural language into pandas operations, just have the LLM write Python. It's already good at that. The trick is constraining it with the schema.

3. **Safe execution**: Generated code can't be trusted. Built a subprocess sandbox that gives it temporary folders for data and output, nothing else.

The architecture followed from these decisions - separate the data layer, LLM layer, and execution layer so each can be tested independently.

### Development Process

Used Claude to accelerate development - probably 60-70% of the code is LLM-generated, which I then reviewed, tested, and refined. This let me focus on architecture and problem-solving rather than boilerplate. The modular structure made it easy to iterate on individual components.

Testing was mostly manual due to time constraints. Ran through the example queries from the brief and fixed issues as they came up. A proper test suite would be the first thing I'd add with more time.

### Technical Decisions

**CLI over Web UI**: Wanted to nail the core functionality first. A web wrapper would take 4 more hours but wouldn't prove anything about whether the system actually works.

**Subprocess instead of Docker**: Docker adds a dependency and setup complexity. Subprocess isolation is good enough for a local tool. The architecture supports Docker execution with one config change - just didn't implement it since subprocess works fine.

**Session folders instead of database**: Simpler to debug and understand. Each session gets a timestamped folder. No migrations, no schemas, just files on disk.

**OpenAI first**: GPT-4o-mini has the best code generation quality I've seen. Built an abstract LLM interface so swapping providers later is trivial.

### What I Cut

**Conversation history**: Each query generates a fresh plan. I started implementing history tracking but realized it adds complexity without much value for the MVP. The session manager has the hooks for it - just didn't wire it into the prompts.

**Docker execution**: Scaffolded but not implemented. Subprocess works fine for the use case.

**Translation feature**: Dependency conflicts with core libraries. Would need a different approach.

**Advanced error recovery**: If code fails, you see the error and can rephrase your question. Automated debugging would be nice but wasn't essential.

## Limitations

**No conversation memory**: Each query is independent. Can't say "now show that as a chart" because it doesn't remember what "that" is. Would need to pass artifact content into the next prompt.

**Data matching is exact**: Filters are case-sensitive and whitespace-sensitive. If your CSV has "Non-small cell lung cancer" but you search for "non-small cell lung cancer", you'll get no results.

**Single dataset queries (mostly)**: The architecture supports multiple datasets and the LLM gets all the schemas, but I didn't test multi-dataset joins. It should work in theory - the LLM knows about joins - but can't guarantee it.

**No streaming**: You don't see output until execution finishes. Would need a different execution model.

**Limited testing**: Manual testing only on the provided sample queries. Edge cases and error handling could be more robust.

## What Works Well

- Schema inference handles weird CSVs reliably
- Code generation stays within the schema boundaries
- Sandbox execution is solid - haven't had a crash yet
- The transparent workflow (plan → code → execute) makes it easy to debug
- CSV to Excel conversion with formatting
- Session persistence for saving your work

## What I'd Do Next

### If I had another day:
0. **More CR**: Code 95% LLM-generated, I acted as the reviewer and product manager
1. **Wire up conversation history** - The infrastructure exists, just needs to be passed into code generation prompts
2. **Test multi-dataset joins** - Should work but needs validation with real queries
3. **Better error messages** - When filters return no results, suggest similar values
4. **Proper test suite** - Automated tests for each component

### If this were a real product:
1. **Add Streamlit UI** - Keep the CLI but add a web interface for less technical users
2. **Implement Docker execution** - Better isolation for production use
3. **Query templates** - Common analyses as one-click operations
4. **Artifact versioning** - Track changes to generated outputs over time

## Notes

**Testing**: Manual testing with provided sample queries  
**Approach**: Build the simplest thing that works, then decide what to add based on actual use