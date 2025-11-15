import Database from 'better-sqlite3'
import path from 'path'

let db: Database.Database | null = null

function getDatabase(): Database.Database {
  if (!db) {
    // Create database file in the project root
    const dbPath = path.join(process.cwd(), 'secret-santa.db')
    db = new Database(dbPath)

    // Enable WAL mode for better concurrent access
    db.pragma('journal_mode = WAL')
    db.pragma('foreign_keys = ON')
    db.pragma('busy_timeout = 5000') // Wait up to 5 seconds if database is locked

    // Initialize database schema
    db.exec(`
      -- Users table
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      );

      -- Assignments table
      CREATE TABLE IF NOT EXISTS assignments (
        id TEXT PRIMARY KEY,
        giver_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        receiver_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        year INTEGER NOT NULL DEFAULT (strftime('%Y', 'now')),
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(giver_id, year),
        CHECK (giver_id != receiver_id)
      );

      -- Wishlist items table
      CREATE TABLE IF NOT EXISTS wishlist_items (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        description TEXT,
        price REAL,
        url TEXT,
        is_purchased INTEGER DEFAULT 0,
        purchased_by TEXT REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      );

      -- Sessions table for authentication
      CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
      );

      -- Create indexes for better performance
      CREATE INDEX IF NOT EXISTS idx_assignments_giver ON assignments(giver_id);
      CREATE INDEX IF NOT EXISTS idx_assignments_receiver ON assignments(receiver_id);
      CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist_items(user_id);
      CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    `)
  }

  return db
}

// Export the getter function so database is initialized lazily
export default { get: getDatabase }
export { getDatabase }
