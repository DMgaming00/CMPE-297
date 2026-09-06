# 🏗️ FlowForge DAG Engine — Matt Pocock TypeScript Architecture

An enterprise-grade, type-safe autonomous workflow DAG (Directed Acyclic Graph) orchestration engine built strictly adhering to **Matt Pocock's Total TypeScript architectural patterns** and **Kahn's topological sort algorithm**.

---

## 📸 Comprehensive Visual Tour

### 1. Kahn's Topological DAG Canvas
*Interactive directed acyclic graph editor visualizing topological execution levels, parallel concurrency slots, and state machine transitions.*
![FlowForge DAG Canvas](./screenshots/flowforge_dag_canvas.png)

### 2. Matt Pocock TypeScript Architecture Lab
*Interactive code playground demonstrating Nominal Branded Types, Discriminated Unions, `assertNever()` Exhaustiveness Narrowing, and Result types.*
![FlowForge TypeScript Lab](./screenshots/flowforge_typescript_lab.png)

### 3. Real-Time Server-Sent Events (SSE) Live Telemetry Stream
*Sub-second event bus streaming node executions, latency tracking, and topological progress.*
![FlowForge Architecture](./screenshots/flowforge_architecture_doc.png)

---

## 🏛️ Type-Safe Architectural Patterns Implemented

1. **Nominal Branded Types**:
   - `type WorkflowId = string & { readonly __brand: unique symbol }`
   - `type NodeId = string & { readonly __brand: unique symbol }`
   - Prevents accidental string ID mixups at compile time.
2. **Discriminated Unions**:
   - 6 strongly typed node schemas (`trigger`, `transform`, `inference`, `condition`, `action`, `join`).
3. **Compile-Time Exhaustiveness Guarantees**:
   - `assertNever(x: never): never` enforces unhandled case compiler errors.
4. **Kahn's Topological Sort**:
   - Linear time $O(V + E)$ in-degree dependency resolution and cycle detection.

---

## 🧠 Autonomous Skills Included

Pre-packaged in `skills/` and `.agents/skills/`:
* `matt-pocock-typescript-patterns`: Type narrowing, branded types, and discriminated unions.
* `matt-pocock-to-spec`: Formal type-driven technical specifications.
* `matt-pocock-to-tickets`: Tracer-bullet independently verifiable engineering tickets.
* `matt-pocock-grill-me`: Rigorous requirements and edge case interrogation.

---

## 🚀 Quick Start

```bash
# Backend (FastAPI on Port 8009)
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8009

# Frontend (Vite React on Port 5182)
cd frontend
npm install
npm run dev # Open http://localhost:5182/
```
