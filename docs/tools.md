# Tools

Tools let agents take actions: things like fetching data, running code, calling external APIs, and even using a computer. There are three classes of tools in the Agent SDK:

-   Hosted tools: these run on LLM servers alongside the AI models. OpenAI offers retrieval, web search and computer use as hosted tools.
-   Function calling: these allow you to use any Python function as a tool.
-   Agents as tools: this allows you to use an agent as a tool, allowing Agents to call other agents without handing off to them.

## Hosted tools

OpenAI offers a few built-in tools when using the [`OpenAIResponsesModel`][agents.models.openai_responses.OpenAIResponsesModel]:

-   The [`WebSearchTool`][agents.tool.WebSearchTool] lets an agent search the web.
-   The [`FileSearchTool`][agents.tool.FileSearchTool] allows retrieving information from your OpenAI Vector Stores.
-   The [`ComputerTool`][agents.tool.ComputerTool] allows automating computer use tasks.
-   The [`CodeInterpreterTool`][agents.tool.CodeInterpreterTool] lets the LLM execute code in a sandboxed environment.
-   The [`HostedMCPTool`][agents.tool.HostedMCPTool] exposes a remote MCP server's tools to the model.
-   The [`ImageGenerationTool`][agents.tool.ImageGenerationTool] generates images from a prompt.
-   The [`LocalShellTool`][agents.tool.LocalShellTool] runs shell commands on your machine.

```python
from agents import Agent, FileSearchTool, Runner, WebSearchTool

agent = Agent(
    name="Assistant",
    tools=[
        WebSearchTool(),
        FileSearchTool(
            max_num_results=3,
            vector_store_ids=["VECTOR_STORE_ID"],
        ),
    ],
)

async def main():
    result = await Runner.run(agent, "Which coffee shop should I go to, taking into account my preferences and the weather today in SF?")
    print(result.final_output)
```

## Function tools

You can use any Python function as a tool. The Agents SDK will setup the tool automatically:

-   The name of the tool will be the name of the Python function (or you can provide a name)
-   Tool description will be taken from the docstring of the function (or you can provide a description)
-   The schema for the function inputs is automatically created from the function's arguments
-   Descriptions for each input are taken from the docstring of the function, unless disabled

We use Python's `inspect` module to extract the function signature, along with [`griffe`](https://mkdocstrings.github.io/griffe/) to parse docstrings and `pydantic` for schema creation.

```python
import json

from typing_extensions import TypedDict, Any

from agents import Agent, FunctionTool, RunContextWrapper, function_tool


class Location(TypedDict):
    lat: float
    long: float

@function_tool  # (1)!
async def fetch_weather(location: Location) -> str:
    # (2)!
    """Fetch the weather for a given location.

    Args:
        location: The location to fetch the weather for.
    """
    # In real life, we'd fetch the weather from a weather API
    return "sunny"


@function_tool(name_override="fetch_data")  # (3)!
def read_file(ctx: RunContextWrapper[Any], path: str, directory: str | None = None) -> str:
    """Read the contents of a file.

    Args:
        path: The path to the file to read.
        directory: The directory to read the file from.
    """
    # In real life, we'd read the file from the file system
    return "<file contents>"


agent = Agent(
    name="Assistant",
    tools=[fetch_weather, read_file],  # (4)!
)

for tool in agent.tools:
    if isinstance(tool, FunctionTool):
        print(tool.name)
        print(tool.description)
        print(json.dumps(tool.params_json_schema, indent=2))
        print()

```

1.  You can use any Python types as arguments to your functions, and the function can be sync or async.
2.  Docstrings, if present, are used to capture descriptions and argument descriptions
3.  Functions can optionally take the `context` (must be the first argument). You can also set overrides, like the name of the tool, description, which docstring style to use, etc.
4.  You can pass the decorated functions to the list of tools.

??? note "Expand to see output"

    ```
    fetch_weather
    Fetch the weather for a given location.
    {
    "$defs": {
      "Location": {
        "properties": {
          "lat": {
            "title": "Lat",
            "type": "number"
          },
          "long": {
            "title": "Long",
            "type": "number"
          }
        },
        "required": [
          "lat",
          "long"
        ],
        "title": "Location",
        "type": "object"
      }
    },
    "properties": {
      "location": {
        "$ref": "#/$defs/Location",
        "description": "The location to fetch the weather for."
      }
    },
    "required": [
      "location"
    ],
    "title": "fetch_weather_args",
    "type": "object"
    }

    fetch_data
    Read the contents of a file.
    {
    "properties": {
      "path": {
        "description": "The path to the file to read.",
        "title": "Path",
        "type": "string"
      },
      "directory": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "description": "The directory to read the file from.",
        "title": "Directory"
      }
    },
    "required": [
      "path"
    ],
    "title": "fetch_data_args",
    "type": "object"
    }
    ```

### Custom function tools

Sometimes, you don't want to use a Python function as a tool. You can directly create a [`FunctionTool`][agents.tool.FunctionTool] if you prefer. You'll need to provide:

