# 14 — Google ADK: Multi-Agent Orchestration

> **Why this matters for FDEs:** The Google Agent Development Kit (ADK)
> is the primary framework for building production multi-agent systems
> on GCP. It integrates natively with Vertex AI, BigQuery, Cloud Run,
> and GKE. Knowing ADK deeply is a direct differentiator for any FDE
> deploying AI solutions in a Google cloud environment.

---

## 1. ADK Mental Model — What It Is and Why It Exists

```
BEFORE ADK (the problem):
  Developer builds an AI agent as a monolithic system.
  Single LLM call handles: routing, retrieval, analysis, generation.
  Result: 
    - Hard to debug (which step failed?)
    - Hard to scale (can't scale retrieval independently from generation)
    - Hard to improve (changing one part breaks others)
    - Single model handles ALL tasks regardless of their cost/complexity

ADK SOLUTION — The Multi-Agent Pattern:
  Break into specialized agents, each with one responsibility.
  An ORCHESTRATOR agent routes tasks to SPECIALIST agents.
  Each specialist has its own tools, context window, and model.
  
  ORCHESTRATOR
  ├── Understands intent, routes to right specialist
  │
  ├── DATA ANALYST AGENT
  │   ├── Tool: execute_bigquery_sql
  │   ├── Tool: list_available_tables
  │   └── Model: gemini-2.0-flash (fast, cheap for SQL generation)
  │
  ├── DOCUMENT SEARCH AGENT  
  │   ├── Tool: vertex_ai_search
  │   ├── Tool: get_document_content
  │   └── Model: gemini-1.5-pro (long context for document analysis)
  │
  └── REPORT WRITER AGENT
      ├── Tool: format_as_markdown
      ├── Tool: send_to_slack
      └── Model: gemini-1.5-pro (strong instruction following)
```

---

## 2. ADK Core Concepts

```python
# Install ADK
# pip install google-adk

from google.adk.agents import Agent, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.tools import FunctionTool, VertexAiSearchTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types

# ── CORE CONCEPT 1: A Tool ────────────────────────────────────────────────────
# A Tool is a Python function the agent can call to interact with the world.
# The function's docstring and type hints ARE the tool description — the LLM
# reads these to decide when and how to call the tool.

def execute_bigquery_query(sql_query: str) -> dict:
    """
    Execute a SQL query against BigQuery and return the results.
    Use this tool when the user asks questions that require querying structured data.
    
    Args:
        sql_query: A valid GoogleSQL query string. Must be a SELECT statement only.
                   Never include DDL (CREATE, DROP) or DML (INSERT, UPDATE, DELETE).
    
    Returns:
        dict with keys:
          - rows: list of result rows as dicts
          - row_count: total number of rows returned
          - error: error message if query failed (None if successful)
    """
    from google.cloud import bigquery
    client = bigquery.Client()
    
    try:
        # SECURITY: only allow SELECT statements
        if not sql_query.strip().upper().startswith("SELECT"):
            return {"rows": [], "row_count": 0, "error": "Only SELECT queries are allowed"}
        
        query_job = client.query(sql_query)
        results = query_job.result()
        rows = [dict(row) for row in results]
        return {"rows": rows, "row_count": len(rows), "error": None}
    except Exception as e:
        return {"rows": [], "row_count": 0, "error": str(e)}

# Wrap the function as an ADK tool
bq_tool = FunctionTool(func=execute_bigquery_query)
```

---

## 3. Building the Data Analyst Agent

