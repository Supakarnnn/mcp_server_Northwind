import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from model.module import RequestMessage, AgentResponse
from agent.graph import create_graph,react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Assistant")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatOpenAI(
    base_url=os.environ.get("BASE_URL"),
    model='gpt-4o-mini',
    api_key=os.environ["OPENAI_API_KEY"],
    temperature=0
)

film_planning_agent = create_graph()

@app.post("/chat")
async def chat(chatmessage: RequestMessage):
    try:
        messages = []
        
        for chat in chatmessage.messages:
            if chat.role == 'ai':
                messages.append({"role": "assistant", "content": chat.content})
            elif chat.role == 'human':
                messages.append({"role": "user", "content": chat.content})
            elif chat.role == 'system':
                messages.append({"role": "system", "content": chat.content})
        
        try:
            async with MultiServerMCPClient(
                {
                    "db": {
                        "url": "http://localhost:8000/sse",
                        "transport": "sse",
                    }
                }
            ) as client:
                agent = create_react_agent(llm, client.get_tools())
                result = await agent.ainvoke({"messages": messages})        
                final_result = result["messages"][-1].content
                
                return{
                    "response": final_result
                }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to MCP server: {str(e)}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@app.post("/create-film-plan", response_model=AgentResponse)
async def create_film_plan(request: RequestMessage):
    try:

        messages = []
        for msg in request.messages:
            if msg.role == 'human':
                messages.append(HumanMessage(content=msg.content))
        
        result = film_planning_agent.invoke({"messages": messages})
        
        response = "Your film plan is ready!"
        plan = result.get("plan", "No plan was generated.")
        
        return AgentResponse(
            response=response,
            plan=plan,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating film plan: {str(e)}")
    

@app.post("/create-report", response_model=AgentResponse)
async def create_report(request: RequestMessage):
    try:
        query = None
        for msg in request.messages:
            if msg.role == 'human':
                query = msg.content
                break
        
        if not query:
            raise HTTPException(status_code=400, detail="No query provided in messages")
        
        try:
            async with MultiServerMCPClient(
                {
                    "db": {
                        "url": "http://localhost:8000/sse",
                        "transport": "sse",
                    }
                }
            ) as client:
                agent = react_agent(llm, client.get_tools(), "async")
                result = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
                
                report = result.get("f_report","No report was generated.")
                
                return AgentResponse(
                    response="Your report is ready!",
                    report=report
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to MCP server: {str(e)}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating report: {str(e)}")
    

@app.get("/")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8001)