-   `name`
-   `description`
-   `params_json_schema`, which is the JSON schema for the arguments
-   `on_invoke_tool`, which is an async function that receives the context and the arguments as a JSON string, and must return the tool output as a string.

```python
from typing import Any

from pydantic import BaseModel

from agents import RunContextWrapper, FunctionTool



def do_some_work(data: str) -> str:
    return "done"


class FunctionArgs(BaseModel):
    username: str
    age: int


async def run_function(ctx: RunContextWrapper[Any], args: str) -> str:
    parsed = FunctionArgs.model_validate_json(args)
    return do_some_work(data=f"{parsed.username} is {parsed.age} years old")


tool = FunctionTool(
    name="process_user",
    description="Processes extracted user data",
    params_json_schema=FunctionArgs.model_json_schema(),
    on_invoke_tool=run_function,
)
```

### Automatic argument and docstring parsing

As mentioned before, we automatically parse the function signature to extract the schema for the tool, and we parse the docstring to extract descriptions for the tool and for individual arguments. Some notes on that:

1. The signature parsing is done via the `inspect` module. We use type annotations to understand the types for the arguments, and dynamically build a Pydantic model to represent the overall schema. It supports most types, including Python primitives, Pydantic models, TypedDicts, and more.
2. We use `griffe` to parse docstrings. Supported docstring formats are `google`, `sphinx` and `numpy`. We attempt to automatically detect the docstring format, but this is best-effort and you can explicitly set it when calling `function_tool`. You can also disable docstring parsing by setting `use_docstring_info` to `False`.

The code for the schema extraction lives in [`agents.function_schema`][].

## Streaming tools

`@streaming_tool` is a powerful decorator in the `openai-agents-python` SDK designed to create tools that provide **real-time process feedback**. Unlike standard `@function_tool` (which can only return results after all computation is complete), `@streaming_tool` allows you to continuously **stream notification events** to the client during the tool's lengthy execution process.

### Design Philosophy: Strict Separation of "Process Display" and "Final Result"

To master `@streaming_tool`, you only need to understand two completely orthogonal core mechanisms:

#### 1. Final Result: `yield "..."` (as the last yield)

This is the most important design principle of `streaming_tool`: **its final output must be completely symmetric with `@function_tool`**.

- **Mechanism**: In the **final step** of your async generator function, you must `yield` a **string (`str`)** to provide the tool's final output.
- **History Impact**: The SDK's `Runner` considers the tool execution complete when it detects a yielded string value. It captures this string result, wraps it as a `ToolCallOutputItem`, and sends it as an **conversation-history-affecting** `item.completed` event.

#### 2. Process Notifications: `yield` various events

Before yielding the final string result, you can `yield` various **purely display-oriented** events. The `Runner` will pass these events directly to the client but **never** record them in the conversation history.

- **`NotifyStreamEvent`**: The most commonly used notification event.
  - `data: str`: **(Required)** The notification content.
  - `is_delta: bool`: (Default `False`) Used to distinguish between "one-time notifications" (`False`) and "typewriter increments" (`True`).
  - `tag: Optional[str]`: Custom tags for frontend-specific UI logic.

- **`ToolStreamStartEvent` / `ToolStreamEndEvent`**: "Bracket" events for process orchestration, automatically generated by the decorator.

### Core Usage Examples

#### Multi-stage Progress Updates

```python
from agents import streaming_tool, NotifyStreamEvent
import asyncio

@streaming_tool
async def data_pipeline(source_url: str):
    yield NotifyStreamEvent(data="[1/3] Establishing connection...")
    await asyncio.sleep(1)
    yield NotifyStreamEvent(data="[2/3] ✅ Connection successful, starting download...", tag="success")
    await asyncio.sleep(1)

    yield "Data pipeline processing successful, parsed 1,234 records."
```

#### RAG Typewriter Effect

```python
from agents import streaming_tool, NotifyStreamEvent
import asyncio

@streaming_tool
async def research_and_summarize(topic: str):
    yield NotifyStreamEvent(data=f"Searching for '{topic}'...")
    documents = await retrieve_documents(topic)
    yield NotifyStreamEvent(data="✅ Search complete, generating summary...")

    full_summary = ""
    async for text_delta in get_llm_summary_stream(documents):
        full_summary += text_delta
        yield NotifyStreamEvent(data=text_delta, is_delta=True)
        await asyncio.sleep(0.02)

    yield full_summary
```

### Advanced Process Orchestration: Agent as a Tool

This is the most powerful application scenario of `streaming_tool`. We provide an extremely simple API for this.

#### Official Recommendation: Use `Agent.as_tool(streaming=True)`

You don't need to manually implement any complex orchestration logic. Simply call the `.as_tool()` method on your `Agent` instance and pass `streaming=True`.

