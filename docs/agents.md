# Agents

Agents are the core building block in your apps. An agent is a large language model (LLM), configured with instructions and tools.

## Basic configuration

The most common properties of an agent you'll configure are:

-   `instructions`: also known as a developer message or system prompt.
-   `model`: which LLM to use, and optional `model_settings` to configure model tuning parameters like temperature, top_p, etc.
-   `tools`: Tools that the agent can use to achieve its tasks.

```python
from agents import Agent, ModelSettings, function_tool

@function_tool
def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Haiku agent",
    instructions="Always respond in haiku form",
    model="o3-mini",
    tools=[get_weather],
)
```

## Context

Agents are generic on their `context` type. Context is a dependency-injection tool: it's an object you create and pass to `Runner.run()`, that is passed to every agent, tool, handoff etc, and it serves as a grab bag of dependencies and state for the agent run. You can provide any Python object as the context.

```python
@dataclass
class UserContext:
    uid: str
    is_pro_user: bool

    async def fetch_purchases() -> list[Purchase]:
        return ...

agent = Agent[UserContext](
    ...,
)
```

## Output types

By default, agents produce plain text (i.e. `str`) outputs. If you want the agent to produce a particular type of output, you can use the `output_type` parameter. A common choice is to use [Pydantic](https://docs.pydantic.dev/) objects, but we support any type that can be wrapped in a Pydantic [TypeAdapter](https://docs.pydantic.dev/latest/api/type_adapter/) - dataclasses, lists, TypedDict, etc.

```python
from pydantic import BaseModel
from agents import Agent


class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

agent = Agent(
    name="Calendar extractor",
    instructions="Extract calendar events from text",
    output_type=CalendarEvent,
)
```

!!! note

    When you pass an `output_type`, that tells the model to use [structured outputs](https://platform.openai.com/docs/guides/structured-outputs) instead of regular plain text responses.

### JSON Object Output Compatibility

For LLM providers that only support `{'type': 'json_object'}` format (instead of the more advanced `json_schema`), the SDK provides `JsonObjectOutputSchema` for explicit compatibility handling.

#### Business Layer Routing

The recommended approach is to let the business layer choose the appropriate schema based on model capabilities:

```python
from agents import Agent, AgentOutputSchema, JsonObjectOutputSchema
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    name: str = Field(description="用户的姓名")
    age: int = Field(description="用户的年龄", ge=0, le=150)
    city: str = Field(description="用户居住的城市")
    is_active: bool = Field(description="用户当前是否活跃")

def create_agent(model):
    """Business layer controls schema selection based on model capabilities"""
    if model_supports_json_schema(model):
        # Use standard json_schema for advanced models
        output_type = AgentOutputSchema(UserProfile, strict_json_schema=True)
    else:
        # Use json_object mode for limited models
        output_type = JsonObjectOutputSchema(UserProfile)

    return Agent(
        name="UserProfileAgent",
        instructions="你是一个专业的用户信息处理助手",
        output_type=output_type,
        model=model
    )
```

#### JsonObjectOutputSchema

Use `JsonObjectOutputSchema` when you know the model only supports `json_object` mode:

```python
from agents import Agent, JsonObjectOutputSchema

# Explicitly uses json_object mode with automatic prompt injection
agent = Agent(
    name="JsonObjectAgent",
    instructions="你是一个专业的用户信息处理助手",
    output_type=JsonObjectOutputSchema(UserProfile)
)
```

#### Key Features

- **Explicit Control**: Business layer explicitly chooses the appropriate schema
- **Automatic Prompt Injection**: Injects JSON schema instructions into system prompts for `json_object` mode
- **User-Controlled Instructions**: Generates instructions based on user-defined schema language and descriptions
- **Type Safety**: Maintains strict Pydantic validation with JSON repair capabilities
- **Simplified Design**: No complex auto-detection, just clear business logic

#### Custom Instructions

The `custom_instructions` parameter allows you to provide additional instructions that will be appended after the JSON Schema. This is useful for adding examples, special formatting requirements, or domain-specific guidance.

```python
# Default behavior - uses standard JSON Schema + simple instruction
schema = JsonObjectOutputSchema(UserProfile)
# Generates: JSON Schema + "Always respond strictly in the following JSON format with no additional explanatory text."

# Custom instructions with examples
schema = JsonObjectOutputSchema(
    UserProfile,
    custom_instructions="""Return a JSON object with user profile information.

Example:
{
  "name": "John Doe",
  "age": 25,
  "city": "Beijing",
  "is_active": true,
  "interests": ["reading", "coding"]
}

Output only valid JSON with no additional text or explanations."""
)

# Custom instructions for specific requirements
schema = JsonObjectOutputSchema(
    UserProfile,
    custom_instructions="""Please ensure:
1. All string values are properly escaped
2. Age must be a positive integer
3. City names should be in title case
4. Interests array should contain at least one item

Output only valid JSON."""
)
```

The final instruction will be: `JSON Schema + "\n\n" + custom_instructions`

#### JSON Repair Functionality

The SDK includes powerful JSON repair capabilities to handle malformed LLM outputs:

```python
# JSON repair is enabled by default
schema = JsonObjectOutputSchema(UserProfile)

# Test with broken JSON
broken_json = """{
    name: "张三",        // Missing quotes
    age: 25,
    city: "北京",
    is_active: true,
    interests: ["编程", "阅读",],  // Trailing comma
}"""

# Automatically repairs and validates
try:
    result = schema.validate_json(broken_json)
    print(f"Repaired successfully: {result}")
except ModelBehaviorError as e:
    print(f"Repair failed: {e}")

# Disable repair if needed
schema_no_repair = JsonObjectOutputSchema(
    UserProfile,
    enable_json_repair=False
)
```

**Supported repair types:**
- Missing quotes around property names
- Trailing commas
- Single quotes instead of double quotes
- Incomplete JSON structures
- Other common format errors

**Performance:** The repair process is highly optimized and typically adds only 1-10ms overhead.

#### Factory Methods

```python
# For different data types
pydantic_schema = JsonObjectOutputSchema.for_pydantic_model(UserProfile)
dataclass_schema = JsonObjectOutputSchema.for_dataclass(TaskItem)
typed_dict_schema = JsonObjectOutputSchema.for_typed_dict(UserDict)
```

!!! tip "When to Use Each Approach"

    - Use `JsonObjectOutputSchema` when you know the model only supports `json_object` mode
    - Use `AgentOutputSchema` when you know the model supports `json_schema` mode
    - Let your business layer choose the appropriate schema based on model capabilities for maximum flexibility

## Handoffs

Handoffs are sub-agents that the agent can delegate to. You provide a list of handoffs, and the agent can choose to delegate to them if relevant. This is a powerful pattern that allows orchestrating modular, specialized agents that excel at a single task. Read more in the [handoffs](handoffs.md) documentation.

```python
from agents import Agent

booking_agent = Agent(...)
refund_agent = Agent(...)

triage_agent = Agent(
    name="Triage agent",
    instructions=(
        "Help the user with their questions."
        "If they ask about booking, handoff to the booking agent."
        "If they ask about refunds, handoff to the refund agent."
    ),
    handoffs=[booking_agent, refund_agent],
)
```

## Dynamic instructions

In most cases, you can provide instructions when you create the agent. However, you can also provide dynamic instructions via a function. The function will receive the agent and context, and must return the prompt. Both regular and `async` functions are accepted.

```python
def dynamic_instructions(
    context: RunContextWrapper[UserContext], agent: Agent[UserContext]
) -> str:
    return f"The user's name is {context.context.name}. Help them with their questions."


agent = Agent[UserContext](
    name="Triage agent",
    instructions=dynamic_instructions,
)
```

## Lifecycle events (hooks)

Sometimes, you want to observe the lifecycle of an agent. For example, you may want to log events, or pre-fetch data when certain events occur. You can hook into the agent lifecycle with the `hooks` property. Subclass the [`AgentHooks`][agents.lifecycle.AgentHooks] class, and override the methods you're interested in.

## Guardrails

Guardrails allow you to run checks/validations on user input, in parallel to the agent running. For example, you could screen the user's input for relevance. Read more in the [guardrails](guardrails.md) documentation.

## Cloning/copying agents

By using the `clone()` method on an agent, you can duplicate an Agent, and optionally change any properties you like.

```python
pirate_agent = Agent(
    name="Pirate",
    instructions="Write like a pirate",
    model="o3-mini",
)

robot_agent = pirate_agent.clone(
    name="Robot",
    instructions="Write like a robot",
)
```

## Forcing tool use

Supplying a list of tools doesn't always mean the LLM will use a tool. You can force tool use by setting [`ModelSettings.tool_choice`][agents.model_settings.ModelSettings.tool_choice]. Valid values are:

1. `auto`, which allows the LLM to decide whether or not to use a tool.
2. `required`, which requires the LLM to use a tool (but it can intelligently decide which tool).
3. `none`, which requires the LLM to _not_ use a tool.
4. Setting a specific string e.g. `my_tool`, which requires the LLM to use that specific tool.

!!! note

    To prevent infinite loops, the framework automatically resets `tool_choice` to "auto" after a tool call. This behavior is configurable via [`agent.reset_tool_choice`][agents.agent.Agent.reset_tool_choice]. The infinite loop is because tool results are sent to the LLM, which then generates another tool call because of `tool_choice`, ad infinitum.

    If you want the Agent to completely stop after a tool call (rather than continuing with auto mode), you can set [`Agent.tool_use_behavior="stop_on_first_tool"`] which will directly use the tool output as the final response without further LLM processing.
