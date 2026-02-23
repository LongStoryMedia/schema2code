# Auto-generated model exports
# This file was automatically generated to export all models for easy importing

from __future__ import annotations

# Import all model modules
try:
    from . import chat_completion_allowed_tools
    from . import chat_completion_allowed_tools_choice
    from . import chat_completion_function_call_option
    from . import chat_completion_functions
    from . import chat_completion_message_tool_calls
    from . import chat_completion_named_tool_choice
    from . import chat_completion_named_tool_choice_custom
    from . import chat_completion_request_assistant_message
    from . import chat_completion_request_developer_message
    from . import chat_completion_request_function_message
    from . import chat_completion_request_message
    from . import chat_completion_request_system_message
    from . import chat_completion_request_tool_message
    from . import chat_completion_request_user_message
    from . import chat_completion_stream_options
    from . import chat_completion_tool
    from . import chat_completion_tool_choice_option
    from . import chat_model
    from . import create_model_response_properties
    from . import custom_tool_chat_completions
    from . import function_object
    from . import function_parameters
    from . import metadata
    from . import model_ids_shared
    from . import model_response_properties
    from . import parallel_tool_calls
    from . import prediction_content
    from . import reasoning_effort
    from . import response_format_json_object
    from . import response_format_json_schema
    from . import response_format_json_schema_schema
    from . import response_format_text
    from . import response_modalities
    from . import service_tier
    from . import stop_configuration
    from . import test_rebuild
    from . import verbosity
    from . import voice_ids_shared
    from . import web_search_context_size
    from . import web_search_location
except ImportError as e:
    import sys
    print(f"Warning: Some model modules could not be imported: {e}", file=sys.stderr)

# Define what gets imported with 'from models import *'
__all__ = [
    'chat_completion_allowed_tools',
    'chat_completion_allowed_tools_choice',
    'chat_completion_function_call_option',
    'chat_completion_functions',
    'chat_completion_message_tool_calls',
    'chat_completion_named_tool_choice',
    'chat_completion_named_tool_choice_custom',
    'chat_completion_request_assistant_message',
    'chat_completion_request_developer_message',
    'chat_completion_request_function_message',
    'chat_completion_request_message',
    'chat_completion_request_system_message',
    'chat_completion_request_tool_message',
    'chat_completion_request_user_message',
    'chat_completion_stream_options',
    'chat_completion_tool',
    'chat_completion_tool_choice_option',
    'chat_model',
    'create_model_response_properties',
    'custom_tool_chat_completions',
    'function_object',
    'function_parameters',
    'metadata',
    'model_ids_shared',
    'model_response_properties',
    'parallel_tool_calls',
    'prediction_content',
    'reasoning_effort',
    'response_format_json_object',
    'response_format_json_schema',
    'response_format_json_schema_schema',
    'response_format_text',
    'response_modalities',
    'service_tier',
    'stop_configuration',
    'test_rebuild',
    'verbosity',
    'voice_ids_shared',
    'web_search_context_size',
    'web_search_location',
    'ChatCompletionAllowedTools',
    'ChatCompletionAllowedToolsChoice',
    'ChatCompletionFunctionCallOption',
    'ChatCompletionFunctions',
    'ChatCompletionMessageToolCalls',
    'ChatCompletionNamedToolChoice',
    'Function',
    'ChatCompletionNamedToolChoiceCustom',
    'Custom',
    'Audio',
    'ChatCompletionRequestAssistantMessage',
    'FunctionCall',
    'ChatCompletionRequestDeveloperMessage',
    'ChatCompletionRequestFunctionMessage',
    'ChatCompletionRequestSystemMessage',
    'ChatCompletionRequestToolMessage',
    'ChatCompletionRequestUserMessage',
    'ChatCompletionStreamOptions',
    'ChatCompletionTool',
    'ChatCompletionToolChoiceOption',
    'Custom',
    'Function',
    'ChatModel',
    'CreateModelResponseProperties',
    'Custom',
    'CustomToolChatCompletions',
    'FunctionObject',
    'FunctionParameters',
    'Metadata',
    'ModelIdsShared',
    'ModelResponseProperties',
    'ParallelToolCalls',
    'PredictionContent',
    'ReasoningEffort',
    'ResponseFormatJsonObject',
    'JsonSchema',
    'ResponseFormatJsonSchema',
    'ResponseFormatJsonSchemaSchema',
    'ResponseFormatText',
    'ResponseModalities',
    'ServiceTier',
    'StopConfiguration',
    'Audio',
    'CreateChatCompletionRequest',
    'UserLocation',
    'WebSearchOptions',
    'Verbosity',
    'VoiceIdsShared',
    'WebSearchContextSize',
    'WebSearchLocation',
]