```python
# ── TOOL DEFINITIONS ──────────────────────────────────────────────────────────

def list_available_tables() -> dict:
    """
    List all available BigQuery tables the analyst can query.
    Call this first to understand what data is available.
    
    Returns:
        dict with key 'tables': list of objects with 'table_id', 'description',
        'row_count', and 'key_columns' fields.
    """
    return {
        "tables": [
            {
                "table_id": "gold_analytics.fct_sales",
                "description": "Sales transactions fact table. One row per order line item.",
                "row_count": "~50M rows",
                "key_columns": ["order_date", "customer_id", "product_id", "region",
                               "amount", "gross_margin"]
            },
            {
                "table_id": "gold_analytics.dim_customer",
                "description": "Customer dimension. One row per customer (current state).",
                "row_count": "~500K rows",
                "key_columns": ["customer_id", "customer_name", "tier", "region",
                               "acquisition_date"]
            },
        ]
    }

def get_current_date() -> dict:
    """Get the current date for use in time-relative queries."""
    from datetime import date
    return {"current_date": str(date.today())}

# ── DATA ANALYST AGENT DEFINITION ────────────────────────────────────────────
data_analyst_agent = LlmAgent(
    name="data_analyst",
    model="gemini-2.0-flash-exp",  # fast model for SQL generation
    description="Analyzes business data by writing and executing BigQuery SQL queries.",
    instruction="""You are a senior data analyst with expertise in SQL and BigQuery.
    
    Your job:
    1. Understand what data question the user is asking
    2. Check what tables are available using list_available_tables()
    3. Write precise, efficient BigQuery SQL to answer the question
    4. Execute the query and interpret the results
    5. Present findings clearly with the key insight highlighted first
    
    SQL RULES (strictly follow these):
    - Always use fully qualified table names: project.dataset.table
    - Always add a LIMIT clause unless aggregating to few rows
    - Always use partition filters on partitioned tables to control cost
    - Never write DML (INSERT/UPDATE/DELETE) or DDL (CREATE/DROP)
    - If a query would scan > 1TB, warn the user before executing
    
    After getting results:
    - Lead with the key insight in 1-2 sentences
    - Show the supporting data in a formatted table
    - Note any caveats or limitations in the data
    """,
    tools=[
        FunctionTool(func=list_available_tables),
        FunctionTool(func=execute_bigquery_query),
        FunctionTool(func=get_current_date),
    ],
)
```

---

## 4. Building the Document Search Agent

```python
# ── VERTEX AI SEARCH TOOL ─────────────────────────────────────────────────────
# Vertex AI Search provides managed RAG with Google-quality retrieval

vertex_search_tool = VertexAiSearchTool(
    data_store_id="projects/my-project/locations/us/collections/default_collection/dataStores/my-datastore"
)

def get_document_details(document_id: str, chunk_index: int = 0) -> dict:
    """
    Retrieve the full text of a specific document section.
    Use this when Vertex AI Search returns a document reference and you
    need the full content to answer the user's question accurately.
    
    Args:
        document_id: The document identifier returned by vertex_ai_search
        chunk_index: Which section of the document to retrieve (0=first/most relevant)
    
    Returns:
        dict with 'title', 'content', 'source_url', 'last_updated'
    """
    # Implementation: fetch from GCS or document store
    from google.cloud import storage
    client = storage.Client()
    # ... fetch and return document content
    pass

document_search_agent = LlmAgent(
    name="document_search",
    model="gemini-1.5-pro-002",  # large context model for long documents
    description="Searches company documents and knowledge base to answer questions.",
    instruction="""You are an expert at finding and synthesizing information from
    company documents, policies, and knowledge base articles.
    
    Your job:
    1. Search for relevant documents using vertex_ai_search
    2. Retrieve full document details if the snippets aren't sufficient
    3. Synthesize information from multiple documents into a clear answer
    4. ALWAYS cite your sources with document title and relevant section
    
    CITATION FORMAT:
    - Quote directly when precision matters (policies, procedures, requirements)
    - Paraphrase when summarizing general concepts
    - Always end with: "Sources: [Document Title 1], [Document Title 2]"
    
    If you can't find relevant information:
    - Be explicit: "I couldn't find information about X in the knowledge base"
    - Suggest where the user might find the information
    - Never make up information or extrapolate beyond what documents say
    """,
    tools=[
        vertex_search_tool,
        FunctionTool(func=get_document_details),
    ],
)
```

---

## 5. The Orchestrator Agent — Routing and Coordination

