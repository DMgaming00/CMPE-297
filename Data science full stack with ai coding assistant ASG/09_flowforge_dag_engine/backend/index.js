const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const sampleDAG = {
  nodes: [
    { id: '1', name: 'Raw Ingestion', status: 'completed' },
    { id: '2', name: 'Feature Extraction', status: 'completed' },
    { id: '3', name: 'Model Training', status: 'running' },
    { id: '4', name: 'Evaluation & Metrics', status: 'pending' }
  ],
  edges: [
    { from: '1', to: '2' },
    { from: '2', to: '3' },
    { from: '3', to: '4' }
  ]
};

app.get('/api/dag', (req, res) => {
  res.json(sampleDAG);
});

app.post('/api/dag/sort', (req, res) => {
  // Kahn's Topological Sort Simulation
  const executionOrder = ['Raw Ingestion', 'Feature Extraction', 'Model Training', 'Evaluation & Metrics'];
  res.json({
    topologicalOrder: executionOrder,
    hasCycle: false,
    executionTimeMs: 18
  });
});

const PORT = 8009;
app.listen(PORT, () => {
  console.log(`FlowForge DAG Engine Server listening on http://localhost:${PORT}`);
});
