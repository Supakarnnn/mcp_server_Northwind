from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from typing import TypedDict, Annotated, Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.messages import ToolMessage
from dotenv import load_dotenv
import os
from tavily import TavilyClient
from langchain_openai import ChatOpenAI
from prompt.ppp import one_PLAN_PROMPT
from .state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
import json

# Load environment variablesc
load_dotenv()

# Setup clients
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

PLAN_REPORT = """You are an ultimate data analyst. Your task is to analyze the following query and summarize the results in the specified report format.

Query:
{query}


Report Format:

Highest Price
Highest Price per unit
Finally, provide a summary of other relevant observations or insights based on the analysis.

Please proceed with the analysis and generate the report accordingly.

"""

@tool
def tavily_search(query: str) -> str:
    """Search the web using Tavily and return a short summary."""
    response = tavily_client.search(query=query, search_depth="advanced", include_answer=True)
    return response.get("answer", "No answer found.")

tools = [tavily_search]

def create_graph():

    llm = ChatOpenAI(
        base_url=os.environ["BASE_URL"],
        model='gpt-4o-mini',
        api_key=os.environ["OPENAI_API_KEY"]
    )
    llm_gem = ChatGoogleGenerativeAI(
        api_key=os.environ["GOOGLE_API_KEY"],
        model="gemini-2.0-flash-exp-image-generation"
    )
    llm_openai = llm.bind_tools(tools)
    
    return plan_agent(llm, llm_openai, llm_gem, tools)

def plan_agent(llm: ChatOpenAI, llm_openai: ChatOpenAI, llm_gem: ChatGoogleGenerativeAI, tools: list):
    
    def extract_research_from_message(message):
        return message.content

    
    def call_plan(state: AgentState):
        messages = state["messages"]
        film_plan_message = [SystemMessage(content=one_PLAN_PROMPT),*messages]
        film_plan = llm.invoke(film_plan_message)
        format_content = film_plan.content.replace("\\n", "\n")        
        return {
            "messages": messages + [film_plan], 
            "plan": format_content, 
        }
    
  
    builder = StateGraph(AgentState)
    builder.add_node("planner", call_plan)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", END)
     
    return builder.compile()


###################################################################################################

def react_agent(llm: ChatOpenAI, tools: list, event: str):

    llm = ChatOpenAI(
        base_url=os.environ["BASE_URL"],
        model='gpt-4o-mini',
        api_key=os.environ["OPENAI_API_KEY"]
    )

    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]
        temp: str
        f_report :str

    model_with_tool = llm.bind_tools(tools)

    def call_model(state: AgentState):
        messages = state["messages"]
        p = """you are a powerful assistance that have access to database you have tool that you can use to get access database""" 
        new_query = [SystemMessage(content=p), *messages]
        for_temp = model_with_tool.invoke(new_query)        
        return {
            "messages": messages + [for_temp], 
            "temp": for_temp.content
        }
    
    def call_report(state: AgentState):
        messages = state["messages"]
        query = state["temp"]
        new_report = [SystemMessage(content=PLAN_REPORT),HumanMessage(content=query)]
        final_report = llm.invoke(new_report)

        return {
            "messages": messages + [final_report],
            "f_report": final_report.content
        }
    
    def should_continue(state: AgentState) -> Literal["tool", "report"]:
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tool"
        return "report"


    async def call_tool(state: AgentState):
        print("Tool is calling!!")
        tools_by_name = {tool.name: tool for tool in tools}
        messages = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            result = await tool.ainvoke(tool_call["args"])
            # print(result)
            messages.append(ToolMessage(
                content=json.dumps(result),
                tool_call_id=tool_call["id"],
                tools_by_name=tool_call["name"]
            ))
        return {
            "messages": state["messages"] + messages,
            "temp": messages
        }
        
    builder = StateGraph(AgentState)
    builder.add_node("query", call_model)
    builder.add_node("report", call_report)
    builder.add_node("tool", call_tool)

    builder.add_edge(START, "query")

    builder.add_conditional_edges("query", should_continue, {
        "tool": "tool",
        "report": "report"
    })
    
    builder.add_edge("tool","query")
    builder.add_edge("report", END)

    return builder.compile()