```python
# ── ORCHESTRATOR: routes to the right specialist agent ───────────────────────

root_agent = LlmAgent(
    name="orchestrator",
    model="gemini-2.0-flash-exp",
    description="Routes user questions to the appropriate specialist agent.",
    instruction="""You are the coordinator for an AI assistant system.
    
    You have access to specialist agents:
    - data_analyst: for questions about business metrics, trends, numbers,
      customer data, sales data, or anything requiring database queries
    - document_search: for questions about company policies, procedures,
      product information, how-to guides, or anything in company documents
    
    ROUTING RULES:
    - Quantitative questions ("How many...", "What was revenue...", "Compare...") 
      → data_analyst
    - Policy/process questions ("What is the policy for...", "How do I...") 
      → document_search
    - Questions needing both data AND documents → call both agents, synthesize
    
    QUALITY CONTROL:
    - Review the specialist's response before returning to user
    - If the answer seems incomplete, ask the specialist for more detail
    - If data_analyst returns an error, diagnose and try a corrected query
    - Always present results in a clear, professional format
    """,
    # Sub-agents are exposed as tools to the orchestrator
    agents=[data_analyst_agent, document_search_agent],
)
```

---

## 6. Parallel and Sequential Agents

```python
# ── PARALLEL AGENT: run multiple agents simultaneously ──────────────────────
# Use when multiple tasks are INDEPENDENT and can run concurrently

from google.adk.agents import ParallelAgent

parallel_research = ParallelAgent(
    name="parallel_researcher",
    description="Runs data analysis and document search simultaneously for comprehensive answers",
    agents=[data_analyst_agent, document_search_agent],
    # Both agents run in parallel, results are returned together
)

# ── SEQUENTIAL AGENT: run agents in a fixed order ────────────────────────────
# Use when output of agent N is input to agent N+1

from google.adk.agents import SequentialAgent

def format_report(analysis_results: str, document_context: str) -> dict:
    """Combine analysis results with document context into a formatted report."""
    return {
        "combined_context": f"Data Analysis:\n{analysis_results}\n\nDocument Context:\n{document_context}"
    }

report_pipeline = SequentialAgent(
    name="report_pipeline",
    description="Gather data, then format a final report",
    agents=[
        data_analyst_agent,        # Step 1: Run the analysis
        document_search_agent,     # Step 2: Find relevant policies
        # Step 3: A report writing agent that uses output from steps 1+2
    ],
)
```

---

## 7. Running the Agent — Sessions and the Runner

```python
# ── SESSION MANAGEMENT ────────────────────────────────────────────────────────
# Sessions maintain conversation history between user turns

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
import asyncio

# For development: in-memory services (no persistence)
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()

# For production: use VertexAI-backed persistent sessions
# from google.adk.sessions import VertexAiSessionService
# session_service = VertexAiSessionService(
#     project="my-project", location="us-central1"
# )

# Create a Runner (the execution engine)
runner = Runner(
    agent=root_agent,
    app_name="enterprise-ai-assistant",
    session_service=session_service,
    artifact_service=artifact_service,
)

async def chat(user_message: str, session_id: str, user_id: str = "user"):
    """Send a message and get a response from the agent system."""

    # Create or retrieve session
    session = await session_service.get_session(
        app_name="enterprise-ai-assistant",
        user_id=user_id,
        session_id=session_id,
    )

    # Run the agent
    content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    )

    final_response = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    ):
        # Events stream during agent execution
        if event.is_final_response():
            final_response = event.content.parts[0].text

    return final_response

# Run it:
async def main():
    session_id = "session_001"
    user_id = "analyst_jane"

    # First turn
    response1 = await chat(
        "What were our top 5 revenue products last quarter?",
        session_id, user_id
    )
    print(f"Agent: {response1}")

    # Second turn (agent remembers first turn)
    response2 = await chat(
        "Now show me the customer tier breakdown for those products",
        session_id, user_id
    )
    print(f"Agent: {response2}")

asyncio.run(main())
```

---

## 8. Deploying ADK Agents to Vertex AI Agent Engine