```python
from agents import Agent, Runner

# 1. Define a sub-agent with specific capabilities
sub_agent = Agent(
    name="SubAgent",
    instructions="You are a subtask executor. You report your status.",
    model=MODEL_NAME,
    tools=[...], # Sub-agent's own tools
)

# 2. Define orchestrator agent, using sub-agent as a streaming tool
#    SDK automatically handles all event stream forwarding
orchestrator_agent = Agent(
    name="OrchestratorAgent",
    instructions="You must call your 'run_sub_agent' tool to complete tasks.",
    model=MODEL_NAME,
    tools=[
        sub_agent.as_tool(
            tool_name="run_sub_agent",
            tool_description="Run sub-agent to execute specific tasks",
            streaming=True, # Key!
            enable_bracketing=True # Recommended for UI display
        )
    ],
)

# 3. Run and observe
# The orchestrator agent's event stream will automatically include all streaming events from the sub-agent
async for event in Runner.run_streamed(orchestrator_agent, "Please run the sub-agent").stream_events():
    print(event)
```

## Agents as tools

In some workflows, you may want a central agent to orchestrate a network of specialized agents, instead of handing off control. You can do this by modeling agents as tools.

```python
from agents import Agent, Runner
import asyncio

spanish_agent = Agent(
    name="Spanish agent",
    instructions="You translate the user's message to Spanish",
)

french_agent = Agent(
    name="French agent",
    instructions="You translate the user's message to French",
)

orchestrator_agent = Agent(
    name="orchestrator_agent",
    instructions=(
        "You are a translation agent. You use the tools given to you to translate."
        "If asked for multiple translations, you call the relevant tools."
    ),
    tools=[
        spanish_agent.as_tool(
            tool_name="translate_to_spanish",
            tool_description="Translate the user's message to Spanish",
        ),
        french_agent.as_tool(
            tool_name="translate_to_french",
            tool_description="Translate the user's message to French",
        ),
    ],
)

async def main():
    result = await Runner.run(orchestrator_agent, input="Say 'Hello, how are you?' in Spanish.")
    print(result.final_output)
```

### Customizing tool-agents

The `agent.as_tool` function is a convenience method to make it easy to turn an agent into a tool. It supports most common configuration options including `run_config` for custom model providers and settings. For advanced use cases that require additional configuration (e.g., `max_turns`), use `Runner.run` directly in your tool implementation:

```python
@function_tool
async def run_my_agent() -> str:
    """A tool that runs the agent with custom configs"""

    agent = Agent(name="My agent", instructions="...")

    result = await Runner.run(
        agent,
        input="...",
        max_turns=5,
        run_config=...
    )

    return str(result.final_output)
```

### Using custom model providers with tool-agents

You can pass a `run_config` parameter to `as_tool()` to specify custom model providers, model settings, and other configuration options for the tool execution. This is particularly useful when you need to use different models or providers for different agents:

```python
from agents import Agent, RunConfig, ModelProvider

# Create a custom model provider for enterprise models
custom_provider = MyCustomModelProvider()
run_config = RunConfig(model_provider=custom_provider)

# Create an agent that uses a custom model prefix
enterprise_agent = Agent(
    name="EnterpriseAgent",
    instructions="You are an enterprise AI assistant",
    model="doubao/enterprise-model"  # Custom model prefix
)

# Convert to tool with custom run_config
enterprise_tool = enterprise_agent.as_tool(
    tool_name="enterprise_assistant",
    tool_description="Access enterprise AI capabilities",
    run_config=run_config  # Pass custom configuration
)

# Use in main agent
main_agent = Agent(
    name="MainAgent",
    instructions="You coordinate different AI capabilities",
    tools=[enterprise_tool]
)
```

This ensures that when the tool is executed, it uses the specified model provider and configuration, rather than falling back to the default settings.

### Custom output extraction

In certain cases, you might want to modify the output of the tool-agents before returning it to the central agent. This may be useful if you want to:

- Extract a specific piece of information (e.g., a JSON payload) from the sub-agent's chat history.
- Convert or reformat the agent’s final answer (e.g., transform Markdown into plain text or CSV).
- Validate the output or provide a fallback value when the agent’s response is missing or malformed.

You can do this by supplying the `custom_output_extractor` argument to the `as_tool` method:

```python
async def extract_json_payload(run_result: RunResult) -> str:
    # Scan the agent’s outputs in reverse order until we find a JSON-like message from a tool call.
    for item in reversed(run_result.new_items):
        if isinstance(item, ToolCallOutputItem) and item.output.strip().startswith("{"):
            return item.output.strip()
    # Fallback to an empty JSON object if nothing was found
    return "{}"


json_tool = data_agent.as_tool(
    tool_name="get_data_json",
    tool_description="Run the data agent and return only its JSON payload",
    custom_output_extractor=extract_json_payload,
)
```

## Handling errors in function tools

When you create a function tool via `@function_tool`, you can pass a `failure_error_function`. This is a function that provides an error response to the LLM in case the tool call crashes.

-   By default (i.e. if you don't pass anything), it runs a `default_tool_error_function` which tells the LLM an error occurred.
-   If you pass your own error function, it runs that instead, and sends the response to the LLM.
-   If you explicitly pass `None`, then any tool call errors will be re-raised for you to handle. This could be a `ModelBehaviorError` if the model produced invalid JSON, or a `UserError` if your code crashed, etc.

If you are manually creating a `FunctionTool` object, then you must handle errors inside the `on_invoke_tool` function.
