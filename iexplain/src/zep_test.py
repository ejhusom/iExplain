import asyncio
import uuid
from zep_python.client import AsyncZep
from zep_python.types import Message
from zep_python.client import Zep

BASE_URL = "http://localhost:8000"
API_KEY = "password"


# Replace with Zep API URL and (optionally) API key
client = Zep(api_key="password", base_url="http://localhost:8000")

user_id = uuid.uuid4().hex # A new user identifier
new_user = client.user.add(
    user_id=user_id,
    email="user@example.com",
    first_name="Jane",
    last_name="Smith",
    metadata={"foo": "bar"},
)

# create a chat session
session_id = uuid.uuid4().hex # A new session identifier
session = client.memory.add_session(
    session_id=session_id,
    user_id=user_id,
    metadata={"foo" : "bar"}
)

# Add a memory to the session
client.memory.add_memory(
    session_id=session_id,
    messages=[
        Message(
            role_type = "user", # One of ("system", "assistant", "user", "function", "tool")
            role = "Researcher", # Optional, a use case specific string representing the role of the user
            content = "Who was Octavia Butler?", # The message content
        )
    ],
)

# Get session memory
memory = client.memory.get(session_id=session_id)
messages = memory.messages # List of messages in the session (quantity determined by optional lastn parameter in memory.get)
relevant_facts = memory.relevant_facts # List of facts relevant to the recent messages in the session

# Search user facts across all sessions
search_response = client.memory.search_sessions(
    user_id=user_id,
    search_scope="facts",
    text="What science fiction books did I recently read?",
)
facts = [r.fact for r in search_response.results]

# async def main():

#     client = AsyncZep(
#         api_key=API_KEY,
#         base_url=BASE_URL,
#     )

#     user_id = uuid.uuid4().hex # A new user identifier
#     new_user = await client.user.add(
#         user_id=user_id,
#         email="user@example.com",
#         first_name="Jane",
#         last_name="Smith",
#         metadata={"foo": "bar"},
#     )

#     # create a chat session
#     session_id = uuid.uuid4().hex # A new session identifier
#     session = await client.memory.add_session(
#         session_id=session_id,
#         user_id=user_id,
#         metadata={"foo" : "bar"}
#     )

#     # Add a memory to the session
#     await client.memory.add_memory(
#         session_id=session_id,
#         messages=[
#             Message(
#                 role_type = "user", # One of ("system", "assistant", "user", "function", "tool")
#                 role = "Researcher", # Optional, a use case specific string representing the role of the user
#                 content = "Who was Octavia Butler?", # The message content
#             )
#         ],
#     )

#     # Get session memory
#     memory = await client.memory.get(session_id=session_id)
#     messages = memory.messages # List of messages in the session (quantity determined by optional lastn parameter in memory.get)
#     relevant_facts = memory.relevant_facts # List of facts relevant to the recent messages in the session

#     # Search user facts across all sessions
#     search_response = await client.memory.search_sessions(
#         user_id=user_id,
#         search_scope="facts",
#         text="What science fiction books did I recently read?",
#     )
#     facts = [r.fact for r in search_response.results]

# if __name__ == "__main__":
#     asyncio.run(main())