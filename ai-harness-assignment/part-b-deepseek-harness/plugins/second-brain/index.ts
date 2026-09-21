
import { Context, Service } from 'cordis'
import * as sqlite3 from 'sqlite3'

export class SecondBrain extends Service {
  db: sqlite3.Database;

  constructor(ctx: Context) {
    super(ctx, 'second_brain')
    this.db = new sqlite3.Database('notes.db');
    this.db.run(`CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, content TEXT)`);
  }

  save_note(title: string, content: string) {
    this.db.run(`INSERT INTO notes (title, content) VALUES (?, ?)`, [title, content]);
    return `Note '${title}' saved.`;
  }
  
  search_notes(query: string) {
    // In a real plugin, use async/await db logic
    return `Searching for ${query}... (Mocked for async execution)`;
  }
}

export default SecondBrain
