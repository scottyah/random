import { getDatabase } from './index'
import bcrypt from 'bcryptjs'
import { v4 as uuidv4 } from 'uuid'
import { Profile, WishlistItem, Assignment } from '../types'

// User queries
export function getUserById(id: string): Profile | null {
  const db = getDatabase()
  const stmt = db.prepare('SELECT id, email, full_name, created_at, updated_at FROM users WHERE id = ?')
  return stmt.get(id) as Profile | null
}

export function getUserByEmail(email: string) {
  const db = getDatabase()
  const stmt = db.prepare('SELECT * FROM users WHERE email = ?')
  return stmt.get(email) as (Profile & { password_hash: string }) | null
}

export function createUser(email: string, fullName: string, password: string): Profile {
  const db = getDatabase()
  const id = uuidv4()
  const passwordHash = bcrypt.hashSync(password, 10)
  const stmt = db.prepare(`
    INSERT INTO users (id, email, full_name, password_hash)
    VALUES (?, ?, ?, ?)
  `)
  stmt.run(id, email, fullName, passwordHash)
  return getUserById(id)!
}

export function verifyPassword(plainPassword: string, hashedPassword: string): boolean {
  return bcrypt.compareSync(plainPassword, hashedPassword)
}

export function getAllUsers(): Profile[] {
  const db = getDatabase()
  const stmt = db.prepare('SELECT id, email, full_name, created_at, updated_at FROM users')
  return stmt.all() as Profile[]
}

// Assignment queries
export function getAssignmentForUser(userId: string, year: number) {
  const db = getDatabase()
  const stmt = db.prepare(`
    SELECT
      a.*,
      u.id as receiver_id,
      u.email as receiver_email,
      u.full_name as receiver_full_name,
      u.created_at as receiver_created_at,
      u.updated_at as receiver_updated_at
    FROM assignments a
    JOIN users u ON a.receiver_id = u.id
    WHERE a.giver_id = ? AND a.year = ?
  `)
  const result = stmt.get(userId, year) as any

  if (!result) return null

  return {
    id: result.id,
    giver_id: result.giver_id,
    receiver_id: result.receiver_id,
    year: result.year,
    created_at: result.created_at,
    receiver: {
      id: result.receiver_id,
      email: result.receiver_email,
      full_name: result.receiver_full_name,
      created_at: result.receiver_created_at,
      updated_at: result.receiver_updated_at,
    },
  }
}

export function createAssignment(giverId: string, receiverId: string, year: number) {
  const db = getDatabase()
  const id = uuidv4()
  const stmt = db.prepare(`
    INSERT INTO assignments (id, giver_id, receiver_id, year)
    VALUES (?, ?, ?, ?)
  `)
  stmt.run(id, giverId, receiverId, year)
  return { id, giver_id: giverId, receiver_id: receiverId, year }
}

export function deleteAssignmentsForYear(year: number) {
  const db = getDatabase()
  const stmt = db.prepare('DELETE FROM assignments WHERE year = ?')
  stmt.run(year)
}

export function getAllAssignmentsForYear(year: number) {
  const db = getDatabase()
  const stmt = db.prepare(`
    SELECT
      a.*,
      g.email as giver_email,
      g.full_name as giver_full_name,
      r.email as receiver_email,
      r.full_name as receiver_full_name
    FROM assignments a
    JOIN users g ON a.giver_id = g.id
    JOIN users r ON a.receiver_id = r.id
    WHERE a.year = ?
  `)
  return stmt.all(year)
}

// Wishlist queries
export function getWishlistForUser(userId: string): WishlistItem[] {
  const db = getDatabase()
  const stmt = db.prepare(`
    SELECT * FROM wishlist_items
    WHERE user_id = ?
    ORDER BY created_at DESC
  `)
  const items = stmt.all(userId) as any[]
  return items.map((item) => ({
    ...item,
    is_purchased: Boolean(item.is_purchased),
  }))
}

export function createWishlistItem(
  userId: string,
  title: string,
  description: string | null,
  price: number | null,
  url: string | null
): WishlistItem {
  const db = getDatabase()
  const id = uuidv4()
  const stmt = db.prepare(`
    INSERT INTO wishlist_items (id, user_id, title, description, price, url)
    VALUES (?, ?, ?, ?, ?, ?)
  `)
  stmt.run(id, userId, title, description, price, url)

  const getStmt = db.prepare('SELECT * FROM wishlist_items WHERE id = ?')
  const item = getStmt.get(id) as any
  return {
    ...item,
    is_purchased: Boolean(item.is_purchased),
  }
}

export function updateWishlistItem(
  id: string,
  userId: string,
  title: string,
  description: string | null,
  price: number | null,
  url: string | null
) {
  const db = getDatabase()
  const stmt = db.prepare(`
    UPDATE wishlist_items
    SET title = ?, description = ?, price = ?, url = ?, updated_at = datetime('now')
    WHERE id = ? AND user_id = ?
  `)
  stmt.run(title, description, price, url, id, userId)
}

export function deleteWishlistItem(id: string, userId: string) {
  const db = getDatabase()
  const stmt = db.prepare('DELETE FROM wishlist_items WHERE id = ? AND user_id = ?')
  stmt.run(id, userId)
}

export function markItemAsPurchased(id: string, purchasedBy: string, isPurchased: boolean) {
  const db = getDatabase()
  const stmt = db.prepare(`
    UPDATE wishlist_items
    SET is_purchased = ?, purchased_by = ?, updated_at = datetime('now')
    WHERE id = ?
  `)
  stmt.run(isPurchased ? 1 : 0, isPurchased ? purchasedBy : null, id)
}

export function canUserAccessWishlist(userId: string, targetUserId: string, year: number): boolean {
  const db = getDatabase()
  // User can always access their own wishlist
  if (userId === targetUserId) return true

  // Check if user is assigned to give to this person
  const stmt = db.prepare(`
    SELECT 1 FROM assignments
    WHERE giver_id = ? AND receiver_id = ? AND year = ?
  `)
  return !!stmt.get(userId, targetUserId, year)
}