# Re-export all model classes for easy importing and IDE autocompletion
from .chat_completion_allowed_tools import (
    ChatCompletionAllowedTools,
)
from .chat_completion_allowed_tools_choice import (
    ChatCompletionAllowedToolsChoice,
)
from .chat_completion_function_call_option import (
    ChatCompletionFunctionCallOption,
)
from .chat_completion_functions import (
    ChatCompletionFunctions,
)
from .chat_completion_message_tool_calls import (
    ChatCompletionMessageToolCalls,
)
from .chat_completion_named_tool_choice import (
    ChatCompletionNamedToolChoice,
    Function,
)
from .chat_completion_named_tool_choice_custom import (
    ChatCompletionNamedToolChoiceCustom,
    Custom,
)
from .chat_completion_request_assistant_message import (
    Audio,
    ChatCompletionRequestAssistantMessage,
    FunctionCall,
)
from .chat_completion_request_developer_message import (
    ChatCompletionRequestDeveloperMessage,
)
from .chat_completion_request_function_message import (
    ChatCompletionRequestFunctionMessage,
)
from .chat_completion_request_system_message import (
    ChatCompletionRequestSystemMessage,
)
from .chat_completion_request_tool_message import (
    ChatCompletionRequestToolMessage,
)
from .chat_completion_request_user_message import (
    ChatCompletionRequestUserMessage,
)
from .chat_completion_stream_options import (
    ChatCompletionStreamOptions,
)
from .chat_completion_tool import (
    ChatCompletionTool,
)
from .chat_completion_tool_choice_option import (
    ChatCompletionToolChoiceOption,
    Custom,
    Function,
)
from .chat_model import (
    ChatModel,
)
from .create_model_response_properties import (
    CreateModelResponseProperties,
)
from .custom_tool_chat_completions import (
    Custom,
    CustomToolChatCompletions,
)
from .function_object import (
    FunctionObject,
)
from .function_parameters import (
    FunctionParameters,
)
from .metadata import (
    Metadata,
)
from .model_ids_shared import (
    ModelIdsShared,
)
from .model_response_properties import (
    ModelResponseProperties,
)
from .parallel_tool_calls import (
    ParallelToolCalls,
)
from .prediction_content import (
    PredictionContent,
)
from .reasoning_effort import (
    ReasoningEffort,
)
from .response_format_json_object import (
    ResponseFormatJsonObject,
)
from .response_format_json_schema import (
    JsonSchema,
    ResponseFormatJsonSchema,
)
from .response_format_json_schema_schema import (
    ResponseFormatJsonSchemaSchema,
)
from .response_format_text import (
    ResponseFormatText,
)
from .response_modalities import (
    ResponseModalities,
)
from .service_tier import (
    ServiceTier,
)
from .stop_configuration import (
    StopConfiguration,
)
from .test_rebuild import (
    Audio,
    CreateChatCompletionRequest,
    UserLocation,
    WebSearchOptions,
)
from .verbosity import (
    Verbosity,
)
from .voice_ids_shared import (
    VoiceIdsShared,
)
from .web_search_context_size import (
    WebSearchContextSize,
)
from .web_search_location import (
    WebSearchLocation,
)