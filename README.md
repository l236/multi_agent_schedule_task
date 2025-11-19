# Multi-Agent Schedule Task Framework

A lightweight agent task scheduling system for automating complex multi-step tasks. This framework supports process decomposition, automatic tool invocation, dynamic execution adjustments, and solves automation problems for multi-step tasks.

## Features

- **YAML Configuration**: Define task flows through YAML configuration files, specifying step sequences (serial/parallel), dependencies, tools per step, and parameters
- **Tool Registration**: Dynamic tool registration mechanism (`register_tool("doc_parse", DocParseTool)`) - new tools don't require modifying core framework, just implement standard interface `run(input, context)`
- **Context Management**: Saves intermediate results across the entire flow, supports cross-step data passing, includes expiration cleanup mechanism
- **Exception Handling**: Supports automatic retry (configurable count and interval), fallback tool switching, dynamic flow adjustment (conditional branching)
- **Observability**: Records input/output for each step, execution time, provides execution results, flow diagrams, and execution logs
- **Multi-Agent Collaboration** (Bonus): Supports multi-agent collaboration for task division and execution
- **Priority Scheduling** (Bonus): High-priority task preemption resource scheduling

## Architecture

```
multi_agent_schedule_task/
├── __init__.py              # Main package exports
├── scheduler.py             # Core task scheduler
├── registry.py              # Tool registration system
├── context.py               # Context management
├── config.py                # YAML configuration parser
└── tools/                   # Tool implementations
    ├── __init__.py
    ├── doc_parser.py        # Document parsing tool
    ├── retrieval.py         # Information retrieval tool
    ├── generation.py        # Content generation tool
    ├── http_fetcher.py      # HTTP web fetching tool
    ├── web_analyzer.py      # Web content analysis tool
    ├── text_exporter.py     # Text file exporter tool
    └── pdf_exporter.py      # PDF file exporter tool
```

## Installation

### Option 1: Install with Conda (Recommended for Data Science)

```bash
# Clone or download the repository
git clone <repository-url>
cd multi-agent-schedule-task

# Option A: Use the provided environment file (recommended)
conda env create -f environment.yml
conda activate multi-agent-scheduler

# Option B: Manual environment creation
conda create -n task-scheduler python=3.9
conda activate task-scheduler

# Install conda-available packages
conda install -c conda-forge python-dotenv pyyaml fastapi uvicorn pydantic

# Install pip-only packages (autogen, langchain)
pip install langchain>=0.2.0 autogen>=0.8.0

# Install the package in development mode
pip install -e .
```

**Note**: Uses hybrid conda + pip approach since some packages (autogen, langchain) are only available via pip.

### Option 2: Install with Pip

```bash
# Clone or download the repository
git clone <repository-url>
cd multi-agent-schedule-task

# Install in development mode
pip install -e .

# Or create and install distribution package
python setup.py sdist bdist_wheel
pip install dist/multi-agent-schedule-task-1.0.0.tar.gz
```

### Option 3: Install from PyPI (when published)
```bash
pip install multi-agent-schedule-task
# or
conda install -c conda-forge multi-agent-schedule-task
```

### With Extras
```bash
# For API server
pip install -e .[api]

# For Django integration
pip install -e .[django]

# For development
pip install -e .[dev]
```

## Dependencies

Core dependencies (automatically installed):
- langchain>=0.2.0: Agent foundation framework
- autogen>=0.8.0: Multi-agent collaboration
- python-dotenv>=1.0.0: Environment configuration
- pyyaml>=6.0: YAML configuration support
- requests>=2.0.0: HTTP requests for web fetching
- beautifulsoup4>=4.0.0: HTML parsing and analysis
- lxml>=4.0.0: XML/HTML processing backend
- reportlab>=4.0.0: PDF generation

Optional dependencies:
- fastapi>=0.100.0, uvicorn>=0.20.0: For HTTP API server
- Django>=4.0, djangorestframework>=3.14: For Django integration
- pytest>=7.0, black>=22.0, flake8>=5.0: For development

## Quick Start

### 1. Define Task Flow (YAML)

