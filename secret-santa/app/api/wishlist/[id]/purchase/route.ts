import { NextResponse } from 'next/server'
import { getCurrentUser } from '@/lib/session'
import { markItemAsPurchased, canUserAccessWishlist } from '@/lib/db/queries'
import { getDatabase } from '@/lib/db'

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const userId = await getCurrentUser()
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { id } = await params
    const { is_purchased } = await request.json()

    // Get the item to check ownership/access
    const db = getDatabase()
    const stmt = db.prepare('SELECT * FROM wishlist_items WHERE id = ?')
    const item = stmt.get(id) as { user_id: string } | null

    if (!item) {
      return NextResponse.json({ error: 'Item not found' }, { status: 404 })
    }

    // Check if user has permission to mark this item as purchased
    const year = new Date().getFullYear()
    const canAccess = canUserAccessWishlist(userId, item.user_id, year)

    if (!canAccess) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }

    markItemAsPurchased(id, userId, is_purchased)
    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error marking item as purchased:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
