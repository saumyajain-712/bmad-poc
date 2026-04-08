from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .sql_app import models
from .sql_app.database import engine
from .api.v1.endpoints import runs

# Create database tables
models.Base.metadata.create_all(bind=engine)




@asynccontextmanager
async def lifespan(app: FastAPI):  # pylint: disable=unused-argument
    # Application startup
    print("BMAD Backend starting up...")
    yield
    # Application shutdown
    print("BMAD Backend shutting down.")


app = FastAPI(lifespan=lifespan)

app.include_router(runs.router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"message": "BMAD Backend is running!"}


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Eco back received messages for now
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #disconnected")