```yaml
name: "Contract Analysis Pipeline"
description: "Automated pipeline for parsing contracts, retrieving regulations, and generating analysis reports"

steps:
  - id: parse_contract
    name: "Parse Contract Document"
    tool: "doc_parser"
    parameters:
      file_path: "contract.txt"
    retry_count: 2

  - id: retrieve_regulations
    name: "Retrieve Relevant Regulations"
    tool: "retrieval"
    parameters:
      query: "contract law regulatory compliance"
    dependencies: ["parse_contract"]

  - id: generate_analysis
    name: "Generate Analysis Report"
    tool: "generation"
    parameters:
      type: "analysis"
      data:
        subject: "Contract Compliance Analysis"
    dependencies: ["parse_contract", "retrieve_regulations"]

parallel_groups:
  - ["retrieve_regulations", "generate_analysis"]
```

### 2. Implement and Register Tools

```python
from multi_agent_schedule_task import ToolRegistry, BaseTool

class DocParseTool(BaseTool):
    @property
    def name(self) -> str:
        return "doc_parser"

    @property
    def description(self) -> str:
        return "Parses documents and extracts text content"

    def run(self, input_data, context):
        # Implementation
        pass

# Register tool
registry = ToolRegistry()
registry.register_tool("doc_parser", DocParseTool)
```

### 3. Configure Email Server Integration (Optional)

For automated email processing, configure email server access:

```yaml
steps:
  - id: fetch_emails
    tool: "doc_parser"
    parameters:
      email_config:
        server: "imap.gmail.com"
        port: 993
        username: "your-email@example.com"
        password: "your-app-password"
        mailbox: "INBOX"
        search_criteria: "UNSEEN FROM legal@company.com"
        max_emails: 10
        mark_as_read: true
```

### 3. Execute Task

```python
import asyncio
from multi_agent_schedule_task import TaskScheduler, ToolRegistry, ContextManager
from multi_agent_schedule_task.config import ConfigParser

async def main():
    # Initialize components
    tool_registry = ToolRegistry()
    context_manager = ContextManager()
    scheduler = TaskScheduler(tool_registry, context_manager)

    # Register tools
    # ... register your tools

    # Load and execute configuration
    config = ConfigParser.parse_config("task_config.yaml")
    result = await scheduler.execute_task(config)

    print(f"Task completed: {result.success}")

asyncio.run(main())
```

## Tool Interface

All tools must inherit from `BaseTool` and implement:

```python
class BaseTool(ABC):
    @abstractmethod
    def run(self, input_data: Any, context: Dict[str, Any]) -> Any:
        """Execute tool with input data and shared context."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
```

## Configuration Schema

### Task Flow Configuration

```yaml
name: string                    # Task name
description: string            # Task description
steps:                         # List of steps
  - id: string                 # Unique step identifier
    name: string              # Human-readable name
    tool: string              # Tool name to execute
    parameters: dict          # Tool parameters
    dependencies: list        # Step dependencies
    retry_count: int          # Retry attempts (default: 3)
    retry_delay: float        # Delay between retries (default: 1.0)
    fallback_tools: list      # Fallback tools on failure
    condition: string         # Execution condition
parallel_groups: list         # Groups of parallel steps
```

### Parameter Interpolation

You can reference outputs from previous steps using the syntax `${step_id.field}`:

```yaml
steps:
  - id: fetch_page
    tool: "http_fetcher"
    parameters:
      url: "https://example.com"
  
  - id: analyze
    tool: "web_analyzer"
    parameters:
      content: "${fetch_page.content}"  # References previous step output
    dependencies: ["fetch_page"]
  
  - id: export
    tool: "text_exporter"
    parameters:
      filename: "output.txt"
      content: |
        URL: ${fetch_page.url}
        Title: ${fetch_page.title}
        Summary: ${analyze.summary}
    dependencies: ["fetch_page", "analyze"]
```

The scheduler automatically resolves these references when executing steps.

## Example Tools

### Document Parser
Parses documents (PDF, email, plain text) and extracts text content.
- Supports email attachments and server-based email fetching
- Detects file types and applies appropriate parsing