```python
# Vertex AI Agent Engine = managed, auto-scaling runtime for ADK agents
# No cluster management, automatic scaling to zero, built-in logging

import vertexai
from vertexai.preview import reasoning_engines

vertexai.init(project="my-project", location="us-central1")

# ── STEP 1: Define the app class (wraps your ADK agent) ──────────────────────
class EnterpriseAIAssistant(reasoning_engines.AdkApp):
    def __init__(self):
        super().__init__(
            agent=root_agent,
            enable_tracing=True,  # enables Cloud Trace for debugging
        )

# ── STEP 2: Deploy to Agent Engine ───────────────────────────────────────────
remote_app = reasoning_engines.ReasoningEngine.create(
    EnterpriseAIAssistant(),
    display_name="Enterprise AI Assistant",
    description="Multi-agent system for data analysis and document search",
    requirements=[
        "google-adk>=0.3.0",
        "google-cloud-bigquery>=3.0.0",
        "google-cloud-storage>=2.0.0",
    ],
    extra_packages=[],
)

print(f"Deployed to: {remote_app.resource_name}")
# Output: projects/my-project/locations/us-central1/reasoningEngines/123456

# ── STEP 3: Query the deployed agent ─────────────────────────────────────────
session = remote_app.create_session(user_id="analyst_jane")

response = remote_app.query(
    user_id="analyst_jane",
    session_id=session["id"],
    message="What were our top 5 revenue products last quarter?"
)
print(response)

# ── STEP 4: Monitor the deployment ───────────────────────────────────────────
# Cloud Trace: go to Cloud Console → Trace → Filter by "reasoning_engine"
# Cloud Logging: filter by resource.type="ml_job" for agent logs
# Metrics: Cloud Monitoring → Custom Metrics → "reasoning_engine/*"
```

---

## 9. ADK Best Practices for Production

```
AGENT DESIGN:
□ One agent = one clear responsibility (not "do everything")
□ Model choice: use the smallest/cheapest model that can do the job
   - Routing/orchestration: gemini-2.0-flash (fast, cheap)
   - SQL generation: gemini-2.0-flash (good enough, fast)
   - Long document analysis: gemini-1.5-pro (needs large context)
   - Complex reasoning: gemini-2.0-pro (save for hard problems)
□ Tools return structured dicts, not strings — enables better parsing
□ Agents return structured output when downstream processing needed
□ Always include error handling in tool functions
□ Add SECURITY checks in tools (no DML/DDL in SQL tools)

DEBUGGING:
□ Enable tracing: enable_tracing=True in AdkApp
□ Use Cloud Trace to visualize agent call chains
□ Log every tool call input and output for audit trail
□ Test each tool function independently before adding to agent
□ Build a golden test set for the orchestrator routing logic

COST CONTROL:
□ Use gemini-2.0-flash for routing (don't waste pro-tier on routing)
□ Set max_turns on LlmAgent to prevent infinite loops
□ Cache Vertex AI Search responses for repeated queries
□ Monitor tokens per session in Cloud Monitoring
□ Set budget alerts on Vertex AI usage
```

---

## 10. ADK Troubleshooting Guide

```
PROBLEM: Agent loops (keeps calling same tool repeatedly)
  Cause: Tool error response not helpful enough; agent retries
  Fix: Improve error messages in tools; add max_turns=5 limit
  Fix: Add explicit "if you get an error, explain it to the user" to instructions

PROBLEM: Wrong agent is being called (routing mistakes)
  Cause: Agent descriptions overlap; routing instructions too vague
  Fix: Make agent descriptions specific and distinct
  Fix: Add explicit routing examples in orchestrator instructions
  Fix: Add a small test set for routing quality evaluation

PROBLEM: Agent ignores tools and makes up answers (hallucination)
  Cause: Instructions don't emphasize tool use strongly enough
  Fix: Add "ALWAYS use the available tools. Never answer from memory."
  Fix: Use tool_call_mode="ANY" to force tool use on first turn

PROBLEM: Slow response time (> 10 seconds for simple questions)
  Cause: Using gemini-1.5-pro for simple tasks; too many agent hops
  Fix: Use gemini-2.0-flash for routing and simple SQL generation
  Fix: Use ParallelAgent when tasks are independent
  Fix: Cache frequently-asked questions

PROBLEM: 429 Quota Exceeded errors
  Cause: Too many concurrent sessions hitting Vertex AI rate limits
  Fix: Implement exponential backoff retry in runner wrapper
  Fix: Request quota increase in GCP console
  Fix: Add caching layer for common queries
```
