const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

let todos = [
  { id: '1', title: 'Complete CRISP-DM Business Understanding', priority: 'Urgent & Important', category: 'Data Science', completed: true, dueDate: '2026-09-06', tags: ['audit', 'crisp-dm'] },
  { id: '2', title: 'Train PyTorch Autoregressive Transformer', priority: 'Urgent & Important', category: 'Deep Learning', completed: false, dueDate: '2026-09-07', tags: ['llm', 'pytorch'] },
  { id: '3', title: 'Evaluate Isolation Forest PR-AUC Scores', priority: 'Not Urgent & Important', category: 'ML Security', completed: false, dueDate: '2026-09-08', tags: ['anomaly', 'security'] },
  { id: '4', title: 'Refactor Kahn\'s DAG Topological Sort Visualizer', priority: 'Not Urgent & Not Important', category: 'Frontend UX', completed: false, dueDate: '2026-09-10', tags: ['dag', 'typescript'] }
];

app.get('/api/todos', (req, res) => {
  res.json(todos);
});

app.post('/api/todos', (req, res) => {
  const newTodo = { id: Date.now().toString(), completed: false, tags: [], ...req.body };
  todos.push(newTodo);
  res.status(201).json(newTodo);
});

app.patch('/api/todos/:id', (req, res) => {
  const { id } = req.params;
  todos = todos.map(t => t.id === id ? { ...t, ...req.body } : t);
  const updated = todos.find(t => t.id === id);
  res.json(updated);
});

app.delete('/api/todos/:id', (req, res) => {
  const { id } = req.params;
  todos = todos.filter(t => t.id !== id);
  res.json({ success: true, id });
});

app.get('/api/analytics', (req, res) => {
  const total = todos.length;
  const completed = todos.filter(t => t.completed).length;
  const urgent = todos.filter(t => t.priority.includes('Urgent')).length;
  const rate = total > 0 ? ((completed / total) * 100).toFixed(1) : 0;
  
  res.json({
    total,
    completed,
    pending: total - completed,
    completionRate: `${rate}%`,
    urgentCount: urgent,
    aiSummary: `Productivity velocity is strong with ${completed} completed tasks out of ${total}. Focusing on ${urgent} urgent items will maximize milestone progress.`
  });
});

const PORT = process.env.PORT || 5001;
app.listen(PORT, () => {
  console.log(`Zenith Task Workspace Server running on http://localhost:${PORT}`);
});