### Retrieval Tool
Retrieves relevant information based on queries from a knowledge base.

### Generation Tool
Generates content such as reports, summaries, and analysis.

### HTTP Fetcher (New)
Fetches content from URLs and extracts normalized text.
- Supports HTML parsing and content extraction
- Returns page title, content, and metadata
- Example usage: web scraping and data collection

### Web Analyzer (New)
Analyzes text content and extracts structured information.
- Generates summaries of text
- Extracts keywords using frequency analysis
- Identifies links (HTTP/HTTPS URLs)
- Example usage: content analysis and information extraction

### Text Exporter (New)
Exports text content to `.txt` files.
- Useful for saving reports and analysis results
- Supports parameter interpolation from previous steps

### PDF Exporter
Exports text content to PDF files using ReportLab.
- Handles text wrapping and formatting
- Example usage: generating PDF reports

## Deployment Options

### 1. Python Package Distribution

The framework is delivered as a standard Python package that can be installed via pip:

```bash
# Create distribution package
python setup.py sdist bdist_wheel

# Install from local package
pip install dist/multi-agent-schedule-task-1.0.0.tar.gz
```

### 2. HTTP API Service

Run as a REST API service using FastAPI:

```bash
# Install API dependencies
pip install -e .[api]

# Start API server
python api_service.py

# Or use the installed command
task-api
```

The API provides endpoints for:
- `POST /tasks/execute` - Execute tasks synchronously or asynchronously
- `GET /tasks/{task_id}` - Check task status
- `GET /tools` - List available tools
- `POST /files/upload` - Upload files for processing
- `POST /config/validate` - Validate configurations

### 3. Command Line Interface

Use the CLI for direct execution:

```bash
# Install package
pip install -e .

# Run task
task-scheduler example_config.yaml

# With options
task-scheduler config.yaml --log-level DEBUG --max-workers 8 --output-format json
```

### 4. Framework Integration

Integrate into existing applications:

#### Django Integration
```python
# See integrations/django_example.py for complete example
from .django_example import task_service

def process_document(request, doc_id):
    config = {
        'name': f'Process Document {doc_id}',
        'steps': [
            {
                'id': 'parse',
                'tool': 'doc_parser',
                'parameters': {'file_path': f'/path/to/doc_{doc_id}.pdf'}
            }
        ]
    }
    result = task_service.execute_task_sync(config)
    return JsonResponse({'success': result.success})
```

## Running the Example

### Web Scraping & Analysis Example

Fetch a web page, analyze its content, and export results to a text file:

```bash
python main.py examples/web_scrape_analysis_workflow.yaml
```

This executes the following pipeline:
1. **Fetch Page** - Retrieves HTML content from a URL using `http_fetcher`
2. **Analyze Page** - Extracts summary, keywords, and links using `web_analyzer`
3. **Export Report** - Saves the analysis results to `outputs/web_page_analysis_report.txt`

Output file example:
```
# Web Page Analysis Report

## Page URL
https://google.com

## Page Title
Google

## Page Summary
Google Suche Bilder

## Keywords
['google', 'suche', 'bilder', 'maps', 'play', 'youtube', 'news', 'gmail', 'drive', 'mehr']

## Links
[]
```

### Local Execution
```bash
python3 main.py
```

This will execute the example contract analysis pipeline defined in `example_config.yaml`.

### API Server
```bash
# Start server
python api_service.py

# Execute via API
curl -X POST "http://localhost:8000/tasks/execute" \
     -H "Content-Type: application/json" \
     -d @example_config.yaml
```

### CLI Execution
```bash
# Direct execution
python main.py example_config.yaml

# JSON output
python main.py example_config.yaml --output-format json
```

## Assessment Criteria

- **Process Flexibility**: Supports serial/parallel steps, dynamic flow adjustment
- **Tool Reusability**: At least 3 different tool types
- **Fault Tolerance**: Single step failure recovery rate ≥80%
- **Bonus Features**: Multi-agent collaboration, priority scheduling

## License

MIT License
